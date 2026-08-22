---
name: sqlite-wal-concurrency
description: Rules for multi-threaded SQLite concurrency, WAL mode configuration, transaction management, and zero lock contention
---

# SQLite WAL Mode Concurrency Protocols

## Mandatory Pragmas & Connection Rules
Every SQLite connection created via `core.database.db_manager` must execute:
```sql
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=10000;
PRAGMA synchronous=NORMAL;
```

## Transaction Invariants
1. **Single-Statement Reads**: Use `db_manager.query_rows(query, *args)` or `db_manager.query_one(query, *args)` which execute concurrently without blocking writers.
2. **Multi-Statement Atomic Writes**: Use `with db_manager.transaction() as conn:` which acquires `self._lock` and executes `BEGIN IMMEDIATE;` to prevent write collision deadlocks.
3. **High-Frequency Batch Inserts**: Use `db_manager.execute_many(query, list_of_tuples)` to commit hundreds of time-series records in a single disk I/O burst.
4. **Parameterized Placeholders**: NEVER format SQL queries with f-strings or string concatenation. Always use `?` placeholders.
5. **Autonomous Maintenance**: `DatabaseMaintenanceDaemon` runs background `PRAGMA wal_checkpoint(TRUNCATE);` and `PRAGMA optimize;` to keep the database compact under 200-stream loads.
