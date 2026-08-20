"""Thread-safe SQLite Database Manager with WAL mode and transaction handling."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator

from config import settings


def utcnow() -> str:
    """Return formatted UTC timestamp string."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class DatabaseManager:
    """Manages SQLite database connections, schema migrations, and queries safely."""

    def __init__(self, db_path: str = settings.db_path):
        self.db_path = db_path
        self._lock = threading.RLock()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Create a new SQLite connection configured with WAL mode and row factory."""
        con = sqlite3.connect(self.db_path, timeout=15.0, check_same_thread=False)
        con.row_factory = sqlite3.Row
        # Enable WAL mode and performance pragmas for robust multi-threading
        con.execute("PRAGMA journal_mode=WAL;")
        con.execute("PRAGMA busy_timeout=10000;")
        con.execute("PRAGMA synchronous=NORMAL;")
        return con

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an auto-closing SQLite connection."""
        con = self.get_connection()
        try:
            yield con
        finally:
            con.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager providing an atomic SQLite transaction with commit on success and rollback on error."""
        with self._lock:
            con = self.get_connection()
            try:
                con.execute("BEGIN IMMEDIATE;")
                yield con
                con.commit()
            except Exception:
                con.rollback()
                raise
            finally:
                con.close()

    def execute(self, query: str, *args: Any) -> None:
        """Execute a write query safely with immediate commit."""
        with self._lock:
            with self.connection() as con:
                con.execute(query, args)
                con.commit()

    def query_rows(self, query: str, *args: Any) -> list[dict[str, Any]]:
        """Execute a SELECT query and return list of dictionaries."""
        with self.connection() as con:
            cur = con.execute(query, args)
            return [dict(r) for r in cur.fetchall()]

    def query_one(self, query: str, *args: Any) -> dict[str, Any] | None:
        """Execute a SELECT query and return the first row as dictionary or None."""
        with self.connection() as con:
            r = con.execute(query, args).fetchone()
            return dict(r) if r else None

    def init_schema(self, cities_data: list[dict] | None = None, demo_cams_data: list[dict] | None = None, sample_points_fn=None) -> None:
        """Initialize SQLite database tables, perform migrations, and apply default seeds."""
        with self._lock:
            with self.connection() as con:
                con.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS cameras (
                      id TEXT PRIMARY KEY, name TEXT, place TEXT, lat REAL, lng REAL,
                      source TEXT, kind TEXT, trust INTEGER DEFAULT 100, status TEXT DEFAULT 'idle',
                      last_note TEXT
                    );
                    CREATE TABLE IF NOT EXISTS watchlist (
                      id TEXT PRIMARY KEY, kind TEXT, plate TEXT, note TEXT, priority TEXT
                    );
                    CREATE TABLE IF NOT EXISTS jobs (
                      id TEXT PRIMARY KEY, camera_id TEXT, video TEXT, status TEXT, result TEXT, created TEXT
                    );
                    CREATE TABLE IF NOT EXISTS alerts (
                      id TEXT PRIMARY KEY, camera_id TEXT, kind TEXT, title TEXT, detail TEXT,
                      severity TEXT, trust INTEGER, t REAL, created TEXT, status TEXT
                    );
                    CREATE TABLE IF NOT EXISTS messages (
                      id TEXT PRIMARY KEY, room TEXT, user TEXT, role TEXT, text TEXT, created TEXT
                    );
                    CREATE TABLE IF NOT EXISTS hashes (
                      id INTEGER PRIMARY KEY AUTOINCREMENT,
                      job_id TEXT, t_start REAL, t_end REAL, sha256 TEXT, prev TEXT
                    );
                    CREATE TABLE IF NOT EXISTS cities (
                      id TEXT PRIMARY KEY, name TEXT, lat REAL, lng REAL, cameras INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS areas (
                      id TEXT PRIMARY KEY, city_id TEXT, name TEXT, lat REAL, lng REAL, cameras INTEGER
                    );
                    CREATE TABLE IF NOT EXISTS events (
                      id TEXT PRIMARY KEY, kind TEXT, title TEXT, camera_id TEXT,
                      place TEXT, extra TEXT, created TEXT
                    );
                    CREATE TABLE IF NOT EXISTS persons (
                      id TEXT PRIMARY KEY, name TEXT, kind TEXT, note TEXT
                    );
                    CREATE TABLE IF NOT EXISTS evidence (
                      id TEXT PRIMARY KEY, camera_id TEXT, sha256 TEXT, path TEXT, created TEXT
                    );
                    CREATE TABLE IF NOT EXISTS cyber (
                      id TEXT PRIMARY KEY, kind TEXT, detail TEXT, camera_id TEXT, created TEXT, status TEXT
                    );
                    CREATE TABLE IF NOT EXISTS sightings (
                      id TEXT PRIMARY KEY,
                      plate TEXT, camera_id TEXT, camera_name TEXT, place TEXT,
                      city_id TEXT, area_id TEXT, lat REAL, lng REAL,
                      created TEXT, source TEXT
                    );
                    CREATE TABLE IF NOT EXISTS vehicle_detections (
                      id TEXT PRIMARY KEY, camera_id TEXT, vehicle_type TEXT, tracking_id TEXT,
                      plate TEXT, confidence REAL, created TEXT, lat REAL, lng REAL, place TEXT
                    );
                    """
                )

                # Schema migrations for cameras table
                cols = {r[1] for r in con.execute("PRAGMA table_info(cameras)")}
                for col, typ in (
                    ("city_id", "TEXT"),
                    ("area_id", "TEXT"),
                    ("owner", "TEXT"),
                    ("spot", "TEXT"),
                    ("estate", "INTEGER DEFAULT 1"),
                    ("live_url", "TEXT"),
                ):
                    if col not in cols:
                        try:
                            con.execute(f"ALTER TABLE cameras ADD COLUMN {col} {typ}")
                        except Exception:
                            pass

                # Seed cities and sample government cameras if empty
                if cities_data and con.execute("SELECT COUNT(*) n FROM cities").fetchone()["n"] == 0:
                    for city in cities_data:
                        con.execute(
                            "INSERT OR REPLACE INTO cities VALUES(?,?,?,?,?)",
                            (city["id"], city["name"], city["lat"], city["lng"], city["cameras"]),
                        )
                        for aid, aname, alat, alng, acnt in city["areas"]:
                            con.execute(
                                "INSERT OR REPLACE INTO areas VALUES(?,?,?,?,?,?)",
                                (f"{city['id']}:{aid}", city["id"], aname, alat, alng, acnt),
                            )
                            if sample_points_fn:
                                for p in sample_points_fn(city, (aid, aname, alat, alng, acnt), n=5):
                                    con.execute(
                                        """INSERT OR IGNORE INTO cameras
                                           (id,name,place,lat,lng,source,kind,status,last_note,city_id,area_id,owner,spot,estate)
                                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                                        (
                                            p["id"], p["name"], city["name"], p["lat"], p["lng"],
                                            "", "registry", "offline",
                                            f"Government camera · {p['owner']} · no live link yet",
                                            city["id"], aid, p["owner"], p["spot"], 1,
                                        ),
                                    )

                # Seed demo cameras
                if demo_cams_data:
                    for c in demo_cams_data:
                        con.execute(
                            """INSERT OR REPLACE INTO cameras
                               (id,name,place,lat,lng,source,kind,status,last_note,city_id,area_id,owner,spot,estate)
                               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (
                                c["id"], c["name"], "Surat", c["lat"], c["lng"],
                                os.path.join(settings.demos_dir, c["demo"]), "recorded", "ready",
                                "Has recorded video — government owned",
                                c["city"], c["area"], c["owner"], c["spot"], 1,
                            ),
                        )

                # Seed initial watchlist and demo sightings if not disabled
                no_seed = os.path.exists(os.path.join(settings.data_dir, ".no_seed"))
                if not no_seed and con.execute("SELECT COUNT(*) n FROM watchlist").fetchone()["n"] == 0:
                    con.execute(
                        "INSERT INTO watchlist VALUES(?,?,?,?,?)",
                        ("wl1", "stolen", "GJ05SS2026", "Stolen SUV — FIR demo 2026-08-12", "CRITICAL"),
                    )
                    con.execute(
                        "INSERT INTO watchlist VALUES(?,?,?,?,?)",
                        ("wl2", "blacklisted", "GJ27HK9009", "RTO blacklist sample", "HIGH"),
                    )
                    con.execute(
                        "INSERT INTO watchlist VALUES(?,?,?,?,?)",
                        ("wl3", "suspect", "MH12DE4455", "Interstate suspect vehicle", "MEDIUM"),
                    )

                if not no_seed and con.execute("SELECT COUNT(*) n FROM sightings").fetchone()["n"] == 0:
                    demo_path = [
                        ("GJ05SS2026", "cam-gate", "Police HQ Gate", "Surat", "surat", "ringroad", 21.1959, 72.8302, "live-ai"),
                        ("GJ05SS2026", "cam-ring", "Ring Road Junction", "Surat", "surat", "ringroad", 21.1702, 72.8311, "live-ai"),
                        ("GJ05AB4321", "cam-ring", "Ring Road Junction", "Surat", "surat", "ringroad", 21.1702, 72.8311, "live-ai"),
                        ("GJ01CD7788", "cam-park", "VR Surat parking", "Surat", "surat", "athwa", 21.1418, 72.7709, "live-ai"),
                        ("GJ18XY1100", "cam-lobby", "Collector office lobby", "Surat", "surat", "ringroad", 21.1860, 72.8081, "live-ai"),
                        ("GJ27HK9009", "gov-ahmedabad-sg_highway-01", "S.G. Highway Gov cam 01", "Ahmedabad", "ahmedabad", "sg_highway", 23.07, 72.51, "live-ai"),
                    ]
                    now_ts = utcnow()
                    for i, row in enumerate(demo_path):
                        plate, cid, cname, place, city, area, lat, lng, src = row
                        con.execute(
                            "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (f"see-seed-{i}", plate, cid, cname, place, city, area, lat, lng, now_ts, src),
                        )
                con.commit()

    def purge_all_data(self) -> None:
        """Purge all operational, alert, cyber, and event records cleanly."""
        with self._lock:
            tables = [
                "watchlist", "sightings", "events", "alerts", "jobs",
                "hashes", "cyber", "evidence", "messages", "persons", "vehicle_detections"
            ]
            with self.connection() as con:
                for tbl in tables:
                    con.execute(f"DELETE FROM {tbl};")
                con.execute("DELETE FROM cameras WHERE kind='registry' OR id LIKE 'gov-%';")
                con.commit()
            with open(os.path.join(settings.data_dir, ".no_seed"), "w") as f:
                f.write("")


db_manager = DatabaseManager()
