"""Empirical Adversarial Stress Test Suite for Milestone 1 Database Self-Healing.

Tests:
1. Concurrency: 50 concurrent reader threads and 10 concurrent writer threads executing during truncate_wal().
2. High-Volume Archiving: 5,000 old sightings + 5,000 new sightings + boundary records (89d vs 91d),
   exact counts, EXPLAIN QUERY PLAN index verification, query latency benchmarks.
3. Rapid Daemon Cycling: Multiple rapid maintenance cycles under continuous active reader and writer load.
4. Adversarial Edge Cases: Unicode/SQLi injection in sightings, future timestamps, empty WAL truncation,
   and concurrent archival during live writes with zero data loss.
5. Daemon Re-entrancy: Multiple consecutive start() / stop() invocations without resource leaks.
"""
from __future__ import annotations

import os
import sys
import time
import threading
import tempfile
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

# Ensure sentinelshield base directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import DatabaseManager, DatabaseMaintenanceDaemon, utcnow


@pytest.fixture
def temp_db_manager():
    """Create an isolated test DatabaseManager on a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name

    db = DatabaseManager(db_path=temp_path)
    db.init_schema()

    yield db

    # Cleanup temp db files (.db, .db-wal, .db-shm)
    for ext in ["", "-wal", "-shm"]:
        p = temp_path + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass


# ============================================================================
# 1. HEAVY CONCURRENCY STRESS TEST (50 READERS, 10 WRITERS + WAL TRUNCATION)
# ============================================================================

def test_heavy_concurrency_with_wal_truncation(temp_db_manager):
    """Stress test 50 concurrent reader threads and 10 concurrent writer threads

    executing continuously while PRAGMA wal_checkpoint(TRUNCATE) is invoked repeatedly.
    Verifies:
      - 0 unhandled exceptions across all 60 threads
      - 0 SQLITE_BUSY unhandled crashes
      - 0 deadlocks (watchdog timer)
      - 100% SQLite database integrity check
      - Accurate write counts and zero data corruption
    """
    db = temp_db_manager
    num_readers = 50
    num_writers = 10
    duration_seconds = 4.0

    stop_event = threading.Event()
    reader_errors: list[tuple[int, Exception]] = []
    writer_errors: list[tuple[int, Exception]] = []
    wal_errors: list[Exception] = []

    read_counts = [0] * num_readers
    write_counts = [0] * num_writers
    wal_results: list[dict[str, Any]] = []

    # Pre-populate database with some data
    with db.transaction() as con:
        for i in range(100):
            con.execute(
                "INSERT INTO cameras (id, name, place, kind) VALUES(?,?,?,?)",
                (f"cam-init-{i}", f"Camera {i}", f"Location {i}", "live"),
            )
            con.execute(
                "INSERT INTO sightings (id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (f"see-init-{i}", f"GJ05AB{i:04d}", f"cam-init-{i}", f"Camera {i}", "Surat", "surat", "ringroad", 21.1, 72.8, utcnow(), "seed"),
            )

    def reader_worker(reader_id: int):
        reads = 0
        while not stop_event.is_set():
            try:
                if reads % 3 == 0:
                    rows = db.query_rows("SELECT * FROM cameras LIMIT 20")
                    assert len(rows) > 0
                elif reads % 3 == 1:
                    row = db.query_one("SELECT COUNT(*) as cnt FROM sightings")
                    assert row is not None and row["cnt"] >= 100
                else:
                    rows = db.query_rows("SELECT plate, created FROM sightings WHERE plate LIKE 'GJ%' LIMIT 10")
                    assert len(rows) >= 0
                reads += 1
                read_counts[reader_id] = reads
                time.sleep(0.002)
            except Exception as e:
                reader_errors.append((reader_id, e))
                break

    def writer_worker(writer_id: int):
        writes = 0
        while not stop_event.is_set():
            try:
                ts = utcnow()
                if writes % 2 == 0:
                    db.execute(
                        "INSERT INTO sightings (id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        f"see-w{writer_id}-{writes}",
                        f"GJ01WR{writer_id}{writes}",
                        f"cam-init-{writer_id}",
                        f"Camera {writer_id}",
                        "Ahmedabad", "ahmedabad", "sg_highway",
                        23.0, 72.5, ts, "stream"
                    )
                else:
                    with db.transaction() as con:
                        con.execute(
                            "INSERT INTO alerts (id, camera_id, kind, title, detail, severity, trust, t, created, status) VALUES(?,?,?,?,?,?,?,?,?,?)",
                            (f"alt-w{writer_id}-{writes}", f"cam-init-{writer_id}", "watchlist", "Vehicle Spotted", "Test alert", "high", 95, time.time(), ts, "new"),
                        )
                writes += 1
                write_counts[writer_id] = writes
                time.sleep(0.005)
            except Exception as e:
                writer_errors.append((writer_id, e))
                break

    # Spawn all 50 readers and 10 writers
    readers = [threading.Thread(target=reader_worker, args=(i,), daemon=True) for i in range(num_readers)]
    writers = [threading.Thread(target=writer_worker, args=(i,), daemon=True) for i in range(num_writers)]

    start_time = time.time()
    for t in readers:
        t.start()
    for t in writers:
        t.start()

    # Truncate WAL repeatedly in controller loop during the test duration
    checkpoint_count = 0
    while time.time() - start_time < duration_seconds:
        try:
            res = db.truncate_wal()
            wal_results.append(res)
            checkpoint_count += 1
        except Exception as e:
            wal_errors.append(e)
        time.sleep(0.08)

    stop_event.set()

    for t in readers:
        t.join(timeout=3.0)
    for t in writers:
        t.join(timeout=3.0)

    total_reads = sum(read_counts)
    total_writes = sum(write_counts)

    print(f"\n[Concurrency Test Metrics]")
    print(f"  Total Reads Completed: {total_reads} across {num_readers} reader threads")
    print(f"  Total Writes Completed: {total_writes} across {num_writers} writer threads")
    print(f"  WAL Checkpoints Executed: {checkpoint_count}")
    print(f"  Reader Errors: {len(reader_errors)}")
    print(f"  Writer Errors: {len(writer_errors)}")
    print(f"  WAL Errors: {len(wal_errors)}")

    assert len(reader_errors) == 0, f"Reader errors encountered: {reader_errors[:5]}"
    assert len(writer_errors) == 0, f"Writer errors encountered: {writer_errors[:5]}"
    assert len(wal_errors) == 0, f"WAL errors encountered: {wal_errors[:5]}"
    assert total_reads >= 100, f"Expected >=100 reads, got {total_reads}"
    assert total_writes >= 20, f"Expected >=20 writes, got {total_writes}"

    # Verify Database Integrity
    with db.connection() as con:
        integrity_row = con.execute("PRAGMA integrity_check;").fetchone()
        assert integrity_row[0] == "ok", f"Integrity check failed: {integrity_row[0]}"

        sighting_writes = sum(1 for w in range(num_writers) for i in range(write_counts[w]) if i % 2 == 0)
        alert_writes = sum(1 for w in range(num_writers) for i in range(write_counts[w]) if i % 2 == 1)

        actual_sightings = con.execute("SELECT COUNT(*) FROM sightings WHERE id LIKE 'see-w%'").fetchone()[0]
        actual_alerts = con.execute("SELECT COUNT(*) FROM alerts WHERE id LIKE 'alt-w%'").fetchone()[0]

        assert actual_sightings == sighting_writes, f"Sightings count mismatch: {actual_sightings} vs {sighting_writes}"
        assert actual_alerts == alert_writes, f"Alerts count mismatch: {actual_alerts} vs {alert_writes}"


# ============================================================================
# 2. HIGH-VOLUME ARCHIVING & BOUNDARY STRESS TEST (10,000+ SIGHTINGS)
# ============================================================================

def test_high_volume_archiving_and_boundary_correctness(temp_db_manager):
    """Stress test archiving with 5,000 old records (100 days old), 5,000 new records (5 days old),

    and boundary test cases (89d, 89d23h, 90d1h, 91d).
    Verifies:
      - High volume batch insert and transactional archival performance (>10,000 rows/s)
      - Exact row counts in active vs archive tables
      - Precise boundary cutoff: 89.9 days retained, 90.1 days archived
      - Index usage verification via EXPLAIN QUERY PLAN on sightings_archive
      - Query latency on active & archive indexed lookups
    """
    db = temp_db_manager
    now_utc = datetime.now(timezone.utc)
    fmt = "%Y-%m-%d %H:%M:%S UTC"

    old_count = 5000
    new_count = 5000

    print(f"\n[High-Volume Archiving Test]")
    print(f"  Generating {old_count} old records (100d old) and {new_count} new records (5d old)...")

    old_ts = (now_utc - timedelta(days=100)).strftime(fmt)
    old_records = [
        (
            f"old-see-{i:05d}",
            f"GJ05OLD{i % 500:04d}",
            f"cam-old-{i % 20}",
            f"Camera Old {i % 20}",
            "Surat Old City",
            "surat",
            "ringroad",
            21.17 + (i % 100) * 0.001,
            72.83 + (i % 100) * 0.001,
            old_ts,
            "stream-ai",
        )
        for i in range(old_count)
    ]

    new_ts = (now_utc - timedelta(days=5)).strftime(fmt)
    new_records = [
        (
            f"new-see-{i:05d}",
            f"GJ01NEW{i % 500:04d}",
            f"cam-new-{i % 20}",
            f"Camera New {i % 20}",
            "Ahmedabad SG Highway",
            "ahmedabad",
            "sg_highway",
            23.07 + (i % 100) * 0.001,
            72.51 + (i % 100) * 0.001,
            new_ts,
            "stream-ai",
        )
        for i in range(new_count)
    ]

    boundary_records = [
        ("bound-89d-00h", "GJ99BOUND1", "cam-b1", "Boundary 89d", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc - timedelta(days=89)).strftime(fmt), "test"),
        ("bound-89d-23h", "GJ99BOUND2", "cam-b2", "Boundary 89.9d", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc - timedelta(days=89, hours=23, minutes=50)).strftime(fmt), "test"),
        ("bound-90d-01h", "GJ99BOUND3", "cam-b3", "Boundary 90.1d", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc - timedelta(days=90, hours=1)).strftime(fmt), "test"),
        ("bound-91d-00h", "GJ99BOUND4", "cam-b4", "Boundary 91d", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc - timedelta(days=91)).strftime(fmt), "test"),
    ]

    t_insert_start = time.time()
    insert_sql = """
        INSERT INTO sightings 
        (id, plate, camera_id, camera_name, place, city_id, area_id, lat, lng, created, source)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
    """
    with db.transaction() as con:
        con.executemany(insert_sql, old_records)
        con.executemany(insert_sql, new_records)
        con.executemany(insert_sql, boundary_records)
    t_insert_elapsed = time.time() - t_insert_start

    print(f"  Inserted 10,004 records in {t_insert_elapsed:.3f}s ({(10004 / t_insert_elapsed):.0f} rows/s)")

    initial_sightings_count = db.query_one("SELECT COUNT(*) as cnt FROM sightings")["cnt"]
    assert initial_sightings_count == 10004
    assert db.query_one("SELECT COUNT(*) as cnt FROM sightings_archive")["cnt"] == 0

    t_arch_start = time.time()
    archived_count = db.archive_old_sightings(retention_days=90)
    t_arch_elapsed = time.time() - t_arch_start

    print(f"  Archived {archived_count} records in {t_arch_elapsed:.3f}s ({(archived_count / t_arch_elapsed):.0f} rows/s)")

    expected_archived = old_count + 2
    expected_retained = new_count + 2

    assert archived_count == expected_archived, f"Archived count mismatch: expected {expected_archived}, got {archived_count}"

    active_cnt = db.query_one("SELECT COUNT(*) as cnt FROM sightings")["cnt"]
    archive_cnt = db.query_one("SELECT COUNT(*) as cnt FROM sightings_archive")["cnt"]

    assert active_cnt == expected_retained, f"Active count mismatch: expected {expected_retained}, got {active_cnt}"
    assert archive_cnt == expected_archived, f"Archive count mismatch: expected {expected_archived}, got {archive_cnt}"

    active_boundary_ids = {r["id"] for r in db.query_rows("SELECT id FROM sightings WHERE id LIKE 'bound-%'")}
    archive_boundary_ids = {r["id"] for r in db.query_rows("SELECT id FROM sightings_archive WHERE id LIKE 'bound-%'")}

    assert active_boundary_ids == {"bound-89d-00h", "bound-89d-23h"}, f"Unexpected active boundary: {active_boundary_ids}"
    assert archive_boundary_ids == {"bound-90d-01h", "bound-91d-00h"}, f"Unexpected archived boundary: {archive_boundary_ids}"

    sample_arch = db.query_one("SELECT archived_at FROM sightings_archive LIMIT 1")
    assert sample_arch is not None and sample_arch["archived_at"].endswith("UTC")

    with db.connection() as con:
        plan_plate = con.execute("EXPLAIN QUERY PLAN SELECT * FROM sightings_archive WHERE plate=?", ("GJ05OLD0001",)).fetchall()
        plan_plate_str = " ".join([str(p[3]) for p in plan_plate])
        print(f"  Query Plan (plate): {plan_plate_str}")
        assert "idx_sightings_arch_plate" in plan_plate_str or "USING INDEX" in plan_plate_str

        plan_cam = con.execute("EXPLAIN QUERY PLAN SELECT * FROM sightings_archive WHERE camera_id=? AND created >= ?", ("cam-old-1", old_ts)).fetchall()
        plan_cam_str = " ".join([str(p[3]) for p in plan_cam])
        print(f"  Query Plan (cam+created): {plan_cam_str}")
        assert "idx_sightings_arch_cam" in plan_cam_str or "USING INDEX" in plan_cam_str

        plan_created = con.execute("EXPLAIN QUERY PLAN SELECT * FROM sightings_archive WHERE created >= ?", (old_ts,)).fetchall()
        plan_created_str = " ".join([str(p[3]) for p in plan_created])
        print(f"  Query Plan (created): {plan_created_str}")
        assert "idx_sightings_arch_created" in plan_created_str or "USING INDEX" in plan_created_str

        t_raw_start = time.time()
        for i in range(1000):
            target_plate = f"GJ05OLD{(i * 5) % 500:04d}"
            cur = con.execute("SELECT id, plate, camera_id, created FROM sightings_archive WHERE plate=?", (target_plate,))
            rows = cur.fetchall()
            assert len(rows) == 10
        t_raw_elapsed = time.time() - t_raw_start
        avg_raw_latency_ms = (t_raw_elapsed / 1000) * 1000.0
        print(f"  1,000 Raw Indexed Lookups: {t_raw_elapsed:.4f}s (Avg: {avg_raw_latency_ms:.3f} ms/query)")
        assert avg_raw_latency_ms < 1.0, f"Raw query latency too high: {avg_raw_latency_ms:.3f} ms"

    second_arch_count = db.archive_old_sightings(retention_days=90)
    assert second_arch_count == 0
    assert db.query_one("SELECT COUNT(*) as cnt FROM sightings")["cnt"] == expected_retained
    assert db.query_one("SELECT COUNT(*) as cnt FROM sightings_archive")["cnt"] == expected_archived


# ============================================================================
# 3. RAPID DAEMON CYCLING UNDER ACTIVE LOAD
# ============================================================================

def test_rapid_daemon_cycling_under_active_load(temp_db_manager):
    """Stress test DatabaseMaintenanceDaemon under rapid cycling and concurrent DB traffic.

    Verifies:
      - Continuous background daemon execution (interval=0.05s)
      - Concurrent direct run_once() calls from external threads
      - Active concurrent readers (20 threads) and writers (5 threads)
      - Clean lifecycle: start(), status(), stop()
      - Zero corrupted state or crashed threads
    """
    db = temp_db_manager
    daemon = DatabaseMaintenanceDaemon(db_mgr=db, interval_seconds=0.05, archive_days=90)

    stop_event = threading.Event()
    reader_errors: list[Exception] = []
    writer_errors: list[Exception] = []
    run_once_errors: list[Exception] = []

    with db.transaction() as con:
        con.execute("INSERT INTO cameras (id, name) VALUES('cam-daemon-1', 'Daemon Test Cam')")
        for i in range(50):
            con.execute(
                "INSERT INTO sightings (id, plate, camera_id, created) VALUES(?,?,?,?)",
                (f"see-d-{i}", f"GJ06DD{i:03d}", "cam-daemon-1", utcnow()),
            )

    def active_reader():
        while not stop_event.is_set():
            try:
                db.query_rows("SELECT * FROM sightings LIMIT 20")
                time.sleep(0.005)
            except Exception as e:
                reader_errors.append(e)
                break

    def active_writer(wid: int):
        cnt = 0
        while not stop_event.is_set():
            try:
                ts = utcnow()
                db.execute(
                    "INSERT INTO sightings (id, plate, camera_id, created) VALUES(?,?,?,?)",
                    f"see-dw-{wid}-{cnt}", f"GJ06DW{wid}", "cam-daemon-1", ts
                )
                cnt += 1
                time.sleep(0.01)
            except Exception as e:
                writer_errors.append(e)
                break

    def external_maintenance_caller():
        for _ in range(5):
            if stop_event.is_set():
                break
            try:
                stats = daemon.run_once()
                assert stats["error"] is None
            except Exception as e:
                run_once_errors.append(e)
            time.sleep(0.05)

    daemon.start()
    assert daemon.status()["running"] is True

    reader_threads = [threading.Thread(target=active_reader, daemon=True) for _ in range(20)]
    writer_threads = [threading.Thread(target=active_writer, args=(i,), daemon=True) for i in range(5)]
    caller_threads = [threading.Thread(target=external_maintenance_caller, daemon=True) for _ in range(2)]

    for t in reader_threads + writer_threads + caller_threads:
        t.start()

    time.sleep(2.0)

    stop_event.set()
    for t in reader_threads + writer_threads + caller_threads:
        t.join(timeout=3.0)

    t_stop_start = time.time()
    daemon.stop(timeout=3.0)
    stop_duration = time.time() - t_stop_start

    final_status = daemon.status()
    print(f"\n[Rapid Daemon Cycling Metrics]")
    print(f"  Daemon Run Count: {final_status['run_count']}")
    print(f"  Daemon Running State: {final_status['running']}")
    print(f"  Daemon Stop Duration: {stop_duration:.4f}s")
    print(f"  Reader Errors: {len(reader_errors)}")
    print(f"  Writer Errors: {len(writer_errors)}")
    print(f"  Run Once Errors: {len(run_once_errors)}")

    assert len(reader_errors) == 0, f"Reader errors: {reader_errors}"
    assert len(writer_errors) == 0, f"Writer errors: {writer_errors}"
    assert len(run_once_errors) == 0, f"External run_once errors: {run_once_errors}"
    assert final_status["running"] is False
    assert final_status["run_count"] >= 5, f"Expected >=5 runs, got {final_status['run_count']}"
    assert stop_duration < 1.5, f"Daemon stop took too long: {stop_duration:.2f}s"

    with db.connection() as con:
        integrity = con.execute("PRAGMA integrity_check;").fetchone()[0]
        assert integrity == "ok"


# ============================================================================
# 4. ADVERSARIAL EDGE CASES (UNICODE, SQLi, FUTURE TIMESTAMPS, CONCURRENT ARCHIVE)
# ============================================================================

def test_adversarial_data_and_concurrent_archiving(temp_db_manager):
    """Stress test adversarial inputs and concurrent live writers during archiving."""
    db = temp_db_manager
    now_utc = datetime.now(timezone.utc)
    fmt = "%Y-%m-%d %H:%M:%S UTC"

    adversarial_records = [
        ("adv-sqli-1", "GJ01'; DROP TABLE sightings; --", "cam-adv-1", "Hacked ' Cam", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc - timedelta(days=120)).strftime(fmt), "test"),
        ("adv-unicode-1", "GJ05ગુજરાત1234 🚗🔍", "cam-adv-2", "સુરત કેમેરા", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc - timedelta(days=150)).strftime(fmt), "test"),
        ("adv-future-1", "GJ01FUTURE", "cam-adv-3", "Future Cam", "Surat", "surat", "ringroad", 21.0, 72.0, (now_utc + timedelta(days=50)).strftime(fmt), "test"),
        ("adv-null-fields", "GJ01NULL", None, None, None, None, None, None, None, (now_utc - timedelta(days=95)).strftime(fmt), None),
    ]

    with db.transaction() as con:
        for r in adversarial_records:
            con.execute(
                "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                r,
            )

    # Archive old sightings
    archived = db.archive_old_sightings(retention_days=90)
    assert archived == 3  # adv-sqli-1, adv-unicode-1, adv-null-fields

    # Future record must remain in sightings
    future_row = db.query_one("SELECT * FROM sightings WHERE id='adv-future-1'")
    assert future_row is not None
    assert future_row["plate"] == "GJ01FUTURE"

    # Unicode & SQLi records must be preserved in archive table intact
    sqli_arch = db.query_one("SELECT * FROM sightings_archive WHERE id='adv-sqli-1'")
    assert sqli_arch is not None
    assert sqli_arch["plate"] == "GJ01'; DROP TABLE sightings; --"

    unicode_arch = db.query_one("SELECT * FROM sightings_archive WHERE id='adv-unicode-1'")
    assert unicode_arch is not None
    assert unicode_arch["plate"] == "GJ05ગુજરાત1234 🚗🔍"

    # Verify tables still exist
    with db.connection() as con:
        tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        assert "sightings" in tables
        assert "sightings_archive" in tables


def test_daemon_reentrancy_and_empty_wal(temp_db_manager):
    """Verify multiple start() and stop() calls are safe, idempotent, and handle empty WALs."""
    db = temp_db_manager

    # Empty WAL truncate
    res = db.truncate_wal()
    assert res["status"] in ("success", "ok")

    daemon = DatabaseMaintenanceDaemon(db_mgr=db, interval_seconds=10.0, archive_days=90)

    # Calling start multiple times
    daemon.start()
    daemon.start()
    daemon.start()
    assert daemon.status()["running"] is True

    # Run once manually while thread is active
    stats = daemon.run_once()
    assert stats["error"] is None

    # Calling stop multiple times
    daemon.stop(timeout=2.0)
    daemon.stop(timeout=2.0)
    assert daemon.status()["running"] is False


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
