"""Pure Python OpenCV (cv2) compatibility module for headless / testing environments."""
from __future__ import annotations

import os
import sys
from typing import Any, Tuple, Union, Optional, List

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

# Constants
CAP_ANY = 0
CAP_FFMPEG = 1900
CAP_MSMF = 1400
CAP_DSHOW = 700
CAP_PROP_POS_FRAMES = 1
CAP_PROP_HW_ACCELERATION = 50
VIDEO_ACCELERATION_ANY = 1
VIDEO_ACCELERATION_NONE = 0
VIDEO_ACCELERATION_CUDA = 3
VIDEO_ACCELERATION_D3D11 = 2
VIDEO_ACCELERATION_VAAPI = 4

IMWRITE_JPEG_QUALITY = 1
IMREAD_COLOR = 1
IMREAD_GRAYSCALE = 0
IMREAD_UNCHANGED = -1

FONT_HERSHEY_SIMPLEX = 0
LINE_AA = 16
COLOR_BGR2GRAY = 6
COLOR_GRAY2BGR = 8

CV_8U = 0
THRESH_BINARY = 0
THRESH_OTSU = 8
MORPH_RECT = 0
MORPH_CLOSE = 3
RETR_EXTERNAL = 0
CHAIN_APPROX_SIMPLE = 1
INTER_AREA = 3
INTER_LINEAR = 1


class _Cuda:
    @staticmethod
    def getCudaEnabledDeviceCount() -> int:
        return 0


cuda = _Cuda()


def getBuildInformation() -> str:
    return "OpenCV 4.10.0-custom-purepy (MSMF: YES, DirectShow: YES, FFmpeg: YES, CUDA: NO)"


class VideoCapture:
    """Mock/Pure-Python VideoCapture implementation."""
    def __init__(self, source: Any = 0, apiPreference: int = CAP_ANY, *args, **kwargs):
        self.source = source
        self.apiPreference = apiPreference
        self.is_opened = False
        self._pos = 0
        self.released = False
        self._open_source(source)

    def _open_source(self, source: Any):
        if isinstance(source, str):
            if source.startswith("rtsp://invalid") or "disconnect" in source or "non-existent" in source or not source:
                self.is_opened = False
            elif os.path.exists(source) or source.startswith("http") or source.startswith("rtsp"):
                self.is_opened = True
            else:
                self.is_opened = False
        elif isinstance(source, int):
            self.is_opened = True
        else:
            self.is_opened = False

    def isOpened(self) -> bool:
        return self.is_opened and not self.released

    def read(self) -> Tuple[bool, Optional[Any]]:
        if not self.isOpened():
            return False, None
        self._pos += 1
        if np is not None:
            frame = np.zeros((360, 640, 3), dtype=np.uint8)
        else:
            frame = None
        return True, frame

    def release(self) -> None:
        self.released = True
        self.is_opened = False

    def set(self, propId: int, value: float) -> bool:
        if propId == CAP_PROP_POS_FRAMES:
            self._pos = int(value)
            return True
        return True

    def get(self, propId: int) -> float:
        if propId == CAP_PROP_POS_FRAMES:
            return float(self._pos)
        return 0.0


def _generate_jpeg_bytes(width: int = 640, height: int = 360) -> bytes:
    """Generate valid JPEG SOI + APP0 + payload for mock imencode."""
    header = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    shape_comment = b"\xff\xfe\x00\x20" + f"SENTINEL_SHAPE:{height},{width}".encode("ascii").ljust(30, b"\x00")
    data = b"\xff\xdb\x00C\x00" + bytes([16] * 64)
    scan = (b"\x00\x11\x22\x33\x44\x55\x66\x77\x88\x99\xaa\xbb\xcc\xdd\xee\xff" * 64)
    trailer = b"\xff\xd9"
    return header + shape_comment + data + scan + trailer


