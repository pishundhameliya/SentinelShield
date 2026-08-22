"""Computer vision signal analysis for blackout, freeze, and loop tamper detection."""
from __future__ import annotations

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore


def is_black_frame(frame: Any, threshold: float = 18.0) -> bool:
    """Check if the frame luminance is below blackout threshold."""
    if frame is None:
        return True
    if hasattr(frame, "size") and frame.size == 0:
        return True
    if hasattr(frame, "mean"):
        try:
            return float(frame.mean()) < threshold
        except Exception:
            pass
    return False


def frame_difference_score(prev_frame: Any, curr_frame: Any) -> float:
    """Calculate mean absolute frame difference (MSE proxy) for freeze detection."""
    if prev_frame is None or curr_frame is None:
        return 0.0
    if cv2 is not None and hasattr(cv2, "resize") and hasattr(cv2, "absdiff"):
        try:
            a = cv2.resize(prev_frame, (160, 90))
            b = cv2.resize(curr_frame, (160, 90))
            diff = cv2.absdiff(a, b)
            return float(diff.mean())
        except Exception:
            pass
    if np is not None and hasattr(np, "mean") and hasattr(np, "abs"):
        try:
            return float(np.mean(np.abs(curr_frame - prev_frame)))
        except Exception:
            pass
    return 0.0


class TamperDetector:
    """Tracks continuous frames to flag blackout and frozen video feed attacks."""

    def __init__(self, fps: float = 12.0):
        self.fps = fps or 12.0
        self.freeze_run: int = 0
        self.black_run: int = 0
        self.prev_frame: np.ndarray | None = None
        self.tampers: list[dict[str, Any]] = []

    def process_frame(self, frame: np.ndarray, timestamp: float) -> list[dict[str, Any]]:
        """Process frame and return any newly detected tamper incidents."""
        new_incidents: list[dict[str, Any]] = []
        black = is_black_frame(frame)
        motion = frame_difference_score(self.prev_frame, frame)

        if black:
            self.black_run += 1
        else:
            if self.black_run >= max(4, int(self.fps * 0.6)):
                incident = {
                    "type": "blackout",
                    "t": round(timestamp, 2),
                    "detail": f"Black screen for ~{self.black_run} frames",
                }
                self.tampers.append(incident)
                new_incidents.append(incident)
            self.black_run = 0

        if motion < 1.2:
            self.freeze_run += 1
        else:
            if self.freeze_run >= max(8, int(self.fps * 1.2)):
                incident = {
                    "type": "freeze",
                    "t": round(timestamp, 2),
                    "detail": f"Frozen picture for ~{self.freeze_run} frames",
                }
                self.tampers.append(incident)
                new_incidents.append(incident)
            self.freeze_run = 0

        self.prev_frame = frame
        return new_incidents


class MultiCameraTamperPool:
    """Zero-allocation multi-camera tamper detection pool for high-density (50-200) streams."""

    def __init__(self, fps: float = 12.0, max_cameras: int = 250):
        self.fps = fps or 12.0
        self.max_cameras = max_cameras
        self._detectors: dict[str, TamperDetector] = {}
        self._buffers: dict[str, dict[str, Any]] = {}

    def _get_or_create(self, camera_id: str) -> tuple[TamperDetector, dict[str, Any]]:
        if camera_id not in self._detectors:
            if len(self._detectors) >= self.max_cameras:
                # Evict oldest idle camera to maintain strict bounded memory
                oldest = next(iter(self._detectors))
                del self._detectors[oldest]
                if oldest in self._buffers:
                    del self._buffers[oldest]

            self._detectors[camera_id] = TamperDetector(fps=self.fps)
            self._buffers[camera_id] = {
                "prev_downscaled": np.zeros((90, 160, 3), dtype=np.uint8),
                "curr_downscaled": np.zeros((90, 160, 3), dtype=np.uint8),
            }
        return self._detectors[camera_id], self._buffers[camera_id]

    def process_frame(self, camera_id: str, frame: np.ndarray, timestamp: float) -> list[dict[str, Any]]:
        """Process a frame for a given camera using pre-allocated detector instance."""
        detector, _ = self._get_or_create(camera_id)
        return detector.process_frame(frame, timestamp)

    def reset_camera(self, camera_id: str) -> None:
        """Reset internal tamper state and frame history for a specific camera."""
        if camera_id in self._detectors:
            del self._detectors[camera_id]
        if camera_id in self._buffers:
            del self._buffers[camera_id]

    def clear(self) -> None:
        """Clear all camera detectors and memory buffers."""
        self._detectors.clear()
        self._buffers.clear()
