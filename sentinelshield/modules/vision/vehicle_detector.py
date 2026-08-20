"""Morphological and differential motion vehicle candidate detector."""
from __future__ import annotations

from typing import Any
import cv2
import numpy as np


def detect_vehicles(frame: np.ndarray, prev_gray: np.ndarray | None = None) -> list[dict[str, Any]]:
    """Vehicle Detection Engine.
    
    Detects vehicle candidates by combining Sobel edge/contour analysis
    and differential motion tracking across consecutive frames.
    """
    if frame is None or frame.size == 0:
        return []

    h, w = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # Morphological Edge Detection for Stationary/Moving Vehicles
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    sobel = cv2.Sobel(blur, cv2.CV_8U, 1, 0, ksize=3)
    _, thresh = cv2.threshold(sobel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 5))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    cnts, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    boxes = []

    for c in cnts:
        bx, by, bw, bh = cv2.boundingRect(c)
        area = bw * bh
        aspect = bw / float(bh) if bh > 0 else 0

        # Vehicle aspect ratio heuristics (improved for car, bike, bus/truck)
        if area > 1000 and 0.3 < aspect < 4.5 and bw > 30 and bh > 30:
            confidence = min(0.98, round(0.65 + (area / (w * h)) * 5.0, 2))
            if aspect > 2.6:
                cls_name = "bus/truck"
            elif aspect > 1.1:
                cls_name = "car"
            elif aspect <= 1.1:
                cls_name = "bike/activa"
            else:
                cls_name = "vehicle"

            boxes.append({
                "x": int(bx), "y": int(by), "w": int(bw), "h": int(bh),
                "cls": cls_name, "confidence": confidence
            })

    # Add motion difference boxes if prev_gray is available
    if prev_gray is not None:
        diff = cv2.absdiff(prev_gray, gray)
        _, m_th = cv2.threshold(diff, 20, 255, cv2.THRESH_BINARY)
        m_th = cv2.dilate(m_th, None, iterations=2)
        m_cnts, _ = cv2.findContours(m_th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for mc in m_cnts:
            mx, my, mw, mh = cv2.boundingRect(mc)
            if mw * mh > 1000 and mw > 30:
                overlap = False
                for b in boxes:
                    if abs(b["x"] - mx) < 40 and abs(b["y"] - my) < 40:
                        overlap = True
                        break
                if not overlap:
                    m_aspect = mw / float(mh) if mh > 0 else 0
                    if m_aspect > 2.6:
                        cls_name = "bus/truck"
                    elif m_aspect > 1.1:
                        cls_name = "car"
                    elif m_aspect <= 1.1:
                        cls_name = "bike/activa"
                    else:
                        cls_name = "vehicle"

                    boxes.append({
                        "x": int(mx), "y": int(my), "w": int(mw), "h": int(mh),
                        "cls": cls_name, "confidence": 0.85
                    })

    return boxes
