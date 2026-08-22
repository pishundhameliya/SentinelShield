"""Unit test for StreamWorkerPool multi-process stream multiplexing and dynamic autotuning."""
from __future__ import annotations

import sys
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

if "fastapi" not in sys.modules:
    from unittest.mock import MagicMock
    sys.modules["fastapi"] = MagicMock()
    sys.modules["fastapi.responses"] = MagicMock()

from modules.streaming.stream_pool import StreamWorkerPool


def test_stream_worker_pool_partitioning_and_autotuning():
    pool = StreamWorkerPool(num_workers=4)

    # Test partitioning 100 cameras
    cams = [{"id": f"cam-{i}", "name": f"Camera {i}", "source": "synthetic"} for i in range(100)]
    partitions = pool.partition_cameras(cams)
    assert len(partitions) == 4
    assert sum(len(p) for p in partitions) == 100
    assert len(partitions[0]) == 25

    # Test adaptive resolution tiers
    assert pool.get_optimal_substream_resolution(30) == (640, 360)
    assert pool.get_optimal_substream_resolution(75) == (480, 270)
    assert pool.get_optimal_substream_resolution(150) == (320, 180)

    # Test hardware profile autodiscovery
    profile = pool.get_hardware_profile()
    assert "cpu_cores" in profile
    assert profile["cpu_cores"] >= 1
    assert "recommended_workers" in profile

    # Test adaptive sampling throttle
    throttle_30 = pool.compute_adaptive_throttle(active_streams=30, cpu_percent=35.0)
    throttle_200 = pool.compute_adaptive_throttle(active_streams=200, cpu_percent=85.0)
    assert throttle_30 >= throttle_200, "Throttle should be lower (more conservative FPS) under high load"

    print("[PASS] Task 3 Verified: StreamWorkerPool multi-process partitioning & hardware autotuning working!")


if __name__ == "__main__":
    test_stream_worker_pool_partitioning_and_autotuning()
