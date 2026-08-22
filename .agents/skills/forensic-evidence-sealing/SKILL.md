---
name: forensic-evidence-sealing
description: Standards and cryptographic protocols for digital evidence packaging, Section 65B/BSA 2023 legal compliance, and LSB watermarking
---

# Forensic Evidence & Digital Custody Standards

## Legal Standards
- **Section 65B(4)**: Indian Evidence Act, 1872
- **Section 63**: Bharatiya Sakshya Adhiniyam (BSA), 2023

## Cryptographic Invariants
1. **Deterministic Canonical Hashing**:
   - Evidence metadata manifests must be serialized with sorted keys and compact separators: `json.dumps(payload, sort_keys=True, separators=(',', ':'))`.
   - Never hash unordered or formatted JSON where whitespace/key variations could produce different digests.
2. **Rolling Hash Chaining**:
   - Video segments are hashed sequentially where each block contains $H_n = \text{SHA256}(\text{payload} + H_{n-1})$.
   - Hash chain integrity is verifiable in $O(N)$ with zero false positives.
3. **LSB Steganographic Watermarking**:
   - Frames are watermarked in the blue channel LSB with a 256-bit binary payload containing magic signature `SNTL`, UTC timestamp, camera hash, frame sequence number, and CRC32 checksum.
4. **Courtroom PDF Certificates**:
   - Certificates generated via `modules/evidence/pdf_builder.py` include government headers, incident timelines, SHA-256 seal digests, legal admissibility clauses, and QR codes.
