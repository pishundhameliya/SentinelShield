#!/usr/bin/env python3
"""SentinelShield — Modular CCTV, GIS, AI, Cybersecurity, and Forensics Command Desk."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config import settings
from core.database import db_maintenance_daemon, db_manager
from modules.alerts.webhooks import webhook_dispatch_service
from modules.alerts.router import router as alerts_router
from modules.auth.router import router as auth_router
from modules.chat.router import router as chat_router
from modules.cyber.router import router as cyber_router
from modules.evidence.router import router as evidence_router
from modules.registry.estate_data import CITIES, DEMO_CAMS, sample_points
from modules.registry.router import router as registry_router
from modules.relay.router import router as relay_router
from modules.streaming.ai_daemon import ai_guardian_daemon
from modules.streaming.router import router as streaming_router
from modules.tracking.router import router as tracking_router
from modules.twin.router import router as twin_router
from modules.vision.router import router as vision_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifecycle manager initializing DB schema and background daemons."""
    db_manager.init_schema(
        cities_data=CITIES,
        demo_cams_data=DEMO_CAMS,
        sample_points_fn=sample_points,
    )
    ai_guardian_daemon.start()
    db_maintenance_daemon.start()
    webhook_dispatch_service.start_worker()
    yield
    webhook_dispatch_service.stop_worker()
    db_maintenance_daemon.stop()
    ai_guardian_daemon.stop()


app = FastAPI(title="SentinelShield", lifespan=lifespan)


@app.middleware("http")
async def preview_headers(request: Request, call_next):
    """Add security and iframe embedding headers to all HTTP responses."""
    resp = await call_next(request)
    resp.headers["Content-Security-Policy"] = "frame-ancestors *"
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


# Mount media and static directories
app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
app.mount("/static", StaticFiles(directory=settings.static_dir), name="static")


@app.get("/")
def home():
    """Serve Gujarat Command Desk UI portal index page."""
    return FileResponse(os.path.join(settings.static_dir, "index.html"))


# Mount Domain API Routers
app.include_router(auth_router)
app.include_router(registry_router)
app.include_router(vision_router)
app.include_router(tracking_router)
app.include_router(alerts_router)
app.include_router(streaming_router)
app.include_router(evidence_router)
app.include_router(cyber_router)
app.include_router(twin_router)
app.include_router(chat_router)
app.include_router(relay_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
