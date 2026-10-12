"""Automatic ANPR: continuously reads number plates on the camera open in Live.

Every `settings.auto_anpr_interval_s` the daemon takes the latest decoded frame of the
active live stream (no extra camera connection), runs the full-frame plate detector,
and for every valid Indian plate:

  * links it to the live vehicle track whose box contains the plate (vehicle type),
  * records a vehicle detection, a sighting (Find vehicle / route history) and an event,
  * raises a watchlist alert for stolen / blacklisted / suspect plates.

The same plate on the same camera is recorded at most once per `auto_anpr_dedupe_s`.
"""
from __future__ import annotations

import base64
import logging
import threading
import time
import uuid
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

from sentinelshield.config import settings
from sentinelshield.core.database import db_manager, utcnow
from sentinelshield.core.state import auto_anpr_state, live_stream_state, tracking_state
from sentinelshield.modules.vision.alpr_ocr import normalize_plate
from sentinelshield.modules.vision.plate_recognizer import plate_recognizer

logger = logging.getLogger(__name__)


def camera_info(camera_id: str) -> dict[str, Any]:
    cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
    if cam:
        return cam
    from sentinelshield.modules.registry.estate_data import SENTINEL_LIVE_CAMS
    return next((c for c in SENTINEL_LIVE_CAMS if c["id"] == camera_id), None) or {"id": camera_id, "name": camera_id}


def _plate_thumbnail(frame, box: dict[str, int]) -> str:
    """Small JPEG of the plate region (with margin) as a data URI for the UI."""
    if cv2 is None:
        return ""
    h, w = frame.shape[:2]
    mx, my = int(box["w"] * 0.15), int(box["h"] * 0.3)
    x1, y1 = max(box["x"] - mx, 0), max(box["y"] - my, 0)
    x2, y2 = min(box["x"] + box["w"] + mx, w), min(box["y"] + box["h"] + my, h)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return ""
    scale = 64.0 / max(crop.shape[0], 1)
    crop = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    ok, buf = cv2.imencode(".jpg", crop, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode() if ok else ""


def _match_track(camera_id: str, box: dict[str, int]) -> tuple[str | None, dict[str, Any] | None]:
    """Find the live vehicle track whose box contains the plate centre."""
    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    state = tracking_state.get_camera_state(camera_id)
    best_id, best, best_area = None, None, None
    for track_id, track in list((state.get("tracks") or {}).items()):
        v = track.get("box") or {}
        if not v:
            continue
        if v["x"] <= cx <= v["x"] + v["w"] and v["y"] <= cy <= v["y"] + v["h"]:
            area = v["w"] * v["h"]
            if best_area is None or area < best_area:  # tightest box wins when vehicles overlap
                best_id, best, best_area = track_id, track, area
    return best_id, best


def record_plate_read(camera_id: str, cam: dict[str, Any], hit: dict[str, Any], frame) -> dict[str, Any] | None:
    """Persist one plate read (deduplicated). Returns the UI entry, or None if a duplicate."""
    plate = hit["plate"]
    if not auto_anpr_state.should_record(camera_id, plate, settings.auto_anpr_dedupe_s):
        return None

    ts = utcnow()
    track_id, track = _match_track(camera_id, hit["box"])
    vehicle_type = ((track or {}).get("box") or {}).get("cls") or "vehicle"
    if track is not None:
        track["plate"], track["confidence"], track["saved"] = plate, hit["confidence"], True

    with db_manager.transaction() as con:
        updated = 0
        if track_id:
            updated = con.execute(
                "UPDATE vehicle_detections SET plate=?, confidence=? WHERE camera_id=? AND tracking_id=?",
                (plate, hit["confidence"], camera_id, track_id),
            ).rowcount
        if not updated:
            con.execute(
                "INSERT INTO vehicle_detections VALUES(?,?,?,?,?,?,?,?,?,?)",
                ("vd-" + uuid.uuid4().hex[:10], camera_id, vehicle_type, track_id or "auto-anpr",
                 plate, hit["confidence"], ts, cam.get("lat"), cam.get("lng"), cam.get("place")),
            )
        con.execute(
            "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            ("see-" + uuid.uuid4().hex[:10], plate, camera_id, cam.get("name"), cam.get("place"),
             cam.get("city_id"), cam.get("area_id"), cam.get("lat"), cam.get("lng"), ts, "auto-anpr"),
        )
        con.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
            ("ev-" + uuid.uuid4().hex[:8], "vehicle", f"Plate {plate} at {cam.get('name') or camera_id}",
             camera_id, cam.get("place"), plate, ts),
        )

        watch = None
        for row in con.execute("SELECT * FROM watchlist"):
            if normalize_plate(row["plate"]) == plate:
                watch = dict(row)
                break
        if watch:
            recent = con.execute(
                "SELECT id FROM alerts WHERE camera_id=? AND title LIKE ? AND created > datetime('now','-3 minutes')",
                (camera_id, f"%{plate}%"),
            ).fetchone()
            if not recent:
                con.execute(
                    "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                    ("al-" + uuid.uuid4().hex[:10], camera_id, "watchlist", f"Watchlist hit {plate}",
                     f"{watch['kind'].upper()} — {watch.get('note') or ''} · seen on {cam.get('name') or camera_id} (auto ANPR)",
                     watch.get("priority") or "HIGH", 100, 0, ts, "new"),
                )

    entry = {
        "camera_id": camera_id,
        "camera_name": cam.get("name") or camera_id,
        "plate": plate,
        "formatted": hit.get("formatted") or plate,
        "confidence": hit["confidence"],
        "vehicle_type": vehicle_type,
        "track_id": track_id,
        "watchlist": {"kind": watch["kind"], "note": watch.get("note") or ""} if watch else None,
        "plate_image": _plate_thumbnail(frame, hit["box"]),
        "seen_at": ts,
    }
    auto_anpr_state.add_read(entry)
    return entry


def scan_frame(camera_id: str, frame) -> list[dict[str, Any]]:
    """Read every plate in one frame and record the new ones. Returns the recorded entries."""
    auto_anpr_state.record_scan(camera_id)
    hits = [h for h in plate_recognizer.detect(frame) if h["valid"]]
    if not hits:
        return []
    cam = camera_info(camera_id)
    recorded = []
    for hit in hits:
        try:
            entry = record_plate_read(camera_id, cam, hit, frame)
        except Exception as exc:  # DB busy etc. — never kill the loop
            logger.warning("auto ANPR record failed for %s: %s", hit.get("plate"), exc)
            continue
        if entry:
            recorded.append(entry)
    return recorded


class AutoAnprDaemon:
    """Background loop scanning the active live camera for number plates."""

    def __init__(self) -> None:
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        auto_anpr_state.set_enabled(settings.auto_anpr_enabled)
        if self._thread is None or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, name="auto-anpr", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        while self._running:
            started = time.time()
            try:
                if auto_anpr_state.is_enabled and live_stream_state.is_active:
                    camera_id = live_stream_state.current_camera_id
                    frame = live_stream_state.get_frame()
                    if camera_id and frame is not None:
                        scan_frame(camera_id, frame)
            except Exception as exc:
                logger.warning("auto ANPR cycle failed: %s", exc)
            time.sleep(max(0.2, settings.auto_anpr_interval_s - (time.time() - started)))


auto_anpr_daemon = AutoAnprDaemon()
