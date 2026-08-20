"""Registry and Gujarat estate module."""
from modules.registry.estate_data import (
    CITIES,
    OWNERS,
    DEMO_CAMS,
    SENTINEL_LIVE_CAMS,
    total_cameras,
    sample_points,
)
from modules.registry.service import registry_service, RegistryService
from modules.registry.router import router as registry_router

__all__ = [
    "CITIES",
    "OWNERS",
    "DEMO_CAMS",
    "SENTINEL_LIVE_CAMS",
    "total_cameras",
    "sample_points",
    "registry_service",
    "RegistryService",
    "registry_router",
]
