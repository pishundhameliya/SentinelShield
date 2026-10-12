"""Tests for automatic ANPR (modules/vision/auto_anpr.py): read, record, dedupe, watchlist alert."""
from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import cv2

from sentinelshield.config import settings
from sentinelshield.core.database import db_manager
from sentinelshield.core.state import auto_anpr_state, tracking_state
from sentinelshield.modules.vision.auto_anpr import scan_frame
from sentinelshield.modules.vision.plate_recognizer import plate_recognizer

CAM = "test-auto-anpr-cam"


def _frame_with_plate(clip: str, plate: str):
    cap = cv2.VideoCapture(os.path.join(settings.demos_dir, clip))
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    for k in range(0, n, max(n // 60, 1)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, frame = cap.read()
        if ok and any(h["plate"] == plate for h in plate_recognizer.detect(frame)):
            cap.release()
            return frame
    cap.release()
    return None


def _cleanup():
    for table in ("vehicle_detections", "sightings", "events", "alerts"):
        db_manager.execute(f"DELETE FROM {table} WHERE camera_id=?", CAM)


def test_auto_scan_records_and_dedupes():
    db_manager.init_schema()
    if not plate_recognizer.available:
        print(f"[SKIP] ANPR engine unavailable: {plate_recognizer.status()['error']}")
        return
    _cleanup()
    try:
        frame = _frame_with_plate("ring_road_normal.mp4", "GJ05AB4321")
        assert frame is not None, "demo clip should contain a readable GJ05AB4321"

        # A live vehicle track around the plate -> the read is linked to that vehicle
        hit = next(h for h in plate_recognizer.detect(frame) if h["plate"] == "GJ05AB4321")
        b = hit["box"]
        state = tracking_state.get_camera_state(CAM)
        state["tracks"] = {f"{CAM}-v1": {"box": {"x": b["x"] - 40, "y": b["y"] - 80, "w": b["w"] + 80,
                                                 "h": b["h"] + 120, "cls": "car"}, "plate": None}}
        db_manager.execute(
            "INSERT INTO vehicle_detections VALUES(?,?,?,?,?,?,?,?,?,?)",
            "vd-test-auto-1", CAM, "car", f"{CAM}-v1", "Plate Not Clear", 0.0, "2026-01-01 00:00:00", None, None, None,
        )

        first = scan_frame(CAM, frame)
        assert [e["plate"] for e in first] == ["GJ05AB4321"], first
        assert first[0]["vehicle_type"] == "car" and first[0]["plate_image"].startswith("data:image/jpeg")
        row = db_manager.query_one("SELECT plate FROM vehicle_detections WHERE id=?", "vd-test-auto-1")
        assert row["plate"] == "GJ05AB4321", "the tracked vehicle's row should get the plate"
        assert db_manager.query_one("SELECT id FROM sightings WHERE camera_id=? AND plate=?", CAM, "GJ05AB4321")
        assert state["tracks"][f"{CAM}-v1"]["plate"] == "GJ05AB4321"

        # Same plate seconds later is not recorded again
        assert scan_frame(CAM, frame) == []
        n = db_manager.query_one("SELECT COUNT(*) AS n FROM sightings WHERE camera_id=?", CAM)["n"]
        assert n == 1, f"duplicate sighting recorded ({n})"
        assert any(r["plate"] == "GJ05AB4321" for r in auto_anpr_state.snapshot(camera_id=CAM)["recent"])
        print("[PASS] Auto ANPR reads, links to vehicle track, records sighting, and dedupes!")

        # Stolen vehicle on the watchlist -> alert
        stolen = _frame_with_plate("gate_stolen_vehicle.mp4", "GJ05SS2026")
        assert stolen is not None, "demo clip should contain a readable GJ05SS2026"
        entries = scan_frame(CAM, stolen)
        assert any(e["plate"] == "GJ05SS2026" and e["watchlist"] for e in entries), entries
        alert = db_manager.query_one(
            "SELECT kind, title FROM alerts WHERE camera_id=? AND title LIKE ?", CAM, "%GJ05SS2026%")
        assert alert and alert["kind"] == "watchlist"
        print("[PASS] Auto ANPR raises a watchlist alert for a stolen vehicle!")
    finally:
        _cleanup()
        db_manager.execute("DELETE FROM vehicle_detections WHERE id=?", "vd-test-auto-1")


if __name__ == "__main__":
    test_auto_scan_records_and_dedupes()
    print("\n[ALL PASS] Automatic ANPR verified!")
