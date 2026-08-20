"""API router for live ANPR scanning and deblurred plate recognition."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import cv2

from core.database import db_manager
from core.state import live_stream_state
from modules.vision.service import vision_service

router = APIRouter(tags=["vision"])


@router.post("/api/anpr/scan-live/{camera_id}")
def scan_live_anpr(camera_id: str):
    """Scan live frame from camera, run vehicle detection & deblurred ANPR, and save timestamped annotated photo."""
    cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
    if not cam:
        from modules.registry.estate_data import SENTINEL_LIVE_CAMS
        cam = next((item for item in SENTINEL_LIVE_CAMS if item["id"] == camera_id), None)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, 404)

    number = camera_id.rsplit("-", 1)[-1] if camera_id.startswith("sentinel-cam-") else ""
    sentinel_stream = f"https://live.sentinelgujarat.in/stream/{number}" if number.isdigit() else ""
    active_path = live_stream_state.current_path if live_stream_state.current_camera_id == camera_id else None
    source = active_path or sentinel_stream or cam.get("live_url") or cam.get("source") or ""

    frame = None
    if live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
        frame = live_stream_state.get_frame()

    if frame is None and source:
        cap = cv2.VideoCapture(source)
        if cap.isOpened():
            ok, frame = cap.read()
            cap.release()

    if frame is None:
        return JSONResponse({"error": "Could not capture a frame from the selected camera source"}, 400)

    result = vision_service.process_frame_anpr(frame, camera_id, cam.get("name", camera_id))
    note = f"ANPR scan complete · {len(result['vehicles'])} vehicles · {len(result['plates_enhanced'])} plates read · Photo saved at {result['timestamp']}"
    if db_manager.query_one("SELECT id FROM cameras WHERE id=?", camera_id):
        db_manager.execute("UPDATE cameras SET last_note=? WHERE id=?", note, camera_id)

    return result
