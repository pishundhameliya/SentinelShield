# Antigravity Rule: Architecture & Domain Boundary Invariants

## Domain Segregation
- Code is segregated into **12 domain subsystems** in `sentinelshield/modules/`:
  - `core/`: SQLite WAL manager, state locking, timing-safe session security.
  - `modules/vision/`: Vehicle detection, Fast-ALPR, CLAHE deblurring, OCR.
  - `modules/integrity/`: SHA-256 rolling hash chains, zero-allocation tamper pools, LSB watermarks.
  - `modules/evidence/`: Section 65B/BSA 2023 courtroom PDF briefs, canonical JSON verification.
  - `modules/streaming/`: StreamWorkerPool (multiprocess), hw_accel probe, dynamic backpressure.
  - `modules/tracking/`: Centroid vehicle tracker, route reconstruction.
  - `modules/alerts/`: Threat fusion, tri-lingual translation (EN/HI/GU), HMAC webhooks.
  - `modules/registry/`: Gujarat CCTV estate registry, transactional CSV bulk importer.
  - `modules/twin/`: Spatial predictive risk heatmaps, local regex NLP parser.
  - `modules/cyber/`: Fake ONVIF honeypot decoy traps, intrusion ledger.
  - `modules/chat/`: WebSocket hub (`/ws`) with dead-socket cleanup.
  - `modules/relay/`: Mobile webcam JPEG relay testbed.
  - `modules/auth/`: Timing-safe authentication and RBAC.

## Non-Negotiables
- `app.py` is a top-level composer only. Never write business logic in `app.py`.
- Re-export legacy symbols in `engine.py` and `gujarat_estate.py` for backward compatibility.
