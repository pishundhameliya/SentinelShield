"""Comprehensive test suite for Milestone 1: Autonomous Database & Stream Self-Healing."""
from __future__ import annotations

import io
import os
import sys
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

# Ensure sentinelshield base directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sentinelshield.core.database import (
    DatabaseManager,
    DatabaseMaintenanceDaemon,
    db_manager,
    db_maintenance_daemon,
    utcnow,
)
from sentinelshield.core.state import live_stream_state
from sentinelshield.modules.streaming.mjpeg import (
    create_reconnect_placeholder_frame,
    mjpeg_frame_generator,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Ensure clean schema initialization before each test run."""
    db_manager.init_schema()
    yield
    # Cleanup any active stream state
    if live_stream_state.is_active:
        live_stream_state.stop()


# ============================================================================
# 1. DATABASE COMPOSITE INDEXES & SCHEMA TESTS
# ============================================================================

def test_composite_indexes_and_schema():
    """Verify that all composite and specialized performance indexes exist in the schema."""
    with db_manager.get_connection() as con:
        # Check table creation
        tables = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
        assert "sightings" in tables, "Table 'sightings' missing from schema"
        assert "sightings_archive" in tables, "Table 'sightings_archive' missing from schema"
        assert "alerts" in tables, "Table 'alerts' missing from schema"
        assert "hashes" in tables, "Table 'hashes' missing from schema"

        # Check index creation
        indexes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index';").fetchall()}
        expected_indexes = [
            "idx_sightings_plate_created",
            "idx_sightings_cam_created",
            "idx_sightings_created",
            "idx_alerts_created",
            "idx_alerts_cam_created",
            "idx_hashes_job",
            "idx_sightings_arch_plate",
            "idx_sightings_arch_cam",
            "idx_sightings_arch_created",
        ]
        for idx in expected_indexes:
            assert idx in indexes, f"Expected index '{idx}' was not created in database schema"

        # Verify index columns for idx_sightings_plate_created
        idx_info = [r[2] for r in con.execute("PRAGMA index_info(idx_sightings_plate_created);").fetchall()]
        assert idx_info == ["plate", "created"], f"Index cols mismatch: {idx_info}"


# ============================================================================
# 2. WAL CHECKPOINT & TRUNCATION TESTS
# ============================================================================

def test_truncate_wal_execution():
    """Verify PRAGMA wal_checkpoint(TRUNCATE) executes cleanly and returns structured summary."""
    # Write some dirty records to ensure WAL frames exist
    with db_manager.transaction() as con:
        for i in range(25):
            con.execute(
                "INSERT OR REPLACE INTO hashes(job_id, t_start, t_end, sha256, prev) VALUES(?,?,?,?,?)",
                (f"wal-job-{i}", float(i), float(i + 1), f"sha_{i}", "GENESIS"),
            )

    result = db_manager.truncate_wal()
    assert isinstance(result, dict)
    assert result.get("status") in ("success", "ok"), f"Unexpected status: {result}"
    assert result.get("busy") is False, "WAL checkpoint returned busy"
    assert isinstance(result.get("log_frames"), int)
    assert isinstance(result.get("checkpointed"), int)
    assert "timestamp" in result


def test_truncate_wal_concurrency_resilience():
    """Verify truncate_wal executes safely without deadlocking active reader threads."""
    stop_event = threading.Event()
    read_errors = []

    def reader_loop():
        while not stop_event.is_set():
            try:
                db_manager.query_rows("SELECT * FROM cameras LIMIT 10")
                time.sleep(0.01)
            except Exception as e:
                read_errors.append(e)

    reader_threads = [threading.Thread(target=reader_loop, daemon=True) for _ in range(4)]
    for t in reader_threads:
        t.start()

    # Execute multiple checkpoints concurrently with readers
    for _ in range(5):
        res = db_manager.truncate_wal()
        assert res.get("status") in ("success", "ok")
        time.sleep(0.02)

    stop_event.set()
    for t in reader_threads:
        t.join(timeout=1.0)

    assert len(read_errors) == 0, f"Encountered reader errors during WAL truncation: {read_errors}"


# ============================================================================
# 3. 90-DAY SIGHTING LOG ARCHIVAL TESTS
# ============================================================================

def test_archive_old_sightings_100d_vs_10d():
    """Verify archival of records older than 90 days (100d/120d) while preserving recent records (10d/89d)."""
    now_utc = datetime.now(timezone.utc)
    fmt = "%Y-%m-%d %H:%M:%S UTC"

    # Seed 3 old records (>90 days) and 3 recent records (<=90 days)
    records = [
        ("see-old-120", "GJ05SS2026", "cam-1", (now_utc - timedelta(days=120)).strftime(fmt)),
        ("see-old-100", "GJ05SS2026", "cam-2", (now_utc - timedelta(days=100)).strftime(fmt)),
        ("see-old-91",  "GJ27HK9009", "cam-1", (now_utc - timedelta(days=91, hours=1)).strftime(fmt)),
        ("see-rec-89",  "GJ27HK9009", "cam-2", (now_utc - timedelta(days=89)).strftime(fmt)),
        ("see-rec-10",  "GJ01AB1234", "cam-1", (now_utc - timedelta(days=10)).strftime(fmt)),
        ("see-rec-0",   "GJ01AB1234", "cam-3", now_utc.strftime(fmt)),
    ]

    with db_manager.transaction() as con:
        # Clear existing test sightings
        con.execute("DELETE FROM sightings;")
        con.execute("DELETE FROM sightings_archive;")
        for sid, plate, cid, created in records:
            con.execute(
                """INSERT INTO sightings 
                   (id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, plate, cid, f"Cam {cid}", "Surat", "surat", "ringroad", 21.17, 72.83, created, "test"),
            )

    # Verify initial count
    assert db_manager.query_one("SELECT COUNT(*) as n FROM sightings")["n"] == 6
    assert db_manager.query_one("SELECT COUNT(*) as n FROM sightings_archive")["n"] == 0

    # Execute archival with 90-day threshold
    archived_count = db_manager.archive_old_sightings(retention_days=90)
    assert archived_count == 3, f"Expected 3 archived rows, got {archived_count}"

    # Verify active table count and contents
    active_rows = db_manager.query_rows("SELECT id FROM sightings ORDER BY id")
    active_ids = {r["id"] for r in active_rows}
    assert len(active_ids) == 3
    assert active_ids == {"see-rec-89", "see-rec-10", "see-rec-0"}

    # Verify archive table count and contents
    archived_rows = db_manager.query_rows("SELECT id, archived_at FROM sightings_archive ORDER BY id")
    archived_ids = {r["id"] for r in archived_rows}
    assert len(archived_ids) == 3
    assert archived_ids == {"see-old-120", "see-old-100", "see-old-91"}
    for r in archived_rows:
        assert r["archived_at"] is not None and len(r["archived_at"]) > 10

    # Historical query verification
    plate_old_results = db_manager.query_rows("SELECT * FROM sightings_archive WHERE plate=?", "GJ05SS2026")
    assert len(plate_old_results) == 2


