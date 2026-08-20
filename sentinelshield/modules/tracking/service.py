"""Tracking Service for sightings, vehicle queries, and route reconstruction."""
from __future__ import annotations

import uuid
from typing import Any

from core.database import db_manager, utcnow
from modules.vision.alpr_ocr import normalize_plate


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
        p = normalize_plate(plate)
        hits = db_manager.query_rows("SELECT * FROM sightings WHERE plate=? ORDER BY created ASC LIMIT 30", p)
        pts = [h for h in hits if h.get("lat") is not None]
        speed = None
        direction = "unknown"

        if len(pts) >= 2:
            a, b = pts[0], pts[-1]
            dlat = (b["lat"] or 0) - (a["lat"] or 0)
            dlng = (b["lng"] or 0) - (a["lng"] or 0)
            km = (dlat ** 2 + dlng ** 2) ** 0.5 * 111
            direction = "north" if dlat > 0.01 else ("south" if dlat < -0.01 else "east-west")
            if dlng > 0.01:
                direction = "east" if abs(dlat) < abs(dlng) else direction
            speed = round(km * 40, 1)

        return {
            "plate": p,
            "points": hits,
            "timeline": [{"cam": h["camera_name"], "when": h["created"], "place": h["place"]} for h in hits],
            "direction": direction,
            "speed_kmh_est": speed,
            "hops": len(hits),
        }


tracking_service = TrackingService()
