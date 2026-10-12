"""Tests for the ANPR number plate recognition engine (modules/vision/plate_recognizer.py)."""
from __future__ import annotations

import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import cv2

from sentinelshield.config import settings
from sentinelshield.modules.vision.alpr_ocr import detect_fast_alpr, read_plate_text
from sentinelshield.modules.vision.plate_recognizer import parse_indian_plate, plate_recognizer


def test_indian_plate_correction():
    cases = {
        # raw OCR text           -> expected plate
        "GJ05AB4321": "GJ05AB4321",   # already correct
        "GJO5AB4321": "GJ05AB4321",   # O read for 0 in the district
        "4J05AB4321": "GJ05AB4321",   # 4 read for the state letter
        "CJ05SS2026": "GJ05SS2026",   # C/G confusion in the state code
        "gj 18 xy 11OO": "GJ18XY1100",  # spaces, lower case, O for 0 in the number
        "MH12DE1433": "MH12DE1433",   # other state
        "DL3CAB1234": "DL03CAB1234",  # 1-digit district padded, 3-letter series
        "22BH1234AA": "22BH1234AA",   # Bharat (BH) series
    }
    for raw, expected in cases.items():
        got = parse_indian_plate(raw)
        assert got["valid"], f"{raw!r} should parse as a valid plate, got {got}"
        assert got["plate"] == expected, f"{raw!r}: expected {expected}, got {got['plate']}"

    assert parse_indian_plate("GJ05AB4321")["formatted"] == "GJ 05 AB 4321"
    assert parse_indian_plate("CJ05SS2026")["corrected"] is True
    for junk in ("", "HELLO", "12345", "XXXXXXXXXXXXXXXX"):
        assert not parse_indian_plate(junk)["valid"], f"{junk!r} must not be a valid plate"
    print("[PASS] Indian plate format validation and OCR correction verified!")


def _frames(clip: str, samples: int = 12):
    cap = cv2.VideoCapture(clip)
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    for k in range(0, n, max(n // samples, 1)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, k)
        ok, frame = cap.read()
        if ok:
            yield frame
    cap.release()


def test_engine_reads_demo_plates():
    if not plate_recognizer.available:
        print(f"[SKIP] ANPR engine unavailable: {plate_recognizer.status()['error']}")
        return

    expected = {
        "ring_road_normal.mp4": "GJ05AB4321",
        "parking_freeze_attack.mp4": "GJ01CD7788",
        "lobby_blackout.mp4": "GJ18XY1100",
        "gate_stolen_vehicle.mp4": "GJ05SS2026",
    }
    for clip, plate in expected.items():
        path = os.path.join(settings.demos_dir, clip)
        if not os.path.isfile(path):
            print(f"[SKIP] demo clip missing: {clip}")
            continue
        seen = set()
        crop_reads = set()
        for frame in _frames(path):
            for hit in detect_fast_alpr(frame):
                assert {"plate", "confidence", "box", "valid"} <= hit.keys()
                seen.add(hit["plate"])
                b = hit["box"]
                crop = frame[b["y"]:b["y"] + b["h"], b["x"]:b["x"] + b["w"]]
                text, _ = read_plate_text(crop)
                if text:
                    crop_reads.add(text)
        assert plate in seen, f"{clip}: expected {plate}, engine read {sorted(seen)}"
        assert plate in crop_reads, f"{clip}: crop OCR expected {plate}, got {sorted(crop_reads)}"
    status = plate_recognizer.status()
    assert status["available"] and status["state"] == "ready"
    print("[PASS] ANPR engine reads demo clip number plates (full frame + cropped plate)!")


def test_vehicle_detector_no_false_vehicles():
    """Signs, lights and road texture must not be reported as vehicles (old heuristic did)."""
    import numpy as np

    from sentinelshield.modules.vision.vehicle_detector import detect_vehicles, detector_status

    detect_vehicles(np.zeros((8, 8, 3), dtype=np.uint8))  # trigger model load
    if not detector_status()["available"]:
        print(f"[SKIP] vehicle detector unavailable: {detector_status()['error']}")
        return

    rng = np.random.default_rng(7)
    scene = rng.integers(40, 90, (720, 1280, 3), dtype=np.uint8)          # rough road texture
    for x in range(40, 1240, 160):                                         # rows of shop signs
        cv2.rectangle(scene, (x, 60), (x + 120, 120), (30, 200, 240), -1)
        cv2.putText(scene, "SHOP", (x + 15, 102), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (20, 20, 20), 3)
    for x in range(100, 1280, 250):                                        # street lights
        cv2.circle(scene, (x, 220), 30, (255, 255, 255), -1)
    assert detect_vehicles(scene) == [], "detector must not invent vehicles in a scene with none"

    clip = os.path.join(settings.demos_dir, "cam26_dhanori.mp4")
    if os.path.isfile(clip):
        cap = cv2.VideoCapture(clip)
        cap.set(cv2.CAP_PROP_POS_FRAMES, 50)
        ok, frame = cap.read()
        cap.release()
        found = detect_vehicles(frame) if ok else []
        assert found, "real two-wheeler in cam26_dhanori frame 50 should be detected"
        allowed = {"car", "bike/activa", "bus/truck"}
        assert all(v["cls"] in allowed and v["confidence"] >= settings.vehicle_min_conf for v in found)
    print("[PASS] Vehicle detector reports only real vehicles (no signs / lights / road texture)!")


if __name__ == "__main__":
    test_indian_plate_correction()
    test_engine_reads_demo_plates()
    test_vehicle_detector_no_false_vehicles()
    print("\n[ALL PASS] ANPR number plate recognition verified!")
