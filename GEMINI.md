# SentinelShield — Google Gemini Antigravity (AGY) Optimization Guide

> **Target Platform**: Google Gemini 3.7 Flash & Pro in Antigravity (CLI / IDE)  
> **Workspace**: `D:\Projects\SentinelShield`  
> **Repository Architecture**: Modular Domain Subsystems with SQLite WAL Concurrency & High-Density Streaming (200+ Feeds)  
> **Governance Policy**: [`docs/ENGINEERING_POLICY.md`](docs/ENGINEERING_POLICY.md) & [`docs/GOVERNANCE_PROTOCOL.md`](docs/GOVERNANCE_PROTOCOL.md)

---

## 🚀 1. Antigravity Native Workflows & Commands

SentinelShield is optimized for Gemini Antigravity's multi-agent orchestration, large context window, and reactive background tasks:

### Custom Slash Commands
| Command | Action | Execution Target |
| :--- | :--- | :--- |
| `/verify` | Run all 13 unit, integration, and stress benchmark suites | `python verify.py` |
| `/benchmark` | Run 50, 100, and 200 concurrent stream scaling tests | `python sentinelshield/tests/benchmark_200_streams.py` |
| `/sync-estate` | Pull live camera feeds from `live.corp8.cloud` & sync SQLite DB | `python sentinelshield/fetch_31.py && python sentinelshield/import_all_31_cams.py` |

### Automatic Sandbox Pre-Approvals
The following command prefixes are configured in `.gemini/settings.json` for smooth, uninterrupted execution:
- `python verify.py`
- `python sentinelshield/tests/*`
- `python scripts/setup_costwise.py`
- `git status`, `git log`, `git diff`

---

## 🧠 2. Subagent Roles for Teamwork & Parallel Sprints

When using `invoke_subagent` or `/teamwork-preview`, the following specialized subagent roles are pre-configured:

1. **`StreamingOptimizer`**:
   - Focus: Video multiplexing, hardware decode probing (`CUDA`, `NVDEC`), dynamic backpressure frame dropping.
   - Files: `sentinelshield/modules/streaming/*`, `sentinelshield/modules/vision/*`.
2. **`DatabaseGuardian`**:
   - Focus: SQLite WAL maintenance, transaction safety, 90-day sighting archiving, zero-lock batching.
   - Files: `sentinelshield/core/database.py`, `sentinelshield/core/state.py`.
3. **`ForensicAuditor`**:
   - Focus: Section 65B / BSA 2023 courtroom PDF brief builder, canonical JSON hashing, LSB watermarking.
   - Files: `sentinelshield/modules/evidence/*`, `sentinelshield/modules/integrity/*`.
4. **`VerificationSpecialist`**:
   - Focus: Automated test execution, regression auditing, benchmark telemetry.
   - Files: `verify.py`, `sentinelshield/tests/*`.

---

## ⚡ 3. Token-Efficient Exploration via CostWise MCP

Gemini Antigravity agents must use the **CostWise MCP** tools to keep the prompt cache lean:
- Use `find_symbol(name=...)` and `read_symbol(name=...)` before opening large files.
- Use `stash_context(content=...)` to park large outputs (>500 tokens) outside the context window.
- If CostWise MCP is missing on any developer machine, run `python scripts/setup_costwise.py`.

---

## 🛡️ 4. The 5-Phase Development Protocol

```text
1. Context & Trace  ──▶  2. Failing Test (TDD)  ──▶  3. Minimal Fix  ──▶  4. python verify.py  ──▶  5. Clean Commit
```

Always verify with `python verify.py` before concluding any turn.
