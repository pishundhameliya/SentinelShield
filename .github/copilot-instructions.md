# GitHub Copilot Instructions for SentinelShield

## Project Profile
SentinelShield (Sentinel-X Gujarat) is a modular CCTV surveillance, GIS digital twin, Fast-ALPR, cyber honeypot, and digital forensics platform written in Python (FastAPI + SQLite WAL).

## Architectural Guidelines
- **Domain Subsystems**: Follow the 12 domain subsystems under `sentinelshield/modules/`.
- **Database Rules**: All database operations use `core.database.db_manager` with WAL mode and parameterized placeholders (`?`). Do not use raw connection strings or unparameterized queries.
- **State Management**: All thread-safe shared state belongs in `core.state`. Protect all dictionary/list operations with `threading.RLock()` or `asyncio.Lock()`.
- **High-Density Scaling**: Optimize for 200 concurrent live streams on 24GB RAM / 6GB VRAM. Use zero-allocation buffers (`MultiCameraTamperPool`) and batch database operations (`execute_many`).
- **Forensics & Legal Standards**: Maintain compliance with Section 65B of the Indian Evidence Act / Section 63 BSA 2023 for courtroom PDF evidence briefs and deterministic SHA-256 custody seals.
- **Testing**: Ensure all changes pass `python verify.py`.
