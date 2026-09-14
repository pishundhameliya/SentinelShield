"""Sentinel-X Vision and ANPR Subsystem."""
from sentinelshield.modules.vision.deblur import enhance_blurry_crop, blur_box
from sentinelshield.modules.vision.vehicle_detector import detect_vehicles
from sentinelshield.modules.vision.alpr_ocr import (
    PLATE_RE,
    normalize_plate,
    extract_plates_from_text,
    detect_fast_alpr,
    extract_plate_candidate,
    read_plate_text,
)
from sentinelshield.modules.vision.service import vision_service, VisionService
from sentinelshield.modules.vision.router import router as vision_router

__all__ = [
    "enhance_blurry_crop",
    "blur_box",
    "detect_vehicles",
    "PLATE_RE",
    "normalize_plate",
    "extract_plates_from_text",
    "detect_fast_alpr",
    "extract_plate_candidate",
    "read_plate_text",
    "vision_service",
    "VisionService",
    "vision_router",
]
