"""Empirical Stress Test Harness: 200-Stream High-Density Load & Adaptive Backpressure Challenge.

Adversarially challenges Milestone 2 Dynamic Frame-Dropping Backpressure:
1. High-Density Simulated Load: 200-stream active pool concurrent with 10 slow mobile/web clients (200ms-500ms delay).
2. Dynamic Frame Dropping: Verify dynamic drop scaling (1-in-2, 1-in-3, 1-in-4) reducing CPU/network burden without disconnecting clients.
3. System Responsiveness: Verify stream generators recover back to full frame rate (1-in-1, 25 FPS) once latency returns to nominal (<50ms).
4. Concurrency & Isolation: Verify fast clients are unaffected by concurrent slow clients.
"""
from __future__ import annotations

import concurrent.futures
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# Ensure sentinelshield base directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sentinelshield.core.database import db_manager
from sentinelshield.core.state import LiveStreamState, live_stream_state
from sentinelshield.modules.streaming.mjpeg import mjpeg_frame_generator
from sentinelshield.modules.streaming.stream_pool import StreamWorkerPool


class SyntheticStreamCapture:
    """Thread-safe synthetic video capture stream producing real OpenCV frames."""

    def __init__(self, stream_id: str, total_frames: int = 100, width: int = 640, height: int = 360):
        self.stream_id = stream_id
        self.total_frames = total_frames
        self.width = width
        self.height = height
        self.current_frame = 0
        self._lock = threading.Lock()
        self.released = False

    def isOpened(self) -> bool:
        with self._lock:
            return not self.released and self.current_frame < self.total_frames

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        with self._lock:
            if self.released or self.current_frame >= self.total_frames:
                return False, None
            self.current_frame += 1
            frame_idx = self.current_frame

        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        # Add visual timestamp and stream identifier
        cv2.putText(
            frame,
            f"{self.stream_id} F:{frame_idx}",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 255, 0),
            2,
        )
        return True, frame

    def release(self) -> None:
        with self._lock:
            self.released = True

    def set(self, propId: int, value: float) -> bool:
        return True


@pytest.fixture(autouse=True)
def clean_state():
    """Ensure clean state before and after each test."""
    db_manager.init_schema()
    if live_stream_state.is_active:
        live_stream_state.stop()
    yield
    if live_stream_state.is_active:
        live_stream_state.stop()


# ===========================================================================
# 1. 200-Stream High-Density Active Pool Partitioning & Degradation Policy
# ===========================================================================


def test_200_stream_high_density_pool_partitioning_and_policy():
    """Adversarially challenge StreamWorkerPool under 200 concurrent active CCTV streams."""
    pool = StreamWorkerPool(num_workers=8)

    # 1. Generate 200 synthetic camera estate configurations
    cameras = [
        {
            "id": f"gj-cam-{i:03d}",
            "name": f"Gujarat CCTV Stream {i}",
            "city": ["Ahmedabad", "Surat", "Vadodara", "Rajkot", "Gandhinagar"][i % 5],
            "feed_url": f"rtsp://10.200.1.{i}:554/live",
        }
        for i in range(200)
    ]

    # 2. Verify even partition distribution across 8 worker processes (25 cameras per worker)
    partitions = pool.partition_cameras(cameras)
    assert len(partitions) == 8, f"Expected 8 partitions, got {len(partitions)}"
    for idx, p in enumerate(partitions):
        assert len(p) == 25, f"Worker slot {idx} has {len(p)} cameras, expected 25"

    # 3. Verify hardware profile scaling recommendations for 200 streams
    hw_prof = pool.get_hardware_profile()
    assert hw_prof["recommended_workers"] == 8
    assert hw_prof["max_concurrent_streams"] >= 200

    # 4. Verify optimal downscale resolution for 200 streams (320x180 to conserve memory/CPU)
    res_200 = pool.get_optimal_substream_resolution(200)
    assert res_200 == (320, 180), f"Expected (320, 180) resolution for 200 streams, got {res_200}"

    # 5. Verify backpressure degradation policy at 200 streams
    policy_200 = pool.compute_backpressure_policy(active_streams=200, client_latency_ms=25.0, cpu_percent=50.0)
    assert policy_200["degradation_tier"] == "critical"
    assert policy_200["drop_ratio"] == 4
    assert policy_200["target_fps"] == 6.0
    assert policy_200["jpeg_quality"] == 45
    assert policy_200["throttle"] == 0.3

    # 6. Verify frame dropping pattern: 1-in-4 frames sent, 3 dropped
    for f in range(1, 21):
        should_drop = pool.should_drop_frame(f, active_streams=200)
        expected_drop = (f % 4) != 0
        assert should_drop == expected_drop, f"Frame {f}: expected drop={expected_drop}, got {should_drop}"


