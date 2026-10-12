"""API router for live ANPR scanning and deblurred plate recognition."""
from __future__ import annotations

import glob
import os
import uuid
from typing import Any

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

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

from sentinelshield.config import settings
from sentinelshield.core.database import db_manager, utcnow
from sentinelshield.core.state import auto_anpr_state, live_stream_state
from sentinelshield.modules.vision.plate_recognizer import plate_recognizer
from sentinelshield.modules.vision.service import vision_service
from sentinelshield.modules.vision.vehicle_detector import detector_status

router = APIRouter(tags=["vision"])


@router.get("/api/anpr/status")
def anpr_status():
    """Report whether the number plate and vehicle detection engines are loaded and usable."""
    status = plate_recognizer.status()
    status["vehicle_detector"] = detector_status()
    status["auto_scan"] = {k: v for k, v in auto_anpr_state.snapshot(limit=0).items() if k != "recent"}
    return status


@router.get("/api/anpr/auto")
def anpr_auto_status(camera_id: str = "", limit: int = 20):
    """Automatic ANPR status and the latest plates it recorded (optionally for one camera)."""
    snap = auto_anpr_state.snapshot(camera_id=camera_id or None, limit=max(1, min(limit, 100)))
    snap["interval_s"] = settings.auto_anpr_interval_s
    snap["dedupe_s"] = settings.auto_anpr_dedupe_s
    snap["live_camera_id"] = live_stream_state.current_camera_id if live_stream_state.is_active else None
    snap["engine_ready"] = plate_recognizer.status()["available"]
    return snap


@router.post("/api/anpr/auto/{mode}")
def anpr_auto_toggle(mode: str):
    """Turn automatic ANPR on or off."""
    if mode not in {"on", "off"}:
        return JSONResponse({"error": "mode must be 'on' or 'off'"}, 400)
    auto_anpr_state.set_enabled(mode == "on")
    return {"ok": True, "enabled": auto_anpr_state.is_enabled}


def _collect_camera_source_candidates(camera_id: str, cam: dict[str, Any] | None) -> list[str]:
    """Build a resilient list of possible source URLs for a camera without changing existing behavior."""
    candidates: list[str] = []

    if cam:
        for key in ("live_url", "source", "url"):
            value = str(cam.get(key) or "").strip()
            if value and value not in candidates:
                candidates.append(value)

    number = camera_id.rsplit("-", 1)[-1] if camera_id.startswith("sentinel-cam-") else ""
    if number.isdigit():
        for path in (
            f"https://live.corp8.cloud/camera/{number}",
            f"https://live.corp8.cloud/stream/{number}",
            f"rtsp://live.corp8.cloud:8554/stream/{number}",
            f"https://live.sentinelgujarat.in/camera/{number}",
            f"https://live.sentinelgujarat.in/stream/{number}",
            f"http://live.sentinelgujarat.in/camera/{number}",
            f"http://live.sentinelgujarat.in/stream/{number}",
        ):
            if path not in candidates:
                candidates.append(path)

    active_path = live_stream_state.current_path if live_stream_state.current_camera_id == camera_id else None
    if active_path and active_path not in candidates:
        candidates.insert(0, active_path)

    return candidates


def _read_frame_from_demo_fallback() -> Any:
    """Read a local demo frame when the live network source is unavailable."""
    demo_candidates = sorted(glob.glob(os.path.join(settings.demos_dir, "*.mp4")))
    for demo_path in demo_candidates:
        try:
            if cv2 is None:
                break
            cap = cv2.VideoCapture(demo_path)
            if not cap.isOpened():
                cap.release()
                continue
            ok, frame = cap.read()
            cap.release()
            if ok and frame is not None and frame.size > 0:
                return frame
        except Exception:
            continue
    return None


@router.post("/api/anpr/scan-live/{camera_id}")
def scan_live_anpr(camera_id: str):
    """Scan live frame from camera, run vehicle detection & deblurred ANPR, and save timestamped annotated photo."""
    cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
    if not cam:
        from sentinelshield.modules.registry.estate_data import SENTINEL_LIVE_CAMS
        cam = next((item for item in SENTINEL_LIVE_CAMS if item["id"] == camera_id), None)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, 404)

    frame = None
    if live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
        frame = live_stream_state.get_frame()

    if frame is None and cv2 is not None:
        for source in _collect_camera_source_candidates(camera_id, cam):
            if not source:
                continue
            try:
                cap = cv2.VideoCapture(source)
                if not cap.isOpened():
                    cap.release()
                    continue
                ok, frame = cap.read()
                cap.release()
                if ok and frame is not None and frame.size > 0:
                    break
            except Exception:
                continue

    if frame is None:
        frame = _read_frame_from_demo_fallback()

    if frame is None:
        return JSONResponse({"error": "Could not capture a frame from the selected camera source"}, 400)

    result = vision_service.process_scan_frame(frame, camera_id, cam.get("name", camera_id))
    note = f"Scanned: {len(result['vehicles'])} vehicles, {len(result['plates_enhanced'])} plates"
    if db_manager.query_one("SELECT id FROM cameras WHERE id=?", camera_id):
        db_manager.execute("UPDATE cameras SET last_note=? WHERE id=?", note, camera_id)

    # One row per vehicle, using the plate actually read on *that* vehicle (plates are not
    # paired by list position). Saved for every camera, including the built-in feeds.
    plates_by_vehicle = {}
    extra_plates = []
    for p in result.get("plates_enhanced") or []:
        if p.get("vehicle") in (result.get("vehicles") or []):
            plates_by_vehicle[id(p["vehicle"])] = p
        elif p.get("raw_plate"):
            extra_plates.append(p)
    place = cam.get("place") or cam.get("name") or camera_id
    rows = []
    for idx, vehicle in enumerate(result.get("vehicles") or []):
        p = plates_by_vehicle.get(id(vehicle)) or {}
        rows.append((vehicle.get("cls") or "vehicle", f"scan-{idx + 1}", p.get("raw_plate") or "Plate Not Clear",
                     float(p.get("ocr_confidence") or vehicle.get("confidence") or 0.0)))
    for idx, p in enumerate(extra_plates):
        rows.append(("vehicle", f"scan-plate-{idx + 1}", p["raw_plate"], float(p.get("ocr_confidence") or 0.0)))
    for cls, track, plate_text, confidence in rows:
        db_manager.execute(
            "INSERT INTO vehicle_detections VALUES(?,?,?,?,?,?,?,?,?,?)",
            "scan-" + uuid.uuid4().hex[:12], camera_id, cls, track, plate_text, confidence,
            utcnow(), cam.get("lat"), cam.get("lng"), place,
        )

    return result
