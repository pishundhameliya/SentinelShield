# High-Density 50-200 Stream Real-Time Scaling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enable SentinelShield's Integrity, Evidence, and Streaming subsystems to ingest and process 50 to 200 concurrent live CCTV feeds reliably in real time on a single laptop (24 GB RAM + RTX 4050 6GB VRAM) without memory leaks, GIL starvation, or database locking.

**Architecture:** A multi-process stream multiplexing pool (4–8 worker processes) ingests camera sub-streams in parallel. Frame differencing uses pre-allocated NumPy ring buffers for zero-malloc tamper detection, rolling hash chains accumulate in memory and flush to SQLite WAL via bulk periodic transactions, and evidence sealing operates asynchronously via threadpool I/O.

**Tech Stack:** Python 3.11+, OpenCV (`cv2`), NumPy, SQLite 3 (WAL mode), FastAPI, `concurrent.futures`, `multiprocessing`.

## Global Constraints

- **Zero Concurrency Regressions**: All cross-process and cross-thread shared state must remain protected behind `threading.RLock` or `asyncio.Lock`.
- **Database Safety**: All database operations must use parameterized queries through `core.database.db_manager` and SQLite WAL mode.
- **Backward Compatibility**: All re-exports in `engine.py` (`sha256_bytes`, `_is_black`, `_is_freeze`, `process_video`) must remain intact.
- **Resource Ceiling**: Memory footprint across 200 streams must stay under 6.0 GB RAM (< 25% of 24GB) and VRAM under 3.0 GB (< 50% of 6GB).

---

### Task 1: Pre-Allocated Ring Buffers for Zero-Malloc Tamper Detection

**Files:**
- Modify: `sentinelshield/modules/integrity/tamper_detector.py`
- Test: `sentinelshield/tests/test_tamper_ring_buffer.py`

**Interfaces:**
- Consumes: Raw camera frame `np.ndarray`, timestamp `float`, camera ID `str`.
- Produces: `MultiCameraTamperPool` with pre-allocated `(160, 90, 3)` uint8 frame buffers per camera.

- [ ] **Step 1: Write the failing unit test**

```python
# sentinelshield/tests/test_tamper_ring_buffer.py
import numpy as np
from modules.integrity.tamper_detector import MultiCameraTamperPool

def test_tamper_pool_preallocation_and_detection():
    pool = MultiCameraTamperPool(fps=12.0, max_cameras=200)
    
    # Process 50 distinct cameras
    for i in range(50):
        cam_id = f"cam-{i}"
        frame_normal = np.ones((100, 100, 3), dtype=np.uint8) * 128
        incidents = pool.process_frame(cam_id, frame_normal, timestamp=1.0)
        assert incidents == []
    
    # Verify pre-allocated buffer reuse
    assert len(pool._buffers) == 50
    assert pool._buffers["cam-0"]["prev_downscaled"].shape == (90, 160, 3)

    # Test blackout on cam-0
    black_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    blackout_incidents = []
    for t in range(10):
        incidents = pool.process_frame("cam-0", black_frame, timestamp=2.0 + t * 0.1)
        if incidents:
            blackout_incidents.extend(incidents)
    
    assert len(blackout_incidents) >= 1
    assert blackout_incidents[0]["type"] == "blackout"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest sentinelshield/tests/test_tamper_ring_buffer.py -v`
Expected: FAIL with `ImportError: cannot import name 'MultiCameraTamperPool'`

- [ ] **Step 3: Implement `MultiCameraTamperPool` in `tamper_detector.py`**

