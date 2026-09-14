"""API router for vehicle sightings, tracking history, and route reconstruction."""
from __future__ import annotations

try:
    from fastapi import APIRouter
    from fastapi.responses import JSONResponse
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    JSONResponse = dict  # type: ignore

from sentinelshield.modules.tracking.service import tracking_service

router = APIRouter(tags=["tracking"])


@router.get("/api/vehicle")
def find_vehicle(plate: str = ""):
    res = tracking_service.find_vehicle(plate)
    if "error" in res:
        return JSONResponse({"error": res["error"]}, res.get("status_code", 400))
    return res


@router.get("/api/vehicle-detections")
def vehicle_detections(camera_id: str = "", q: str = ""):
    return tracking_service.get_vehicle_detections(camera_id=camera_id, query=q)


@router.get("/api/route")
def api_route(plate: str = ""):
    return tracking_service.calculate_route(plate)
