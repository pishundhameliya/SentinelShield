"""MJPEG Streaming loop with real-time AI vehicle analytics and plate privacy blurring."""
from __future__ import annotations

import time
import uuid
from typing import Generator

import cv2
import numpy as np

from core.database import db_manager, utcnow
from core.state import live_stream_state, tracking_state
from modules.tracking.tracker import CentroidVehicleTracker
from modules.vision.alpr_ocr import (
    extract_plate_candidate,
    normalize_plate,
    read_plate_text,
)
from modules.vision.deblur import blur_box
from modules.vision.vehicle_detector import detect_vehicles


def live_analytics_frame(camera_id: str, frame: np.ndarray) -> np.ndarray:
    """Run real-time vehicle detection, tracking, ALPR, and privacy blurring on a live frame."""
    if frame is None or frame.size == 0:
        return frame

    state = tracking_state.get_camera_state(camera_id)
    vehicles = detect_vehicles(frame, state.get("prev_gray"))
    state["prev_gray"] = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    active_tracks, track_results = CentroidVehicleTracker.associate_tracks(camera_id, vehicles, state)
    watch = {normalize_plate(r["plate"]): dict(r) for r in db_manager.query_rows("SELECT * FROM watchlist")}
    cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id) or {}

    for track_id, vehicle, is_new in track_results:
        track = active_tracks[track_id]
        v_crop = frame[vehicle["y"]:vehicle["y"] + vehicle["h"], vehicle["x"]:vehicle["x"] + vehicle["w"]]
        candidate = extract_plate_candidate(v_crop) if v_crop.size > 0 else None
        plate_box = None
        plate = track.get("plate")
        confidence = track.get("confidence", 0.0)

        if candidate:
            plate_box = dict(candidate["box"])
            plate_box["x"] += vehicle["x"]
            plate_box["y"] += vehicle["y"]
            plate_read, conf_read = read_plate_text(candidate["enhanced_bgr"])
            if plate_read:
                plate = normalize_plate(plate_read)
                track["plate"] = plate
                track["confidence"] = conf_read

        if is_new:
            record_plate = plate or "Plate Not Clear"
            db_manager.execute(
                "INSERT INTO vehicle_detections VALUES(?,?,?,?,?,?,?,?,?,?)",
                "vd-" + uuid.uuid4().hex[:10], camera_id, vehicle.get("cls", "vehicle"),
                track_id, record_plate, confidence, utcnow(), cam.get("lat"), cam.get("lng"), cam.get("place"),
            )
            if plate:
                track["saved"] = True
                db_manager.execute(
                    "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    "see-" + uuid.uuid4().hex[:10], plate, camera_id, cam.get("name"), cam.get("place"),
                    cam.get("city_id"), cam.get("area_id"), cam.get("lat"), cam.get("lng"), utcnow(), "live-ai",
                )
                if plate in watch:
                    item = watch[plate]
                    db_manager.execute(
                        "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                        "al-" + uuid.uuid4().hex[:10], camera_id, "watchlist", f"Watchlist hit {plate}",
                        f"{item['kind'].upper()} — {item['note']}", item.get("priority") or "HIGH", 100, 0, utcnow(), "new",
                    )
        else:
            if plate and not track.get("saved"):
                track["saved"] = True
                db_manager.execute(
                    "UPDATE vehicle_detections SET plate=?, confidence=? WHERE tracking_id=?",
                    plate, confidence, track_id,
                )
                db_manager.execute(
                    "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    "see-" + uuid.uuid4().hex[:10], plate, camera_id, cam.get("name"), cam.get("place"),
                    cam.get("city_id"), cam.get("area_id"), cam.get("lat"), cam.get("lng"), utcnow(), "live-ai",
                )
                if plate in watch:
                    item = watch[plate]
                    db_manager.execute(
                        "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                        "al-" + uuid.uuid4().hex[:10], camera_id, "watchlist", f"Watchlist hit {plate}",
                        f"{item['kind'].upper()} — {item['note']}", item.get("priority") or "HIGH", 100, 0, utcnow(), "new",
                    )

        if plate_box:
            blur_box(frame, plate_box)

        cv2.rectangle(
            frame,
            (vehicle["x"], vehicle["y"]),
            (vehicle["x"] + vehicle["w"], vehicle["y"] + vehicle["h"]),
            (0, 255, 0),
            2,
        )
        cv2.putText(
            frame,
            f"{track_id} {vehicle.get('cls', 'vehicle')}",
            (vehicle["x"], max(20, vehicle["y"] - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )

    cv2.putText(
        frame,
        f"Vehicles passed: {state['count']}",
        (15, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (56, 189, 248),
        2,
    )
    return frame


def mjpeg_frame_generator(camera_id: str, path: str, loop_file: bool) -> Generator[bytes, None, None]:
    """Generate multipart MJPEG stream from file or network RTSP/HTTP feed."""
    while live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            err = np.zeros((240, 640, 3), np.uint8)
            cv2.putText(err, "Cannot open camera link", (30, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (80, 80, 240), 2)
            cv2.putText(err, "Check RTSP/HTTP and same Wi-Fi", (30, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
            ok, jpg = cv2.imencode(".jpg", err)
            if ok:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
            break

        fail = 0
        frame_count = 0
        while live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
            ok, frame = cap.read()
            if not ok:
                if loop_file:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    continue
                fail += 1
                if fail > 40:
                    break
                time.sleep(0.15)
                continue

            fail = 0
            live_stream_state.set_frame(frame)
            frame_count += 1
            if frame_count % 10 == 1 or loop_file:
                frame = live_analytics_frame(camera_id, frame)

            if frame_count % 3 == 0 or loop_file:
                ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 75])
                if not ok:
                    continue
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n")
                if loop_file:
                    time.sleep(1 / 12)

        cap.release()
        break
