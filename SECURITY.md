# Security Policy

The SentinelShield engineering team takes security and forensic integrity seriously. As a command desk operating across critical CCTV infrastructure, law enforcement databases, and digital evidence vaults, we maintain strict vulnerability disclosure and resolution protocols.

---

## 🛡️ Supported Versions

We provide security updates and patches for the following versions:

| Version | Supported | Status |
| :--- | :--- | :--- |
| `2.0.x` (Modular) | ✅ Yes | Current Active Release |
| `< 2.0.0` (Monolithic) | ❌ No | Deprecated — Please upgrade to modular `main` |

---

## 🚨 Reporting a Vulnerability

If you discover a potential security vulnerability in SentinelShield, please **do not report it in public GitHub issues**.

Instead, follow the responsible disclosure process:

1. **Email Details**: Send an email to the security team at **security@sentinelgujarat.in** (or contact the lead maintainer directly via GitHub private security advisories).
2. **Include in Report**:
   - Description of the vulnerability and potential impact.
   - Exact steps or proof-of-concept (PoC) script to reproduce the issue.
   - Affected subsystem (e.g., Auth, MJPEG Streamer, Evidence Vault, SQLite Manager).
3. **Response Window**: You will receive an initial response within **24–48 hours** acknowledging receipt of your report.
4. **Resolution**: We will provide a remediation plan and coordinate a security patch release prior to public disclosure.

---

## 🔒 Security Architecture Highlights

SentinelShield incorporates built-in defensive measures:

- **Honeypot Decoys (`modules/cyber/`)**: Unauthenticated access to `/honeypot` and `/onvif/device_service` is isolated and monitored as a network intrusion trap.
- **Forensic Chain Integrity (`modules/integrity/`)**: Video segments are sealed with rolling SHA-256 hash chains ($\text{Hash}_n = \text{SHA256}(\text{Bytes}_n \parallel \text{Hash}_{n-1})$) to prevent tampering and undetected frame alterations.
- **SQL Injection Prevention (`core/database.py`)**: All database operations use parameterized queries (`?` placeholders) and atomic `BEGIN IMMEDIATE;` transactions under SQLite WAL concurrency.
- **Role-Based Access Control (`core/security.py`)**: Session tokens are verified cryptographically via `secrets.token_hex` with strict RBAC segregation between `admin`, `operator`, and `police` roles.
