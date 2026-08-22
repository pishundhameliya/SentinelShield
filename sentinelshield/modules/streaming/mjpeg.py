"""MJPEG Streaming loop with real-time AI vehicle analytics, hardware acceleration, and dynamic frame-dropping backpressure."""
from __future__ import annotations

import time
import uuid
from typing import Generator

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

from core.database import db_manager, utcnow
from core.state import live_stream_state, tracking_state
from modules.streaming.hw_accel import create_hw_videocapture, safe_release_capture
from modules.streaming.stream_pool import StreamWorkerPool
from modules.tracking.tracker import CentroidVehicleTracker
from modules.vision.alpr_ocr import (
    extract_plate_candidate,
    normalize_plate,
    read_plate_text,
)
from modules.vision.deblur import blur_box
from modules.vision.vehicle_detector import detect_vehicles

_stream_pool = StreamWorkerPool()


def live_analytics_frame(camera_id: str, frame: np.ndarray) -> np.ndarray:
    """Run real-time vehicle detection, tracking, ALPR, and privacy blurring on a live frame."""
    if frame is None or frame.size == 0 or cv2 is None:
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


def create_reconnect_placeholder_frame(
    camera_id: str = "cam",
    path: str = "",
    attempt: int = 1,
    backoff: float = 1.0,
    status_text: str = "FEED OFFLINE - AUTO-RECONNECTING...",
    width: int = 640,
    height: int = 360,
    reason: str = "",
    next_retry_s: float | None = None,
) -> bytes:
    """Create a high-visibility diagnostic HUD placeholder JPEG frame during stream drops."""
    if cv2 is None or np is None:
        return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n\r\n"

    if reason and (status_text == "FEED OFFLINE - AUTO-RECONNECTING..." or not status_text):
        status_text = reason

    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    canvas[:] = (15, 23, 42)  # Slate-900 dark background

    # Subtle inner diagnostic border
    cv2.rectangle(canvas, (10, 10), (width - 10, height - 10), (30, 41, 59), 2)
    cv2.rectangle(canvas, (12, 12), (width - 12, height - 12), (51, 65, 85), 1)

    # Status Banner
    cv2.rectangle(canvas, (20, 20), (width - 20, 60), (30, 35, 60), -1)
    cv2.rectangle(canvas, (20, 20), (width - 20, 60), (0, 140, 255), 2)  # Amber warning border

    cv2.putText(
        canvas,
        f"WARNING: {status_text}",
        (30, 47),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        (0, 200, 255),
        2,
        cv2.LINE_AA,
    )

    # Camera Estate Info
    cam_info = db_manager.query_one("SELECT name, place FROM cameras WHERE id=?", camera_id) or {}
    cam_name = cam_info.get("name", camera_id)
    cam_place = cam_info.get("place", "Gujarat Network")

    cv2.putText(
        canvas,
        f"Camera    : {cam_name} ({camera_id})",
        (30, 100),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (255, 255, 255),
        1,
        cv2.LINE_AA,
    )
    cv2.putText(
        canvas,
        f"Location  : {cam_place}",
        (30, 130),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (200, 200, 200),
        1,
        cv2.LINE_AA,
    )

    if path:
        trunc_path = path if len(path) <= 45 else (path[:20] + "..." + path[-22:])
        cv2.putText(
            canvas,
            f"Source    : {trunc_path}",
            (30, 160),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.44,
            (160, 160, 160),
            1,
            cv2.LINE_AA,
        )

    cv2.putText(
        canvas,
        f"Attempt #{attempt} | Next Retry: {backoff:.1f}s (Max: 16.0s)",
        (30, 200),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        (0, 215, 255),
        1,
        cv2.LINE_AA,
    )

    # Live UTC Timestamp
    ts = utcnow()
    cv2.putText(
        canvas,
        f"Timestamp : {ts}",
        (30, 240),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.44,
        (140, 140, 140),
        1,
        cv2.LINE_AA,
    )

    # Heartbeat Pulse indicator (blinking animation)
    pulse = "." * (int(time.time() * 2) % 4 + 1)
    cv2.putText(
        canvas,
        f"Autonomous Self-Healing Active {pulse}",
        (30, 300),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.52,
        (50, 205, 50),
        1,
        cv2.LINE_AA,
    )

    ok, jpg = cv2.imencode(".jpg", canvas, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not ok:
        return b""
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"


def mjpeg_frame_generator(
    camera_id: str,
    path: str,
    loop_file: bool = False,
    max_backoff: float = 16.0,
    initial_backoff: float = 1.0,
    preferred_accel: str = "auto",
    adaptive_backpressure: bool = True,
    max_fps: int = 25,
) -> Generator[bytes, None, None]:
    """Generate multipart MJPEG stream with hardware acceleration, adaptive backpressure, and self-healing auto-reconnect."""
    reconnect_attempt = 0
    ema_latency_ms = 0.0

    while live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
        cap = None
        try:
            cap, _backend = create_hw_videocapture(path, preferred_accel=preferred_accel)
        except Exception:
            try:
                cap = cv2.VideoCapture(path) if cv2 is not None else None
            except Exception:
                cap = None

        if cap is None or not cap.isOpened():
            safe_release_capture(cap)
            cap = None

            if loop_file:
                # If local file is missing/unreadable, yield single diagnostic error and exit
                err_frame = create_reconnect_placeholder_frame(
                    camera_id=camera_id,
                    path=path,
                    attempt=1,
                    backoff=0.0,
                    status_text="ERROR: LOCAL CLIP NOT ACCESSIBLE",
                )
                if err_frame:
                    yield err_frame
                break

            # Network stream failed to open: enter exponential backoff
            reconnect_attempt += 1
            backoff = min(max_backoff, initial_backoff * (2 ** min(reconnect_attempt - 1, 4)))

            # Heartbeat sleep loop emitting diagnostic frames every ~0.5s
            deadline = time.time() + backoff
            while time.time() < deadline:
                if not (live_stream_state.is_active and live_stream_state.current_camera_id == camera_id):
                    return
                placeholder = create_reconnect_placeholder_frame(
                    camera_id=camera_id,
                    path=path,
                    attempt=reconnect_attempt,
                    backoff=max(0.0, deadline - time.time()),
                    status_text="FEED DISCONNECTED - AUTO-RECONNECTING...",
                )
                if placeholder:
                    yield placeholder
                time.sleep(0.5)
            continue

        # Stream successfully opened
        fail_count = 0
        frame_count = 0

        try:
            while live_stream_state.is_active and live_stream_state.current_camera_id == camera_id:
                ok, frame = cap.read()
                if not ok or frame is None or getattr(frame, "size", 1) == 0:
                    if loop_file:
                        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                        ok2, frame2 = cap.read()
                        if ok2 and frame2 is not None and getattr(frame2, "size", 1) > 0:
                            frame = frame2
                            ok = True
                        else:
                            fail_count += 1
                            if fail_count > 30:
                                break
                            time.sleep(0.1)
                            continue
                    else:
                        fail_count += 1
                        if fail_count > 30:  # ~3.0s of stalled read attempts
                            break
                        time.sleep(0.1)
                        continue

                # Successful frame read: reset fail counters & reconnect attempt
                fail_count = 0
                reconnect_attempt = 0

                live_stream_state.set_frame(frame)
                frame_count += 1

                # Calculate Dynamic Backpressure policy
                if adaptive_backpressure and not loop_file:
                    policy = _stream_pool.compute_backpressure_policy(
                        active_streams=1,
                        client_latency_ms=ema_latency_ms,
                    )
                    drop_ratio = policy["drop_ratio"]
                    jpeg_quality = policy["jpeg_quality"]
                else:
                    drop_ratio = 1
                    jpeg_quality = 75

                # Dynamic Frame-Dropping: skip intermediate heavy processing and transmission under load
                if drop_ratio > 1 and (frame_count % drop_ratio) != 0:
                    continue

                if frame_count % 10 == 1 or loop_file:
                    frame = live_analytics_frame(camera_id, frame)

                ok, jpg = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), jpeg_quality])
                if not ok:
                    continue

                chunk = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpg.tobytes() + b"\r\n"

                t_yield_start = time.time()
                yield chunk
                t_yield_end = time.time()

                if loop_file:
                    time.sleep(1 / 12)
                elif adaptive_backpressure:
                    # Measure consumer round-trip delivery latency and update smoothing EMA
                    delivery_latency_ms = max(0.0, (t_yield_end - t_yield_start) * 1000.0)
                    ema_latency_ms = 0.7 * ema_latency_ms + 0.3 * delivery_latency_ms
        finally:
            safe_release_capture(cap)
            cap = None

        # Check if stream ended because user stopped it or switched cameras
        if not (live_stream_state.is_active and live_stream_state.current_camera_id == camera_id):
            break

        # If dropped due to network read timeout (fail_count > 30), initiate backoff & heartbeat
        if not loop_file:
            reconnect_attempt += 1
            backoff = min(max_backoff, initial_backoff * (2 ** min(reconnect_attempt - 1, 4)))

            deadline = time.time() + backoff
            while time.time() < deadline:
                if not (live_stream_state.is_active and live_stream_state.current_camera_id == camera_id):
                    return
                placeholder = create_reconnect_placeholder_frame(
                    camera_id=camera_id,
                    path=path,
                    attempt=reconnect_attempt,
                    backoff=max(0.0, deadline - time.time()),
                    status_text="FEED LOST - RECONNECTING...",
                )
                if placeholder:
                    yield placeholder
                time.sleep(0.5)
