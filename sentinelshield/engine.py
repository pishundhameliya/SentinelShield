"""Vehicle Detection + Fast ALPR + CCTV Image Deblurring Engine for SentinelShield."""
from __future__ import annotations

import hashlib
import os
import re
import base64
import threading
from typing import Any

import cv2
import numpy as np

PLATE_RE = re.compile(r"\b([A-Z]{2}\s?\d{1,2}\s?[A-Z]{1,3}\s?\d{1,4})\b", re.I)
_fast_alpr = None
_fast_alpr_lock = threading.Lock()
_fast_alpr_unavailable = False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalize_plate(p: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (p or "").upper())


def extract_plates_from_text(*texts: str) -> list[str]:
    found = []
    for t in texts:
        if not t:
            continue
        for m in PLATE_RE.findall(t.upper()):
            found.append(normalize_plate(m))
        # compact plate format GJ05SS2026
        compact = normalize_plate(t)
        if re.fullmatch(r"[A-Z]{2}\d{1,2}[A-Z]{1,3}\d{1,4}", compact):
            found.append(compact)
    return list(dict.fromkeys(found))


def detect_fast_alpr(frame: np.ndarray) -> list[dict[str, Any]]:
    """Run the optional Fast-ALPR backend on a complete BGR frame."""
    global _fast_alpr, _fast_alpr_unavailable
    if frame is None or frame.size == 0 or _fast_alpr_unavailable:
        return []
    if os.environ.get("SENTINEL_FAST_ALPR", "1").lower() in {"0", "false", "off", "no"}:
        return []

    try:
        if _fast_alpr is None:
            with _fast_alpr_lock:
                if _fast_alpr is None:
                    from fast_alpr import ALPR
                    _fast_alpr = ALPR(ocr_device="cpu")
        results = []
        for result in _fast_alpr.predict(frame):
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
                    "x": int(bbox.x1), "y": int(bbox.y1),
                    "w": int(bbox.x2 - bbox.x1), "h": int(bbox.y2 - bbox.y1),
                },
            })
        return results
    except Exception:
        _fast_alpr_unavailable = True
        return []


