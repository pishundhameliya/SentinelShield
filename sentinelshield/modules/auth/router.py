"""API Router for user authentication and session verification."""
from __future__ import annotations

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse

from core.security import session_manager

router = APIRouter(tags=["auth"])


@router.post("/api/login")
def login(username: str = Form(...), password: str = Form(...)):
    token, user = session_manager.authenticate(username, password)
    if not token or not user:
        return JSONResponse({"ok": False, "error": "Wrong name or password"}, 401)
    return {"ok": True, "token": token, "user": user}


@router.get("/api/me")
def me(token: str = ""):
    u = session_manager.get_user(token)
    if not u:
        return JSONResponse({"ok": False}, 401)
    return {"ok": True, "user": u}
