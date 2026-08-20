"""Computer vision signal analysis for blackout, freeze, and loop tamper detection."""
from __future__ import annotations

import cv2
import numpy as np


def is_black_frame(frame: np.ndarray, threshold: float = 18.0) -> bool:
    """Check if the frame luminance is below blackout threshold."""
    if frame is None or frame.size == 0:
        return True
    return float(frame.mean()) < threshold


def frame_difference_score(prev_frame: np.ndarray | None, curr_frame: np.ndarray) -> float:
    """Calculate mean absolute frame difference (MSE proxy) for freeze detection."""
    if prev_frame is None or curr_frame is None:
        return 0.0
    a = cv2.resize(prev_frame, (160, 90))
    b = cv2.resize(curr_frame, (160, 90))
    diff = cv2.absdiff(a, b)
    return float(diff.mean())


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