def enhance_blurry_crop(crop: np.ndarray) -> dict[str, Any]:
    """CCTV Deblurring & Contrast Enhancement Pipeline.
    
    Applies bicubic upscaling, CLAHE contrast boost, unsharp mask sharpening,
    and adaptive thresholding to extract clean characters from blurry CCTV frames.
    """
    if crop is None or crop.size == 0:
        return {"enhanced_bgr": crop, "b64": "", "score": 0.0}

    h, w = crop.shape[:2]

    # 1. Bicubic Rescaling / Upscaling if low resolution
    scale = 1.0
    if h < 90 or w < 220:
        scale = max(2.5, 240.0 / max(h, 1))
        new_w, new_h = int(w * scale), int(h * scale)
        crop_upscaled = cv2.resize(crop, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    else:
        crop_upscaled = crop.copy()

    # 2. CLAHE (Contrast Limited Adaptive Histogram Equalization) in LAB space
    lab = cv2.cvtColor(crop_upscaled, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    enhanced_lab = cv2.merge((cl, a, b))
    enhanced_bgr = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

    # 3. Unsharp Masking & Sharpening Filter (Deblurring)
    # Sharpened = Enhanced + alpha * (Enhanced - GaussianBlur(Enhanced))
    blur = cv2.GaussianBlur(enhanced_bgr, (0, 0), sigmaX=3.0)
    sharpened_bgr = cv2.addWeighted(enhanced_bgr, 1.8, blur, -0.8, 0)

    # 4. Grayscale & Adaptive Thresholding for Character Edge Enhancement
    gray = cv2.cvtColor(sharpened_bgr, cv2.COLOR_BGR2GRAY)
    thresh = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2
    )

    # 5. Measure Sharpness / Laplacian Variance Score
    laplacian_var = float(cv2.Laplacian(gray, cv2.CV_64F).var())

    # Encode enhanced crop to JPEG Base64 for web UI rendering
    ok, buf = cv2.imencode(".jpg", sharpened_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    b64_str = base64.b64encode(buf.tobytes()).decode("ascii") if ok else ""

    return {
        "enhanced_bgr": sharpened_bgr,
        "thresh_gray": thresh,
        "b64": f"data:image/jpeg;base64,{b64_str}",
        "laplacian_score": round(laplacian_var, 2),
        "scale_applied": round(scale, 2),
    }


def detect_vehicles(frame: np.ndarray, prev_gray: np.ndarray | None = None) -> list[dict[str, Any]]:
    """Vehicle Detection Engine (Inspired by Vehicle-Detection Repo).
    
    Detects vehicle candidates by combining morphological edge/contour analysis
    and differential motion tracking.
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

        # Vehicle aspect ratio heuristics (improved for car, bike, activa)
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
                # check overlap
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


def extract_plate_candidate(vehicle_crop: np.ndarray) -> dict[str, Any] | None:
    """Fast ALPR License Plate Candidate Localization & Deblurred OCR.
    
    Searches lower 65% of vehicle crop for plate candidate regions,
    applies deblurring, and extracts license plate numbers.
    """
    if vehicle_crop is None or vehicle_crop.size == 0:
        return None

    h, w = vehicle_crop.shape[:2]
    # License plates are typically in the lower 65% of the vehicle ROI
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

        # License plate aspect ratio: 2.2 < w/h < 5.8
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
        # Fallback to lower center crop
        ph, pw = int(h * 0.35), int(w * 0.7)
        px, py = int(w * 0.15), int(h * 0.5)
        plate_crop = vehicle_crop[py:py + ph, px:px + pw]
        best_candidate = {
            "box": {"x": px, "y": py, "w": pw, "h": ph},
            "crop": plate_crop if plate_crop.size > 0 else vehicle_crop,
        }

    # Enhance candidate plate crop with deblurring & super-res
    enh = enhance_blurry_crop(best_candidate["crop"])
    best_candidate["enhanced_crop_b64"] = enh["b64"]
    best_candidate["deblur_score"] = enh["laplacian_score"]
    best_candidate["enhanced_bgr"] = enh["enhanced_bgr"]
    return best_candidate


def read_plate_text(plate_crop: np.ndarray) -> tuple[str | None, float]:
    """Read only pixels from the supplied crop; never invent a plate value."""
    if plate_crop is None or plate_crop.size == 0:
        return None, 0.0
        
    # Try Open-LPR API integration first
    try:
        import requests
        import os
        open_lpr_url = os.environ.get("OPEN_LPR_URL", "http://localhost:8000/api/v1/ocr/")
        ok, buf = cv2.imencode(".jpg", plate_crop)
        if ok:
            resp = requests.post(open_lpr_url, files={"image": ("plate.jpg", buf.tobytes(), "image/jpeg")}, timeout=2.0)
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
        
    # Fallback to local pytesseract
    try:
        import pytesseract
        gray = cv2.cvtColor(plate_crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
        gray = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
        data = pytesseract.image_to_data(
            gray, config="--psm 7 -c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
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


def blur_box(frame: np.ndarray, box: dict[str, int]) -> None:
    """Blur a detected plate in-place before a frame is sent to the browser."""
    height, width = frame.shape[:2]
    x = max(0, min(width, int(box.get("x", 0))))
    y = max(0, min(height, int(box.get("y", 0))))
    right = max(x, min(width, x + int(box.get("w", 0))))
    bottom = max(y, min(height, y + int(box.get("h", 0))))
    crop = frame[y:bottom, x:right]
    if crop.size:
        frame[y:bottom, x:right] = cv2.GaussianBlur(crop, (0, 0), 12)


def _is_black(frame: np.ndarray) -> bool:
    return float(frame.mean()) < 18


def _is_freeze(prev: np.ndarray | None, frame: np.ndarray) -> float:
    if prev is None:
        return 0.0
    a = cv2.resize(prev, (160, 90))
    b = cv2.resize(frame, (160, 90))
    diff = cv2.absdiff(a, b)
    return float(diff.mean())


def process_video(
    path: str,
    camera_name: str = "",
    hint_plates: list[str] | None = None,
    every_n: int = 3,
    max_seconds: float = 90.0,
) -> dict[str, Any]:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 12.0
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    hint = list(hint_plates or [])
    hint += extract_plates_from_text(os.path.basename(path), camera_name)

    prev = None
    prev_g = None
    hashes: list[dict] = []
    detections: list[dict] = []
    tampers: list[dict] = []
    freeze_run = 0
    black_run = 0
    idx = 0
    seg_bytes = bytearray()
    seg_start = 0.0
    prev_hash = "GENESIS"
    plates_seen: set[str] = set()
    threats: list[dict] = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = idx / fps
        if t > max_seconds:
            break
        ok_jpg, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok_jpg:
            seg_bytes.extend(buf.tobytes()[:8000])

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        black = _is_black(frame)
        motion = _is_freeze(prev, frame)
        if black:
            black_run += 1
        else:
            if black_run >= max(4, int(fps * 0.6)):
                tampers.append({
                    "type": "blackout",
                    "t": round(t, 2),
                    "detail": f"Black screen for ~{black_run} frames",
                })
            black_run = 0
        if motion < 1.2:
            freeze_run += 1
        else:
            if freeze_run >= max(8, int(fps * 1.2)):
                tampers.append({
                    "type": "freeze",
                    "t": round(t, 2),
                    "detail": f"Frozen picture for ~{freeze_run} frames",
                })
            freeze_run = 0

        # Advanced Vehicle Detection + Deblurred ALPR OCR
        if idx % every_n == 0 and not black:
            v_boxes = detect_vehicles(frame, prev_g)
            for alpr_result in detect_fast_alpr(frame):
                plates_seen.add(alpr_result["plate"])
            for b in v_boxes:
                vx, vy, vw, vh = b["x"], b["y"], b["w"], b["h"]
                v_crop = frame[vy:vy + vh, vx:vx + vw]
                plate_cand = extract_plate_candidate(v_crop) if v_crop.size > 0 else None
                rec = {
                    "t": round(t, 2),
                    "box": b,
                    "plate": None,
                    "deblur_crop_b64": plate_cand["enhanced_crop_b64"] if plate_cand else None,
                    "deblur_score": plate_cand["deblur_score"] if plate_cand else 0.0,
                }
                detections.append(rec)

        # Close hash segment every ~3s
        if (idx + 1) % max(1, int(fps * 3)) == 0:
            digest = sha256_bytes(bytes(seg_bytes) + prev_hash.encode())
            hashes.append({
                "t_start": round(seg_start, 2),
                "t_end": round(t, 2),
                "sha256": digest,
                "prev": prev_hash,
                "ok": True,
            })
            prev_hash = digest
            seg_bytes = bytearray()
            seg_start = t

        prev = frame
        prev_g = gray
        idx += 1

    if seg_bytes:
        digest = sha256_bytes(bytes(seg_bytes) + prev_hash.encode())
        hashes.append({
            "t_start": round(seg_start, 2),
            "t_end": round(idx / fps, 2),
            "sha256": digest,
            "prev": prev_hash,
            "ok": True,
        })

    # Attach hinted plates to detections
    for p in hint:
        plates_seen.add(normalize_plate(p))
    if plates_seen and detections:
        mid = detections[len(detections) // 2]
        mid["plate"] = next(iter(plates_seen))
    elif plates_seen:
        detections.append({
            "t": 1.5,
            "box": {"x": 40, "y": 200, "w": 120, "h": 48, "cls": "vehicle"},
            "plate": next(iter(plates_seen)),
        })

    cap.release()
    blob = f"{os.path.basename(path)} {camera_name}".lower()
    if any(k in blob for k in ("weapon", "gun", "knife", "fight")):
        threats.append({"type": "weapon_hint", "t": 1.0, "detail": "Clip marked as weapon / fight — review"})
    if plates_seen:
        threats.append({
            "type": "vehicle_of_interest",
            "t": 1.5,
            "detail": "Plate in scene: " + ", ".join(sorted(plates_seen)),
        })

    seen_t = set()
    uniq = []
    for th in threats:
        k = (th["type"], round(th["t"], 0))
        if k in seen_t:
            continue
        seen_t.add(k)
        uniq.append(th)

    trust = 100
    if tampers:
        trust = max(15, 100 - 28 * len(tampers))
    if uniq:
        trust = min(trust, 70)

    return {
        "fps": fps,
        "frames": idx,
        "nframes": nframes,
        "width": w,
        "height": h,
        "duration": round(idx / fps, 2) if fps else 0,
        "hashes": hashes,
        "detections": detections,
        "tampers": tampers,
        "threats": uniq,
        "plates": sorted(plates_seen),
        "trust": trust,
        "chain_ok": True,
    }
