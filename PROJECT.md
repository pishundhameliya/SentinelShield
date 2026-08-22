# Project: SentinelShield (Sentinel-X Gujarat) — Production Upgrade & Forensic Roadmap

## Architecture
- **Framework**: FastAPI (Python 3.10+) with Uvicorn and modular domain routing.
- **Database**: SQLite in WAL mode (`PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=10000;`, `PRAGMA synchronous=NORMAL;`), with serialized writes via `threading.RLock()` and concurrent non-blocking readers.
- **Domain Subsystems**:
  - `core/`: Database connection management, schema initialization, autonomous maintenance daemon (`DatabaseMaintenanceDaemon`), composite indexes, `sightings_archive`, shared thread-safe application state (`core/state.py`).
  - `modules/streaming/`: MJPEG generator with hardware-accelerated decode probe and exponential backoff auto-reconnect; `StreamWorkerPool` for multi-core camera partitioning and adaptive backpressure; `ai_daemon.py` background guardian.
  - `modules/integrity/`: SHA-256 rolling hash chains (`HashChainManager`, `BulkHashBatcher`), zero-allocation tamper detector (`MultiCameraTamperPool`), and vectorized LSB frame watermarking (`lsb_watermark.py`).
  - `modules/evidence/`: Evidence vault sealing (`EvidenceVaultService`), courtroom forensic PDF brief builder (`pdf_builder.py` with Section 65B/BSA 2023 compliance & QR codes), and deterministic SHA-256 metadata verification.
  - `modules/alerts/`: Threat fusion and localization, alert cooldown deduplication, and asynchronous operator dispatch webhook engine (`webhooks.py`) with HMAC SHA-256 signing and circuit-breaking.
  - `modules/registry/`: Gujarat camera estate definitions across 15 zones, camera CRUD, and validated transactional CSV bulk importer (`importer.py`) with coordinate bounds checking.
  - `modules/vision/`, `modules/tracking/`, `modules/cyber/`, `modules/twin/`, `modules/chat/`, `modules/relay/`, `modules/auth/`: Core analytical subsystems.

---

## Feature Inventory & Status

| # | Feature | Description | Milestone | Status |
|---|---------|-------------|-----------|--------|
| 1 | DB WAL Checkpoint Truncation | Automated `PRAGMA wal_checkpoint(TRUNCATE);` execution to prevent unbounded WAL file growth under 200-stream loads | M1 | DONE |
| 2 | DB Periodic Vacuuming & Optimize | Background daemon performing periodic `PRAGMA optimize;` and space maintenance without blocking active readers/writers | M1 | DONE |
| 3 | Sighting Log 90-Day Archiving | Automated archival of vehicle `sightings` older than 90 days into `sightings_archive` with composite indexing | M1 | DONE |
| 4 | Stream Exponential Backoff Reconnection | Auto-reconnection loop with exponential backoff (1s, 2s, 4s, 8s, 16s) for dropped RTSP/video feeds in MJPEG generator | M1 | DONE |
| 5 | Hardware-Assisted Video Decode Probing | Probing CUDA/NVDEC/MSMF/D3D11 hardware acceleration flags with graceful fallback to software CPU decoding in VideoCapture | M2 | DONE |
| 6 | Dynamic Frame-Dropping Backpressure | Adaptive client latency tracking and frame-dropping backpressure for lagging mobile/web viewers during 200-stream load | M2 | DONE |
| 7 | Court-Ready Evidence PDF Brief | Section 65B / BSA 2023 compliant PDF evidence certificate with Gujarat Police banner, incident metadata, timeline, and QR code | M3 | DONE |
| 8 | Deterministic SHA-256 Verification | Canonical sorted JSON hashing and verification endpoint (`/api/evidence/verify`) for tamper-evident validation | M3 | DONE |
| 9 | Vectorized LSB Frame Watermarking | Low-overhead (<15 µs) LSB blue-channel frame timestamping with magic bytes, camera hash, and CRC32 tamper check | M3 | DONE |
| 10 | Operator Dispatch Webhooks | Asynchronous alert dispatch webhook worker with HMAC SHA-256 signing, 3-attempt exponential backoff, and circuit-breaker | M4 | DONE |
| 11 | Estate CSV Bulk Importer | Validated CSV camera estate bulk importer with header aliasing, Gujarat coordinate bounds check (Lat [20.0, 24.8], Lng [68.0, 74.5]), and atomic transactions | M4 | DONE |
| 12 | App Lifespan Daemon Orchestration | Clean startup and shutdown lifecycle management in `app.py` for Database Maintenance Daemon and Webhook Worker Daemon | M4 | DONE |
| 13 | Comprehensive E2E Testing Suite | Requirements-driven multi-tier opaque-box test suite (13 suites) validating all production upgrade features and AST lints | M5 | DONE |
| 14 | 200-Stream Benchmark & Scaling Hardening | High-density benchmark execution ($>28,000\text{ FPS}$, latency $<0.04\text{ ms}$) on a single workstation | M5 | DONE |
| 15 | CostWise MCP Automated Provisioning | Zero-touch installer (`scripts/setup_costwise.py`), `.mcp.json`, and `.cursor/mcp.json` configs | MCP | DONE |
| 16 | Antigravity Optimization Package | `.gemini/settings.json`, `.gemini/rules/`, `.gemini/commands/`, and root `GEMINI.md` | AGY | DONE |
| 17 | CI/CD GitHub Actions Workflow | Multi-platform (Ubuntu, Windows) and multi-version (Python 3.11, 3.12, 3.13) matrix testing in `.github/workflows/ci.yml` | CI | DONE |

---

## Milestone Execution Summary

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Autonomous Database & Stream Self-Healing | DB indexes, 90-day sightings archive, WAL checkpoint/vacuum daemon, RTSP exponential backoff reconnect | none | **100% COMPLETE** |
| M2 | High-Density Video Acceleration & Adaptive Backpressure | Hardware-assisted video decode probing, dynamic client frame-dropping backpressure, zero-alloc tamper pools | M1 | **100% COMPLETE** |
| M3 | Courtroom Forensic Evidence Brief Generation | Section 65B/BSA PDF brief builder with QR code, deterministic SHA-256 verification, LSB frame watermarking | M1 | **100% COMPLETE** |
| M4 | Operator Dispatch & Estate Bulk Importer | Webhooks database schema, async webhook worker with HMAC & backoff, CSV bulk importer with Gujarat bounds check, app lifespan hooks | M1 | **100% COMPLETE** |
| M5 | E2E Verification & CI/CD Hardening | 13 test suites, GitHub Actions matrix workflow, AST syntax linting, 200-stream scaling benchmark | M1–M4 | **100% COMPLETE** |

---

## Universal Verification Command
```bash
python verify.py
```
Outputs automated test results across all 13 test suites and benchmarks with execution durations and pass/fail metrics.
