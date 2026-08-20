"""Streaming Service orchestrating live feeds, video analysis jobs, and stream generators."""
from __future__ import annotations

import os
import threading
import uuid
from typing import Any, Generator

from core.database import db_manager, utcnow
from core.state import live_stream_state, tracking_state
from modules.streaming.mjpeg import mjpeg_frame_generator
from modules.streaming.worker import run_video_job


class StreamingService:
    """Service providing live camera streaming and video analysis jobs."""

    @staticmethod
    def start_live(camera_id: str, source_mode: str = "auto") -> tuple[dict[str, Any] | None, str | None]:
        cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
        if not cam:
            return None, "Camera not found"

        url = (cam.get("live_url") or "").strip()
        file_src = cam.get("source") or ""

        if source_mode == "loop" or not url:
            if file_src and os.path.isfile(file_src):
                mode = "loop"
                path = file_src
                note = "Live preview = recorded clip loop"
            elif url:
                mode = "url"
                path = url
                note = "Live camera link"
            else:
                return None, "No recorded clip and no live link. Connect a camera first."
        else:
            mode = "url"
            path = url
            note = "Live camera link"

        live_stream_state.start(camera_id=camera_id, source_mode=mode, path=path)
        tracking_state.init_camera(camera_id)
        db_manager.execute("UPDATE cameras SET status=?, last_note=? WHERE id=?", "live", note, camera_id)

        return {"on": True, "camera_id": camera_id, "mode": mode}, None

    @staticmethod
    def stop_live() -> None:
        prev_cam = live_stream_state.stop()
        if prev_cam:
            db_manager.execute("UPDATE cameras SET status=? WHERE id=?", "ready", prev_cam)

    @staticmethod
    def get_mjpeg_stream(camera_id: str, path: str) -> Generator[bytes, None, None]:
        return mjpeg_frame_generator(camera_id, path, os.path.isfile(path))

    @staticmethod
    def analyze_camera_video(camera_id: str) -> tuple[str | None, str | None]:
        cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
        if not cam or not cam.get("source") or not os.path.isfile(cam["source"]):
            return None, "No recorded video on this camera"

        job_id = "job-" + uuid.uuid4().hex[:8]
        db_manager.execute(
            "INSERT INTO jobs VALUES(?,?,?,?,?,?)",
            job_id, camera_id, cam["source"], "running", "{}", utcnow(),
        )
        db_manager.execute("UPDATE cameras SET status=? WHERE id=?", "checking", camera_id)

        thread = threading.Thread(target=run_video_job, args=(job_id, cam, cam["source"]), daemon=True)
        thread.start()
        return job_id, None


streaming_service = StreamingService()
