"""Fast-ALPR, Plate Candidate Extraction, and OCR Character Recognition with YOLOv8 & PaddleOCR."""
from __future__ import annotations

import re
import threading
from typing import Any
import os
import logging

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

from sentinelshield.config import settings
from sentinelshield.modules.vision.deblur import enhance_blurry_crop

logger = logging.getLogger(__name__)

PLATE_RE = re.compile(r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4})\b", re.I)

_fast_alpr_instance = None
_fast_alpr_lock = threading.Lock()
_fast_alpr_unavailable = False

_plate_yolo = None
_plate_yolo_initialized = False

_paddle_ocr = None
_paddle_ocr_initialized = False


def _init_plate_yolo():
    global _plate_yolo, _plate_yolo_initialized
    if _plate_yolo_initialized:
        return _plate_yolo
    _plate_yolo_initialized = True
    try:
        from ultralytics import YOLO
        import torch
        model_path = os.path.join(os.path.dirname(__file__), "models", "license_plate_detector.pt")
        if os.path.exists(model_path):
            _plate_yolo = YOLO(model_path)
            if torch.cuda.is_available():
                _plate_yolo.model.half()
    except Exception as e:
        logger.warning("YOLO license plate model failed to load: %s", e)
    return _plate_yolo

def _init_paddle_ocr():
    global _paddle_ocr, _paddle_ocr_initialized
    if _paddle_ocr_initialized:
        return _paddle_ocr
    _paddle_ocr_initialized = True
    try:
        from paddleocr import PaddleOCR
        _paddle_ocr = PaddleOCR(use_angle_cls=False, lang='en', show_log=False)
    except Exception as e:
        logger.warning("PaddleOCR failed to load: %s", e)
    return _paddle_ocr


def normalize_plate(p: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9]", "", (p or "").upper())
    if not cleaned:
        return ""
    match = re.search(r"([A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4})", cleaned)
    if match:
        return match.group(1)
    stripped = re.sub(r"^(IND|IN|USA|UK|US|GB)", "", cleaned)
    if stripped:
        return stripped
    return cleaned


def extract_plates_from_text(*texts: str) -> list[str]:
    found = []
    for t in texts:
        if not t:
            continue
        for m in PLATE_RE.findall(t.upper()):
            found.append(normalize_plate(m))
        compact = normalize_plate(t)
        if re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4}", compact):
            found.append(compact)
    return list(dict.fromkeys(found))


def detect_fast_alpr(frame: np.ndarray) -> list[dict[str, Any]]:
    return []


def extract_plate_candidate(vehicle_crop: np.ndarray) -> dict[str, Any] | None:
    if vehicle_crop is None or vehicle_crop.size == 0:
        return None

    yolo = _init_plate_yolo()
    if yolo is not None:
        try:
            res = yolo.predict(source=vehicle_crop, conf=0.25, verbose=False)
            if res and len(res) > 0 and res[0].boxes is not None and len(res[0].boxes) > 0:
                box = res[0].boxes[0]
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                pw, ph = int(x2-x1), int(y2-y1)
                px, py = int(x1), int(y1)
                
                plate_crop = vehicle_crop[py:py+ph, px:px+pw]
                if plate_crop.size > 0:
                    cand = {
                        "box": {"x": px, "y": py, "w": pw, "h": ph},
                        "crop": plate_crop,
                    }
                    enh = enhance_blurry_crop(cand["crop"])
                    cand["enhanced_crop_b64"] = enh["b64"]
                    cand["deblur_score"] = enh["laplacian_score"]
                    cand["enhanced_bgr"] = enh["enhanced_bgr"]
                    return cand
        except Exception:
            pass

    # Fallback to morphological
    h, w = vehicle_crop.shape[:2]
    roi_top = int(h * 0.25)
    lower_roi = vehicle_crop[roi_top:h, :]

    enhanced_dict = enhance_blurry_crop(lower_roi)
    gray = cv2.cvtColor(enhanced_dict["enhanced_bgr"], cv2.COLOR_BGR2GRAY)

    sobel = cv2.Sobel(gray, cv2.CV_8U, 1, 0, ksize=3)
    _, thresh = cv2.threshold(sobel, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (17, 3))
    morph = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)

    cnts, _ = cv2.findContours(morph, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best_candidate = None
    max_score = 0.0

    for c in cnts:
        px, py, pw, ph = cv2.boundingRect(c)
        aspect = pw / float(ph) if ph > 0 else 0
        area = pw * ph

        if 2.0 < aspect < 6.0 and 400 < area < 45000:
            score = area * aspect
            if score > max_score:
                max_score = score
                plate_crop = lower_roi[py:py + ph, px:px + pw]
                if plate_crop.size > 0:
                    best_candidate = {
                        "box": {"x": int(px), "y": int(py + roi_top), "w": int(pw), "h": int(ph)},
                        "crop": plate_crop,
                    }

    if best_candidate is None:
        ph, pw = int(h * 0.35), int(w * 0.7)
        px, py = int(w * 0.15), int(h * 0.5)
        plate_crop = vehicle_crop[py:py + ph, px:px + pw]
        best_candidate = {
            "box": {"x": px, "y": py, "w": pw, "h": ph},
            "crop": plate_crop if plate_crop.size > 0 else vehicle_crop,
        }

    enh = enhance_blurry_crop(best_candidate["crop"])
    best_candidate["enhanced_crop_b64"] = enh["b64"]
    best_candidate["deblur_score"] = enh["laplacian_score"]
    best_candidate["enhanced_bgr"] = enh["enhanced_bgr"]
    return best_candidate


def read_plate_text(plate_crop: np.ndarray) -> tuple[str | None, float]:
    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0
        
    ocr = _init_paddle_ocr()
    if ocr is not None:
        try:
            res = ocr.ocr(plate_crop, cls=False)
            if res and res[0]:
                texts = []
                confs = []
                for line in res[0]:
                    txt, cf = line[1][0], line[1][1]
                    val = normalize_plate(txt)
                    if val:
                        texts.append(val)
                        confs.append(cf)
                if texts:
                    return "".join(texts), round(sum(confs)/len(confs), 3)
        except Exception:
            pass

    # Try Open-LPR
    try:
        import requests
        ok, buf = cv2.imencode(".jpg", plate_crop)
        if ok:
            resp = requests.post(
                settings.open_lpr_url,
                files={"image": ("plate.jpg", buf.tobytes(), "image/jpeg")},
                timeout=1.5,
            )
            if resp.status_code == 200:
                data = resp.json()
                if data.get("success") and "results" in data and "detections" in data["results"]:
                    dets = data["results"]["detections"]
                    if dets and len(dets) > 0 and "ocr" in dets[0] and len(dets[0]["ocr"]) > 0:
                        ocr_data = dets[0]["ocr"][0]
                        text = normalize_plate(ocr_data.get("text", ""))
                        if text:
                            return text, float(ocr_data.get("confidence", 0.0))
    except Exception:
        pass

    # Try pytesseract
    try:
        import pytesseract
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        data = pytesseract.image_to_data(
            gray,
            config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            output_type=pytesseract.Output.DICT,
        )
        words, confidences = [], []
        for text, confidence in zip(data["text"], data["conf"]):
            val = normalize_plate(text)
            score = float(confidence) if str(confidence).replace('.','').isdigit() else -1
            if val and score >= 0:
                words.append(val)
                confidences.append(score)
        if words:
            return "".join(words), round(sum(confidences) / len(confidences) / 100, 3)
    except Exception:
        pass

    return None, 0.0
