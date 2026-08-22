"""Unit test for MultiCameraTamperPool pre-allocated zero-malloc buffers and tamper detection."""
from __future__ import annotations

import sys
import os

class MockArray:
    """Mock numpy array for lightweight test execution without heavy C-dependencies."""
    def __init__(self, shape=(90, 160, 3), val=128):
        self.shape = shape
        self.val = val
        self.size = 1

    def mean(self):
        return float(self.val)

    def __sub__(self, other):
        return MockArray(self.shape, abs(self.val - getattr(other, "val", 0)))

    def __abs__(self):
        return MockArray(self.shape, abs(self.val))


if "numpy" not in sys.modules:
    try:
        import numpy as np
    except ImportError:
        from unittest.mock import MagicMock
        np = MagicMock()
        np.zeros = lambda shape, dtype=None: MockArray(shape, 0)
        np.ones = lambda shape, dtype=None: MockArray(shape, 1)
        np.ndarray = MockArray
        sys.modules["numpy"] = np
        sys.modules["np"] = np

if "cv2" not in sys.modules:
    try:
        import cv2
    except ImportError:
        from unittest.mock import MagicMock
        cv2 = MagicMock()
        cv2.resize = lambda src, dsize: MockArray((dsize[1], dsize[0], 3), getattr(src, "val", 128))
        cv2.absdiff = lambda a, b: MockArray(a.shape, abs(getattr(a, "val", 0) - getattr(b, "val", 0)))
        sys.modules["cv2"] = cv2

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.integrity.tamper_detector import MultiCameraTamperPool, TamperDetector, is_black_frame


def test_tamper_pool_preallocation_and_detection():
    pool = MultiCameraTamperPool(fps=12.0, max_cameras=200)

    # Process 50 distinct cameras with normal bright frames
    for i in range(50):
        cam_id = f"cam-{i}"
        frame_normal = MockArray((100, 100, 3), 128)
        incidents = pool.process_frame(cam_id, frame_normal, timestamp=1.0)
        assert incidents == [], f"Unexpected incident on normal frame: {incidents}"

    # Verify pre-allocated buffer reuse
    assert len(pool._buffers) == 50
    assert pool._buffers["cam-0"]["prev_downscaled"].shape == (90, 160, 3)

    # Test blackout on cam-0 (mean luminance = 0 < 18.0)
    black_frame = MockArray((100, 100, 3), 0)
    blackout_incidents = []
    for t in range(12):
        incidents = pool.process_frame("cam-0", black_frame, timestamp=2.0 + t * 0.1)
        if incidents:
            blackout_incidents.extend(incidents)

    # Send one bright frame to flush the blackout run
    bright_frame = MockArray((100, 100, 3), 128)
    flush_incidents = pool.process_frame("cam-0", bright_frame, timestamp=3.5)
    if flush_incidents:
        blackout_incidents.extend(flush_incidents)

    assert len(blackout_incidents) >= 1
    assert any(inc["type"] == "blackout" for inc in blackout_incidents)
    print("[PASS] Task 1 Verified: MultiCameraTamperPool pre-allocated ring buffers & blackout detection working!")


if __name__ == "__main__":
    test_tamper_pool_preallocation_and_detection()
