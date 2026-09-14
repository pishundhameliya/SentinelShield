# SentinelShield Project Manifest

Complete registry of all files, services, endpoints, and data tables in the SentinelShield repository.

---

## 1. Core Component Directory

| Path | Primary Exports | Description |
| :--- | :--- | :--- |
| `sentinelshield/config.py` | `Settings`, `settings` | Central configuration, typed directories, default users |
| `sentinelshield/core/database.py` | `DatabaseManager`, `db_manager`, `utcnow` | SQLite WAL connection and transaction provider |
| `sentinelshield/core/security.py` | `SessionManager`, `session_manager` | Token-based auth and RBAC |
| `sentinelshield/core/state.py` | `live_stream_state`, `ai_state`, `tracking_state`, `relay_state`, `ws_hub` | Thread-safe in-memory state managers |
| `sentinelshield/app.py` | `app`, `lifespan` | FastAPI application composer |
| `sentinelshield/engine.py` | `detect_vehicles`, `detect_fast_alpr`, `enhance_blurry_crop`, `normalize_plate`, `read_plate_text`, ... | Backward compatibility vision re-exports |
| `sentinelshield/gujarat_estate.py` | `CITIES`, `DEMO_CAMS`, `OWNERS`, `SENTINEL_LIVE_CAMS`, `total_cameras`, `sample_points` | Backward compatibility estate re-exports |

---

## 2. Domain Subsystems

| Module | Service Class / Functions | Router File | Primary Endpoints |
| :--- | :--- | :--- | :--- |
| **Integrity** | `HashChainManager`, `TamperDetector`, `IntegrityService` | `modules/integrity/` | Rolling SHA-256 chain, blackout & freeze detector, trust scoring |
| **Vision & ANPR** | `enhance_blurry_crop`, `detect_vehicles`, `detect_fast_alpr`, `VisionService` | `modules/vision/router.py` | `POST /api/anpr/scan-live/{camera_id}` |
| **Tracking & Routes** | `CentroidVehicleTracker`, `TrackingService` | `modules/tracking/router.py` | `GET /api/vehicle`, `GET /api/vehicle-detections`, `GET /api/route` |
| **Alerts & Watchlist** | `translate_alert`, `AlertService` | `modules/alerts/router.py` | `POST /api/watchlist`, `DELETE /api/watchlist/{id}`, `POST /api/alerts/{id}/status`, `POST /api/demo/panic`, `POST /api/demo/abandoned` |
| **Streaming & AI** | `StreamingService`, `AIGuardianDaemon`, `process_video`, `run_video_job` | `modules/streaming/router.py` | `GET /api/health`, `GET /api/overview`, `GET /api/events`, `POST /api/live/start`, `POST /api/live/stop`, `GET /api/live/stream`, `POST /api/analyze/{id}`, `POST /api/analyze-all`, `GET /api/job/{id}`, `POST /api/ai/on`, `POST /api/ai/off`, `POST /api/upload` |
| **Registry & GIS** | `RegistryService`, `CITIES`, `DEMO_CAMS`, `SENTINEL_LIVE_CAMS` | `modules/registry/router.py` | `GET /api/cities`, `GET /api/areas`, `GET /api/cameras`, `GET /api/hot-cams`, `GET /api/live-cameras`, `POST /api/cameras`, `POST /api/cameras/{id}/connect`, `POST /api/purge-static-data` |
| **Evidence Vault** | `EvidenceVaultService` | `modules/evidence/router.py` | `GET /api/evidence`, `POST /api/evidence/{id}`, `GET /api/rank-evidence` |
| **Cybersecurity** | `CyberHoneypotService` | `modules/cyber/router.py` | `GET /honeypot`, `POST /honeypot`, `GET /onvif/device_service`, `GET /api/honeypot`, `GET /api/cyber` |
| **Digital Twin** | `DigitalTwinService`, `AssistantNLPService` | `modules/twin/router.py` | `GET /api/heat`, `GET /api/twin`, `GET /api/cam-health`, `POST /api/drones/launch`, `POST /api/ask`, `GET /api/persons`, `GET /api/workflow` |
| **Team Chat** | `ChatService` | `modules/chat/router.py` | `POST /api/chat`, `GET /api/chat`, `WS /ws` |
| **Relay & Auth** | `SessionManager` | `modules/relay/router.py`, `modules/auth/router.py` | `POST /api/temp/webcam-relay`, `GET /api/temp/webcam-relay.jpg`, `GET /phone-send`, `POST /api/login`, `GET /api/me` |

---

## 3. Frontend Modules

| File Path | Namespace | Purpose |
| :--- | :--- | :--- |
| `sentinelshield/static/css/styles.css` | CSS Stylesheet | Dark theme, grid layout, buttons, alerts, chat drawer |
| `sentinelshield/static/js/state.js` | `SSState` | Reactive shared client state store and HTML escaping |
| `sentinelshield/static/js/api.js` | `SSApi` | Promise-based fetch API client |
| `sentinelshield/static/js/main.js` | `SSApp` | Application bootstrap, lifecycle, and event delegation |
| `sentinelshield/static/js/modules/auth.js` | `SSAuth` | Login, logout, session verification |
| `sentinelshield/static/js/modules/registry.js` | `SSRegistry` | City & area exploration, camera cards, breadcrumbs |
| `sentinelshield/static/js/modules/live_player.js` | `SSLivePlayer` | MJPEG video streaming, play/pause canvas freeze |
| `sentinelshield/static/js/modules/anpr_scanner.js` | `SSAnpr` | Live frame vehicle detection, deblurring gallery |
| `sentinelshield/static/js/modules/vehicle_find.js` | `SSVehicleFind` | Plate search, sighting history, Leaflet route trail |
| `sentinelshield/static/js/modules/map_twin.js` | `SSTwinMap` | Predictive crime heatmaps, cyber attack pins, drones |
| `sentinelshield/static/js/modules/alerts_threats.js` | `SSAlerts` | Incident triage table, Seen / Done updates |
| `sentinelshield/static/js/modules/watchlist.js` | `SSWatchlist` | Watchlist addition, removal, table rendering |
| `sentinelshield/static/js/modules/evidence_vault.js` | `SSEvidence` | Cryptographic evidence sealing & seriousness ranking |
| `sentinelshield/static/js/modules/cyber_tools.js` | `SSCyber` | Decoy honeypot testing & cyber log audit |
| `sentinelshield/static/js/modules/assistant.js` | `SSAssistant` | Natural language query parsing & speech recognition |
| `sentinelshield/static/js/modules/chat_drawer.js` | `SSChat` | Real-time WebSocket team room messaging |
