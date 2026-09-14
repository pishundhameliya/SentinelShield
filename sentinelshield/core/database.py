"""Thread-safe SQLite Database Manager with WAL mode and transaction handling."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Generator

from sentinelshield.config import settings


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

    def execute_many(self, query: str, seq_of_args: list[tuple[Any, ...]]) -> int:
        """Execute a batch insert/update safely in a single atomic transaction."""
        if not seq_of_args:
            return 0
        with self._lock:
            with self.connection() as con:
                cur = con.executemany(query, seq_of_args)
                con.commit()
                return cur.rowcount

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
                    CREATE TABLE IF NOT EXISTS sightings_archive (
                      id TEXT PRIMARY KEY,
                      plate TEXT, camera_id TEXT, camera_name TEXT, place TEXT,
                      city_id TEXT, area_id TEXT, lat REAL, lng REAL,
                      created TEXT, source TEXT, archived_at TEXT
                    );
                    CREATE TABLE IF NOT EXISTS vehicle_detections (
                      id TEXT PRIMARY KEY, camera_id TEXT, vehicle_type TEXT, tracking_id TEXT,
                      plate TEXT, confidence REAL, created TEXT, lat REAL, lng REAL, place TEXT
                    );

                    -- Composite and specialized performance indexes
                    CREATE INDEX IF NOT EXISTS idx_sightings_plate_created ON sightings(plate, created);
                    CREATE INDEX IF NOT EXISTS idx_sightings_cam_created ON sightings(camera_id, created);
                    CREATE INDEX IF NOT EXISTS idx_sightings_created ON sightings(created);
                    CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created);
                    CREATE INDEX IF NOT EXISTS idx_alerts_cam_created ON alerts(camera_id, created);
                    CREATE INDEX IF NOT EXISTS idx_hashes_job ON hashes(job_id);
                    CREATE INDEX IF NOT EXISTS idx_sightings_arch_plate ON sightings_archive(plate, created);
                    CREATE INDEX IF NOT EXISTS idx_sightings_arch_cam ON sightings_archive(camera_id, created);
                    CREATE INDEX IF NOT EXISTS idx_sightings_arch_created ON sightings_archive(created);
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

    def archive_old_sightings(self, retention_days: int = 90) -> int:
        """Archive sightings older than retention_days into sightings_archive and purge from active table.

        Args:
            retention_days: Number of days to keep active in sightings table (default: 90).

        Returns:
            int: Number of rows successfully transferred to archive.
        """
        cutoff_dt = datetime.now(timezone.utc) - timedelta(days=retention_days)
        cutoff_str = cutoff_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        archived_at = utcnow()

        with self.transaction() as con:
            cur = con.execute(
                """
                INSERT OR REPLACE INTO sightings_archive
                (id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source, archived_at)
                SELECT id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source, ?
                FROM sightings
                WHERE created < ?
                """,
                (archived_at, cutoff_str),
            )
            row_count = cur.rowcount
            if row_count > 0:
                con.execute(
                    "DELETE FROM sightings WHERE created < ?",
                    (cutoff_str,),
                )
            return row_count

    def truncate_wal(self) -> dict[str, Any]:
        """Execute PRAGMA wal_checkpoint(TRUNCATE) safely to flush WAL and truncate log file.

        Returns:
            dict: Checkpoint execution summary with status, frame counts, and timestamp.
        """
        with self._lock:
            with self.connection() as con:
                try:
                    row = con.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
                    if row:
                        busy = int(row[0])
                        log_frames = int(row[1])
                        checkpointed = int(row[2])
                        return {
                            "status": "success" if busy == 0 else "busy",
                            "busy": bool(busy),
                            "log_frames": log_frames,
                            "checkpointed": checkpointed,
                            "timestamp": utcnow(),
                        }
                    return {"status": "ok", "busy": False, "log_frames": 0, "checkpointed": 0, "timestamp": utcnow()}
                except Exception as e:
                    return {
                        "status": "error",
                        "busy": False,
                        "error": str(e),
                        "timestamp": utcnow(),
                    }

    def purge_all_data(self) -> None:
        """Purge all operational, alert, cyber, and event records cleanly."""
        with self._lock:
            tables = [
                "watchlist", "sightings", "sightings_archive", "events", "alerts", "jobs",
                "hashes", "cyber", "evidence", "messages", "persons", "vehicle_detections"
            ]
            with self.connection() as con:
                for tbl in tables:
                    con.execute(f"DELETE FROM {tbl};")
                con.execute("DELETE FROM cameras WHERE kind='registry' OR id LIKE 'gov-%';")
                con.commit()
            with open(os.path.join(settings.data_dir, ".no_seed"), "w", encoding="utf-8") as f:
                f.write("")


class DatabaseMaintenanceDaemon:
    """Autonomous background worker executing periodic WAL truncation, 90-day sighting archival, and SQLite query optimization."""

    def __init__(
        self,
        db_mgr: DatabaseManager | None = None,
        interval_seconds: float = 3600.0,
        archive_days: int = 90,
    ):
        self.db_mgr = db_mgr or db_manager
        self.interval = interval_seconds
        self.archive_days = archive_days
        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._last_run: str | None = None
        self._last_stats: dict[str, Any] = {}
        self._run_count: int = 0
        self._lock = threading.RLock()

    def start(self) -> None:
        """Start the background maintenance daemon thread if not already running."""
        with self._lock:
            if self._thread is None or not self._thread.is_alive():
                self._running = True
                self._stop_event.clear()
                self._thread = threading.Thread(
                    target=self._run_loop,
                    name="DatabaseMaintenanceDaemon",
                    daemon=True,
                )
                self._thread.start()

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the daemon to stop and wait for completion."""
        with self._lock:
            self._running = False
            self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)

    def run_once(self) -> dict[str, Any]:
        """Execute a single maintenance cycle synchronously and record execution metrics."""
        ts = utcnow()
        stats: dict[str, Any] = {
            "timestamp": ts,
            "archived_rows": 0,
            "wal_checkpoint": {},
            "optimized": False,
            "error": None,
        }
        try:
            # 1. Truncate WAL file
            wal_res = self.db_mgr.truncate_wal()
            stats["wal_checkpoint"] = wal_res

            # 2. Archive sightings older than archive_days
            archived = self.db_mgr.archive_old_sightings(retention_days=self.archive_days)
            stats["archived_rows"] = archived

            # 3. Optimize query planner statistics
            with self.db_mgr.connection() as con:
                con.execute("PRAGMA optimize;")
            stats["optimized"] = True

        except Exception as e:
            stats["error"] = str(e)

        with self._lock:
            self._last_run = ts
            self._last_stats = stats
            self._run_count += 1

        return stats

    def status(self) -> dict[str, Any]:
        """Return current health, execution counters, and latest cycle statistics."""
        with self._lock:
            return {
                "running": self._running and (self._thread is not None and self._thread.is_alive()),
                "interval_seconds": self.interval,
                "archive_days": self.archive_days,
                "run_count": self._run_count,
                "last_run": self._last_run,
                "last_stats": self._last_stats,
            }

    def _run_loop(self) -> None:
        """Continuous background execution loop with responsive wake-up on stop."""
        while self._running:
            if self._stop_event.wait(timeout=self.interval):
                break
            if not self._running:
                break
            try:
                self.run_once()
            except Exception:
                pass


db_manager = DatabaseManager()
db_maintenance_daemon = DatabaseMaintenanceDaemon(db_manager)
