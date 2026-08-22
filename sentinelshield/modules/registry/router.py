"""API Router for estate exploration, camera registry, and live links."""
from __future__ import annotations

try:
    from fastapi import APIRouter, Form
    from fastapi.responses import JSONResponse
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    JSONResponse = dict  # type: ignore
    Form = lambda default=None, **kw: default  # type: ignore

from core.database import db_manager
from core.state import ai_state
from modules.registry.estate_data import total_cameras
from modules.registry.service import registry_service

router = APIRouter(tags=["registry"])


@router.get("/api/cities")
def api_cities():
    return {
        "cities": registry_service.get_cities(),
        "estate_total": total_cameras(),
    }


@router.get("/api/areas")
def api_areas(city: str):
    return {"areas": registry_service.get_areas(city)}


@router.get("/api/cameras")
def api_cameras(city: str = "", area: str = "", owner: str = "government"):
    return registry_service.get_cameras(city=city, area=area, owner=owner)


@router.get("/api/hot-cams")
def hot_cams():
    return {"cameras": registry_service.get_hot_cams()}


@router.get("/api/live-cameras")
def live_cameras():
    return {"cameras": registry_service.get_live_cams()}


@router.post("/api/cameras")
def add_camera(
    name: str = Form(...),
    place: str = Form("Surat"),
    lat: float = Form(21.17),
    lng: float = Form(72.83),
    city_id: str = Form(""),
    area_id: str = Form(""),
    owner: str = Form("Gujarat Police"),
    live_url: str = Form(""),
):
    cid = registry_service.add_camera(
        name=name,
        place=place,
        lat=lat,
        lng=lng,
        city_id=city_id,
        area_id=area_id,
        owner=owner,
        live_url=live_url,
    )
    return {"ok": True, "id": cid}


@router.post("/api/cameras/{camera_id}/connect")
def connect_live(camera_id: str, live_url: str = Form(...)):
    """Save a real camera URL: rtsp://, http://, or https://."""
    cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, 404)
    url = (live_url or "").strip()
    if not url:
        return JSONResponse({"error": "Paste a camera link"}, 400)
    low = url.lower()
    if not (low.startswith("rtsp://") or low.startswith("rtsps://")
            or low.startswith("http://") or low.startswith("https://")):
        return JSONResponse({"error": "Link must start with rtsp:// or http://"}, 400)

    registry_service.connect_camera_url(camera_id, url)
    return {"ok": True, "camera_id": camera_id}


@router.post("/api/cameras/import-csv")
def import_cameras_csv(csv_text: str = Form(""), mode: str = Form("update")):
    """Bulk import cameras from CSV spreadsheet."""
    from modules.registry.importer import import_cameras_from_csv
    return import_cameras_from_csv(csv_text, duplicate_mode=mode)


@router.post("/api/purge-static-data")
def purge_static_data():
    ai_state.set_active(False)
    db_manager.purge_all_data()
    return {"ok": True, "message": "All static and demo data erased cleanly!"}