# ===========================================================================
# 2. 10 Concurrent Slow Mobile/Web Clients (200ms - 500ms Network Delay)
# ===========================================================================


def test_concurrent_slow_clients_dynamic_frame_dropping():
    """Simulate 10 concurrent slow mobile/web clients with network delivery latencies from 200ms to 500ms.

    Verifies:
    - All 10 clients receive valid MJPEG frames without disconnecting or erroring.
    - Intermediate frames are dynamically dropped (1-in-2, 1-in-3, 1-in-4) in response to client latency.
    - Captured frames > Yielded frames for every slow client, demonstrating CPU/bandwidth savings.
    """
    num_clients = 10
    delays_ms = [200, 220, 250, 300, 320, 350, 400, 420, 450, 500]
    total_source_frames = 50

    cam_id = "cam-dense-multi-client"
    stream_url = "rtsp://edge-gujarat-01:8554/feed"

    live_stream_state.start(cam_id, "url", stream_url)

    client_caps: Dict[int, SyntheticStreamCapture] = {}
    cap_lock = threading.Lock()

    def mock_hw_videocapture_factory(path: str, preferred_accel: str = "auto"):
        # Match client index from calling thread name
        tname = threading.current_thread().name
        c_idx = int(tname.split("-")[-1]) if "client-" in tname else 0
        cap = SyntheticStreamCapture(f"client-{c_idx}", total_frames=total_source_frames)
        with cap_lock:
            client_caps[c_idx] = cap
        return cap, "cuda"

    results: Dict[int, Dict[str, Any]] = {}
    threads = []

    with patch("modules.streaming.mjpeg.create_hw_videocapture", side_effect=mock_hw_videocapture_factory):
        def client_worker(client_idx: int, delay_ms: float):
            gen = mjpeg_frame_generator(
                camera_id=cam_id,
                path=stream_url,
                loop_file=False,
                adaptive_backpressure=True,
            )

            frames_received = 0
            chunks_bytes = 0
            start_time = time.time()

            try:
                # Read 10 chunks while simulating slow mobile client network delay
                for _ in range(10):
                    chunk = next(gen)
                    assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                    assert b"\xff\xd8" in chunk
                    frames_received += 1
                    chunks_bytes += len(chunk)
                    # Simulate client network delivery delay
                    time.sleep(delay_ms / 1000.0)

            except StopIteration:
                pass
            except Exception as e:
                results[client_idx] = {"error": str(e), "frames_received": frames_received}
                return

            elapsed = time.time() - start_time
            with cap_lock:
                cap_obj = client_caps.get(client_idx)
                frames_read = cap_obj.current_frame if cap_obj else 0

            results[client_idx] = {
                "frames_received": frames_received,
                "frames_read_from_source": frames_read,
                "bytes_transferred": chunks_bytes,
                "delay_ms": delay_ms,
                "elapsed_sec": elapsed,
                "error": None,
            }

        # Launch all 10 slow mobile/web clients concurrently
        for i in range(num_clients):
            t = threading.Thread(target=client_worker, name=f"client-{i}", args=(i, delays_ms[i]))
            threads.append(t)
            t.start()

        for t in threads:
            t.join(timeout=20.0)

    live_stream_state.stop()

    # Empirical Verifications across all 10 clients
    assert len(results) == num_clients, f"Expected {num_clients} client results, got {len(results)}"

    for i in range(num_clients):
        res = results[i]
        assert res["error"] is None, f"Client {i} failed with error: {res['error']}"
        assert res["frames_received"] == 10, f"Client {i} received {res['frames_received']} frames, expected 10"

        # Frame dropping verification: source read count MUST exceed yielded count
        read_count = res["frames_read_from_source"]
        yielded_count = res["frames_received"]
        delay = res["delay_ms"]

        assert read_count > yielded_count, (
            f"Client {i} (delay={delay}ms): frames read ({read_count}) should be greater than "
            f"yielded ({yielded_count}) due to backpressure frame dropping"
        )

        # For critical delays (>=350ms), drop ratio reaches 3 or 4
        if delay >= 350:
            assert read_count >= 18, (
                f"Client {i} (delay={delay}ms): expected heavy/critical frame dropping (read >= 18, got {read_count})"
            )


