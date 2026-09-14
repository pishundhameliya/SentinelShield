# SentinelShield — Claude Code Instructions

## Overview
SentinelShield (Sentinel-X Gujarat) is an enterprise CCTV surveillance, digital twin, GIS, computer vision, cybersecurity, and courtroom forensics platform optimized for real-time execution across 200+ camera streams on a single workstation.

## Essential Commands
- **Run Verification & Tests**: `python verify.py`
- **Run 200-Stream Benchmark**: `python sentinelshield/tests/benchmark_200_streams.py`
- **Run FastAPI Server**: `uvicorn sentinelshield.app:app --host 0.0.0.0 --port 8000`

## Architecture & Code Map
- `sentinelshield/app.py`: FastAPI composer with lifespan management for `db_maintenance_daemon`, `ai_guardian_daemon`, and `webhook_dispatch_service`.
- `sentinelshield/core/database.py`: Thread-safe SQLite WAL manager, schema migrations, `DatabaseMaintenanceDaemon`, `sightings_archive`, `truncate_wal()`.
- `sentinelshield/core/state.py`: Thread-safe application state behind `threading.RLock()` and `asyncio.Lock()`.
- `sentinelshield/core/security.py`: `SessionManager` with timing-safe `secrets.compare_digest`.
- `sentinelshield/modules/`: 12 isolated domain subsystems (`vision`, `integrity`, `evidence`, `streaming`, `alerts`, `registry`, `tracking`, `twin`, `cyber`, `chat`, `relay`, `auth`).

## Key Development Invariants
1. **Concurrency & Thread Safety**: All shared state is strictly in `core/state.py`.
2. **Database Queries**: Must use `db_manager.query_rows` / `db_manager.query_one` / `db_manager.execute` with parameterized queries (`?`).
3. **No Monolithic Bloat**: Keep business logic in `modules/<domain>/service.py`, HTTP routes in `modules/<domain>/router.py`, and pure utilities in specific helper files.
4. **Forensic Integrity**: Maintain Section 65B/BSA 2023 compliance with canonical sorted JSON SHA-256 verification and LSB frame watermarking.
5. **Zero Regressions**: Verify existing tests and backward compatibility in `engine.py` and `gujarat_estate.py`.
