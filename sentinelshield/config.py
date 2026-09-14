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
    open_lpr_url: str = field(
        default_factory=lambda: os.environ.get("OPEN_LPR_URL", "http://localhost:8000/api/v1/ocr/")
    )


settings = Settings()
