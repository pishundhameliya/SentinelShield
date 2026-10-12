"""Vehicle number plate recognition engine (ANPR) built on fast-alpr ONNX models.

fast-alpr bundles a YOLOv9 plate detector and a CCT plate-OCR model; both run on
CPU through onnxruntime, so no torch / ultralytics / PaddleOCR install is needed.
Model files are downloaded once on first load and cached by the library.

Raw OCR is post-processed against the Indian registration format so common
character confusions (O/0, I/1, S/5, B/8, C/G ...) are corrected by position:

    standard:  GJ 05 AB 4321   -> state(2 letters) district(1-2 digits) series(0-3 letters) number(4 digits)
    BH series: 22 BH 1234 AA   -> year(2 digits) BH number(4 digits) series(1-2 letters)
"""
from __future__ import annotations

import logging
import re
import threading
import time
from typing import Any

from sentinelshield.config import settings

logger = logging.getLogger(__name__)

STATE_CODES = frozenset({
    "AN", "AP", "AR", "AS", "BR", "CG", "CH", "CT", "DD", "DL", "DN", "GA", "GJ", "HP", "HR",
    "JH", "JK", "KA", "KL", "LA", "LD", "MH", "ML", "MN", "MP", "MZ", "NL", "OD", "OR", "PB",
    "PY", "RJ", "SK", "TG", "TN", "TR", "TS", "UA", "UK", "UP", "WB",
})

# OCR look-alikes: letter read where a digit belongs, and the reverse
_TO_DIGIT = {"O": "0", "Q": "0", "D": "0", "U": "0", "I": "1", "L": "1", "J": "1", "Z": "2",
             "A": "4", "S": "5", "G": "6", "T": "7", "B": "8"}
_TO_LETTER = {"0": "O", "1": "I", "2": "Z", "4": "A", "5": "S", "6": "G", "7": "T", "8": "B"}
# Letter pairs the OCR confuses inside a state code (tried only when the code is invalid)
_STATE_CONFUSIONS = {"C": "G", "A": "G", "O": "D", "D": "O", "H": "M", "M": "H", "W": "M",
                     "V": "U", "U": "V", "I": "J", "K": "X", "X": "K", "Q": "O"}


def _as_digits(s: str) -> str:
    return "".join(_TO_DIGIT.get(c, c) for c in s)


def _as_letters(s: str) -> str:
    return "".join(_TO_LETTER.get(c, c) for c in s)


def _fix_state(code: str) -> str:
    if code in STATE_CODES:
        return code
    home = settings.anpr_home_state
    candidates = []
    for i in (0, 1):
        alt = _STATE_CONFUSIONS.get(code[i])
        if alt:
            fixed = code[:i] + alt + code[i + 1:]
            if fixed in STATE_CODES:
                candidates.append(fixed)
    if home in candidates:
        return home
    return candidates[0] if candidates else code


def parse_indian_plate(text: str) -> dict[str, Any]:
    """Correct raw OCR text to an Indian registration number.

    Returns {"plate", "formatted", "valid", "corrected", "raw"}. "plate" is the
    compact upper-case form used for watchlist matching (e.g. "GJ05AB4321").
    """
    raw = re.sub(r"[^A-Z0-9]", "", (text or "").upper())
    result = {"plate": raw, "formatted": raw, "valid": False, "corrected": False, "raw": raw}
    if len(raw) < 6:
        return result

    # BH (Bharat) series: YY BH NNNN L(L)
    bh = re.fullmatch(r"(.{2})(BH|8H|B4)(.{4})(.{1,2})", raw)
    if bh:
        year, number, series = _as_digits(bh.group(1)), _as_digits(bh.group(3)), _as_letters(bh.group(4))
        if year.isdigit() and number.isdigit() and series.isalpha():
            plate = f"{year}BH{number}{series}"
            result.update(plate=plate, formatted=f"{year} BH {number} {series}", valid=True,
                          corrected=plate != raw)
            return result

    if not 7 <= len(raw) <= 11:
        return result

    state = _fix_state(_as_letters(raw[:2]))
    number = _as_digits(raw[-4:])
    middle = raw[2:-4]

    # middle = district (1-2 digits) + series (0-3 letters). Prefer a 2-digit district
    # unless the second character is a letter that is never mistaken for a digit.
    if len(middle) >= 2 and middle[1].isalpha() and middle[1] not in _TO_DIGIT:
        district, series = middle[:1], middle[1:]
    else:
        district, series = middle[:2], middle[2:]
    district, series = _as_digits(district), _as_letters(series)

    valid = (
        state in STATE_CODES
        and district.isdigit()
        and (series == "" or (series.isalpha() and len(series) <= 3))
        and number.isdigit()
    )
    if not valid:
        return result

    plate = f"{state}{district.zfill(2)}{series}{number}"
    formatted = " ".join(p for p in (state, district.zfill(2), series, number) if p)
    result.update(plate=plate, formatted=formatted, valid=True, corrected=plate != raw)
    return result


