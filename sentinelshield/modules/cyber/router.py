"""API Router for cybersecurity honeypot traps and attack logs."""
from __future__ import annotations

try:
    from fastapi import APIRouter
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore

from modules.cyber.honeypot import cyber_service

router = APIRouter(tags=["cyber"])


@router.get("/honeypot")
@router.post("/honeypot")
@router.get("/onvif/device_service")
def honeypot_hit():
    return cyber_service.trigger_honeypot_incident()


@router.get("/api/honeypot")
def honeypot_log():
    return {"hits": cyber_service.get_honeypot_hits()}


@router.get("/api/cyber")
def api_cyber():
    return {"cyber": cyber_service.get_all_cyber_incidents()}
