<!-- costwise-session:start (managed by `costwise skill` — do not edit) -->

## costwise-session

This project is connected to the **costwise** MCP server. Its tools keep the session cheap: the dominant cost is the prompt cache re-reading everything each turn, so keep the window small.

**Route large content out of context, don't paste it inline.**
- For large output, call `stash_context` to park it and get a short handle, then `recall(source=<handle>, query=…)` for only what you need.
- Persist facts with `remember`; retrieve with `recall` instead of re-pasting.

**MANDATORY: Use CostWise-MCP before any raw file tools.**
- `view_file` and `list_dir` are **PROHIBITED for discovery**. Use `find_symbol`, `read_symbol`, `search_code`, or `get_repository_summary` instead.
- Only use `view_file` when making a targeted line-level edit **after** a CostWise tool call has already identified the exact file and line range.
- Tool priority: `find_symbol` → `read_symbol` → `search_code` → `get_repository_summary` → *(last resort)* `view_file`.
- Default budget unless insufficient — one `large` call can add ~10k uncached tokens.

**Start with `session_brief`** to catch up on prior context before re-deriving it from scratch.

<!-- costwise-session:end -->

# Context & Protocols for AI Coding Agents

> Project: **SentinelShield (Sentinel-X Gujarat Command Desk)**  
> Architecture: **Modular Domain Subsystems with SQLite WAL Concurrency & High-Density Streaming (200+ Feeds)**  
> Governance: **[Engineering & Agent Governance Policy](docs/ENGINEERING_POLICY.md)** (Mandatory standard for all agents)

---

## 1. System Invariants & Non-Negotiable Rules

### A. Zero Concurrency Regressions & Thread Safety
- **Never create mutable global variables** (such as plain dicts or lists) in route or worker files. All global state must live in `sentinelshield/core/state.py` encapsulated behind a `threading.RLock()` or `asyncio.Lock()`.
- **Database Access Invariant**: All database operations must go through `core.database.db_manager`. Write operations spanning multiple statements must use `with db_manager.transaction() as con:`. SQLite WAL mode (`PRAGMA journal_mode=WAL;`) with `busy_timeout=10000;` and `synchronous=NORMAL;` is strictly mandatory.
- **Batch Inserts**: Use `db_manager.execute_many(query, args)` for high-frequency time-series inserts (rolling hash chains, detection logs).

### B. Clean Domain Isolation & Directory Map
Code is strictly segregated into domain subsystems inside `sentinelshield/modules/`:
- `core/`: Database connections, migrations, WAL maintenance daemon (`DatabaseMaintenanceDaemon`), thread-safe state managers (`core/state.py`), timing-safe auth sessions (`core/security.py`).
- `modules/integrity/`: SHA-256 rolling hash chains (`HashChainManager`, `BulkHashBatcher`), zero-allocation tamper detector (`MultiCameraTamperPool`), vectorized LSB frame watermarking (`lsb_watermark.py`).
- `modules/evidence/`: Forensic custody sealing (`EvidenceVaultService`), Section 65B / BSA 2023 courtroom PDF brief generator (`pdf_builder.py`), deterministic canonical JSON hash verification (`/api/evidence/verify`).
- `modules/streaming/`: Multi-process stream multiplexing (`StreamWorkerPool`), hardware acceleration probe (`hw_accel.py`), MJPEG streaming with exponential backoff reconnect and client backpressure frame-dropping (`mjpeg.py`), continuous background AI guardian (`ai_daemon.py`).
- `modules/vision/`: Vehicle detection (`vehicle_detector.py`), CLAHE + Laplacian deblurring (`deblur.py`), Fast-ALPR optional deep neural engine with morphological OCR fallback (`alpr_ocr.py`).
- `modules/tracking/`: Centroid multi-frame vehicle tracker (`tracker.py`), sightings search and multi-hop route reconstruction (`service.py`).
- `modules/alerts/`: Threat fusion rules, multi-lingual dispatch translations (EN/HI/GU in `fusion.py`), watchlist CRUD, asynchronous HMAC SHA-256 dispatch webhooks (`webhooks.py`).
- `modules/registry/`: Gujarat CCTV estate catalog across 15 zones (`estate_data.py`), camera CRUD, transactional CSV bulk importer with coordinate bounds validation (`importer.py`).
- `modules/twin/`: Spatial predictive risk heatmaps (`heat.py`), local regex-based natural language assistant intent parser (`assistant.py`), virtual drone dispatch simulation.
- `modules/cyber/`: Fake ONVIF/admin honeypot decoy traps (`honeypot.py`), port-scan reconnaissance logging.
- `modules/chat/`: WebSocket team connection hub (`ws_hub` in `core/state.py`) with dead-socket cleanup and room message persistence.
- `modules/relay/`: Temporary mobile webcam JPEG relay testbed (`relay_state` in `core/state.py`).
- `modules/auth/`: Timing-attack resistant session authentication (`SessionManager`) and RBAC verification.

