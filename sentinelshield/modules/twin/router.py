"""API Router for Digital Twin analytics, heatmaps, assistant, and persons."""
from __future__ import annotations

try:
    from fastapi import APIRouter, Form
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    Form = lambda default=None, **kw: default  # type: ignore

from sentinelshield.core.database import db_manager
from sentinelshield.modules.twin.assistant import assistant_service
from sentinelshield.modules.twin.heat import digital_twin_service

router = APIRouter(tags=["twin"])


@router.get("/api/heat")
def api_heat():
    return digital_twin_service.get_heat_spots()


@router.get("/api/twin")
def api_twin():
    return digital_twin_service.get_twin_state()


@router.get("/api/cam-health")
def cam_health():
    return {"cameras": digital_twin_service.get_camera_health()}


@router.post("/api/drones/launch")
def drone_launch(city: str = Form("surat"), reason: str = Form("CCTV alert")):
    return digital_twin_service.simulate_drone_launch(city=city, reason=reason)


@router.post("/api/ask")
def api_ask(q: str = Form(...)):
    return assistant_service.parse_query(q)


@router.get("/api/persons")
def api_persons():
    return {"persons": db_manager.query_rows("SELECT * FROM persons")}


@router.get("/api/workflow")
def workflow():
    return {
        "name": "Sentinel-X Gujarat",
        "line": "Most projects only do video analytics. We combine CCTV integration, AI, GIS, cybersecurity, forensics and evidence in one platform.",
        "phases": [
            {"n": 1, "name": "Camera Registry", "status": "live"},
            {"n": 2, "name": "GIS Mapping", "status": "live"},
            {"n": 3, "name": "VMS Integration", "status": "demo"},
            {"n": 4, "name": "Live Stream", "status": "live"},
            {"n": 5, "name": "AI Analytics", "status": "live"},
            {"n": 6, "name": "Cybersecurity", "status": "live"},
            {"n": 7, "name": "Watchlist DB", "status": "live"},
            {"n": 8, "name": "Alert Management", "status": "live"},
            {"n": 9, "name": "Evidence Vault", "status": "live"},
            {"n": 10, "name": "Event Search", "status": "live"},
            {"n": 11, "name": "Police Dashboard", "status": "live"},
            {"n": 12, "name": "Scale 80k / 2L", "status": "design"},
        ],
        "vendors": ["Hikvision", "Dahua", "CP Plus", "Axis", "Milestone"],
        "stack": "OpenCV · SHA-256 · AES-256 · Leaflet · YOLOv8-ready · RTSP/ONVIF adapters",
    }
