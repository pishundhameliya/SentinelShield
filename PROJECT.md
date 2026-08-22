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

## Feature Inventory
Every feature identified during the survey phase is enumerated below with its assigned milestone.

| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | DB WAL Checkpoint Truncation | Automated `PRAGMA wal_checkpoint(TRUNCATE);` execution to prevent unbounded WAL file growth under 200-stream loads | M1 (DONE) | Survey E1 / R1 |
| 2 | DB Periodic Vacuuming & Optimize | Background daemon performing periodic `PRAGMA optimize;` and space maintenance without blocking active readers/writers | M1 (DONE) | Survey E1 / R1 |
| 3 | Sighting Log 90-Day Archiving | Automated archival of vehicle `sightings` older than 90 days into `sightings_archive` with composite indexing | M1 (DONE) | Survey E1 / R1 |
| 4 | Stream Exponential Backoff Reconnection | Auto-reconnection loop with exponential backoff (1s, 2s, 4s, 8s, 16s) for dropped RTSP/video feeds in MJPEG generator | M1 (DONE) | Survey E1 / R1 |
| 5 | Hardware-Assisted Video Decode Probing | Probing CUDA/NVDEC/MSMF/D3D11 hardware acceleration flags with graceful fallback to software CPU decoding in VideoCapture | M2 | Survey E1 / R2 |
| 6 | Dynamic Frame-Dropping Backpressure | Adaptive client latency tracking and frame-dropping backpressure for lagging mobile/web viewers during 200-stream load | M2 | Survey E1 / R2 |
| 7 | Court-Ready Evidence PDF Brief | Section 65B / BSA 2023 compliant PDF evidence certificate with Gujarat Police banner, incident metadata, timeline, and QR code | M3 | Survey E2 / R3 |
| 8 | Deterministic SHA-256 Verification | Canonical sorted JSON hashing and verification endpoint (`/api/evidence/verify`) for tamper-evident validation | M3 | Survey E2 / R3 |
| 9 | Vectorized LSB Frame Watermarking | Low-overhead (<15 µs) LSB blue-channel frame timestamping with magic bytes, camera hash, and CRC32 tamper check | M3 | Survey E2 / R3 |
| 10 | Operator Dispatch Webhooks | Asynchronous alert dispatch webhook worker with HMAC SHA-256 signing, 3-attempt exponential backoff, and circuit-breaker | M4 | Survey E3 / R4 |
| 11 | Estate CSV Bulk Importer | Validated CSV camera estate bulk importer with header aliasing, Gujarat coordinate bounds check (Lat [20.0, 24.8], Lng [68.0, 74.5]), and atomic transactions | M4 | Survey E3 / R4 |
| 12 | App Lifespan Daemon Orchestration | Clean startup and shutdown lifecycle management in `app.py` for Database Maintenance Daemon and Webhook Worker Daemon | M4 | Survey E3 / R4 |
| 13 | Comprehensive E2E Testing Suite | Requirements-driven multi-tier opaque-box test suite (Tiers 1-4) validating all production upgrade features | M5 | Survey E1-E3 |
| 14 | 200-Stream Benchmark & Coverage Hardening | High-density benchmark execution and Tier 5 adversarial stress testing on a single workstation | M5 | Survey E1-E3 |

---

## Milestones

| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Autonomous Database & Stream Self-Healing | DB indexes, 90-day sightings archive, WAL checkpoint/vacuum daemon, RTSP exponential backoff reconnect | none | DONE |
| M2 | High-Density Video Acceleration & Adaptive Backpressure | Hardware-assisted video decode probing, dynamic client frame-dropping backpressure | M1 | PLANNED |
| M3 | Courtroom Forensic Evidence Brief Generation | Section 65B/BSA PDF brief builder with QR code, deterministic SHA-256 verification, LSB frame watermarking | M1 | PLANNED |
| M4 | Operator Dispatch & Estate Bulk Importer | Webhooks database schema, async webhook worker with HMAC & backoff, CSV bulk importer with Gujarat bounds check, app lifespan hooks | M1 | PLANNED |
| M5 | E2E Verification & 200-Stream Benchmark Hardening | Multi-tier test suite execution (Tiers 1-4), 200-stream concurrency benchmark verification, and Tier 5 adversarial coverage hardening | M1, M2, M3, M4 | PLANNED |

---

## Interface Contracts

### 1. Database Maintenance & Archival (`core/database.py`) - IMPLEMENTED & VERIFIED
- `DatabaseManager.archive_old_sightings(retention_days: int = 90) -> int`:
  - Prunes rows in `sightings` where `created < datetime('now', '-N days')`, inserts them into `sightings_archive`, and returns count of archived rows.