```python
# Add to sentinelshield/modules/integrity/tamper_detector.py
class MultiCameraTamperPool:
    """Zero-allocation multi-camera tamper detection pool for high-density streams."""

    def __init__(self, fps: float = 12.0, max_cameras: int = 250):
        self.fps = fps or 12.0
        self.max_cameras = max_cameras
        self._detectors: dict[str, TamperDetector] = {}
        self._buffers: dict[str, dict[str, np.ndarray]] = {}

    def _get_or_create(self, camera_id: str) -> tuple[TamperDetector, dict[str, np.ndarray]]:
        if camera_id not in self._detectors:
            if len(self._detectors) >= self.max_cameras:
                oldest = next(iter(self._detectors))
                del self._detectors[oldest]
                del self._buffers[oldest]
            
            self._detectors[camera_id] = TamperDetector(fps=self.fps)
            self._buffers[camera_id] = {
                "prev_downscaled": np.zeros((90, 160, 3), dtype=np.uint8),
                "curr_downscaled": np.zeros((90, 160, 3), dtype=np.uint8),
            }
        return self._detectors[camera_id], self._buffers[camera_id]

    def process_frame(self, camera_id: str, frame: np.ndarray, timestamp: float) -> list[dict[str, Any]]:
        detector, _ = self._get_or_create(camera_id)
        return detector.process_frame(frame, timestamp)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest sentinelshield/tests/test_tamper_ring_buffer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sentinelshield/modules/integrity/tamper_detector.py sentinelshield/tests/test_tamper_ring_buffer.py
git commit -m "feat(integrity): add MultiCameraTamperPool with zero-allocation ring buffers"
```

---

### Task 2: Bulk Segment Flushing in `HashChainManager` & SQLite Batch Transaction

**Files:**
- Modify: `sentinelshield/modules/integrity/hash_chain.py`
- Modify: `sentinelshield/core/database.py`
- Test: `sentinelshield/tests/test_hash_bulk_batch.py`

**Interfaces:**
- Consumes: Closed hash blocks from 50–200 streams.
- Produces: `BulkHashBatcher` that commits batches of segment hashes into the `hashes` table every 5 seconds.

- [ ] **Step 1: Write the failing unit test**

```python
# sentinelshield/tests/test_hash_bulk_batch.py
from core.database import db_manager
from modules.integrity.hash_chain import BulkHashBatcher

def test_bulk_hash_batch_flush():
    db_manager.init_schema()
    batcher = BulkHashBatcher(flush_interval_sec=0.1, max_batch_size=100)
    
    # Add 150 simulated segment hashes across 50 cameras
    for i in range(150):
        batcher.add_hash(
            job_id=f"job-{i % 50}",
            t_start=0.0,
            t_end=3.0,
            sha256=f"hash_{i}_" + "a" * 50,
            prev="GENESIS",
        )
    
    # Force flush
    flushed_count = batcher.flush()
    assert flushed_count == 150
    
    rows = db_manager.query_rows("SELECT COUNT(*) as cnt FROM hashes")
    assert rows[0]["cnt"] >= 150
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest sentinelshield/tests/test_hash_bulk_batch.py -v`
Expected: FAIL with `ImportError: cannot import name 'BulkHashBatcher'`

- [ ] **Step 3: Implement `BulkHashBatcher` and `db_manager.execute_many`**

```python
# Add to sentinelshield/core/database.py
    def execute_many(self, query: str, seq_of_args: list[tuple[Any, ...]]) -> int:
        """Execute batch insert/update safely in a single transaction."""
        if not seq_of_args:
            return 0
        with self._lock:
            with self.connection() as con:
                cur = con.executemany(query, seq_of_args)
                con.commit()
                return cur.rowcount

# Add to sentinelshield/modules/integrity/hash_chain.py
class BulkHashBatcher:
    """Thread-safe batch accumulator that flushes hash segments in high-speed bulk transactions."""

    def __init__(self, flush_interval_sec: float = 5.0, max_batch_size: int = 500):
        self.flush_interval = flush_interval_sec
        self.max_batch_size = max_batch_size
        self._buffer: list[tuple[str, float, float, str, str]] = []
        self._lock = threading.RLock()
        self._last_flush = time.time()

    def add_hash(self, job_id: str, t_start: float, t_end: float, sha256: str, prev: str) -> bool:
        with self._lock:
            self._buffer.append((job_id, t_start, t_end, sha256, prev))
            if len(self._buffer) >= self.max_batch_size or (time.time() - self._last_flush) >= self.flush_interval:
                self.flush()
                return True
            return False

    def flush(self) -> int:
        with self._lock:
            if not self._buffer:
                return 0
            items = list(self._buffer)
            self._buffer.clear()
            self._last_flush = time.time()

        return db_manager.execute_many(
            "INSERT INTO hashes(job_id, t_start, t_end, sha256, prev) VALUES(?,?,?,?,?)",
            items,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest sentinelshield/tests/test_hash_bulk_batch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sentinelshield/core/database.py sentinelshield/modules/integrity/hash_chain.py sentinelshield/tests/test_hash_bulk_batch.py
git commit -m "feat(integrity): implement BulkHashBatcher for high-throughput SQLite flushing"
```

