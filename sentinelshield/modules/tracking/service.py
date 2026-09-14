"""Tracking Service for sightings, vehicle queries, and route reconstruction."""
from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sentinelshield.core.database import db_manager, utcnow
from sentinelshield.modules.vision.alpr_ocr import normalize_plate


def haversine_distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates using the Haversine formula."""
    R = 6371.0  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)

    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))
    return round(R * c, 3)


def calculate_bearing(lat1: float, lng1: float, lat2: float, lng2: float) -> tuple[float, str]:
    """Calculate forward azimuth bearing in degrees (0-360) and 8-point compass direction."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dlam = math.radians(lng2 - lng1)

    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    bearing = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0

    compass_octants = [
        "North", "North-East", "East", "South-East",
        "South", "South-West", "West", "North-West"
    ]
    idx = int((bearing + 22.5) // 45.0) % 8
    return round(bearing, 1), compass_octants[idx]


def parse_timestamp_sec(ts_str: str | None) -> float:
    """Parse common timestamp string formats into unix seconds."""
    if not ts_str:
        return 0.0
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
        try:
            dt = datetime.strptime(ts_str.strip(), fmt).replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    return 0.0


class TrackingService:
    """Service providing vehicle sighting search and trajectory/route reconstruction."""

    @staticmethod
    def find_vehicle(plate: str) -> dict[str, Any]:
        p = normalize_plate(plate)
        if len(p) < 4:
            return {"error": "Enter a vehicle number (e.g. GJ05SS2026)", "status_code": 400}

        hits = db_manager.query_rows(
            "SELECT * FROM sightings WHERE plate=? ORDER BY created DESC LIMIT 40", p
        )
        wl = db_manager.query_one("SELECT * FROM watchlist WHERE plate=?", p)
        last = hits[0] if hits else None

        return {
            "plate": p,
            "found": bool(hits),
            "last": last,
            "history": hits,
            "watchlist": wl,
            "message": (
                f"Last seen at {last['camera_name']}, {last['place']}"
                if last else "No camera has seen this number yet. Continuous AI will add hits when it appears."
            ),
        }

    @staticmethod
    def get_vehicle_detections(camera_id: str = "", query: str = "") -> dict[str, Any]:
        args: list[Any] = []
        where: list[str] = []
        if camera_id:
            where.append("camera_id=?")
            args.append(camera_id)
        if query.strip():
            where.append("(plate LIKE ? OR vehicle_type LIKE ? OR tracking_id LIKE ?)")
            like = f"%{query.strip()}%"
            args.extend([like, like, like])

        clause = (" WHERE " + " AND ".join(where)) if where else ""
        detections = db_manager.query_rows(
            "SELECT * FROM vehicle_detections" + clause + " ORDER BY created DESC LIMIT 100", *args
        )
        count = db_manager.query_one("SELECT COUNT(*) AS n FROM vehicle_detections" + clause, *args)

        return {
            "detections": detections,
            "count": int((count or {}).get("n") or 0),
        }

    @staticmethod
    def calculate_route(plate: str) -> dict[str, Any]:
        """Reconstruct chronological vehicle trajectory with Haversine distances, speeds, and directions."""
        p = normalize_plate(plate)
        hits = db_manager.query_rows("SELECT * FROM sightings WHERE plate=? ORDER BY created ASC LIMIT 40", p)
        pts = [h for h in hits if h.get("lat") is not None and h.get("lng") is not None]

        hops: list[dict[str, Any]] = []
        total_distance_km = 0.0
        speeds: list[float] = []
        anomalies: list[str] = []
        overall_direction = "unknown"
        overall_bearing = 0.0

        for i, curr in enumerate(pts):
            hop_info = {
                "hop_number": i + 1,
                "camera_id": curr.get("camera_id"),
                "camera_name": curr.get("camera_name") or f"Camera {curr.get('camera_id')}",
                "place": curr.get("place") or "",
                "city_id": curr.get("city_id") or "",
                "lat": float(curr["lat"]),
                "lng": float(curr["lng"]),
                "timestamp": curr.get("created") or "",
                "distance_from_prev_km": 0.0,
                "speed_kmh": None,
                "bearing_deg": None,
                "compass_heading": None,
            }

            if i > 0:
                prev = pts[i - 1]
                dist = haversine_distance_km(float(prev["lat"]), float(prev["lng"]), float(curr["lat"]), float(curr["lng"]))
                total_distance_km += dist
                hop_info["distance_from_prev_km"] = dist

                bearing_deg, compass = calculate_bearing(float(prev["lat"]), float(prev["lng"]), float(curr["lat"]), float(curr["lng"]))
                hop_info["bearing_deg"] = bearing_deg
                hop_info["compass_heading"] = compass

                t1 = parse_timestamp_sec(prev.get("created"))
                t2 = parse_timestamp_sec(curr.get("created"))
                dt_sec = max(1.0, abs(t2 - t1)) if (t1 > 0 and t2 > 0) else 0.0

                if dt_sec > 0:
                    dt_hours = dt_sec / 3600.0
                    spd = round(dist / dt_hours, 1)
                    hop_info["speed_kmh"] = spd
                    speeds.append(spd)
                    if spd > 180.0:
                        anomalies.append(f"Hop {i} to {i+1}: Impossible velocity ({spd} km/h). Suspected cloned license plate!")
                else:
                    # Simulated default travel velocity estimate
                    spd = round(dist * 40.0, 1)
                    hop_info["speed_kmh"] = spd
                    speeds.append(spd)

            hops.append(hop_info)

        if len(pts) >= 2:
            first_pt = pts[0]
            last_pt = pts[-1]
            overall_bearing, overall_direction = calculate_bearing(
                float(first_pt["lat"]), float(first_pt["lng"]), float(last_pt["lat"]), float(last_pt["lng"])
            )

        avg_speed = round(sum(speeds) / len(speeds), 1) if speeds else None

        return {
            "plate": p,
            "points": hits,
            "hops_count": len(hits),
            "hops": hops,
            "timeline": [
                {
                    "hop": h["hop_number"],
                    "cam": h["camera_name"],
                    "place": h["place"],
                    "when": h["timestamp"],
                    "speed_kmh": h["speed_kmh"],
                    "compass": h["compass_heading"],
                }
                for h in hops
            ],
            "total_distance_km": round(total_distance_km, 2),
            "speed_kmh_est": avg_speed,
            "direction": overall_direction.lower(),
            "bearing_deg": overall_bearing,
            "anomalies": anomalies,
            "is_suspect_clone": len(anomalies) > 0,
        }


tracking_service = TrackingService()
