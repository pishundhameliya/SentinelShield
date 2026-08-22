---
description: Execute the high-density stress benchmark for 50, 100, and 200 concurrent live streams
---

Run the multi-tier real-time stream stress benchmark:
```bash
python sentinelshield/tests/benchmark_200_streams.py
```
Outputs aggregate throughput (FPS), mean per-frame processing latency (ms), and verifies 100% cryptographic integrity across all 200 concurrent rolling SHA-256 hash chains.