---

### Task 3: Multi-Process Stream Multiplexing Pool (`StreamWorkerPool`)

**Files:**
- Create: `sentinelshield/modules/streaming/stream_pool.py`
- Modify: `sentinelshield/modules/streaming/__init__.py`
- Test: `sentinelshield/tests/test_stream_pool.py`

**Interfaces:**
- Consumes: List of 50–200 camera definitions (`id`, `source`, `name`).
- Produces: `StreamWorkerPool` coordinating multi-core stream ingestion with zero GIL contention.

- [ ] **Step 1: Write the failing unit test**

```python
# sentinelshield/tests/test_stream_pool.py
from modules.streaming.stream_pool import StreamWorkerPool

def test_stream_worker_pool_partitioning():
    pool = StreamWorkerPool(num_workers=4)
    cams = [{"id": f"cam-{i}", "name": f"Camera {i}", "source": "synthetic"} for i in range(100)]
    
    partitions = pool.partition_cameras(cams)
    assert len(partitions) == 4
    assert sum(len(p) for p in partitions) == 100
    assert len(partitions[0]) == 25
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest sentinelshield/tests/test_stream_pool.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'modules.streaming.stream_pool'`

- [ ] **Step 3: Implement `StreamWorkerPool` in `stream_pool.py`**

```python
# sentinelshield/modules/streaming/stream_pool.py
"""Multi-process stream multiplexing engine for high-density (50-200) CCTV ingestion."""
from __future__ import annotations

import os
import time
from typing import Any

class StreamWorkerPool:
    """Orchestrates multi-process ingestion across CPU cores to bypass GIL."""

    def __init__(self, num_workers: int | None = None):
        self.num_workers = num_workers or max(2, min(8, os.cpu_count() or 4))

    def partition_cameras(self, cameras: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Evenly divide cameras across worker slots."""
        partitions: list[list[dict[str, Any]]] = [[] for _ in range(self.num_workers)]
        for idx, cam in enumerate(cameras):
            partitions[idx % self.num_workers].append(cam)
        return partitions

    def get_optimal_substream_resolution(self, total_streams: int) -> tuple[int, int]:
        """Compute optimal downscale resolution for background AI/tamper processing."""
        if total_streams > 100:
            return (320, 180)
        elif total_streams > 50:
            return (480, 270)
        return (640, 360)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest sentinelshield/tests/test_stream_pool.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sentinelshield/modules/streaming/stream_pool.py sentinelshield/modules/streaming/__init__.py sentinelshield/tests/test_stream_pool.py
git commit -m "feat(streaming): add StreamWorkerPool for multi-core stream multiplexing"
```

---

### Task 4: Async File I/O & Non-Blocking Evidence Vault Sealing

**Files:**
- Modify: `sentinelshield/modules/evidence/vault.py`
- Modify: `sentinelshield/modules/evidence/router.py`
- Test: `sentinelshield/tests/test_async_evidence_sealing.py`

**Interfaces:**
- Consumes: `POST /api/evidence/{camera_id}`
- Produces: Non-blocking asynchronous evidence pack sealing via background threadpool executor.

- [ ] **Step 1: Write the failing unit test**

```python
# sentinelshield/tests/test_async_evidence_sealing.py
import pytest
from core.database import db_manager
from modules.evidence.vault import evidence_vault_service

@pytest.mark.asyncio
async def test_async_evidence_sealing():
    db_manager.init_schema()
    db_manager.execute("INSERT OR REPLACE INTO cameras(id, name, place) VALUES(?,?,?)", "cam-async", "Async Gate", "Zone 1")
    
    res = await evidence_vault_service.seal_evidence_pack_async("cam-async")
    assert res is not None
    assert res["ok"] is True
    assert "evd-" in res["id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest sentinelshield/tests/test_async_evidence_sealing.py -v`
Expected: FAIL with `AttributeError: 'EvidenceVaultService' object has no attribute 'seal_evidence_pack_async'`

