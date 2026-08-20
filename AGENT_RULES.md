# SentinelShield Agent Development Rules & Standards

> These rules apply to all AI coding agents working on the **SentinelShield** repository.

---

## 1. Core Engineering Standard: Brutal, Honest & Ambitious

1. **Be Brutally Honest & To The Point**:
   - State facts, root causes, performance trade-offs, and technical limitations directly.
   - Avoid fluff, filler text, or performative agreement.
2. **Zero BS / No Superficial Fixes**:
   - Never mask bugs by catching and swallowing exceptions without root-cause resolution.
   - Never introduce ad-hoc global variables to bypass architectural contracts.
   - Fix the actual root cause at its origin.
3. **Empirical Proof Before Claims**:
   - Never claim work is "complete", "fixed", or "passing" without running the verification suite and confirming 0 errors.

---

## 2. Concurrency & State Invariants

- **SQLite WAL Mode**: Never change SQLite's journal mode away from WAL (`PRAGMA journal_mode=WAL;`).
- **Atomic Transactions**: Never execute multi-statement writes without wrapping them in `with db_manager.transaction() as con:`.
- **Lock Encapsulation**: Any shared in-memory state (frames, tracks, sessions, sockets) MUST be guarded by a `threading.RLock()` or `asyncio.Lock()` in `core/state.py`.
- **Stateless Routers**: Route handlers in `sentinelshield/modules/*/router.py` must never maintain internal mutable state.

---

## 3. Code Style & Maintainability Guidelines

### Python (Backend)
- Use typed Python 3.10+ annotations with `from __future__ import annotations`.
- Keep module imports cleanly grouped: standard library, third-party packages, core infrastructure, domain modules.
- Preserve backward compatibility re-exports in `engine.py` and `gujarat_estate.py`.
- All background long-running loops must be spawned as daemon threads with clean shutdown signals.

### JavaScript (Frontend)
- Maintain separation between presentation (`static/css/styles.css`), reactive state (`static/js/state.js`), API requests (`static/js/api.js`), and domain view controllers (`static/js/modules/`).
- Use event delegation on `document` or specific container elements rather than scattering inline handlers.
- Escape all dynamic user and database strings before injecting into the DOM via `SSState.escapeHtml()`.

---

## 4. Verification Checklist

Before submitting changes:
- [ ] Run full test suite: `pytest sentinelshield/tests/test_modular_sentinel.py -v`
- [ ] Verify clean git status: `git status --short`
- [ ] Verify that no `.DS_Store`, `__pycache__`, or database files are committed
- [ ] Ensure backward compatibility for external scripts (`clear_static_data.py`, `import_all_31_cams.py`)
