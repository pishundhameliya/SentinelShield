"""Comprehensive verification suite for SentinelShield modular architecture."""
from __future__ import annotations

import os
import sys
import numpy as np
import pytest

# Ensure sentinelshield directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from starlette.testclient import TestClient
from app import app
from core.database import db_manager
from core.security import session_manager
from core.state import live_stream_state, ai_state, tracking_state
from modules.integrity.hash_chain import HashChainManager, sha256_bytes
from modules.integrity.tamper_detector import is_black_frame, frame_difference_score
from modules.integrity.service import integrity_service
from modules.vision.deblur import enhance_blurry_crop, blur_box
from modules.vision.vehicle_detector import detect_vehicles
from modules.vision.alpr_ocr import normalize_plate, extract_plates_from_text, detect_fast_alpr
from modules.vision.service import vision_service
from modules.tracking.tracker import CentroidVehicleTracker
from modules.alerts.fusion import translate_alert, LANG


client = TestClient(app)


def test_database_wal_mode():
    """Verify SQLite WAL mode and table initialization."""
    with db_manager.get_connection() as con:
        mode = con.execute("PRAGMA journal_mode;").fetchone()[0]
        assert mode.lower() == "wal", f"Expected WAL mode, got {mode}"
        
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()]
        assert "cameras" in tables
        assert "alerts" in tables
        assert "watchlist" in tables
        assert "events" in tables
        assert "evidence" in tables
        assert "cyber" in tables
        assert "vehicle_detections" in tables


def test_session_manager():
    """Verify RBAC and token generation."""
    token, user = session_manager.authenticate("admin", "admin123")
    assert token is not None
    assert user["role"] == "admin"
    assert session_manager.get_user(token) == user

    bad_token, bad_user = session_manager.authenticate("admin", "wrongpass")
    assert bad_token is None
    assert bad_user is None


def test_hash_chain_and_tamper():
    """Verify SHA-256 rolling hash chain and tamper detection."""
    chain = HashChainManager()
    h1 = chain.append_segment(b"segment1", 0.0, 3.0)
    assert h1["sha256"] != ""
    assert h1["prev"] == "GENESIS"

    h2 = chain.append_segment(b"segment2", 3.0, 6.0)
    assert h2["prev"] == h1["sha256"]
    assert chain.verify_chain() is True

    black_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    assert is_black_frame(black_frame) is True

    bright_frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    assert is_black_frame(bright_frame) is False
    assert frame_difference_score(bright_frame, bright_frame) < 1.0


def test_vision_and_deblur():
    """Verify vehicle detection, deblurring, and plate normalization."""
    assert normalize_plate("gj 05 ss 2026") == "GJ05SS2026"
    assert normalize_plate("IND-GJ-01-AB-1234") == "GJ01AB1234"
    assert "GJ05SS2026" in extract_plates_from_text("Gate_stolen_GJ05SS2026_video.mp4")

    dummy_crop = np.zeros((60, 140, 3), dtype=np.uint8)
    dummy_crop[20:40, 30:110] = 200
    enhanced = enhance_blurry_crop(dummy_crop)
    assert enhanced["enhanced_bgr"].shape[0] == 120
    assert enhanced["enhanced_bgr"].shape[1] == 280
    assert enhanced["b64"].startswith("data:image/jpeg;base64,")
    assert enhanced["laplacian_score"] >= 0.0


def test_centroid_tracking():
    """Verify centroid vehicle tracker multi-frame persistence."""
    state = {"tracks": {}, "next_id": 1, "count": 0}
    vehicles_f1 = [{"x": 100, "y": 100, "w": 50, "h": 50, "cls": "car"}]
    active_f1, results_f1 = CentroidVehicleTracker.associate_tracks("cam-1", vehicles_f1, state)
    assert len(results_f1) == 1
    assert results_f1[0][2] is True  # is_new
    track_id = results_f1[0][0]

    # Frame 2: slightly moved
    vehicles_f2 = [{"x": 105, "y": 105, "w": 50, "h": 50, "cls": "car"}]
    active_f2, results_f2 = CentroidVehicleTracker.associate_tracks("cam-1", vehicles_f2, state)
    assert len(results_f2) == 1
    assert results_f2[0][0] == track_id
    assert results_f2[0][2] is False  # matched existing track


