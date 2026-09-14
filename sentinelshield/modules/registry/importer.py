"""Transactional CSV Bulk Importer for Gujarat Camera Estate with Coordinate Validation."""
from __future__ import annotations

import csv
import io
import uuid
from typing import Any

from sentinelshield.core.database import db_manager
from sentinelshield.modules.registry.estate_data import CITIES

# Bounding box coordinates for Gujarat State
GUJARAT_LAT_MIN, GUJARAT_LAT_MAX = 20.0, 24.8
GUJARAT_LNG_MIN, GUJARAT_LNG_MAX = 68.0, 74.5

HEADER_ALIASES = {
    "id": ["camera_id", "cam_id", "id", "camera_code", "cam_code"],
    "name": ["name", "camera_name", "cam_name", "title", "label", "description"],
    "city": ["city", "city_id", "district", "zone", "city_name"],
    "area": ["area", "location", "junction", "place", "ward", "sector"],
    "lat": ["lat", "latitude", "gps_lat", "y"],
    "lng": ["lng", "lon", "longitude", "gps_lng", "gps_lon", "x"],
    "live_url": ["live_url", "url", "rtsp", "stream_url", "source", "feed"],
    "owner": ["owner", "department", "type", "category", "organization"],
}


def _match_header(col_name: str) -> str | None:
    """Find standardized field name matching the given CSV column header."""
    normalized = col_name.strip().lower().replace(" ", "_").replace("-", "_")
    for standard_field, aliases in HEADER_ALIASES.items():
        if normalized in aliases:
            return standard_field
    return None


def import_cameras_from_csv(csv_content: str, duplicate_mode: str = "update") -> dict[str, Any]:
    """Parse and transactionally import camera definitions from CSV data."""
    if not csv_content or not csv_content.strip():
        return {"total": 0, "imported": 0, "skipped": 0, "errors": ["Empty CSV content"]}

    f = io.StringIO(csv_content.strip())
    reader = csv.reader(f)

    try:
        raw_headers = next(reader)
    except StopIteration:
        return {"total": 0, "imported": 0, "skipped": 0, "errors": ["No header row found"]}

    header_map = {}
    for idx, raw_h in enumerate(raw_headers):
        field = _match_header(raw_h)
        if field:
            header_map[field] = idx

    if "name" not in header_map and "id" not in header_map:
        return {"total": 0, "imported": 0, "skipped": 0, "errors": ["Missing required column: camera name or id"]}

    total_rows = 0
    imported_count = 0
    skipped_count = 0
    errors: list[str] = []
    cameras_to_insert: list[tuple[Any, ...]] = []

    for row_idx, row in enumerate(reader, start=2):
        if not row or not any(field.strip() for field in row):
            continue
        total_rows += 1

        def _get_val(r: list[str], field_name: str, default: str = "") -> str:
            idx = header_map.get(field_name)
            if idx is not None and idx < len(r):
                return r[idx].strip()
            return default

        cam_name = _get_val(row, "name") or f"Camera {row_idx}"
        cam_id = _get_val(row, "id") or ("cam-" + uuid.uuid4().hex[:8])
        city = _get_val(row, "city", "ahmedabad").lower()
        area = _get_val(row, "area", "Command Zone")
        live_url = _get_val(row, "live_url", "")
        owner = _get_val(row, "owner", "government").lower()

        # Coordinate parsing & bounds validation
        raw_lat = _get_val(row, "lat")
        raw_lng = _get_val(row, "lng")

        city_map = {c["id"]: c for c in CITIES} if isinstance(CITIES, list) else CITIES
        city_def = city_map.get(city) or city_map.get("ahmedabad", {"lat": 23.0225, "lng": 72.5714})
        try:
            lat = float(raw_lat) if raw_lat else float(city_def["lat"])
            lng = float(raw_lng) if raw_lng else float(city_def["lng"])
        except ValueError:
            lat = float(city_def["lat"])
            lng = float(city_def["lng"])

        # Check Gujarat geographic bounds
        if not (GUJARAT_LAT_MIN <= lat <= GUJARAT_LAT_MAX and GUJARAT_LNG_MIN <= lng <= GUJARAT_LNG_MAX):
            lat = float(city_def["lat"])
            lng = float(city_def["lng"])

        place = f"{area}, {city.capitalize()}"
        status = "ready"

        cameras_to_insert.append((
            cam_id, cam_name, place, lat, lng, "live", "fixed",
            status, "Imported via CSV", city, area, owner, live_url,
        ))

    if not cameras_to_insert:
        return {"total": total_rows, "imported": 0, "skipped": 0, "errors": errors}

    # Atomic transactional insert/update
    with db_manager.transaction() as conn:
        for cam in cameras_to_insert:
            if duplicate_mode == "update":
                conn.execute("""
                    INSERT INTO cameras(id, name, place, lat, lng, source, kind, status, last_note, city_id, area_id, owner, live_url)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name,
                        place=excluded.place,
                        lat=excluded.lat,
                        lng=excluded.lng,
                        city_id=excluded.city_id,
                        area_id=excluded.area_id,
                        owner=excluded.owner,
                        live_url=excluded.live_url,
                        last_note=excluded.last_note
                """, cam)
            else:
                conn.execute("""
                    INSERT OR IGNORE INTO cameras(id, name, place, lat, lng, source, kind, status, last_note, city_id, area_id, owner, live_url)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, cam)
            imported_count += 1

    return {
        "total": total_rows,
        "imported": imported_count,
        "skipped": skipped_count,
        "errors": errors,
    }
