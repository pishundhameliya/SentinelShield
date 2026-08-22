"""API Router for live streaming, job analysis, AI control, and health overview."""
from __future__ import annotations

import json
import os
import shutil
import time
from typing import Any

try:
    from fastapi import APIRouter, File, Form, UploadFile
    from fastapi.responses import JSONResponse, StreamingResponse
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    JSONResponse = dict  # type: ignore
    StreamingResponse = object  # type: ignore
    File = lambda *a, **kw: None  # type: ignore
    Form = lambda *a, **kw: None  # type: ignore
    UploadFile = Any  # type: ignore

from config import settings
from core.database import db_manager, utcnow
from core.state import ai_state, live_stream_state
from modules.registry.estate_data import total_cameras
from modules.streaming.service import streaming_service

router = APIRouter(tags=["streaming"])


@router.get("/api/health")
def health():
    return {"ok": True, "ai": ai_state.get_status(), "clock": utcnow()}


@router.get("/api/overview")
def overview(city: str = "", area: str = ""):
    alerts = db_manager.query_rows("SELECT * FROM alerts ORDER BY created DESC LIMIT 40")
    watch = db_manager.query_rows("SELECT * FROM watchlist ORDER BY priority")
    jobs = db_manager.query_rows("SELECT id,camera_id,status,created FROM jobs ORDER BY created DESC LIMIT 20")
    chat = db_manager.query_rows("SELECT * FROM messages WHERE room='team' ORDER BY created DESC LIMIT 50")
    chat.reverse()
    cities = db_manager.query_rows("SELECT * FROM cities ORDER BY cameras DESC")
    estate = db_manager.query_one("SELECT SUM(cameras) AS n FROM cities") or {"n": 0}

    return {
        "alerts": alerts,
        "watchlist": watch,
        "jobs": jobs,
        "chat": chat,
        "live": live_stream_state.get_state(),
        "clock": utcnow(),
        "cities": cities,
        "estate_total": int(estate.get("n") or total_cameras()),
        "unread_chat": len(chat),
        "ai": ai_state.get_status(),
    }


@router.get("/api/events")
def api_events(q: str = ""):
    if q.strip():
        like = "%" + q.strip() + "%"
        return {"events": db_manager.query_rows(
            "SELECT * FROM events WHERE title LIKE ? OR extra LIKE ? OR kind LIKE ? ORDER BY created DESC LIMIT 50",
            like, like, like,
        )}
    return {"events": db_manager.query_rows("SELECT * FROM events ORDER BY created DESC LIMIT 50")}


@router.post("/api/live/start")
def live_start(camera_id: str = Form(...), source: str = Form("auto")):
    live_res, err = streaming_service.start_live(camera_id, source)
    if err:
        return JSONResponse({"error": err}, 400)
    return {"ok": True, "live": live_res}


@router.post("/api/live/stop")
def live_stop():
    streaming_service.stop_live()
    return {"ok": True}


@router.get("/api/live/stream")
def live_stream():
    st = live_stream_state.get_state()
    if not st["on"] or not st["camera_id"]:
        return JSONResponse({"error": "live is off"}, 400)

    path = st.get("path") or ""
    if not path:
        cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", st["camera_id"])
        if cam:
            path = cam.get("live_url") or cam.get("source") or ""
    if not path:
        return JSONResponse({"error": "no live source"}, 400)

    return StreamingResponse(
        streaming_service.get_mjpeg_stream(st["camera_id"], path),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/api/analyze/{camera_id}")
def analyze(camera_id: str):
    job_id, err = streaming_service.analyze_camera_video(camera_id)
    if err:
        return JSONResponse({"error": err}, 400)
    return {"ok": True, "job_id": job_id}


@router.post("/api/analyze-all")
def analyze_all():
    cams = db_manager.query_rows("SELECT * FROM cameras WHERE kind='recorded' AND source IS NOT NULL AND source != ''")
    ids = []
    for c in cams:
        if os.path.isfile(c["source"]):
            res = analyze(c["id"])
            if isinstance(res, dict):
                ids.append(res.get("job_id"))
    return {"ok": True, "started": ids}


@router.get("/api/job/{job_id}")
def get_job(job_id: str):
    j = db_manager.query_one("SELECT * FROM jobs WHERE id=?", job_id)
    if not j:
        return JSONResponse({"error": "no job"}, 404)
    if j.get("result"):
        try:
            j["result"] = json.loads(j["result"])
        except Exception:
            pass
    j["hashes"] = db_manager.query_rows("SELECT * FROM hashes WHERE job_id=? ORDER BY t_start", job_id)
    return j


@router.post("/api/ai/on")
def ai_on():
    ai_state.set_active(True)
    return {"ok": True, "ai": ai_state.get_status()}


@router.post("/api/ai/off")
def ai_off():
    ai_state.set_active(False)
    return {"ok": True, "ai": ai_state.get_status()}


@router.post("/api/upload")
async def upload(camera_id: str = Form(...), file: UploadFile = File(...)):
    cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
    if not cam:
        return JSONResponse({"error": "Camera not found"}, 404)
    ext = os.path.splitext(file.filename or "clip.mp4")[1] or ".mp4"
    dest = os.path.join(settings.uploads_dir, f"{camera_id}_{int(time.time())}{ext}")
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    db_manager.execute(
        "UPDATE cameras SET source=?, kind='recorded', status='ready', last_note=? WHERE id=?",
        dest, f"Uploaded {file.filename}", camera_id,
    )
    return {"ok": True, "path": dest}
