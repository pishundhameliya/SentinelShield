"""Registry Service for managing Gujarat cities, areas, and camera assets."""
from __future__ import annotations

import uuid
from typing import Any

from core.database import db_manager
from modules.registry.estate_data import CITIES, DEMO_CAMS, SENTINEL_LIVE_CAMS, sample_points, total_cameras


class RegistryService:
    """Service providing camera asset discovery, filtering, and registration."""

    @staticmethod
    def get_cities() -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM cities ORDER BY cameras DESC")

    @staticmethod
    def get_areas(city_id: str) -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM areas WHERE city_id=? ORDER BY cameras DESC", city_id)

    @staticmethod
    def get_cameras(city_id: str = "", area_id: str = "", owner: str = "government") -> dict[str, Any]:
        q = "SELECT * FROM cameras WHERE 1=1"
        args: list[Any] = []
        if city_id:
            q += " AND city_id=?"
            args.append(city_id)
        if area_id:
            q += " AND area_id=?"
            args.append(area_id)
        if owner == "government":
            q += " AND owner IS NOT NULL AND owner != ''"
        q += " ORDER BY kind DESC, name"
        cams = db_manager.query_rows(q, *args)

        area_row = None
        city_row = None
        if city_id:
            city_row = db_manager.query_one("SELECT * FROM cities WHERE id=?", city_id)
        if city_id and area_id:
            area_row = db_manager.query_one("SELECT * FROM areas WHERE id=?", f"{city_id}:{area_id}")

        return {
            "cameras": cams,
            "shown": len(cams),
            "city": city_row,
            "area": area_row,
            "note": "Only government-owned cameras in this area. Full estate count is on the city/area card.",
        }

    @staticmethod
    def get_hot_cams() -> list[dict[str, Any]]:
        return db_manager.query_rows(
            "SELECT id,name,place,kind FROM cameras WHERE kind='recorded' ORDER BY name"
        )

    @staticmethod
    def get_live_cams() -> list[dict[str, Any]]:
        return SENTINEL_LIVE_CAMS

    @staticmethod
    def add_camera(name: str, place: str = "Surat", lat: float = 21.17, lng: float = 72.83, city_id: str = "", area_id: str = "", owner: str = "Gujarat Police", live_url: str = "") -> str:
        cid = "cam-" + uuid.uuid4().hex[:6]
        kind = "live" if live_url else "recorded"
        status = "ready" if live_url else "empty"
        note = "Live link saved — press Open live" if live_url else "Waiting for a video"
        db_manager.execute(
            """INSERT INTO cameras(id,name,place,lat,lng,source,kind,status,last_note,city_id,area_id,owner,spot,estate,live_url)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            cid, name, place, lat, lng, live_url, kind, status, note, city_id, area_id, owner, place, 1, live_url,
        )
        return cid

    @staticmethod
    def connect_camera_url(camera_id: str, live_url: str) -> None:
        db_manager.execute(
            "UPDATE cameras SET live_url=?, kind=?, status=?, last_note=? WHERE id=?",
            live_url, "live", "ready", "Live link saved — press Open live", camera_id,
        )


registry_service = RegistryService()