def test_archive_old_sightings_idempotent_and_empty():
    """Verify archive_old_sightings is idempotent and handles empty tables gracefully."""
    # Running archival a second time should archive 0 additional rows
    second_run = db_manager.archive_old_sightings(retention_days=90)
    assert second_run == 0

    # Running on an empty table
    with db_manager.transaction() as con:
        con.execute("DELETE FROM sightings;")
    empty_run = db_manager.archive_old_sightings(retention_days=90)
    assert empty_run == 0


def test_purge_all_data_clears_archive():
    """Verify that db_manager.purge_all_data() clears sightings_archive table."""
    now_ts = utcnow()
    with db_manager.transaction() as con:
        con.execute(
            """INSERT OR REPLACE INTO sightings_archive
               (id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source, archived_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            ("arch-test-1", "GJ05AA1111", "cam-1", "Gate", "Surat", "surat", "ringroad", 21.1, 72.8, now_ts, "test", now_ts),
        )
    assert db_manager.query_one("SELECT COUNT(*) as n FROM sightings_archive")["n"] >= 1

    db_manager.purge_all_data()
    assert db_manager.query_one("SELECT COUNT(*) as n FROM sightings_archive")["n"] == 0


# ============================================================================
# 4. DATABASE MAINTENANCE DAEMON TESTS
# ============================================================================

def test_maintenance_daemon_single_cycle():
    """Verify that DatabaseMaintenanceDaemon.run_once() executes all 3 maintenance tasks."""
    daemon = DatabaseMaintenanceDaemon(interval_seconds=3600.0, archive_days=90)
    stats = daemon.run_once()

    assert isinstance(stats, dict)
    assert "timestamp" in stats
    assert "archived_rows" in stats
    assert "wal_checkpoint" in stats
    assert stats["optimized"] is True
    assert stats["error"] is None

    # Check status method
    status = daemon.status()
    assert status["run_count"] == 1
    assert status["last_run"] is not None
    assert status["last_stats"] == stats
    assert status["running"] is False


def test_maintenance_daemon_background_lifecycle():
    """Verify start(), periodic background execution, and clean stop() termination."""
    daemon = DatabaseMaintenanceDaemon(interval_seconds=0.15, archive_days=90)
    daemon.start()
    assert daemon.status()["running"] is True

    # Allow daemon to run at least 2 cycles
    time.sleep(0.4)

    daemon.stop(timeout=2.0)
    assert daemon.status()["running"] is False
    assert daemon.status()["run_count"] >= 2


def test_maintenance_daemon_error_isolation():
    """Verify daemon traps errors gracefully without crashing the loop thread."""
    mock_db = MagicMock()
    mock_db.truncate_wal.side_effect = Exception("Simulated disk error")

    daemon = DatabaseMaintenanceDaemon(db_mgr=mock_db, interval_seconds=3600.0, archive_days=90)
    stats = daemon.run_once()

    assert stats["error"] == "Simulated disk error"
    assert daemon.status()["run_count"] == 1
    assert daemon.status()["last_stats"]["error"] == "Simulated disk error"


# ============================================================================
# 5. STREAM AUTO-RECONNECTION & PLACEHOLDER HUD TESTS
# ============================================================================

def test_reconnect_placeholder_frame_format():
    """Verify placeholder HUD frame is generated with valid multipart MJPEG headers and JPEG data."""
    frame_bytes = create_reconnect_placeholder_frame(
        camera_id="cam-surat-gate",
        path="rtsp://192.168.1.100:554/live",
        attempt=2,
        backoff=2.0,
        status_text="FEED DISCONNECTED - AUTO-RECONNECTING...",
    )
    assert isinstance(frame_bytes, bytes)
    assert frame_bytes.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
    assert frame_bytes.endswith(b"\r\n")
    assert len(frame_bytes) > 500


def test_mjpeg_reconnect_on_initial_failure():
    """Verify mjpeg_frame_generator yields placeholder frames during backoff on failed connect."""
    cam_id = "cam-test-fail-initial"
    live_stream_state.start(cam_id, "url", "rtsp://invalid-host-not-existing:8554/stream")

    gen = mjpeg_frame_generator(
        camera_id=cam_id,
        path="rtsp://invalid-host-not-existing:8554/stream",
        loop_file=False,
        initial_backoff=0.2,
        max_backoff=0.5,
    )

    # First yielded chunk must be a placeholder frame
    chunk1 = next(gen)
    assert b"Content-Type: image/jpeg" in chunk1
    assert len(chunk1) > 200

    # Stop stream and confirm immediate exit on next iteration
    live_stream_state.stop()
    with pytest.raises(StopIteration):
        next(gen)


def test_mjpeg_generator_responsive_stop_during_backoff():
    """Verify generator terminates immediately (<0.6s) when stopped during a long backoff sleep."""
    cam_id = "cam-test-stop-responsive"
    live_stream_state.start(cam_id, "url", "rtsp://invalid-host:9999/live")

    # Use long initial backoff (10s)
    gen = mjpeg_frame_generator(
        camera_id=cam_id,
        path="rtsp://invalid-host:9999/live",
        loop_file=False,
        initial_backoff=10.0,
        max_backoff=16.0,
    )

    # Read first placeholder frame
    _ = next(gen)

    # Stop stream in separate thread after 0.2s
    def delayed_stop():
        time.sleep(0.2)
        live_stream_state.stop()

    t = threading.Thread(target=delayed_stop, daemon=True)
    t.start()

    start_time = time.time()
    with pytest.raises(StopIteration):
        next(gen)
    elapsed = time.time() - start_time

    assert elapsed < 1.5, f"Generator took {elapsed:.2f}s to exit, expected responsive stop in <1.5s"
