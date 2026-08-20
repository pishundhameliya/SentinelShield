# Contributing to SentinelShield

Thank you for your interest in contributing to **SentinelShield (Sentinel-X Gujarat)**! This document outlines our development process, architectural guidelines, coding standards, and pull request procedures.

---

## 🏛️ Architectural Invariants

Before writing code, review [ARCHITECTURE.md](ARCHITECTURE.md), [AGENTS.md](AGENTS.md), and [AGENT_RULES.md](AGENT_RULES.md). All contributions must adhere to the following non-negotiable architectural rules:

1. **Domain Isolation**:
   - Code is organized strictly by domain inside `sentinelshield/modules/` (`vision/`, `streaming/`, `tracking/`, `alerts/`, `integrity/`, `evidence/`, `cyber/`, `twin/`, `registry/`, `chat/`, `relay/`, `auth/`).
   - Do not place domain logic inside `app.py`. `app.py` is reserved exclusively for mounting routers, configuring middleware, and managing lifespan hooks.

2. **Concurrency & Database Invariants**:
   - All shared in-memory state (video streams, active tracking IDs, WebSocket clients) must live in `sentinelshield/core/state.py` encapsulated behind a `threading.RLock()` or `asyncio.Lock()`.
   - All database reads/writes must use `core.database.db_manager`. SQLite is configured in **WAL mode** (`PRAGMA journal_mode=WAL;`). Multi-statement write transactions must use `with db_manager.transaction() as con:`.

3. **Backward Compatibility**:
   - `sentinelshield/engine.py` and `sentinelshield/gujarat_estate.py` must maintain all re-exported symbols so legacy external scripts continue to operate without alteration.

---

## 🛠️ Local Development Setup

### 1. Clone & Setup Environment

```bash
git clone https://github.com/Yashsmakwana/SentinelShield.git
cd SentinelShield/sentinelshield

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Run the Application

```bash
python app.py
```
Open `http://localhost:8080` in your web browser.

---

## 🧪 Testing Guidelines

Every bug fix or feature addition must include automated test coverage in `sentinelshield/tests/test_modular_sentinel.py`.

Run the test suite before submitting changes:

```bash
pytest sentinelshield/tests/test_modular_sentinel.py -v
```

All tests must pass with exit code `0`.

---

## 📝 Commit & PR Conventions

We follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat(module)`: A new feature or endpoint (e.g., `feat(vision): add TensorRT ONNX runtime support`)
- `fix(module)`: A bug fix (e.g., `fix(tracking): persist active track IDs across dropped frames`)
- `docs(module)`: Documentation additions or updates (e.g., `docs(readme): add WebRTC deployment guide`)
- `chore(module)`: Maintenance tasks, dependency bumps, or cleanup (e.g., `chore(deps): update fast-alpr to 0.4.0`)
- `test(module)`: Adding or updating test cases (e.g., `test(integrity): add blackout detection test`)

---

## 📋 Pull Request Checklist

Before opening a pull request, ensure:
- [ ] Code follows domain isolation under `sentinelshield/modules/`.
- [ ] No raw unparameterized SQL queries (`f"SELECT ..."`).
- [ ] Shared state is thread-safe and encapsulated in `core/state.py`.
- [ ] `pytest sentinelshield/tests/test_modular_sentinel.py -v` passes cleanly.
- [ ] Git working tree is clean with no accidental logs, `.pyc`, or `.db` files (`git status --short`).
