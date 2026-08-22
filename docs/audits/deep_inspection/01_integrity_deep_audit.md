# Deep Inspection Audit: `modules/integrity`

> **Audit Frameworks**: Ponytail (Over-Engineering & Dead Code) + Systematic Debugging (Root Cause & Failure Modes) + Paranoid-Minimalist  
> **Target Subsystem**: [`sentinelshield/modules/integrity/`](file:///D:/Projects/SentinelShield/sentinelshield/modules/integrity/)

---

## 1. Ponytail Over-Engineering & Simplification Analysis
- **`<delete>`**: None. All methods in `HashChainManager`, `MultiCameraTamperPool`, and `BulkHashBatcher` are actively consumed in the streaming pipeline.
- **`<stdlib>`**: `hash_chain.py` uses standard library `hashlib`, `threading`, and `time`. Zero bloated third-party crypto dependencies.
- **`<yagni>`**: Avoided full distributed consensus algorithms (Raft/Paxos). The local sequential SHA-256 hash chain satisfies all legal non-repudiation requirements with $O(1)$ complexity.
- **`<shrink>`**: Codebase is tight (under 250 total lines across all 3 files).
- **Net Verdict**: Lean and essential.

---

## 2. Systematic Debugging & Failure Mode Analysis

| Component | Potential Root Cause / Failure Mode | Evidence & Trace | Paranoid Defensive Guard |
| :--- | :--- | :--- | :--- |
| `HashChainManager.append_frame_bytes` | Unbounded memory growth if stream runs for hours without closing segment | If `close_segment` isn't called, `segment_bytes` grows | Capped per frame at `[:8000]` bytes; streaming worker triggers `close_segment` every ~3 seconds. |
| `MultiCameraTamperPool` | Unbounded dictionary growth with 1,000+ ephemeral camera IDs | Dictionary keys accumulate | Bounded at `max_cameras=250` with automatic LRU eviction of oldest idle camera. |
| `TamperDetector.frame_difference_score` | Dimension mismatch when camera dynamically changes aspect ratio | `cv2.absdiff` raises OpenCV assertion on unequal shapes | Frames are always resized to fixed `(160, 90)` before difference calculation. |
| `BulkHashBatcher.flush` | SQLite connection timeout during concurrent write storm | SQLite `OperationalError: database is locked` | `db_manager.execute_many()` runs under `PRAGMA busy_timeout=10000;` and WAL mode with retry lock. |

---

## 3. Polish & Upgrade Recommendations
1. **Steganographic Watermarking**: Embed the 64-char hex digest into the least significant bit (LSB) of the first pixel row of sealed video frames for offline forensic verification.
2. **Periodic Integrity Heartbeat**: Broadcast a rolling hash chain health status packet to the frontend every 30 seconds.
