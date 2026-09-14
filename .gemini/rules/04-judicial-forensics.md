# Antigravity Rule: Judicial Digital Forensics & Custody

## Legal Compliance
- **Section 65B(4)** of the Indian Evidence Act, 1872
- **Section 63** of the Bharatiya Sakshya Adhiniyam (BSA), 2023

## Cryptographic Invariants
1. **Deterministic Canonical JSON Hashing**: Serialization must enforce sorted keys and compact separators: `json.dumps(payload, sort_keys=True, separators=(',', ':'))`.
2. **LSB Frame Watermarking**: 256-bit binary payload embedded in the blue-channel LSB with CRC32 tamper check.
3. **Courtroom PDF Briefs**: Generated via `pdf_builder.py` with official headers, incident metadata, SHA-256 custody seals, Section 65B legal clause, and QR codes.