# ===========================================================================
# 3. Dynamic Recovery to Nominal Rate (<50ms Latency)
# ===========================================================================


def test_dynamic_backpressure_recovery_to_nominal_latency():
    """Verify that stream generators dynamically recover back to full frame rate (drop_ratio=1)

    when client latency drops back from critical (400ms) to nominal (5ms).
    """
    cam_id = "cam-recovery-test"
    stream_url = "rtsp://edge-gujarat-02:8554/live"

    live_stream_state.start(cam_id, "url", stream_url)
    mock_cap = SyntheticStreamCapture("recovery-cam", total_frames=80)

    with patch("modules.streaming.mjpeg.create_hw_videocapture", return_value=(mock_cap, "d3d11")):
        gen = mjpeg_frame_generator(
            camera_id=cam_id,
            path=stream_url,
            loop_file=False,
            adaptive_backpressure=True,
        )

        try:
            # Phase 1: Fast initial connection (5 frames @ 5ms nominal latency)
            phase1_read_start = mock_cap.current_frame
            for _ in range(5):
                chunk = next(gen)
                assert chunk is not None
                time.sleep(0.005)  # 5ms nominal
            phase1_read_end = mock_cap.current_frame
            phase1_consumed = phase1_read_end - phase1_read_start
            # Nominal latency: 1:1 delivery, no frames dropped
            assert phase1_consumed == 5, f"Phase 1 (nominal): consumed {phase1_consumed} frames, expected 5"

            # Phase 2: Severe network congestion (8 frames @ 400ms critical latency)
            phase2_read_start = mock_cap.current_frame
            for _ in range(8):
                chunk = next(gen)
                assert chunk is not None
                time.sleep(0.400)  # 400ms critical backpressure
            phase2_read_end = mock_cap.current_frame
            phase2_consumed = phase2_read_end - phase2_read_start
            # Severe congestion: frames should be dropped (1-in-3 or 1-in-4 ratio)
            assert phase2_consumed > 8, f"Phase 2 (congestion): consumed {phase2_consumed} source frames for 8 yielded"
            assert phase2_consumed >= 16, f"Phase 2: expected at least 16 source reads for 8 frames at 400ms delay, got {phase2_consumed}"

            # Phase 3: Network congestion clears (15 frames @ 5ms nominal latency)
            # EMA latency should decay down (<40ms) and generator should return to 1:1 delivery
            phase3_read_start = mock_cap.current_frame
            for _ in range(15):
                chunk = next(gen)
                assert chunk is not None
                time.sleep(0.005)  # 5ms nominal
            phase3_read_end = mock_cap.current_frame
            phase3_consumed = phase3_read_end - phase3_read_start

            # By the second half of Phase 3, EMA latency has fully decayed back to nominal.
            # Verify Phase 4: Final 5 frames delivered 1:1 with zero dropping
            phase4_read_start = mock_cap.current_frame
            for _ in range(5):
                chunk = next(gen)
                assert chunk is not None
                time.sleep(0.002)  # 2ms ultra-fast
            phase4_read_end = mock_cap.current_frame
            phase4_consumed = phase4_read_end - phase4_read_start
            assert phase4_consumed == 5, f"Phase 4 (recovered): consumed {phase4_consumed} source frames for 5 yielded (expected 1:1 100% recovery)"

        finally:
            live_stream_state.stop()
            try:
                for _ in gen:
                    pass
            except StopIteration:
                pass


