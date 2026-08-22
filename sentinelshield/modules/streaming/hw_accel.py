"""Hardware-assisted VideoCapture probing and backend acceleration engine for SentinelShield."""
from __future__ import annotations

import os
import sys
from typing import Any, List, Optional, Tuple, Union

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore


def get_available_hw_accelerations() -> List[str]:
    """Auto-probe host and OpenCV build capabilities to discover available hardware acceleration backends."""
    if cv2 is None:
        return ["software"]

    accelerations: List[str] = []

    # 1. Probe NVIDIA CUDA / NVDEC
    cuda_detected = False
    if hasattr(cv2, "cuda") and hasattr(cv2.cuda, "getCudaEnabledDeviceCount"):
        try:
            cuda_detected = cv2.cuda.getCudaEnabledDeviceCount() > 0
        except Exception:
            cuda_detected = False

    if not cuda_detected:
        # Check environment and build flags
        cuda_env = os.environ.get("CUDA_VISIBLE_DEVICES", "")
        if cuda_env and cuda_env != "-1":
            cuda_detected = True

    if cuda_detected:
        accelerations.append("cuda")

    # 2. Probe MSMF (Microsoft Media Foundation with Direct3D11) on Windows
    if sys.platform == "win32" or os.name == "nt":
        if hasattr(cv2, "CAP_MSMF"):
            accelerations.append("msmf")
        if hasattr(cv2, "VIDEO_ACCELERATION_D3D11") or hasattr(cv2, "CAP_PROP_HW_ACCELERATION"):
            accelerations.append("d3d11")
        if hasattr(cv2, "CAP_DSHOW"):
            accelerations.append("dshow")

    # 3. Probe FFmpeg backend
    if hasattr(cv2, "CAP_FFMPEG"):
        accelerations.append("ffmpeg")

    # 4. Universal software fallback always available
    accelerations.append("software")

    # Return deduplicated preservation of priority order
    seen = set()
    result = []
    for acc in accelerations:
        if acc not in seen:
            seen.add(acc)
            result.append(acc)
    return result


def create_hw_videocapture(
    source_path: Union[str, int],
    preferred_accel: str = "auto",
) -> Tuple[Optional[Any], str]:
    """Create a hardware-accelerated cv2.VideoCapture with automatic probing and graceful CPU fallback.

    Args:
        source_path: Video file path, RTSP/HTTP URL, or camera device index (int or str).
        preferred_accel: Preferred acceleration backend ("auto", "cuda", "msmf", "d3d11", "dshow", "ffmpeg", "software").

    Returns:
        Tuple of (cv2.VideoCapture instance, backend_name string).
    """
    if cv2 is None:
        return None, "software"

    # Normalize integer camera index string if applicable
    source = source_path
    if isinstance(source, str) and source.isdigit():
        source = int(source)

    preferred = preferred_accel.lower().strip() if isinstance(preferred_accel, str) else "auto"

    # Build prioritized candidate list: list of (backend_name, api_preference, hw_accel_prop)
    candidates: List[Tuple[str, int, Optional[int]]] = []

    cuda_prop = getattr(cv2, "VIDEO_ACCELERATION_CUDA", 3)
    d3d11_prop = getattr(cv2, "VIDEO_ACCELERATION_D3D11", 2)
    cap_ffmpeg = getattr(cv2, "CAP_FFMPEG", getattr(cv2, "CAP_ANY", 0))
    cap_msmf = getattr(cv2, "CAP_MSMF", getattr(cv2, "CAP_ANY", 0))
    cap_dshow = getattr(cv2, "CAP_DSHOW", getattr(cv2, "CAP_ANY", 0))
    cap_any = getattr(cv2, "CAP_ANY", 0)

    if preferred in ("software", "cpu"):
        candidates.append(("software", cap_any, None))
    elif preferred == "cuda":
        candidates.append(("cuda", cap_ffmpeg, cuda_prop))
        candidates.append(("software", cap_any, None))
    elif preferred in ("msmf", "d3d11"):
        candidates.append(("msmf", cap_msmf, d3d11_prop))
        candidates.append(("software", cap_any, None))
    elif preferred == "dshow":
        candidates.append(("dshow", cap_dshow, None))
        candidates.append(("software", cap_any, None))
    elif preferred == "ffmpeg":
        candidates.append(("ffmpeg", cap_ffmpeg, None))
        candidates.append(("software", cap_any, None))
    else:
        # "auto" mode: probe host platform and try backends in order of throughput
        available = get_available_hw_accelerations()
        if "cuda" in available:
            candidates.append(("cuda", cap_ffmpeg, cuda_prop))
        if "msmf" in available:
            candidates.append(("msmf", cap_msmf, d3d11_prop))
        if "dshow" in available and isinstance(source, int):
            candidates.append(("dshow", cap_dshow, None))
        if "ffmpeg" in available:
            candidates.append(("ffmpeg", cap_ffmpeg, None))
        candidates.append(("software", cap_any, None))

    # Probe each candidate in sequence
    for backend_name, api_pref, hw_accel in candidates:
        cap = None
        try:
            if api_pref != cap_any:
                cap = cv2.VideoCapture(source, api_pref)
            else:
                cap = cv2.VideoCapture(source)

            if cap is not None and cap.isOpened():
                if hw_accel is not None and hasattr(cv2, "CAP_PROP_HW_ACCELERATION"):
                    try:
                        cap.set(cv2.CAP_PROP_HW_ACCELERATION, hw_accel)
                    except Exception:
                        pass
                return cap, backend_name

            # If not opened, clean up and try next candidate
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
                cap = None
        except Exception:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
            cap = None
            continue

    # Final fallback: software default VideoCapture
    try:
        cap = cv2.VideoCapture(source, cap_any)
        return cap, "software"
    except Exception:
        try:
            cap = cv2.VideoCapture(source)
            return cap, "software"
        except Exception:
            return None, "software"
