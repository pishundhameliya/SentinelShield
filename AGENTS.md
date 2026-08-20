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

> Project: **SentinelShield (Sentinel-X Gujarat)**  
> Architecture: **Modular Domain Subsystems with SQLite WAL Concurrency**

---

## 1. System Invariants & Non-Negotiable Rules

### A. Zero Concurrency Regressions
- **Never create mutable global variables** (such as plain dicts or lists) in route files. All global state must live in `core/state.py` encapsulated behind a `threading.RLock()` or `asyncio.Lock()`.
- **Database Access Invariant**: All database operations must go through `core.database.db_manager`. Write operations spanning multiple statements must use `with db_manager.transaction() as con:`. SQLite WAL mode (`PRAGMA journal_mode=WAL;`) is mandatory.

### B. Clean Domain Isolation
- Code is strictly segregated into domain subsystems inside `sentinelshield/modules/`:
  - `modules/vision/`: Vehicle detection, Fast-ALPR, CLAHE deblurring, OCR.
  - `modules/integrity/`: SHA-256 rolling hash chains, tamper scoring (blackout/freeze).
  - `modules/tracking/`: Centroid tracking, multi-hop route reconstruction.
  - `modules/alerts/`: Threat fusion rules, multi-lingual translations (EN/HI/GU), watchlist CRUD.
  - `modules/streaming/`: MJPEG generation, continuous AI guardian daemon, video batch jobs.
  - `modules/registry/`: Gujarat CCTV estate definitions, area exploration, camera registry.
  - `modules/evidence/`: Cryptographic evidence sealing, incident seriousness ranking.
  - `modules/cyber/`: Honeypot decoy traps, intrusion logging.
  - `modules/twin/`: Spatial predictive risk heatmaps, natural language assistant parser.
  - `modules/chat/`: WebSocket team broadcast and persistence.
  - `modules/relay/`: Mobile webcam relay testing.
  - `modules/auth/`: User authentication, session tokens, RBAC.

- **Never put cross-domain business logic directly into `app.py`**. `app.py` is reserved solely as a top-level composer that mounts routers, configures middlewares, and manages lifespan hooks.

### C. Backward Compatibility Guarantee
- `engine.py` and `gujarat_estate.py` must maintain re-exports of all legacy symbols (`detect_vehicles`, `normalize_plate`, `extract_plate_candidate`, `process_video`, `CITIES`, `DEMO_CAMS`, etc.) so external scripts (`clear_static_data.py`, `import_all_31_cams.py`, `fetch_31.py`) continue to run without modification.

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
- ❌ **Claiming Work Without Verification**: Never claim a bug is fixed or tests pass without running `pytest sentinelshield/tests/test_modular_sentinel.py` and inspecting output.

---

## 4. Verification Protocol

Before completing any task:
1. **Run Unit & Integration Tests**:
   ```bash
   pytest sentinelshield/tests/test_modular_sentinel.py -v
   ```
2. **Check Git Status**:
   ```bash
   git status --short
   ```
   Ensure no untracked scratch files, temporary logs, or database artifacts are left unstaged.
3. **Verify Zero Regressions**: Confirm that existing endpoints and re-exported APIs remain intact.
