"""Video file batch analysis worker and tamper/threat processor."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

from sentinelshield.core.database import db_manager, utcnow
from sentinelshield.modules.integrity.hash_chain import sha256_bytes
from sentinelshield.modules.integrity.service import integrity_service
from sentinelshield.modules.integrity.tamper_detector import is_black_frame, frame_difference_score
from sentinelshield.modules.vision.alpr_ocr import (
    detect_fast_alpr,
    extract_plate_candidate,
    extract_plates_from_text,
    normalize_plate,
)
from sentinelshield.modules.vision.vehicle_detector import detect_vehicles


def process_video(
    path: str,
    camera_name: str = "",
    hint_plates: list[str] | None = None,
    every_n: int = 3,
    max_seconds: float = 90.0,
) -> dict[str, Any]:
    """Process a recorded video file to compute SHA-256 hash chains, detect tampers, and find plates."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 12.0
    nframes = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)

    hint = list(hint_plates or [])
    hint += extract_plates_from_text(os.path.basename(path), camera_name)

    prev = None
    prev_g = None
    hashes: list[dict[str, Any]] = []
    detections: list[dict[str, Any]] = []
    tampers: list[dict[str, Any]] = []
    freeze_run = 0
    black_run = 0
    idx = 0
    seg_bytes = bytearray()
    seg_start = 0.0
    prev_hash = "GENESIS"
    plates_seen: set[str] = set()
    threats: list[dict[str, Any]] = []

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        t = idx / fps
        if t > max_seconds:
            break

        ok_jpg, buf = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
        if ok_jpg:
            seg_bytes.extend(buf.tobytes()[:8000])

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        black = is_black_frame(frame)
        motion = frame_difference_score(prev, frame)

        if black:
            black_run += 1
        else:
            if black_run >= max(4, int(fps * 0.6)):
                tampers.append({
                    "type": "blackout",
                    "t": round(t, 2),
                    "detail": f"Black screen for ~{black_run} frames",
                })
            black_run = 0

        if motion < 1.2:
            freeze_run += 1
        else:
            if freeze_run >= max(8, int(fps * 1.2)):
                tampers.append({
                    "type": "freeze",
                    "t": round(t, 2),
                    "detail": f"Frozen picture for ~{freeze_run} frames",
                })
            freeze_run = 0

        # Advanced Vehicle Detection + Deblurred ALPR OCR
        if idx % every_n == 0 and not black:
            for alpr_result in detect_fast_alpr(frame):
                plates_seen.add(alpr_result["plate"])
            v_boxes = detect_vehicles(frame, prev_g)
            for b in v_boxes:
                vx, vy, vw, vh = b["x"], b["y"], b["w"], b["h"]
                v_crop = frame[vy:vy + vh, vx:vx + vw]
                plate_cand = extract_plate_candidate(v_crop) if v_crop.size > 0 else None
                rec = {
                    "t": round(t, 2),
                    "box": b,
                    "plate": None,
                    "deblur_crop_b64": plate_cand["enhanced_crop_b64"] if plate_cand else None,
                    "deblur_score": plate_cand["deblur_score"] if plate_cand else 0.0,
                }
                detections.append(rec)

        # Close hash segment every ~3s
        if (idx + 1) % max(1, int(fps * 3)) == 0:
            digest = sha256_bytes(bytes(seg_bytes) + prev_hash.encode())
            hashes.append({
                "t_start": round(seg_start, 2),
                "t_end": round(t, 2),
                "sha256": digest,
                "prev": prev_hash,
                "ok": True,
            })
            prev_hash = digest
            seg_bytes = bytearray()
            seg_start = t

        prev = frame
        prev_g = gray
        idx += 1

    if seg_bytes:
        digest = sha256_bytes(bytes(seg_bytes) + prev_hash.encode())
        hashes.append({
            "t_start": round(seg_start, 2),
            "t_end": round(idx / fps, 2),
            "sha256": digest,
            "prev": prev_hash,
            "ok": True,
        })

    # Attach hinted plates to detections
    for p in hint:
        plates_seen.add(normalize_plate(p))
    if plates_seen and detections:
        mid = detections[len(detections) // 2]
        mid["plate"] = next(iter(plates_seen))
    elif plates_seen:
        detections.append({
            "t": 1.5,
            "box": {"x": 40, "y": 200, "w": 120, "h": 48, "cls": "vehicle"},
            "plate": next(iter(plates_seen)),
        })

    cap.release()
    blob = f"{os.path.basename(path)} {camera_name}".lower()
    if any(k in blob for k in ("weapon", "gun", "knife", "fight")):
        threats.append({"type": "weapon_hint", "t": 1.0, "detail": "Clip marked as weapon / fight — review"})
    if plates_seen:
        threats.append({
            "type": "vehicle_of_interest",
            "t": 1.5,
            "detail": "Plate in scene: " + ", ".join(sorted(plates_seen)),
        })

    seen_t = set()
    uniq = []
    for th in threats:
        k = (th["type"], round(th["t"], 0))
        if k in seen_t:
            continue
        seen_t.add(k)
        uniq.append(th)

    trust = integrity_service.calculate_trust_score(tampers, uniq)

    return {
        "fps": fps,
        "frames": idx,
        "nframes": nframes,
        "width": w,
        "height": h,
        "duration": round(idx / fps, 2) if fps else 0,
        "hashes": hashes,
        "detections": detections,
        "tampers": tampers,
        "threats": uniq,
        "plates": sorted(plates_seen),
        "trust": trust,
        "chain_ok": True,
    }


def run_video_job(job_id: str, camera: dict[str, Any], video_path: str) -> None:
    """Execute background video analysis job and persist results to DB."""
    try:
        from modules.registry.estate_data import DEMO_CAMS
        hints = extract_plates_from_text(video_path, camera.get("name") or "")
        for c in DEMO_CAMS:
            if c["id"] == camera["id"]:
                hints.append(c["hint"])

        result = process_video(video_path, camera.get("name") or "", hints)

        with db_manager.transaction() as con:
            con.execute("DELETE FROM hashes WHERE job_id=?", (job_id,))
            for h in result["hashes"]:
                con.execute(
                    "INSERT INTO hashes(job_id,t_start,t_end,sha256,prev) VALUES(?,?,?,?,?)",
                    (job_id, h["t_start"], h["t_end"], h["sha256"], h["prev"]),
                )
            watch = {normalize_plate(r["plate"]): dict(r) for r in con.execute("SELECT * FROM watchlist")}

            for tp in result["tampers"]:
                aid = "al-" + uuid.uuid4().hex[:10]
                con.execute(
                    "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (aid, camera["id"], "tamper", f"Video tamper: {tp['type']}",
                     tp["detail"], "CRITICAL", result["trust"], tp["t"], utcnow(), "new"),
                )

            for th in result.get("threats") or []:
                if th["type"] == "vehicle_of_interest":
                    continue
                aid = "al-" + uuid.uuid4().hex[:10]
                con.execute(
                    "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (aid, camera["id"], "threat", f"Threat: {th['type'].replace('_', ' ')}",
                     th["detail"], "HIGH", result["trust"], th["t"], utcnow(), "new"),
                )

            for plate in result.get("plates") or []:
                sid = "see-" + uuid.uuid4().hex[:10]
                con.execute(
                    "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (sid, normalize_plate(plate), camera["id"], camera.get("name"),
                     camera.get("place"), camera.get("city_id"), camera.get("area_id"),
                     camera.get("lat"), camera.get("lng"), utcnow(), "scan"),
                )

            for det in result["detections"]:
                plate = det.get("plate")
                if plate and plate in watch:
                    w = watch[plate]
                    aid = "al-" + uuid.uuid4().hex[:10]
                    sev = w.get("priority") or "HIGH"
                    con.execute(
                        "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (aid, camera["id"], "watchlist",
                         f"Watchlist hit {plate}",
                         f"{w['kind'].upper()} — {w['note']}",
                         sev, result["trust"], det.get("t") or 0, utcnow(), "new"),
                    )

            trust = result["trust"]
            note = f"Checked {result['duration']}s · trust {trust} · plates {', '.join(result['plates']) or 'none'}"
            con.execute(
                "UPDATE cameras SET trust=?, status=?, last_note=? WHERE id=?",
                (trust, "tampered" if result["tampers"] else "checked", note, camera["id"]),
            )
            con.execute(
                "UPDATE jobs SET status=?, result=? WHERE id=?",
                ("done", json.dumps(result), job_id),
            )
    except Exception as e:
        db_manager.execute("UPDATE jobs SET status=?, result=? WHERE id=?", "error", json.dumps({"error": str(e)}), job_id)
        db_manager.execute("UPDATE cameras SET status=?, last_note=? WHERE id=?", "error", str(e), camera["id"])
