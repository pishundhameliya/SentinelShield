# SentinelShield — Documentation Portal & Architectural Index

Welcome to the **SentinelShield (Sentinel-X Gujarat Command Desk)** technical documentation suite.

---

## 🏛️ Governance, Standards & Policies

- **[Operational Governance Protocol](file:///D:/Projects/SentinelShield/docs/GOVERNANCE_PROTOCOL.md)**: Non-negotiable constitutional directives, 5-phase agent lifecycle SOP, and quality gatekeeper.
- **[Engineering & Agent Governance Policy](file:///D:/Projects/SentinelShield/docs/ENGINEERING_POLICY.md)**: Deep technical engineering invariants, state concurrency rules, and performance budgets.
- **[Universal Agent Guidelines (`AGENTS.md`)](file:///D:/Projects/SentinelShield/AGENTS.md)**: Master context and protocols for all AI coding assistants.

---

## 📐 System Architecture & Data Specifications

- **[System Architecture Map](file:///D:/Projects/SentinelShield/docs/architecture/SYSTEM_ARCHITECTURE.md)**: Complete subsystem topology, Mermaid component flow, and multiprocessing model.
- **[Database Schema & Concurrency Reference](file:///D:/Projects/SentinelShield/docs/architecture/DATABASE_SCHEMA.md)**: Complete SQLite WAL table dictionary, composite indexes, and archival flows.
- **[REST & WebSocket API Catalog](file:///D:/Projects/SentinelShield/docs/architecture/API_CATALOG.md)**: Exhaustive endpoint documentation with request/response schemas and status codes.

---

## 🛠️ Specialized Engineering Skills in [`.agents/skills/`](file:///D:/Projects/SentinelShield/.agents/skills/)

- [`high-density-streaming`](file:///D:/Projects/SentinelShield/.agents/skills/high-density-streaming/SKILL.md): 200+ stream ingestion, zero-malloc ring buffers, client backpressure.
- [`sqlite-wal-concurrency`](file:///D:/Projects/SentinelShield/.agents/skills/sqlite-wal-concurrency/SKILL.md): Concurrency pragmas, transaction isolation, and high-speed batching.
- [`forensic-evidence-sealing`](file:///D:/Projects/SentinelShield/.agents/skills/forensic-evidence-sealing/SKILL.md): Section 65B/BSA 2023 legal standards and LSB watermarking.
- [`api-security-and-hardening`](file:///D:/Projects/SentinelShield/.agents/skills/api-security-and-hardening/SKILL.md): Timing-safe auth, HMAC webhook signatures, and input clamping.
- [`test-driven-development`](file:///D:/Projects/SentinelShield/.agents/skills/test-driven-development/SKILL.md): Red-Green-Refactor testing protocol.
- [`verification-before-completion`](file:///D:/Projects/SentinelShield/.agents/skills/verification-before-completion/SKILL.md): Evidence before assertion rule.
- [`paranoid`](file:///D:/Projects/SentinelShield/.agents/skills/paranoid/SKILL.md): Senior defensive engineering framework.
- [`ponytail`](file:///D:/Projects/SentinelShield/.agents/skills/ponytail/SKILL.md): Anti-over-engineering and YAGNI auditing.
- [`systematic-debugging`](file:///D:/Projects/SentinelShield/.agents/skills/systematic-debugging/SKILL.md): 4-phase root-cause investigation standard.

---

## 🔍 Module Audits & Roadmaps

- **[Master Paranoid Audit Summary](file:///D:/Projects/SentinelShield/docs/audits/00_master_paranoid_audit_summary.md)**: 12-module defensive audit findings.
- **[Master Upgrade & Polish Plan](file:///D:/Projects/SentinelShield/docs/audits/deep_inspection/00_master_upgrade_polish_debugging_plan.md)**: Comprehensive milestone execution plan.

---

## 🧪 Verification & Test Runner

Run the universal test suite across all 12 test modules and the 200-stream stress benchmark:
```bash
python verify.py
```
