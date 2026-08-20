"""API Router for alerts, watchlist CRUD, and demonstration threat triggers."""
from __future__ import annotations

from fastapi import APIRouter, Form
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
