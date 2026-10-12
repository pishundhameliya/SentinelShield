"""Central configuration, paths, and environment settings for SentinelShield."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ROOT_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "sentinel.db")
MEDIA_DIR = os.path.join(ROOT_DIR, "media")
UPLOADS_DIR = os.path.join(MEDIA_DIR, "uploads")
DEMOS_DIR = os.path.join(MEDIA_DIR, "demos")
SNAPSHOTS_DIR = os.path.join(MEDIA_DIR, "snapshots")
VAULT_DIR = os.path.join(MEDIA_DIR, "vault")
STATIC_DIR = os.path.join(ROOT_DIR, "static")

# Ensure required storage directories exist
for directory in [DATA_DIR, MEDIA_DIR, UPLOADS_DIR, DEMOS_DIR, SNAPSHOTS_DIR, VAULT_DIR, STATIC_DIR]:
    os.makedirs(directory, exist_ok=True)

DEFAULT_USERS = {
    "pishundhameliya@gmail.com": {"password": "DSVB-L42U-X7ZE", "name": "Pishun Dhameliya", "role": "admin"},
    "admin": {"password": "admin123", "name": "Admin Mehta", "role": "admin"},
    "operator": {"password": "oper123", "name": "Operator Patel", "role": "operator"},
    "police": {"password": "police123", "name": "PSI Shah", "role": "police"},
}


@dataclass
class Settings:
    root_dir: str = ROOT_DIR
    data_dir: str = DATA_DIR
    db_path: str = DB_PATH
    media_dir: str = MEDIA_DIR
    uploads_dir: str = UPLOADS_DIR
    demos_dir: str = DEMOS_DIR
    snapshots_dir: str = SNAPSHOTS_DIR
    vault_dir: str = VAULT_DIR
    static_dir: str = STATIC_DIR
    users: dict[str, dict[str, Any]] = field(default_factory=lambda: dict(DEFAULT_USERS))
    enable_fast_alpr: bool = field(
        default_factory=lambda: os.environ.get("SENTINEL_FAST_ALPR", "1").lower() not in {"0", "false", "off", "no"}
    )
    # Optional external Open-LPR OCR service; empty = not used. (The old default pointed at
    # this server's own port, so every plate read made a failing self-request.)
    open_lpr_url: str = field(default_factory=lambda: os.environ.get("OPEN_LPR_URL", ""))
    # ANPR engine (modules/vision/plate_recognizer.py)
    anpr_detector_model: str = field(
        default_factory=lambda: os.environ.get("SENTINEL_ANPR_DETECTOR", "yolo-v9-t-384-license-plate-end2end")
    )
    anpr_ocr_model: str = field(
        default_factory=lambda: os.environ.get("SENTINEL_ANPR_OCR", "cct-xs-v2-global-model")
    )
    anpr_detector_conf: float = field(
        default_factory=lambda: float(os.environ.get("SENTINEL_ANPR_DET_CONF", "0.4"))
    )
    anpr_min_ocr_conf: float = field(
        default_factory=lambda: float(os.environ.get("SENTINEL_ANPR_MIN_CONF", "0.5"))
    )
    anpr_home_state: str = field(default_factory=lambda: os.environ.get("SENTINEL_ANPR_HOME_STATE", "GJ"))
    # Vehicle detector (modules/vision/vehicle_detector.py). "rf-detr-nano-384-coco" is ~2x
    # faster on slow CPUs; "rf-detr-small-512-coco" finds more partly hidden vehicles.
    vehicle_model: str = field(
        default_factory=lambda: os.environ.get("SENTINEL_VEHICLE_MODEL", "rf-detr-small-512-coco")
    )
    vehicle_min_conf: float = field(
        default_factory=lambda: float(os.environ.get("SENTINEL_VEHICLE_MIN_CONF", "0.4"))
    )


settings = Settings()