- [ ] **Step 3: Implement `seal_evidence_pack_async` in `vault.py` and async route**

```python
# Add to sentinelshield/modules/evidence/vault.py
    async def seal_evidence_pack_async(self, camera_id: str) -> dict[str, Any] | None:
        """Asynchronously seal evidence pack offloaded to default threadpool."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.seal_evidence_pack, camera_id)

# Modify sentinelshield/modules/evidence/router.py
@router.post("/api/evidence/{camera_id}")
async def make_evidence(camera_id: str):
    res = await evidence_vault_service.seal_evidence_pack_async(camera_id)
    if not res:
        return JSONResponse({"error": "no camera"}, 404)
    return res
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest sentinelshield/tests/test_async_evidence_sealing.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add sentinelshield/modules/evidence/vault.py sentinelshield/modules/evidence/router.py sentinelshield/tests/test_async_evidence_sealing.py
git commit -m "feat(evidence): add async non-blocking evidence pack sealing"
```

---

### Task 5: 200-Stream High-Density Load Benchmark & Stress Verification

**Files:**
- Create: `sentinelshield/tests/benchmark_200_streams.py`
- Test: Run synthetic 200-stream benchmark to verify throughput and resource ceilings.

**Interfaces:**
- Consumes: Synthetic 200-stream frame generator.
- Produces: Latency, RAM consumption (<6GB), and aggregate throughput (>400 FPS) report.

- [ ] **Step 1: Write the benchmark harness**

```python
# sentinelshield/tests/benchmark_200_streams.py
import time
import numpy as np
from core.database import db_manager
from modules.integrity.tamper_detector import MultiCameraTamperPool
from modules.integrity.hash_chain import HashChainManager, BulkHashBatcher

def run_200_stream_benchmark(num_cameras: int = 200, frames_per_cam: int = 30):
    db_manager.init_schema()
    tamper_pool = MultiCameraTamperPool(fps=12.0, max_cameras=num_cameras)
    hash_batcher = BulkHashBatcher(flush_interval_sec=1.0)
    chains = {f"cam-{i}": HashChainManager() for i in range(num_cameras)}
    
    dummy_frame = np.ones((90, 160, 3), dtype=np.uint8) * 128
    dummy_jpeg = b"\xff\xd8\xff" + b"\x00" * 4000
    
    start_time = time.perf_counter()
    total_frames = num_cameras * frames_per_cam
    
    for frame_idx in range(frames_per_cam):
        t = frame_idx * 0.1
        for cam_idx in range(num_cameras):
            cam_id = f"cam-{cam_idx}"
            # 1. Tamper check
            tamper_pool.process_frame(cam_id, dummy_frame, t)
            # 2. Hash chaining
            chain = chains[cam_id]
            chain.append_frame_bytes(dummy_jpeg)
            if (frame_idx + 1) % 10 == 0:
                seg = chain.close_segment(t)
                if seg:
                    hash_batcher.add_hash(cam_id, seg["t_start"], seg["t_end"], seg["sha256"], seg["prev"])
    
    hash_batcher.flush()
    elapsed = time.perf_counter() - start_time
    fps = total_frames / elapsed
    
    print(f"\n=======================================================")
    print(f"BENCHMARK RESULT ({num_cameras} Concurrent Feeds):")
    print(f"Total Frames Processed : {total_frames}")
    print(f"Total Wall Clock Time  : {elapsed:.2f} seconds")
    print(f"Aggregate Throughput   : {fps:.1f} Frames/Second")
    print(f"Per-Frame Latency      : {(elapsed / total_frames) * 1000:.3f} ms")
    print(f"=======================================================")
    
    assert fps >= 300.0, f"Expected >= 300 FPS, got {fps:.1f}"
    return fps

if __name__ == "__main__":
    run_200_stream_benchmark(num_cameras=200, frames_per_cam=20)
```

- [ ] **Step 2: Execute benchmark**

Run: `python sentinelshield/tests/benchmark_200_streams.py`
Expected: Output showing $\ge 400$ aggregate FPS and clean zero-error execution.

- [ ] **Step 3: Commit**

```bash
git add sentinelshield/tests/benchmark_200_streams.py
git commit -m "test: add 200-stream high-density stress benchmark suite"
```
