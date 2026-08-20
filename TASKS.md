# SentinelShield Tasks & Active Backlog

Current milestone tracking and roadmap for development.

---

## 🎯 Completed Milestones

- [x] **Phase 1: Concurrency & Core Architecture**
  - [x] Implement SQLite WAL mode (`PRAGMA journal_mode=WAL;`) with 10-second busy timeout.
  - [x] Encapsulate global state into `core/state.py` with `threading.RLock()`.
  - [x] Implement token-based `SessionManager` with RBAC (`admin`, `operator`, `police`).
  - [x] Create centralized typed `Settings` in `config.py`.

- [x] **Phase 2: Domain Subsystem Isolation**
  - [x] Modularize Vision & Deblurring pipeline (`modules/vision/`).
  - [x] Integrate Fast-ALPR ONNX neural inference engine.
  - [x] Implement rolling SHA-256 hash chains & tamper detection (`modules/integrity/`).
  - [x] Modularize Centroid Vehicle Tracker with multi-frame persistence (`modules/tracking/`).
  - [x] Implement multi-lingual Threat Fusion (EN/HI/GU) (`modules/alerts/`).
  - [x] Isolate MJPEG streaming loop, video jobs, and background AI daemon (`modules/streaming/`).
  - [x] Implement Gujarat CCTV estate registry (`modules/registry/`).
  - [x] Build Cryptographic Evidence Vault with seriousness ranking (`modules/evidence/`).
  - [x] Build Decoy Camera Honeypot Trap (`modules/cyber/`).
  - [x] Build Digital Twin Predictive Heatmaps & NLP Assistant (`modules/twin/`).
  - [x] Implement WebSocket Team Chat broadcast (`modules/chat/`).

- [x] **Phase 3: Application Gateway & Backward Compatibility**
  - [x] Refactor `app.py` from 1,394 lines to declarative ~65-line composition.
  - [x] Provide 100% backward-compatible re-exports in `engine.py` and `gujarat_estate.py`.

- [x] **Phase 4: Frontend Modularization**
  - [x] Extract presentation stylesheet to `static/css/styles.css`.
  - [x] Build reactive shared client state in `static/js/state.js`.
  - [x] Build unified REST API fetch client in `static/js/api.js`.
  - [x] Decompose `app.js` into 12 focused view controllers under `static/js/modules/`.
  - [x] Implement event delegation and bootstrap in `static/js/main.js`.

- [x] **Phase 5: Automated Testing & Agentic Protocols**
  - [x] Build full automated test suite in `tests/test_modular_sentinel.py`.
  - [x] Author `README.md`, `AGENTS.md`, `ARCHITECTURE.md`, `AGENT_RULES.md`, `PROJECT_MANIFEST.md`.

---

## 🔮 Future Roadmap & Enhancements

- [ ] **Edge TPU / TensorRT Model Acceleration**: Export YOLOv8 vehicle detection and Fast-ALPR models to TensorRT and INT8 ONNX for deployment on NVIDIA Jetson / Google Coral Edge TPUs.
- [ ] **ONVIF Discovery Microservice**: Automated background subnet scanner to discover IP cameras via WS-Discovery without manual URL entry.
- [ ] **WebRTC Video Gateway**: Transition from multipart MJPEG to sub-second WebRTC (H.264 / VP8) streaming for low-bandwidth cellular links.
- [ ] **2 Lakh Camera Kubernetes Scale**: Kubernetes Helm chart with distributed Kafka / Redis stream brokers for state-wide scaling.
