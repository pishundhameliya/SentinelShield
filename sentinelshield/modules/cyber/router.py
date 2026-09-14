"""API routes for cybersecurity monitoring and the isolated CCTV decoy."""
from __future__ import annotations

try:
    from fastapi import APIRouter, HTTPException, Request
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    class HTTPException(Exception):  # type: ignore
        def __init__(self, status_code: int = 400, detail: str = ""):
            self.status_code = status_code
            self.detail = detail
    class Request:  # type: ignore
        client = None

from sentinelshield.modules.cyber.honeypot import cyber_service

router = APIRouter(tags=["cyber"])


@router.get("/honeypot")
@router.post("/honeypot")
@router.get("/onvif/device_service")
def honeypot_hit(request: Request):
    client_host = None
    if request.client and hasattr(request.client, "host"):
        client_host = request.client.host
    action_str = "request"
    if hasattr(request, "method") and hasattr(request, "url") and hasattr(request.url, "path"):
        action_str = f"{request.method} {request.url.path}"
    return cyber_service.trigger_honeypot_incident(
        source_ip=client_host,
        action=action_str,
        request=request
    )


@router.get("/api/honeypot")
def honeypot_log():
    return {"hits": cyber_service.get_honeypot_hits()}


@router.get("/api/cyber")
def api_cyber():
    return {"cyber": cyber_service.get_all_cyber_incidents()}


@router.get("/api/cyber/events")
def cyber_events(limit: int = 30):
    return {"events": cyber_service.get_cyber_events(max(1, min(limit, 200)))}


@router.post("/api/cyber/events")
def ingest_cyber_event(event_type: str, description: str, camera_id: str = "unknown-camera",
                       source_ip: str = "unknown", score: int | None = None):
    return cyber_service.record_event(event_type, description, camera_id, source_ip, score=score)


@router.get("/api/cyber/activity")
def cyber_activity(limit: int = 30):
    return {"activity": cyber_service.get_activity(max(1, min(limit, 200)))}


@router.get("/api/cyber/health")
def cyber_health():
    return {"cameras": cyber_service.get_camera_health()}


@router.post("/api/cyber/health")
def update_cyber_health(camera_id: str, state: str, source_ip: str = "unknown"):
    if state not in ("connected", "disconnected", "reconnected"):
        raise HTTPException(status_code=400, detail="state must be connected, disconnected, or reconnected")
    return cyber_service.update_camera_health(camera_id, state, source_ip)


@router.post("/api/cyber/simulate")
def simulate_cyber_event(event_type: str, source_ip: str = "198.51.100.42",
                         camera_id: str = "cam-ring"):
    try:
        return cyber_service.simulate(event_type, source_ip, camera_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/cyber/auth-attempt")
def record_auth_attempt(source_ip: str, camera_id: str, success: bool, username: str | None = None):
    return cyber_service.track_auth_attempt(source_ip, camera_id, success, username)


@router.post("/api/cyber/track-request")
def track_request(source_ip: str, camera_id: str, endpoint: str):
    return cyber_service.track_request(source_ip, camera_id, endpoint)


@router.post("/api/cyber/track-connection")
def track_connection(source_ip: str, camera_id: str, port: int | None = None):
    return cyber_service.track_connection(source_ip, camera_id, port)
