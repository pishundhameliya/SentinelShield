"""Fast-ALPR, Plate Candidate Extraction, and OCR Character Recognition."""
from __future__ import annotations

import os
import re
import threading
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

from config import settings
from modules.vision.deblur import enhance_blurry_crop

PLATE_RE = re.compile(r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4})\b", re.I)

_fast_alpr_instance = None
_fast_alpr_lock = threading.Lock()
_fast_alpr_unavailable = False


def normalize_plate(p: str) -> str:
    """Normalize alphanumeric plate characters to standard uppercase format."""
    cleaned = re.sub(r"[^A-Z0-9]", "", (p or "").upper())
    if not cleaned:
        return ""

    match = re.search(r"([A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4})", cleaned)
    if match:
        return match.group(1)

    # Fallback: preserve the central plate token while removing obvious country prefixes.
    stripped = re.sub(r"^(IND|IN|USA|UK|US|GB)", "", cleaned)
    if stripped:
        return stripped
    return cleaned


def extract_plates_from_text(*texts: str) -> list[str]:
    """Extract all valid license plate strings from text or filenames."""
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
    """Run the optional Fast-ALPR deep neural backend on a complete BGR frame."""
    global _fast_alpr_instance, _fast_alpr_unavailable
    if frame is None or frame.size == 0 or _fast_alpr_unavailable or not settings.enable_fast_alpr:
        return []

    try:
        if _fast_alpr_instance is None:
            with _fast_alpr_lock:
                if _fast_alpr_instance is None:
                    from fast_alpr import ALPR
                    _fast_alpr_instance = ALPR(ocr_device="cpu")

        results = []
        for result in _fast_alpr_instance.predict(frame):
            ocr = result.ocr
            text = normalize_plate(getattr(ocr, "text", "") if ocr else "")
            if not text:
                continue
            confidence = getattr(ocr, "confidence", 0.0) if ocr else 0.0
            if isinstance(confidence, list):
                confidence = sum(confidence) / len(confidence) if confidence else 0.0
            bbox = result.detection.bounding_box
            results.append({
                "plate": text,
                "confidence": round(float(confidence), 3),
                "box": {
                    "x": int(bbox.x1),
                    "y": int(bbox.y1),
                    "w": int(bbox.x2 - bbox.x1),
                    "h": int(bbox.y2 - bbox.y1),
                },
            })
        return results
    except Exception:
        _fast_alpr_unavailable = True
        return []


def extract_plate_candidate(vehicle_crop: np.ndarray) -> dict[str, Any] | None:
    """Fast ALPR License Plate Candidate Localization & Deblurring."""
    if vehicle_crop is None or vehicle_crop.size == 0:
        return None

    h, w = vehicle_crop.shape[:2]
    roi_top = int(h * 0.25)
    lower_roi = vehicle_crop[roi_top:h, :]

    enhanced_dict = enhance_blurry_crop(lower_roi)
    gray = cv2.cvtColor(enhanced_dict["enhanced_bgr"], cv2.COLOR_BGR2GRAY)

    # Edge detection for rectangular plate contours
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

        # License plate aspect ratio: 2.0 < w/h < 6.0
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
    """Extract plate characters from crop via Open-LPR API or local pytesseract."""
    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0

    # 1. Try Open-LPR API endpoint
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

    # 2. Fallback to local pytesseract
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
        words = []
        confidences = []
        for text, confidence in zip(data["text"], data["conf"]):
            value = normalize_plate(text)
            try:
                score = float(confidence)
            except (TypeError, ValueError):
                score = -1
            if value and score >= 0:
                words.append(value)
                confidences.append(score)
        if words:
            return "".join(words), round(sum(confidences) / len(confidences) / 100, 3)
    except Exception:
        pass

    return None, 0.0
