"""Digital Twin analytics, predictive risk heatmaps, and camera health monitoring."""
from __future__ import annotations

from typing import Any
from sentinelshield.core.database import db_manager


class DigitalTwinService:
    """Service calculating spatial crime risk heatmaps, digital twin layers, and drone simulation."""

    @staticmethod
    def get_heat_spots() -> dict[str, Any]:
        spots = []
        cities = db_manager.query_rows("SELECT * FROM cities")
        for c in cities:
            n_al = db_manager.query_one(
                "SELECT COUNT(*) n FROM alerts a JOIN cameras cam ON a.camera_id=cam.id WHERE cam.city_id=?", c["id"]
            )
            n_ev = db_manager.query_one(
                "SELECT COUNT(*) n FROM events e JOIN cameras cam ON e.camera_id=cam.id WHERE cam.city_id=?", c["id"]
            )
            past = int((n_al or {}).get("n") or 0) + int((n_ev or {}).get("n") or 0)
            pred = past + int((c.get("cameras") or 0) / 8000)
            level = "low"
            if pred >= 12:
                level = "high"
            elif pred >= 5:
                level = "medium"
            spots.append({
                "city_id": c["id"],
                "name": c["name"],
                "lat": c["lat"],
                "lng": c["lng"],
                "past": past,
                "predicted": pred,
                "level": level,
                "cameras": c["cameras"],
            })
        spots.sort(key=lambda x: -x["predicted"])
        return {"spots": spots, "method": "history + camera density (not a trained neural crime model)"}

    @staticmethod
    def get_twin_state() -> dict[str, Any]:
        heat = DigitalTwinService.get_heat_spots()["spots"][:8]
        cyber = db_manager.query_rows("SELECT * FROM cyber ORDER BY created DESC LIMIT 15")
        cams = db_manager.query_rows("SELECT id,name,place,lat,lng,status,city_id,kind FROM cameras WHERE kind='recorded' OR id LIKE 'cam-%'")
        drones = [{"id": "drn-01", "name": "QR-GJ-01", "lat": 21.18, "lng": 72.83, "status": "ready", "city": "Surat"}]
        return {"heat": heat, "cyber": cyber, "cameras": cams, "drones": drones}

    @staticmethod
    def get_camera_health() -> list[dict[str, Any]]:
        cams = db_manager.query_rows("SELECT id,name,place,status,kind,source,trust FROM cameras WHERE kind='recorded' OR id LIKE 'cam-%'")
        out = []
        for c in cams:
            issues = []
            if c.get("status") in ("offline", "error"):
                issues.append("video_loss")
            if c.get("status") == "tampered":
                issues.append("obstruction_or_freeze")
            if not c.get("source"):
                issues.append("no_stream")
            health = "ok" if not issues else "degraded"
            out.append({**c, "health": health, "issues": issues or ["none"]})
        return out

    @staticmethod
    def simulate_drone_launch(city: str = "surat", reason: str = "CCTV alert") -> dict[str, Any]:
        return {
            "ok": True,
            "drone": "QR-GJ-01",
            "city": city,
            "reason": reason,
            "status": "airborne (simulated)",
            "feed": "Aerial overlay on Digital Twin — no real UAV in this ₹0 prototype",
        }


digital_twin_service = DigitalTwinService()
