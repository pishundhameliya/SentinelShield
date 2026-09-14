"""Vehicle Detection + Fast ALPR + CCTV Image Deblurring Engine for SentinelShield.

Re-exports modular vision, integrity, and ALPR functions for backwards compatibility.
"""
from __future__ import annotations

from sentinelshield.modules.integrity.hash_chain import sha256_bytes
from sentinelshield.modules.integrity.tamper_detector import is_black_frame as _is_black, frame_difference_score as _is_freeze
from sentinelshield.modules.streaming.worker import process_video
from sentinelshield.modules.vision.alpr_ocr import (
    PLATE_RE,
    detect_fast_alpr,
    extract_plate_candidate,
    extract_plates_from_text,
    normalize_plate,
    read_plate_text,
)
from sentinelshield.modules.vision.deblur import blur_box, enhance_blurry_crop
from sentinelshield.modules.vision.vehicle_detector import detect_vehicles

__all__ = [
    "sha256_bytes",
    "normalize_plate",
    "extract_plates_from_text",
    "detect_fast_alpr",
    "enhance_blurry_crop",
    "detect_vehicles",
    "extract_plate_candidate",
    "read_plate_text",
    "blur_box",
    "_is_black",
    "_is_freeze",
    "process_video",
    "PLATE_RE",
]