def _mean_conf(conf: Any) -> float:
    if isinstance(conf, (list, tuple)):
        vals = [float(c) for c in conf]
        return round(sum(vals) / len(vals), 3) if vals else 0.0
    try:
        return round(float(conf), 3)
    except (TypeError, ValueError):
        return 0.0


class PlateRecognizer:
    """Thread-safe, lazily loaded fast-alpr plate detector + OCR."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._alpr = None
        self._tried = False
        self._error: str | None = None
        self._load_ms: float | None = None

    def _engine(self):
        if self._tried:
            return self._alpr
        with self._lock:
            if self._tried:
                return self._alpr
            self._tried = True
            if not settings.enable_fast_alpr:
                self._error = "disabled (SENTINEL_FAST_ALPR=0)"
                return None
            started = time.time()
            try:
                from fast_alpr import ALPR  # heavy import; keep lazy
                self._alpr = ALPR(
                    detector_model=settings.anpr_detector_model,
                    detector_conf_thresh=settings.anpr_detector_conf,
                    ocr_model=settings.anpr_ocr_model,
                    ocr_device="cpu",
                )
                self._load_ms = round((time.time() - started) * 1000)
                logger.info("ANPR engine ready in %s ms", self._load_ms)
            except Exception as exc:  # missing package, offline model download, bad ONNX runtime
                self._error = f"{type(exc).__name__}: {exc}"
                logger.warning("ANPR engine unavailable: %s", self._error)
        return self._alpr

    def warm_up(self) -> None:
        """Load models in a background thread so the first scan is not delayed."""
        threading.Thread(target=self._engine, name="anpr-warmup", daemon=True).start()

    @property
    def available(self) -> bool:
        return self._engine() is not None

    def status(self) -> dict[str, Any]:
        loaded = self._tried and self._alpr is not None
        return {
            "engine": "fast-alpr (ONNX)",
            "available": loaded,
            "state": "ready" if loaded else ("error" if self._error else "loading"),
            "error": self._error,
            "detector_model": settings.anpr_detector_model,
            "ocr_model": settings.anpr_ocr_model,
            "load_ms": self._load_ms,
            "plate_format": "India (standard + BH series)",
        }

    def _to_entry(self, text: str, ocr_conf: Any, det_conf: float, box: dict[str, int]) -> dict[str, Any] | None:
        parsed = parse_indian_plate(text)
        conf = _mean_conf(ocr_conf)
        if not parsed["plate"] or conf < settings.anpr_min_ocr_conf:
            return None
        return {
            "plate": parsed["plate"],
            "formatted": parsed["formatted"],
            "valid": parsed["valid"],
            "corrected": parsed["corrected"],
            "raw_text": parsed["raw"],
            "confidence": conf,
            "det_confidence": round(float(det_conf), 3),
            "box": box,
        }

    def detect(self, frame) -> list[dict[str, Any]]:
        """Find and read every plate in a full BGR frame."""
        alpr = self._engine()
        if alpr is None or frame is None or getattr(frame, "size", 0) == 0:
            return []
        try:
            results = alpr.predict(frame)
        except Exception as exc:
            logger.debug("ANPR detect failed: %s", exc)
            return []
        out = []
        for r in results:
            if not r.ocr or not r.ocr.text:
                continue
            bb = r.detection.bounding_box
            box = {"x": int(bb.x1), "y": int(bb.y1), "w": int(bb.x2 - bb.x1), "h": int(bb.y2 - bb.y1)}
            entry = self._to_entry(r.ocr.text, r.ocr.confidence, r.detection.confidence, box)
            if entry:
                out.append(entry)
        # valid Indian plates first, then by confidence
        out.sort(key=lambda e: (not e["valid"], -e["confidence"]))
        return out

    def locate(self, image) -> dict[str, int] | None:
        """Return the most confident plate box inside an image (e.g. a vehicle crop)."""
        alpr = self._engine()
        if alpr is None or image is None or getattr(image, "size", 0) == 0:
            return None
        try:
            dets = alpr.detector.predict(image)
        except Exception:
            return None
        if not dets:
            return None
        best = max(dets, key=lambda d: d.confidence)
        bb = best.bounding_box
        h, w = image.shape[:2]
        x1, y1, x2, y2 = max(int(bb.x1), 0), max(int(bb.y1), 0), min(int(bb.x2), w), min(int(bb.y2), h)
        if x2 <= x1 or y2 <= y1:
            return None
        return {"x": x1, "y": y1, "w": x2 - x1, "h": y2 - y1}

    def read(self, plate_crop) -> tuple[str | None, float]:
        """OCR an already-cropped plate image. Returns (plate, confidence) or (None, 0.0)."""
        alpr = self._engine()
        if alpr is None or plate_crop is None or getattr(plate_crop, "size", 0) == 0:
            return None, 0.0
        try:
            res = alpr.ocr.predict(plate_crop)
        except Exception:
            return None, 0.0
        if not res or not res.text:
            return None, 0.0
        entry = self._to_entry(res.text, res.confidence, 1.0, {})
        if not entry:
            return None, 0.0
        return entry["plate"], entry["confidence"]


plate_recognizer = PlateRecognizer()
