# E2E Test Infrastructure: SentinelShield (Sentinel-X Gujarat)

## Test Philosophy
- Opaque-box, requirement-driven derived from `ORIGINAL_REQUEST.md`.
- Methodology: Category-Partition + Boundary Value Analysis + Pairwise Combinatorial Testing + Workload Stress Testing + AST Lint Static Analysis.

---

## The 13 Automated Test Suites in `sentinelshield/tests/`

| # | Test Suite File | Coverage Scope & Invariants Tested |
|---|----------------|------------------------------------|
| 1 | `benchmark_200_streams.py` | 50, 100, and 200 concurrent real-time stream simulation, throughput ($>28,000\text{ FPS}$), latency ($<0.04\text{ ms}$), and hash chain validation. |
| 2 | `test_async_evidence_sealing.py` | Asynchronous evidence pack sealing, custody metadata verification, and SHA-256 JSON digests. |
| 3 | `test_code_quality_and_lints.py` | AST syntax compilation across 80+ files, DML SQL parameterization guard, domain isolation, and legacy re-export parity. |
| 4 | `test_database_self_healing.py` | Database WAL checkpoint truncation, 90-day sighting archiving, and `DatabaseMaintenanceDaemon`. |
| 5 | `test_forensic_evidence_pdf_and_watermark.py` | Section 65B/BSA 2023 courtroom PDF brief generator, canonical JSON order-invariant hash verification, and 256-bit LSB frame watermarking with CRC32. |
| 6 | `test_hash_bulk_batch.py` | BulkHashBatcher high-speed transaction flushing and rolling SHA-256 block chains. |
| 7 | `test_modular_sentinel.py` | Full REST endpoint, WebSocket channel, and domain subsystem integration suite. |
| 8 | `test_stream_acceleration_and_backpressure.py` | Hardware-assisted video decode probing (`CUDA`, `NVDEC`, `MSMF`), client backpressure frame-dropping, and exponential backoff reconnect. |
| 9 | `test_stream_backpressure_stress_challenge.py` | Adversarial backpressure stress under artificial network latency and consumer queue backlogs. |
| 10 | `test_stream_disconnect_challenge.py` | Stream failure simulation, socket drop handling, and exponential reconnect recovery. |
| 11 | `test_stream_pool.py` | Multi-process `StreamWorkerPool` core partitioning and process lifecycle management. |
| 12 | `test_tamper_ring_buffer.py` | `MultiCameraTamperPool` zero-allocation $(90, 160, 3)$ ring buffer tamper detection (blackout & freeze). |
| 13 | `test_webhooks_and_csv_importer.py` | Operator dispatch webhooks with HMAC SHA-256 signatures, retry queues, and transactional CSV camera estate bulk importer with Gujarat GPS bounds validation. |

---

## Universal Execution Command
```bash
python verify.py
```

## GitHub Actions CI/CD Pipeline
- Workflow: `.github/workflows/ci.yml`
- Multi-OS: `ubuntu-latest`, `windows-latest`
- Multi-Python: `3.11`, `3.12`, `3.13`
