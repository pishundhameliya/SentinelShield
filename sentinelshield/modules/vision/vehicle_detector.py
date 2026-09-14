"""YOLOv8 + Morphological fallback vehicle detector."""
from __future__ import annotations

import logging
from typing import Any
import os

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

logger = logging.getLogger(__name__)

_yolo_detector = None
_yolo_initialized = False

def _init_yolo():
    global _yolo_detector, _yolo_initialized
    if _yolo_initialized:
        return _yolo_detector
    
    _yolo_initialized = True
    try:
        from ultralytics import YOLO
        import torch
        model_path = os.path.join(os.path.dirname(__file__), "models", "yolov8s.pt")
        if not os.path.exists(model_path):
            logger.warning("YOLOv8 model not found at %s. Falling back to morphological.", model_path)
            return None
            
        logger.info("Loading YOLOv8 model from %s", model_path)
        _yolo_detector = YOLO(model_path)
        
        if torch.cuda.is_available():
            _yolo_detector.model.half()
            logger.info("YOLOv8 FP16 mode enabled")
            
    except ImportError:
        logger.warning("Ultralytics/Torch not installed. Falling back to morphological detection.")
    except Exception as e:
        logger.error("Failed to load YOLOv8: %s", e)
        
    return _yolo_detector


def detect_vehicles(frame: np.ndarray, prev_gray: np.ndarray | None = None) -> list[dict[str, Any]]:
    """Vehicle Detection Engine (YOLOv8 with Morphological fallback)."""
    if frame is None or frame.size == 0:
        return []

    h, w = frame.shape[:2]
    
    detector = _init_yolo()
    if detector is not None:
        try:
            # Run YOLO tracking (2, 3, 5, 7 are COCO classes for car, motorcycle, bus, truck)
            results = detector.track(source=frame, persist=True, conf=0.35, iou=0.45, verbose=False, classes=[2, 3, 5, 7])
            boxes_out = []
            if results and len(results) > 0 and results[0].boxes is not None:
                boxes = results[0].boxes
                if boxes.id is not None:
                    ids = boxes.id.int().tolist()
                    confs = boxes.conf.tolist()
                    clss = boxes.cls.int().tolist()
                    xyxys = boxes.xyxy.tolist()
                    
                    coco_names = {2: "car", 3: "bike/activa", 5: "bus/truck", 7: "bus/truck"}
                    for tid, cf, cls_id, (x1, y1, x2, y2) in zip(ids, confs, clss, xyxys):
                        bw = int(x2 - x1)
                        bh = int(y2 - y1)
                        boxes_out.append({
                            "x": int(x1), "y": int(y1), "w": bw, "h": bh,
                            "cls": coco_names.get(cls_id, "vehicle"),
                            "confidence": round(cf, 2),
                            "track_id": tid
                        })
            return boxes_out
        except Exception as e:
            logger.error("YOLO tracking failed: %s", e)
            # Fallback below
            
    # --- Morphological Fallback ---
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
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
                    else:
                        cls_name = "bike/activa"
                    boxes.append({
                        "x": int(mx), "y": int(my), "w": int(mw), "h": int(mh),
                        "cls": cls_name, "confidence": 0.85
                    })

    return boxes
