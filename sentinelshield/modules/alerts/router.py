"""API Router for alerts, watchlist CRUD, and demonstration threat triggers."""
from __future__ import annotations

try:
    from fastapi import APIRouter, Form
except ImportError:
    class _MockAPIRouter:
        def __init__(self, *args, **kwargs): pass
        def post(self, *args, **kwargs): return lambda f: f
        def get(self, *args, **kwargs): return lambda f: f
        def delete(self, *args, **kwargs): return lambda f: f
    APIRouter = _MockAPIRouter  # type: ignore
    Form = lambda default=None, **kw: default  # type: ignore

from modules.alerts.service import alert_service

router = APIRouter(tags=["alerts"])


@router.post("/api/watchlist")
def add_watch(
    plate: str = Form(...),
    kind: str = Form("stolen"),
    note: str = Form(""),
    priority: str = Form("HIGH"),
):
    pid = alert_service.add_watchlist_entry(plate=plate, kind=kind, note=note, priority=priority)
    return {"ok": True, "id": pid}


@router.delete("/api/watchlist/{wid}")
def del_watch(wid: str):
    alert_service.delete_watchlist_entry(wid)
    return {"ok": True}


@router.post("/api/alerts/{aid}/status")
def alert_status(aid: str, status: str = Form(...)):
    alert_service.update_alert_status(aid, status)
    return {"ok": True}


@router.post("/api/demo/panic")
def demo_panic():
    alert_service.trigger_demo_panic()
    return {"ok": True}


@router.post("/api/demo/abandoned")
def demo_abandoned():
    alert_service.trigger_demo_abandoned()
    return {"ok": True}


@router.post("/api/webhooks")
def register_webhook(url: str = Form(...), secret: str = Form(""), events: str = Form("all")):
    from modules.alerts.webhooks import webhook_dispatch_service
    return webhook_dispatch_service.register_webhook(url=url, secret=secret or None, events=events)


@router.get("/api/webhooks")
def list_webhooks():
    from modules.alerts.webhooks import webhook_dispatch_service
    return {"webhooks": webhook_dispatch_service.list_webhooks()}


@router.delete("/api/webhooks/{wid}")
def delete_webhook(wid: str):
    from modules.alerts.webhooks import webhook_dispatch_service
    webhook_dispatch_service.delete_webhook(wid)
    return {"ok": True}
