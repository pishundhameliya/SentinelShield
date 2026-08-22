---
name: api-security-and-hardening
description: Defensive API security guidelines, timing-safe authentication, HMAC webhook signing, and input sanitization
---

# API Security & Hardening Protocols

## Authentication & Session Defense
- **Timing-Attack Resistance**: Always compare passwords and token hashes using `secrets.compare_digest(a, b)` instead of string equality `a == b`.
- **Cryptographic Entropy**: Generate session tokens with `secrets.token_hex(32)`.
- **Role-Based Access Control (RBAC)**: Enforce role permissions (`admin`, `operator`, `police`, `guest`) on critical routes (e.g. purge data, camera deletion).

## Input Sanitization & Bounds Clamping
- **License Plates**: Always normalize plate strings with `re.sub(r"[^A-Z0-9]", "", text.upper())`.
- **Geospatial Coordinates**: Clamp latitudes and longitudes to legitimate Gujarat bounding boxes ($20.0^\circ \le \text{Lat} \le 24.8^\circ$, $68.0^\circ \le \text{Lng} \le 74.5^\circ$) with city centroid fallbacks.
- **Payload Size Limits**: Clamp message texts (`[:500]`) and binary upload sizes ($<2\text{ MB}$) to prevent memory exhaustion DoS attacks.

## Webhook & Decoy Defense
- **HMAC Signatures**: Sign outgoing webhook dispatches with SHA-256 HMAC headers (`X-Sentinel-Signature`).
- **Honeypot Decoys**: Return dummy 200 responses on fake ONVIF endpoints (`/onvif/device_service`) while silently recording attacker IP and port scan patterns in the cyber threat ledger.
