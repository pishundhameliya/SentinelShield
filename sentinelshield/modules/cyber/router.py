"""API Router for cybersecurity honeypot traps and attack logs."""
from __future__ import annotations

from fastapi import APIRouter
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