- **Never put cross-domain business logic directly into `app.py`**. `app.py` is reserved solely as a top-level composer that mounts routers, configures middlewares, and manages lifespan daemon hooks.

### C. Backward Compatibility Guarantee
- `engine.py` and `gujarat_estate.py` must maintain re-exports of all legacy symbols (`detect_vehicles`, `normalize_plate`, `extract_plate_candidate`, `process_video`, `CITIES`, `DEMO_CAMS`, `sample_points`, etc.) so external scripts continue to run without modification.

---

## 2. Tool Selection Hierarchy

| Task | Preferred Tool | Prohibited Action |
| :--- | :--- | :--- |
| **Understand repo structure** | `get_repository_summary` | Broad recursive `list_dir` |
| **Find a class, function, or service** | `find_symbol(name=...)` | Raw `grep_search` across whole repo |
| **Read a specific function implementation** | `read_symbol(name=...)` | `view_file` on 800+ lines |
| **Locate callers of a function** | `find_callers(name=...)` | Manual string searches |
| **Find references to a type** | `find_references(name=...)` | Guessing import locations |
| **Search semantic concepts** | `search_code(query=...)` | Inefficient brute-force greps |
| **Park large outputs (>500 tokens)** | `stash_context(content=...)` | Pasting huge blobs into conversation |
| **Retrieve stashed context** | `recall(source=handle, query=...)` | Re-running expensive operations |
| **Targeted code edit** | `replace_file_content` | Overwriting full files with small edits |

---

## 3. Anti-Pattern Blacklist

- ❌ **Re-introducing Monolithic Scripts**: Never add route handlers directly to `app.py` or vision functions directly to `engine.py`.
- ❌ **Unsafe SQL String Formatting**: Never write queries like `f"SELECT * FROM alerts WHERE id='{id}'"`. Always use parameterized placeholders `?`.
- ❌ **Bypassing State Locks**: Never access `_camera_tracks`, `_frame`, or `_sessions` without acquiring the corresponding `threading.RLock`.
- ❌ **Monolithic Frontend Scripts**: Do not place new client logic in `static/index.html`. Add modular controllers to `static/js/modules/` and wire through `static/js/main.js`.
- ❌ **Claiming Work Without Verification**: Never claim a bug is fixed or tests pass without running `python verify.py` and inspecting output.
- ❌ **Blocking Event Loops**: Disk I/O or heavy cryptography in async routes must be offloaded to threadpools with `loop.run_in_executor(None, ...)`.

---

## 4. Verification Protocol

Before completing any task:
1. **Run Full Verification Suite**:
   ```bash
   python verify.py
   ```
2. **Check Git Status**:
   ```bash
   git status --short
   ```
   Ensure no untracked scratch files, temporary logs, or database artifacts are left unstaged.
3. **Verify Zero Regressions**: Confirm that existing endpoints and re-exported APIs remain intact.
