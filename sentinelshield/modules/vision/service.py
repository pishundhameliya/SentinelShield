"""Vision Service coordinating vehicle detection, deblurring, OCR, and annotated snapshots."""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

from sentinelshield.config import settings
from sentinelshield.modules.vision.alpr_ocr import (
    detect_fast_alpr,
    extract_plate_candidate,
    read_plate_text,
)
from sentinelshield.modules.vision.vehicle_detector import detect_vehicles


class VisionService:
    """Orchestrates computer vision, deblurring, and license plate recognition pipelines."""

    @staticmethod
    def process_frame_anpr(
        frame: np.ndarray,
        camera_id: str,
        camera_name: str,
    ) -> dict[str, Any]:
        """Perform full-frame ANPR scan, generate timestamped annotated snapshot image, and return detections."""
        if frame is None or frame.size == 0:
            raise ValueError("Invalid frame supplied for ANPR scan.")

        now_dt = datetime.now()
        time_str = now_dt.strftime("%Y-%m-%d %H:%M:%S IST")
        ts_filename = int(now_dt.timestamp())

        vehicles = detect_vehicles(frame)
        fast_alpr_results = detect_fast_alpr(frame)
        annotated = frame.copy()
        _, fw = annotated.shape[:2]

        # Draw header timestamp banner on full frame photo
        cv2.rectangle(annotated, (0, 0), (fw, 45), (15, 23, 42), -1)
        header_text = f"SENTINEL SHIELD ANPR | {camera_name or camera_id} | TIME: {time_str}"
        cv2.putText(annotated, header_text, (15, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (56, 189, 248), 2)

        plates_found = []

        for idx, v in enumerate(vehicles):
            vx, vy, vw, vh = v["x"], v["y"], v["w"], v["h"]

            # Draw vehicle bounding box (Green)
            cv2.rectangle(annotated, (vx, vy), (vx + vw, vy + vh), (0, 255, 0), 2)
            cv2.putText(
                annotated,
                f"VEHICLE #{idx+1} ({v['cls'].upper()})",
                (vx, max(20, vy - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2,
            )

            v_crop = frame[vy:vy + vh, vx:vx + vw]
            if v_crop.size > 0:
                cand = extract_plate_candidate(v_crop)
                if cand:
                    px, py, pw, ph = cand["box"]["x"], cand["box"]["y"], cand["box"]["w"], cand["box"]["h"]
                    abs_px, abs_py = vx + px, vy + py

                    # Draw license plate bounding box (Yellow/Cyan)
                    cv2.rectangle(annotated, (abs_px, abs_py), (abs_px + pw, abs_py + ph), (255, 200, 0), 2)

                    raw_plate, ocr_confidence = read_plate_text(cand.get("enhanced_bgr"))
                    formatted_plate = raw_plate or "Plate Not Clear"

                    cv2.putText(
                        annotated,
                        formatted_plate,
                        (abs_px, max(40, abs_py - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (255, 200, 0),
                        2,
                    )

                    plates_found.append({
                        "vehicle": v,
                        "plate_text": formatted_plate,
                        "raw_plate": raw_plate,
                        "ocr_confidence": ocr_confidence,
                        "plate_box": cand["box"],
                        "deblurred_crop_b64": cand["enhanced_crop_b64"],
                        "sharpness_score": cand["deblur_score"],
                        "captured_at": time_str,
                    })

        # Integrate Fast-ALPR results
        known_plates = {item.get("raw_plate") for item in plates_found if item.get("raw_plate")}
        for alpr_result in fast_alpr_results:
            if alpr_result["plate"] in known_plates:
                continue
            plates_found.append({
                "vehicle": {"cls": "fast-alpr", "confidence": alpr_result["confidence"]},
                "plate_text": alpr_result["plate"],
                "raw_plate": alpr_result["plate"],
                "ocr_confidence": alpr_result["confidence"],
                "plate_box": alpr_result["box"],
                "deblurred_crop_b64": "",
                "sharpness_score": 0.0,
                "captured_at": time_str,
            })

        # Save full annotated timestamped snapshot frame
        snap_filename = f"anpr_{camera_id}_{ts_filename}.jpg"
        snap_path = os.path.join(settings.snapshots_dir, snap_filename)
        cv2.imwrite(snap_path, annotated)

        snap_url = f"/media/snapshots/{snap_filename}"
        for p in plates_found:
            p["snapshot_url"] = snap_url

        return {
            "ok": True,
            "camera_id": camera_id,
            "camera_name": camera_name,
            "vehicles": vehicles,
            "plates_enhanced": plates_found,
            "snapshot_url": snap_url,
            "timestamp": time_str,
        }

    process_scan_frame = process_frame_anpr


vision_service = VisionService()
