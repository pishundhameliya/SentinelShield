# SentinelShield — Modular Architecture & Multi-Developer Blueprint

## Executive Summary
This document defines the architectural transformation of **SentinelShield (Sentinel-X Gujarat)** from monolithic single scripts (`app.py`, `engine.py`, `static/app.js`) into a clean, domain-driven modular system. 

It guarantees:
1. **Zero Database Locking Conflicts:** SQLite WAL mode + thread-safe connection pooling.
2. **Zero Global Memory Race Conditions:** Dedicated concurrency-safe state managers for live streaming, background AI monitoring, and centroid vehicle tracking.
3. **Zero Git Merge Conflicts:** Decoupled packages allowing 4–6 developers to build features independently on isolated directories.
4. **100% Zero-Regression Functional Parity:** All 12 workflow phases (live streaming, Fast-ALPR + CLAHE deblurring, vehicle tracking, video tamper hash chains, watchlist alerts, digital twin, cyber honeypot, evidence vault, chat) remain identical in API contract and UX.

---

## 1. Subsystem Decomposition & Directory Topology

```
sentinelshield/
├── app.py                             # Clean FastAPI application entrypoint (mounts all routers)
├── config.py                          # Typed configuration, file paths, and environment settings
├── requirements.txt                   # Project dependencies (FastAPI, OpenCV, Fast-ALPR, Pytesseract)
├── data/
│   └── sentinel.db                    # SQLite Database (WAL mode enabled)
├── core/                              # Infrastructure & Platform Services
│   ├── database.py                    # SQLite connection pool, WAL mode, migrations, queries
│   ├── security.py                    # Authentication, session tokens, RBAC
│   └── state.py                       # Concurrency-safe state managers (Locks & Event emitters)
├── modules/                           # Isolated Domain Modules
│   ├── registry/                      # Gujarat Estate, Cities, Areas, Camera Registry
│   ├── integrity/                     # CyberShield: SHA-256 Hash Chains & Tamper Detection CV
│   ├── vision/                        # Sentinel-X: Deblurring (CLAHE), Vehicle Detect, Fast-ALPR & OCR
│   │   ├── deblur.py                  # Bicubic upscaling, LAB CLAHE, unsharp mask, laplacian score
│   │   ├── vehicle_detector.py        # Sobel morphological filtering & motion difference
│   │   ├── alpr_ocr.py                # Fast-ALPR integration, Open-LPR & Pytesseract fallbacks
│   │   └── service.py                 # Vision orchestration & full-frame snapshot generator
│   ├── tracking/                      # Centroid Tracker, Sighting Logger & Route Reconstruction
│   ├── alerts/                        # Threat Fusion, Watchlist Matching & i18n Translations
│   ├── cyber/                         # Honeypot Decoy & Cyber Attack Logger
│   ├── streaming/                     # Live MJPEG Streamer, Video Batch Runner & AI Daemon
│   ├── evidence/                      # Forensic Evidence Sealing & SHA-256 Fingerprint Vault
│   ├── twin/                          # Digital Twin, Predictive Heatmap & NLP Assistant
│   ├── chat/                          # WebSocket Hub & Team Chat Room
│   └── relay/                         # Mobile Phone Video Stream Relay
└── static/                            # Modular Frontend (Vanilla ES6 Components)
    ├── index.html                     # Clean SPA Shell
    ├── css/styles.css                 # Extracted Dashboard Stylesheet
    └── js/
        ├── state.js                   # Reactive Client State Manager
        ├── api.js                     # Unified Fetch API Client
        ├── main.js                    # SPA Bootstrap & Tab Navigation
        └── modules/                   # Independent View Controllers
            ├── auth.js                # Login & Session Management
            ├── registry.js            # City Cards & Area Exploration
            ├── live_player.js         # Live CCTV Player & Controls
            ├── anpr_scanner.js        # ANPR Scanner & Deblurred Photo Gallery
            ├── vehicle_find.js        # Vehicle Search & Route Map
            ├── map_twin.js            # Digital Twin Leaflet Layers (Heat/Cyber/Route)
            ├── alerts_threats.js      # Threat Dashboard & Demo Triggers
            ├── watchlist.js           # Plate Watchlist Management
            ├── evidence_vault.js      # Evidence Vault & Ranked Incident Scores
            ├── cyber_tools.js         # Honeypot Simulator & Attack Audit
            ├── assistant.js           # Natural Language Query Assistant
            └── chat_drawer.js         # WebSocket Real-Time Chat Drawer
```

---

## 2. Concurrency & Race-Condition Safety

| Hazard | Root Cause in Monolith | Modular Architecture Solution |
|---|---|---|
| **Database Locks** | `sqlite3.connect(check_same_thread=False)` with multi-threaded writes | `PRAGMA journal_mode=WAL;`, `PRAGMA busy_timeout=10000;`, context-managed transactions |
| **Stream State Race** | Global `live_flag` dictionary mutated across threads | `LiveStreamManager` with `threading.RLock()` protecting stream lifecycle |
| **Tracking Memory Race** | `live_tracks` mutated during continuous MJPEG frame analysis | `TrackingManager` with per-camera thread-safe bounding state |
| **Fast-ALPR Model Race** | `_fast_alpr` lazy initialization concurrency race | Dedicated thread-safe singleton wrapper with `threading.Lock()` in `modules/vision/alpr_ocr.py` |
| **AI Daemon Race** | `ai_guard` mutated during periodic batch cycles | `AIGuardianManager` atomic read copies |
| **WebSocket Deadlock** | Async `broadcast()` iterating while clients disconnect | `WebSocketConnectionHub` with `asyncio.Lock()` & dead socket filter |
| **Alert Spam Race** | Rapid detections creating redundant alerts | 3-minute dedup window query enforced before every alert write |

---

## 3. Parallel Multi-Developer Work Allocation

| Developer Track | Primary Codebase Scope | Key Interfaces Produced | Zero-Conflict Git Scope |
|---|---|---|---|
| **Dev 1: Core Platform** | `core/`, `config.py`, `app.py` | `DatabaseManager`, `SessionManager`, `StateManagers` | `core/` & app root |
| **Dev 2: CyberShield Integrity** | `modules/integrity/`, `modules/evidence/` | `IntegrityService` (SHA-256 chains, freeze/blackout CV), `EvidenceVault` | `modules/integrity/`, `modules/evidence/` |
| **Dev 3: Sentinel-X AI & Vision** | `modules/vision/`, `modules/tracking/` | `VisionService` (CLAHE deblur, vehicle detect, Fast-ALPR, OCR), `CentroidTracker` | `modules/vision/`, `modules/tracking/` |
| **Dev 4: Streaming & Background Daemon** | `modules/streaming/`, `modules/registry/` | `LiveStreamManager`, `MJPEGGenerator`, `AIGuardianDaemon` | `modules/streaming/`, `modules/registry/` |
| **Dev 5: Fusion, Alerts & Twin** | `modules/alerts/`, `modules/cyber/`, `modules/twin/`, `modules/chat/` | `AlertFusionService`, `HoneypotService`, `TwinHeatService`, `WebSocketHub` | `modules/alerts/`, `modules/cyber/`, `modules/twin/` |
| **Dev 6: Frontend UI Components** | `static/js/modules/`, `static/css/`, `static/index.html` | Modular ES6 view controllers with Leaflet & WebSocket listeners | `static/` |