def test_api_endpoints_health_and_overview():
    """Test public health and overview APIs."""
    r_health = client.get("/api/health")
    assert r_health.status_code == 200
    assert r_health.json()["ok"] is True

    r_overview = client.get("/api/overview")
    assert r_overview.status_code == 200
    data = r_overview.json()
    assert "alerts" in data
    assert "watchlist" in data
    assert "estate_total" in data
    assert data["estate_total"] >= 200000


def test_api_registry():
    """Test cities, areas, and camera listings."""
    r_cities = client.get("/api/cities")
    assert r_cities.status_code == 200
    cities = r_cities.json()["cities"]
    assert len(cities) >= 10

    r_areas = client.get("/api/areas?city=surat")
    assert r_areas.status_code == 200
    assert len(r_areas.json()["areas"]) >= 5

    r_cams = client.get("/api/cameras?city=surat&area=ringroad")
    assert r_cams.status_code == 200
    assert "cameras" in r_cams.json()

    r_live = client.get("/api/live-cameras")
    assert r_live.status_code == 200
    assert len(r_live.json()["cameras"]) == 31


def test_api_watchlist_and_vehicle():
    """Test watchlist CRUD and vehicle sightings."""
    r_add = client.post("/api/watchlist", data={"plate": "GJ04TT9999", "kind": "suspect", "note": "Test suspect"})
    assert r_add.status_code == 200
    wid = r_add.json()["id"]

    r_find = client.get("/api/vehicle?plate=GJ04TT9999")
    assert r_find.status_code == 200
    assert r_find.json()["watchlist"]["id"] == wid

    r_del = client.delete(f"/api/watchlist/{wid}")
    assert r_del.status_code == 200
    assert r_del.json()["ok"] is True


def test_api_twin_and_cyber():
    """Test digital twin heatmap, drone launch, and cyber honeypot trap."""
    r_twin = client.get("/api/twin")
    assert r_twin.status_code == 200
    assert "heat" in r_twin.json()

    r_drone = client.post("/api/drones/launch", data={"city": "surat", "reason": "CCTV alert"})
    assert r_drone.status_code == 200
    assert r_drone.json()["ok"] is True

    r_hp = client.get("/honeypot")
    assert r_hp.status_code == 200
    assert r_hp.json()["ok"] is False

    r_cyber = client.get("/api/cyber")
    assert r_cyber.status_code == 200
    assert len(r_cyber.json()["cyber"]) >= 1


def test_api_evidence_and_chat():
    """Test evidence vault and chat endpoint."""
    r_seal = client.post("/api/evidence/cam-ring")
    assert r_seal.status_code == 200
    assert r_seal.json()["ok"] is True
    assert "sha256" in r_seal.json()

    r_rank = client.get("/api/rank-evidence")
    assert r_rank.status_code == 200
    assert "ranked" in r_rank.json()

    r_chat_post = client.post("/api/chat", data={"text": "Hello Command Center", "room": "team"})
    assert r_chat_post.status_code == 200
    assert r_chat_post.json()["ok"] is True

    r_chat_list = client.get("/api/chat?room=team")
    assert r_chat_list.status_code == 200
    assert any(m["text"] == "Hello Command Center" for m in r_chat_list.json()["messages"])


def test_api_assistant_and_events():
    """Test NLP operator assistant and event keyword search."""
    r_ask = client.post("/api/ask", data={"q": "show blacklisted vehicles"})
    assert r_ask.status_code == 200
    assert r_ask.json()["intent"] == "watchlist"

    r_events = client.get("/api/events?q=stolen")
    assert r_events.status_code == 200
    assert "events" in r_events.json()
