# E2E Test Infra: SentinelShield (Sentinel-X Gujarat)

## Test Philosophy
- Opaque-box, requirement-driven derived from `ORIGINAL_REQUEST.md`.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial Testing + Workload Stress Testing.

## Feature Inventory
| # | Feature | Source (Requirement) | Tier 1 | Tier 2 | Tier 3 |
|---|---------|----------------------|:------:|:------:|:------:|
| 1 | DB WAL Checkpoint Truncation | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ |
| 2 | DB Periodic Vacuuming & Optimize | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ |
| 3 | Sighting Log 90-Day Archiving | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ |
| 4 | Stream Exponential Backoff Reconnection | ORIGINAL_REQUEST § R1 | 5 | 5 | ✓ |
| 5 | Hardware-Assisted Video Decode Probing | ORIGINAL_REQUEST § R2 | 5 | 5 | ✓ |
| 6 | Dynamic Frame-Dropping Backpressure | ORIGINAL_REQUEST § R2 | 5 | 5 | ✓ |
| 7 | Court-Ready Evidence PDF Brief | ORIGINAL_REQUEST § R3 | 5 | 5 | ✓ |
| 8 | Deterministic SHA-256 Verification | ORIGINAL_REQUEST § R3 | 5 | 5 | ✓ |
| 9 | Vectorized LSB Frame Watermarking | ORIGINAL_REQUEST § R3 | 5 | 5 | ✓ |
| 10 | Operator Dispatch Webhooks | ORIGINAL_REQUEST § R4 | 5 | 5 | ✓ |
| 11 | Estate CSV Bulk Importer | ORIGINAL_REQUEST § R4 | 5 | 5 | ✓ |
| 12 | App Lifespan Daemon Orchestration | ORIGINAL_REQUEST § R1,R4 | 5 | 5 | ✓ |

## Test Architecture
- Test Runner: `pytest sentinelshield/tests/ -v` and `python sentinelshield/tests/benchmark_200_streams.py`
- Test Directory: `sentinelshield/tests/`
- Test Suites:
  - `test_database_self_healing.py`: Tests WAL truncation, 90-day archiving, composite indexes, maintenance daemon.
  - `test_stream_acceleration_and_backpressure.py`: Tests hardware decode probing, backoff auto-reconnection, and client frame-dropping.
  - `test_forensic_pdf_and_lsb.py`: Tests Section 65B PDF generation, QR code parsing, deterministic SHA-256 validation, LSB frame watermark embedding/extraction.
  - `test_webhooks_and_csv_importer.py`: Tests webhook HMAC signing, queue retry backoff, circuit-breaker, and CSV camera estate import with Gujarat geographic bounding box validation.
  - `test_modular_sentinel.py`: Full API and domain integration test suite.
  - `benchmark_200_streams.py`: 200 concurrent real-time stream simulation and throughput benchmark.

## Real-World Application Scenarios (Tier 4)
| # | Scenario | Features Exercised | Complexity |
|---|----------|--------------------|------------|
| 1 | High-Density 200-Stream Ingestion & DB Pressure | F1, F2, F3, F5, F6, F12 | High |
| 2 | Network Jitter & CCTV Feed Auto-Recovery | F4, F6, F12 | Medium |
| 3 | Critical Watchlist Threat Alert & Operator Dispatch | F10, F12 | Medium |
| 4 | Courtroom Evidence Sealing & Section 65B Audit | F7, F8, F9 | High |
| 5 | Statewide Gujarat Camera Estate Bulk Import | F11 | Medium |

## Coverage Thresholds
- Tier 1: ≥5 per feature (Total ≥ 60)
- Tier 2: ≥5 per feature boundary cases (Total ≥ 60)
- Tier 3: Pairwise coverage of major feature interactions
- Tier 4: ≥5 realistic statewide surveillance application scenarios
- Tier 5: Adversarial edge cases and 200 concurrent stream throughput stress testing
