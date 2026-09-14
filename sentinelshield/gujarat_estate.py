"""Gujarat government CCTV estate registry — backwards compatible re-export."""
from __future__ import annotations

from sentinelshield.modules.registry.estate_data import (
    CITIES,
    DEMO_CAMS,
    OWNERS,
    SENTINEL_LIVE_CAMS,
    sample_points,
    total_cameras,
)

__all__ = [
    "CITIES",
    "OWNERS",
    "DEMO_CAMS",
    "SENTINEL_LIVE_CAMS",
    "total_cameras",
    "sample_points",
]