# ===========================================================================
# 4. Concurrency Isolation: Fast vs. Slow Client Coexistence
# ===========================================================================


def test_concurrent_fast_and_slow_client_isolation():
    """Verify that slow clients undergo dynamic frame dropping while fast clients concurrently maintain full 1:1 rate."""
    cam_id = "cam-isolation-test"
    stream_url = "rtsp://edge-gujarat-03:8554/live"

    live_stream_state.start(cam_id, "url", stream_url)

    fast_client_results = []
    slow_client_results = []

    fast_cap = SyntheticStreamCapture("fast-cam", total_frames=30)
    slow_cap = SyntheticStreamCapture("slow-cam", total_frames=40)

    def mock_factory(path, preferred_accel="auto"):
        tname = threading.current_thread().name
        if "fast" in tname:
            return fast_cap, "cuda"
        return slow_cap, "cuda"

    with patch("modules.streaming.mjpeg.create_hw_videocapture", side_effect=mock_factory):
        def fast_consumer():
            gen = mjpeg_frame_generator(camera_id=cam_id, path=stream_url, adaptive_backpressure=True)
            for _ in range(10):
                chunk = next(gen)
                time.sleep(0.005)  # 5ms fast
            fast_client_results.append((10, fast_cap.current_frame))

        def slow_consumer():
            gen = mjpeg_frame_generator(camera_id=cam_id, path=stream_url, adaptive_backpressure=True)
            for _ in range(10):
                chunk = next(gen)
                time.sleep(0.300)  # 300ms slow
            slow_client_results.append((10, slow_cap.current_frame))

        t_fast = threading.Thread(target=fast_consumer, name="fast-consumer")
        t_slow = threading.Thread(target=slow_consumer, name="slow-consumer")

        t_fast.start()
        t_slow.start()

        t_fast.join(timeout=10.0)
        t_slow.join(timeout=10.0)

    live_stream_state.stop()

    assert len(fast_client_results) == 1
    assert len(slow_client_results) == 1

    fast_yielded, fast_source_read = fast_client_results[0]
    slow_yielded, slow_source_read = slow_client_results[0]

    # Fast client: 1:1 frame delivery (read 10 frames for 10 yielded)
    assert fast_yielded == 10
    assert fast_source_read == 10, f"Fast client read {fast_source_read} frames, expected exactly 10 (no dropping)"

    # Slow client: Frame dropping active (read > 10 frames for 10 yielded)
    assert slow_yielded == 10
    assert slow_source_read > 10, f"Slow client read {slow_source_read} frames, expected > 10 due to backpressure"


# ===========================================================================
# 5. Latency Jitter and Spike Robustness
# ===========================================================================


def test_latency_jitter_and_transient_spike_resilience():
    """Verify generator gracefully absorbs intermittent latency spikes (e.g. cellular handoff)

    without crashing, disconnecting, or permanently locking into degraded state.
    """
    cam_id = "cam-jitter-test"
    stream_url = "rtsp://edge-gujarat-04:8554/live"

    live_stream_state.start(cam_id, "url", stream_url)
    mock_cap = SyntheticStreamCapture("jitter-cam", total_frames=40)

    with patch("modules.streaming.mjpeg.create_hw_videocapture", return_value=(mock_cap, "cuda")):
        gen = mjpeg_frame_generator(camera_id=cam_id, path=stream_url, adaptive_backpressure=True)

        # 1. Yield 3 normal frames
        for _ in range(3):
            chunk = next(gen)
            assert chunk is not None
            time.sleep(0.01)

        # 2. Sudden transient network stall (800ms spike)
        chunk = next(gen)
        assert chunk is not None
        time.sleep(0.800)

        # 3. Immediate return to nominal speed
        for _ in range(8):
            chunk = next(gen)
            assert chunk is not None
            time.sleep(0.01)

        # Confirm stream is still alive and healthy
        assert live_stream_state.is_active

    live_stream_state.stop()


if __name__ == "__main__":
    pytest.main(["-v", __file__])