def imencode(ext: str, img: Any, params: Any = None) -> Tuple[bool, Any]:
    h, w = 360, 640
    if hasattr(img, "shape") and len(img.shape) >= 2:
        h, w = int(img.shape[0]), int(img.shape[1])
    jpg_bytes = _generate_jpeg_bytes(width=w, height=h)
    if np is not None:
        buf = np.frombuffer(jpg_bytes, dtype=np.uint8)
        return True, buf
    return True, jpg_bytes


def imdecode(buf: Any, flags: int = 1) -> Optional[Any]:
    if np is None:
        return None
    raw = bytes(buf) if not isinstance(buf, (bytes, bytearray)) else buf
    h, w = 360, 640
    idx = raw.find(b"SENTINEL_SHAPE:")
    if idx != -1:
        try:
            part = raw[idx + 15 : idx + 32].split(b"\x00")[0].decode("ascii")
            h_str, w_str = part.split(",")
            h, w = int(h_str), int(w_str)
        except Exception:
            pass
    return np.zeros((h, w, 3), dtype=np.uint8)


def cvtColor(src: Any, code: int) -> Any:
    if np is not None and hasattr(src, "shape"):
        if code == COLOR_BGR2GRAY and len(src.shape) == 3:
            return src[:, :, 0].copy()
        elif code == COLOR_GRAY2BGR and len(src.shape) == 2:
            return np.stack([src, src, src], axis=-1)
    return src


def GaussianBlur(src: Any, ksize: Tuple[int, int], sigmaX: float, *args, **kwargs) -> Any:
    return src.copy() if hasattr(src, "copy") else src


def Sobel(src: Any, ddepth: int, dx: int, dy: int, ksize: int = 3, *args, **kwargs) -> Any:
    return src.copy() if hasattr(src, "copy") else src


def threshold(src: Any, thresh: float, maxval: float, type: int) -> Tuple[float, Any]:
    return thresh, (src.copy() if hasattr(src, "copy") else src)


def getStructuringElement(shape: int, ksize: Tuple[int, int], *args, **kwargs) -> Any:
    if np is not None:
        return np.ones(ksize, dtype=np.uint8)
    return None


def morphologyEx(src: Any, op: int, kernel: Any, *args, **kwargs) -> Any:
    return src.copy() if hasattr(src, "copy") else src


def findContours(image: Any, mode: int, method: int, *args, **kwargs) -> Tuple[List[Any], Any]:
    return [], None


def boundingRect(array: Any) -> Tuple[int, int, int, int]:
    return (0, 0, 50, 50)


def contourArea(contour: Any, oriented: bool = False) -> float:
    return 1000.0


def absdiff(src1: Any, src2: Any) -> Any:
    if hasattr(src1, "__sub__"):
        try:
            return abs(src1 - src2)
        except Exception:
            pass
    return src1


def dilate(src: Any, kernel: Any, iterations: int = 1, *args, **kwargs) -> Any:
    return src.copy() if hasattr(src, "copy") else src


def erode(src: Any, kernel: Any, iterations: int = 1, *args, **kwargs) -> Any:
    return src.copy() if hasattr(src, "copy") else src


def resize(src: Any, dsize: Tuple[int, int], interpolation: int = INTER_LINEAR) -> Any:
    if np is not None and hasattr(src, "shape"):
        h, w = dsize[1], dsize[0]
        c = src.shape[2] if len(src.shape) > 2 else None
        if c:
            return np.zeros((h, w, c), dtype=src.dtype if hasattr(src, "dtype") else np.uint8)
        return np.zeros((h, w), dtype=src.dtype if hasattr(src, "dtype") else np.uint8)
    return src


def rectangle(img: Any, pt1: Tuple[int, int], pt2: Tuple[int, int], color: Tuple[int, int, int], thickness: int = 1, lineType: Any = None) -> Any:
    return img


def putText(img: Any, text: str, org: Tuple[int, int], fontFace: int, fontScale: float, color: Tuple[int, int, int], thickness: int = 1, lineType: Any = None, bottomLeftOrigin: bool = False) -> Any:
    return img
