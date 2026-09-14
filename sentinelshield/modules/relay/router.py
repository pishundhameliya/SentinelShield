"""API Router for mobile phone temporary webcam relay test."""
from __future__ import annotations

import os
from typing import Any

try:
    from fastapi import APIRouter, Request
    from fastapi.responses import FileResponse, JSONResponse, Response
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    JSONResponse = dict  # type: ignore
    FileResponse = object  # type: ignore
    Response = object  # type: ignore
    Request = Any  # type: ignore

from sentinelshield.config import settings
from sentinelshield.core.state import relay_state

router = APIRouter(tags=["relay"])


@router.post("/api/temp/webcam-relay")
async def temp_webcam_in(request: Request):
    data = await request.body()
    if len(data) < 40 or len(data) > 2_000_000:
        return JSONResponse({"ok": False}, 400)
    relay_state.set_frame(data)
    return {"ok": True}


@router.get("/api/temp/webcam-relay.jpg")
def temp_webcam_out():
    # Tiny gray JPEG fallback so the <img> never looks "broken" while waiting
    wait = (
        b"\xff\xd8\xff\xdb\x00C\x00" + bytes([8] * 64) +
        b"\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00"
        b"\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x08"
        b"\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\x7f\xff\xd9"
    )
    frame_bytes, _ = relay_state.get_frame()
    body = frame_bytes or wait
    return Response(content=body, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@router.get("/phone-send")
def temp_phone_send_page():
    return FileResponse(os.path.join(settings.static_dir, "phone_send.html"))
