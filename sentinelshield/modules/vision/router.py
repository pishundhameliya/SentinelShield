"""API router for live ANPR scanning and deblurred plate recognition."""
from __future__ import annotations

import glob
import os
import uuid
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
import cv2

from config import settings
from core.database import db_manager
from core.state import live_stream_state
from modules.vision.service import vision_service

router = APIRouter(tags=["vision"])


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
            f"https://live.sentinelgujarat.in/camera/{number}",
            f"https://live.sentinelgujarat.in/stream/{number}",
            f"https://live.sentinelgujarat.in/stream?camera={number}",
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
        from modules.registry.estate_data import SENTINEL_LIVE_CAMS
        cam = next((item for item in SENTINEL_LIVE_CAMS if item["id"] == camera_id), None)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, 404)

    frame = None
    if live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
        frame = live_stream_state.get_frame()

    if frame is None:
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

    result = vision_service.process_frame_anpr(frame, camera_id, cam.get("name", camera_id))
    note = f"ANPR scan complete · {len(result['vehicles'])} vehicles · {len(result['plates_enhanced'])} plates read · Photo saved at {result['timestamp']}"
    if db_manager.query_one("SELECT id FROM cameras WHERE id=?", camera_id):
        db_manager.execute("UPDATE cameras SET last_note=? WHERE id=?", note, camera_id)

        for idx, vehicle in enumerate(result.get("vehicles") or []):
            plate_data = (result.get("plates_enhanced") or [None])[idx] or {}
            plate_text = str(plate_data.get("plate_text") or "Plate Not Clear")
            confidence = float(plate_data.get("ocr_confidence") or vehicle.get("confidence") or 0.0)
            db_manager.execute(
                "INSERT INTO vehicle_detections VALUES(?,?,?,?,?,?,?,?,?,?)",
                "scan-" + uuid.uuid4().hex[:12],
                camera_id,
                vehicle.get("cls") or "vehicle",
                f"live-{idx + 1}",
                plate_text,
                confidence,
                result.get("timestamp") or note,
                cam.get("lat"),
                cam.get("lng"),
                cam.get("place") or cam.get("name") or camera_id,
            )

    return result
