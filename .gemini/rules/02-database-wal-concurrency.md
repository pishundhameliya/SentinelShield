# Antigravity Rule: SQLite WAL Concurrency & State Invariants

## 1. Centralized State
- Never create mutable global variables (dicts, lists) in route files.
- All shared state must live in `core/state.py` encapsulated behind `threading.RLock()` or `asyncio.Lock()`.

## 2. Database Concurrency
- All database operations must go through `core.database.db_manager`.
- SQLite WAL mode is strictly mandatory (`PRAGMA journal_mode=WAL;`, `busy_timeout=10000;`).
- Multi-statement write transactions must use:
  ```python
  with db_manager.transaction() as conn:
      conn.execute(...)
  ```
- Use `db_manager.execute_many(query, records)` for high-frequency time-series batch inserts.
- **Never format SQL queries with f-strings**. Always use parameterized `?` placeholders.