- `DatabaseManager.truncate_wal() -> dict`:
  - Executes `PRAGMA wal_checkpoint(TRUNCATE);` and returns checkpoint result status.
- `DatabaseMaintenanceDaemon(interval_seconds: int = 3600, archive_days: int = 90)`:
  - Background thread started in `app.py` lifespan executing periodic WAL truncation, archiving, and `PRAGMA optimize;`.

### 2. Streaming & Backpressure (`modules/streaming/`)
- `create_hw_videocapture(source_path: str) -> Tuple[cv2.VideoCapture, str]`:
  - Probes hardware backends (`CUDA`, `MSMF`, `FFMPEG`), falls back to default software backend, returns `(cap, backend_name)`.
- `mjpeg_frame_generator(path: str, max_fps: int = 25, client_id: str = None) -> AsyncGenerator[bytes, None]`:
  - Implements exponential backoff reconnect loop on frame read drops.
  - Dynamically skips intermediate frames if consumer backpressure / network latency is detected.

### 3. Forensic Evidence & Brief (`modules/evidence/`, `modules/integrity/`)
- `generate_courtroom_pdf_brief(evidence_pack: dict, output_path: str = None) -> bytes`:
  - Builds Section 65B/BSA 2023 compliant PDF with Gujarat Police header, evidence metadata table, alert timeline, SHA-256 seal digest, and QR code verification block.
- `compute_canonical_evidence_hash(evidence_data: dict) -> str`:
  - Computes `sha256` of sorted canonical JSON string (`separators=(',', ':')`).
- `verify_evidence_integrity(evidence_data: dict, provided_hash: str) -> Tuple[bool, str]`:
  - Validates provided certificate hash against recomputed canonical digest.
- `embed_lsb_timestamp(frame: np.ndarray, timestamp_epoch: float, camera_id: str, frame_seq: int) -> np.ndarray`:
  - Embeds 224-bit binary watermark into blue channel LSB with CRC32 integrity check.
- `extract_lsb_timestamp(frame: np.ndarray) -> Optional[dict]`:
  - Extracts and validates embedded steganographic watermark from frame.

### 4. Operator Dispatch & Webhooks (`modules/alerts/`)
- `WebhookDispatchService.register_webhook(url: str, secret: str = None, events: List[str] = None) -> dict`:
  - Registers webhook endpoint in `webhooks` table.
- `WebhookDispatchService.dispatch_alert(alert_dict: dict) -> None`:
  - Pushes alert into thread-safe async dispatch queue.
- `WebhookDispatchService.process_queue_worker()`:
  - Asynchronously delivers payloads with `X-Sentinel-Signature` (HMAC SHA-256) and exponential backoff retry.

### 5. Camera Estate CSV Importer (`modules/registry/`)
- `import_cameras_from_csv(csv_content: str, duplicate_mode: str = "update") -> dict`:
  - Parses CSV, aliases headers, validates Gujarat bounding box ($20.0^\circ \le \text{Lat} \le 24.8^\circ$, $68.0^\circ \le \text{Lng} \le 74.5^\circ$), checks required fields, and executes atomic batch insertion/update.
  - Returns `{"total": N, "imported": M, "skipped": K, "errors": [...]}`.

---

## Code Layout
- `sentinelshield/core/database.py`: Schema additions, composite indexes, `sightings_archive`, `archive_old_sightings()`, `truncate_wal()`, `DatabaseMaintenanceDaemon`.
- `sentinelshield/modules/streaming/hw_accel.py`: Hardware acceleration probing and VideoCapture factory.
- `sentinelshield/modules/streaming/mjpeg.py`: Exponential backoff reconnect and dynamic frame-dropping backpressure.
- `sentinelshield/modules/integrity/lsb_watermark.py`: Vectorized LSB frame watermarking and extraction.
- `sentinelshield/modules/evidence/pdf_builder.py`: ReportLab Platypus courtroom PDF brief builder with QR code.
- `sentinelshield/modules/evidence/vault.py`: Deterministic SHA-256 verification and async PDF brief sealing.
- `sentinelshield/modules/evidence/router.py`: Evidence verification endpoints (`/api/evidence/verify`, `/api/evidence/{eid}/pdf`).
- `sentinelshield/modules/alerts/webhooks.py`: Webhook dispatch service, HMAC signing, background queue worker.
- `sentinelshield/modules/alerts/router.py`: Webhook registration and delivery log endpoints.
- `sentinelshield/modules/registry/importer.py`: Validated CSV estate bulk importer with geographic bounds checking.
- `sentinelshield/modules/registry/router.py`: `POST /api/cameras/import-csv` endpoint.
- `sentinelshield/app.py`: Lifespan hooks for maintenance and webhook workers.
- `sentinelshield/tests/`: Unit, integration, E2E, and concurrency benchmark test suites.
