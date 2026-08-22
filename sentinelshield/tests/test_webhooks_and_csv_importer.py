"""Unit tests for Operator Dispatch Webhooks and Camera Estate CSV Bulk Importer."""
from __future__ import annotations

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import db_manager
from modules.alerts.webhooks import webhook_dispatch_service
from modules.registry.importer import import_cameras_from_csv


def test_webhook_lifecycle_and_queue():
    db_manager.init_schema()

    # Register webhook
    res = webhook_dispatch_service.register_webhook("https://dispatch.police.gujarat.gov.in/alerts", secret="secret_key_123")
    assert res["ok"] is True
    wid = res["id"]

    # List webhooks
    all_whks = webhook_dispatch_service.list_webhooks()
    assert any(w["id"] == wid for w in all_whks)

    # Dispatch alert
    alert = {
        "id": "alt-test-01",
        "kind": "watchlist",
        "severity": "CRITICAL",
        "camera_name": "Surat Ring Road North",
        "plate": "GJ05SS2026",
    }
    webhook_dispatch_service.dispatch_alert(alert)

    with webhook_dispatch_service._lock:
        assert len(webhook_dispatch_service._queue) >= 1
        assert webhook_dispatch_service._queue[-1]["alert"]["id"] == "alt-test-01"

    # Delete webhook
    webhook_dispatch_service.delete_webhook(wid)
    remaining = webhook_dispatch_service.list_webhooks()
    assert not any(w["id"] == wid for w in remaining)
    print("[PASS] Operator dispatch webhook registration and queueing verified!")


def test_camera_estate_csv_importer():
    db_manager.init_schema()

    csv_data = """Camera ID,Camera Name,City,Area,Latitude,Longitude,Live URL,Owner
cam-csv-01,Surat Diamond Bourse North,Surat,Khajod,21.1450,72.7830,rtsp://10.0.1.50:554/live,Surat Police
cam-csv-02,Ahmedabad Sabarmati Riverfront,Ahmedabad,Riverfront East,23.0300,72.5800,rtsp://10.0.1.51:554/live,Smart City AMC
cam-csv-03,Vadodara Alkapuri Junction,Vadodara,Alkapuri,22.3100,73.1800,,Gujarat Police
"""

    res = import_cameras_from_csv(csv_data, duplicate_mode="update")
    assert res["imported"] == 3, f"Expected 3 imported cameras, got {res}"
    assert res["total"] == 3

    # Check database query
    cam1 = db_manager.query_one("SELECT * FROM cameras WHERE id=?", "cam-csv-01")
    assert cam1 is not None
    assert cam1["name"] == "Surat Diamond Bourse North"
    assert cam1["city_id"] == "surat"
    assert abs(cam1["lat"] - 21.1450) < 0.001

    # Coordinate bounding box validation test (out of bounds should fall back to city default)
    csv_out_of_bounds = """id,name,city,area,lat,lng
cam-oob-01,Fake London Cam,Surat,Unknown,51.5074,-0.1278
"""
    res_oob = import_cameras_from_csv(csv_out_of_bounds, duplicate_mode="update")
    assert res_oob["imported"] == 1
    cam_oob = db_manager.query_one("SELECT * FROM cameras WHERE id=?", "cam-oob-01")
    assert cam_oob is not None
    # Must be corrected to Gujarat coordinates
    assert 20.0 <= cam_oob["lat"] <= 24.8
    assert 68.0 <= cam_oob["lng"] <= 74.5
    print("[PASS] Camera Estate CSV bulk importer with Gujarat bounds validation verified!")


if __name__ == "__main__":
    test_webhook_lifecycle_and_queue()
    test_camera_estate_csv_importer()
    print("\n[ALL PASS] Milestone 4 (Webhooks & CSV Importer) 100% Verified!")
