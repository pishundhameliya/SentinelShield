# SentinelShield — Database Schema & Concurrency Reference

> **Storage Engine**: SQLite in Write-Ahead Logging (WAL) Mode  
> **Concurrency Pragmas**: `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=10000;`, `PRAGMA synchronous=NORMAL;`  
> **Thread Access**: Serialized multi-statement transactions via `threading.RLock()`, non-blocking parallel readers.

---

## 1. Complete Table Dictionary

### `cameras`
Stores camera registration, physical geolocation, stream sources, and health status.
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `TEXT PRIMARY KEY` | Unique camera identifier (e.g. `cam-ahmedabad-01`, `cam-surat-02`) |
| `name` | `TEXT` | Human-readable camera label (e.g. `Gandhi Ashram Gate 1`) |
| `place` | `TEXT` | Area and city label (e.g. `Sabarmati, Ahmedabad`) |
| `lat` | `REAL` | Latitude coordinate (Gujarat bounds: $20.0^\circ \le \text{Lat} \le 24.8^\circ$) |
| `lng` | `REAL` | Longitude coordinate (Gujarat bounds: $68.0^\circ \le \text{Lng} \le 74.5^\circ$) |
| `source` | `TEXT` | Local video file path or fallback clip |
| `kind` | `TEXT` | Camera type (`fixed`, `ptz`, `anpr`, `drone`) |
| `trust` | `INTEGER` | Real-time integrity trust score (0–100) |
| `status` | `TEXT` | Stream status (`idle`, `ready`, `live`, `tampered`) |
| `last_note` | `TEXT` | Operator or system status description |
| `city_id` | `TEXT` | Foreign city identifier (e.g. `ahmedabad`, `surat`, `vadodara`) |
| `area_id` | `TEXT` | Foreign area identifier (e.g. `ahmedabad:east`) |
| `owner` | `TEXT` | Government department (e.g. `Gujarat Police`, `AMC`) |
| `spot` | `TEXT` | Specific surveillance junction name |
| `estate` | `INTEGER` | Flag indicating active Gujarat estate membership |
| `live_url` | `TEXT` | Live RTSP or HTTP video stream URL |

---

### `sightings` & `sightings_archive`
Real-time time-series log of all vehicle detections and license plate reads. Records older than 90 days are automatically archived to `sightings_archive` by `DatabaseMaintenanceDaemon`.
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `TEXT PRIMARY KEY` | Sighting UUID (e.g. `sght-a1b2c3d4`) |
| `plate` | `TEXT` | Normalized uppercase license plate string (e.g. `GJ05SS2026`) |
| `camera_id` | `TEXT` | Foreign key referencing `cameras(id)` |
| `camera_name` | `TEXT` | Name of the camera at detection time |
| `place` | `TEXT` | Area/City location of the sighting |
| `city_id` | `TEXT` | City identifier for spatial aggregation |
| `area_id` | `TEXT` | Area identifier |
| `lat`, `lng` | `REAL` | Geolocation coordinates |
| `created` | `TEXT` | Formatted UTC timestamp |
| `source` | `TEXT` | Ingestion mode (`live_anpr`, `video_job`, `ai_guardian`) |
| `archived_at` | `TEXT` | Timestamp when row was moved to archive (archive table only) |

---

### `hashes`
Immutable rolling SHA-256 blockchain-lite ledger ensuring continuous forensic chain-of-custody.
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `INTEGER PRIMARY KEY` | Auto-incrementing block index |
| `job_id` | `TEXT` | Associated camera or video job identifier |
| `t_start` | `REAL` | Video stream segment start time in seconds |
| `t_end` | `REAL` | Video stream segment end time in seconds |
| `sha256` | `TEXT` | SHA-256 digest of current segment payload |
| `prev` | `TEXT` | SHA-256 digest of previous block ($H_{n-1}$) |

---

### `evidence`
Sealed forensic evidence manifests for judicial submission under Section 65B Indian Evidence Act / Section 63 BSA 2023.
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `TEXT PRIMARY KEY` | Evidence pack ID (e.g. `evd-9f8e7d6c`) |
| `camera_id` | `TEXT` | Foreign key referencing `cameras(id)` |
| `sha256` | `TEXT` | Deterministic SHA-256 seal digest |
| `path` | `TEXT` | Absolute path to sealed JSON manifest on disk |
| `created` | `TEXT` | Timestamp of sealing |

---

### `alerts`
Threat fusion events raised by automated vision, tamper detection, cyber honeypots, and watchlist matches.
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `TEXT PRIMARY KEY` | Alert UUID (e.g. `alt-1234abcd`) |
| `camera_id` | `TEXT` | Camera where threat was detected |
| `kind` | `TEXT` | Threat classification (`watchlist`, `tamper`, `cyber`, `panic`, `abandoned`) |
| `title` | `TEXT` | Short alert headline |
| `detail` | `TEXT` | Full incident description with vehicle or attack details |
| `severity` | `TEXT` | Priority rating (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) |
| `trust` | `INTEGER` | Camera trust score at time of alert |
| `t` | `REAL` | Video timestamp offset |
| `created` | `TEXT` | Formatted UTC timestamp |
| `status` | `TEXT` | Operational status (`active`, `acknowledged`, `resolved`) |

---

### `webhooks`
External operator dispatch endpoints for real-time threat notifications.
| Column | Type | Description |
| :--- | :--- | :--- |
| `id` | `TEXT PRIMARY KEY` | Webhook identifier (e.g. `whk-abcdef12`) |
| `url` | `TEXT` | External HTTP(S) endpoint URL |
| `secret` | `TEXT` | Shared HMAC SHA-256 signing secret |
| `events` | `TEXT` | Subscribed event filter (`all`, `watchlist`, `critical`) |
| `status` | `TEXT` | Webhook status (`active`, `disabled`) |
| `created` | `TEXT` | Registration timestamp |
| `last_dispatched` | `TEXT` | Timestamp of latest successful HTTP delivery |

---

## 2. Composite Performance Indexes

```sql
CREATE INDEX IF NOT EXISTS idx_sightings_plate_created ON sightings(plate, created);
CREATE INDEX IF NOT EXISTS idx_sightings_cam_created ON sightings(camera_id, created);
CREATE INDEX IF NOT EXISTS idx_sightings_created ON sightings(created);
CREATE INDEX IF NOT EXISTS idx_sightings_arch_plate ON sightings_archive(plate, created);
CREATE INDEX IF NOT EXISTS idx_sightings_arch_cam ON sightings_archive(camera_id, created);
CREATE INDEX IF NOT EXISTS idx_sightings_arch_created ON sightings_archive(created);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created);
CREATE INDEX IF NOT EXISTS idx_alerts_cam_created ON alerts(camera_id, created);
CREATE INDEX IF NOT EXISTS idx_hashes_job ON hashes(job_id);
```

---

## 3. Database Maintenance Daemon Protocols

`DatabaseMaintenanceDaemon` runs as an asynchronous background thread:
1. **Periodic WAL Checkpoint Truncation**: Executes `PRAGMA wal_checkpoint(TRUNCATE);` hourly to prevent WAL file explosion under 200-stream load.
2. **Automated Sighting Pruning**: Moves records where `created < datetime('now', '-90 days')` into `sightings_archive`.
3. **Query Optimization**: Runs `PRAGMA optimize;` to refresh SQLite query planning statistics.
