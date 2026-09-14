"""Empirical Adversarial Test Suite: Stream Disconnect & Concurrency Challenger (Milestone 1).

Adversarially verifies:
1. Rapid Disconnect Simulation:
   - Video source drops immediately after 5 frames, reconnects, drops again, repeating 10 cycles.
   - Verifies placeholder frame delivery, zero uncaught exceptions, zero file descriptor/VideoCapture leaks, and bounded memory.
2. Concurrent Generator Stop:
   - 20 parallel mjpeg_frame_generator instances pointing to invalid or disconnecting streams.
   - Signals live_stream_state.stop() and measures shutdown latency (must be <1.0s).
"""
from __future__ import annotations

import gc
import os
import sys
import threading
import time
import tracemalloc
from typing import Any, Generator
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from sentinelshield.core.database import db_manager
from sentinelshield.core.state import live_stream_state
from sentinelshield.modules.streaming.mjpeg import (
    create_reconnect_placeholder_frame,
    mjpeg_frame_generator,
)


@pytest.fixture(autouse=True)
def cleanup_stream_state():
    """Ensure clean stream state before and after each test."""
    if live_stream_state.is_active:
        live_stream_state.stop()
    yield
    if live_stream_state.is_active:
        live_stream_state.stop()


class SimulatedFlappingVideoCapture:
    """Simulates a camera source that produces N valid frames and then drops."""

    active_instances: list[SimulatedFlappingVideoCapture] = []
    instance_lock = threading.Lock()

    def __init__(self, path: str, frames_before_drop: int = 5, frame_shape=(480, 640, 3)):
        self.path = path
        self.frames_before_drop = frames_before_drop
        self.frame_shape = frame_shape
        self.frames_read = 0
        self.is_opened = True
        self.released = False

        with self.instance_lock:
            SimulatedFlappingVideoCapture.active_instances.append(self)

    def isOpened(self) -> bool:
        return self.is_opened and not self.released

    def read(self) -> tuple[bool, np.ndarray | None]:
        if self.released or not self.is_opened:
            return False, None

        if self.frames_read < self.frames_before_drop:
            self.frames_read += 1
            # Generate deterministic synthetic video frame
            frame = np.full(self.frame_shape, fill_value=(self.frames_read * 40) % 255, dtype=np.uint8)
            cv2.putText(
                frame,
                f"SIM FRAME #{self.frames_read}",
                (30, 60),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (0, 255, 0),
                2,
            )
            return True, frame
        else:
            # Dropped connection
            return False, None

    def release(self) -> None:
        self.released = True
        self.is_opened = False

    def set(self, prop_id: int, value: float) -> bool:
        return True


def extract_jpeg_from_mjpeg_chunk(chunk: bytes) -> np.ndarray:
    """Extract and decode JPEG payload from multipart MJPEG frame chunk."""
    header_end = chunk.find(b"\r\n\r\n")
    assert header_end != -1, "Malformed multipart MJPEG chunk: missing header terminator"
    jpeg_bytes = chunk[header_end + 4 : -2]  # strip trailing \r\n
    img = cv2.imdecode(np.frombuffer(jpeg_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert img is not None, "Failed to decode JPEG bytes from MJPEG chunk"
    return img


def test_rapid_disconnect_10_cycles_empirical():
    """Adversarial Test 1: Rapid Disconnect Simulation (10x drops after 5 frames).

    Verifies:
    - 10 consecutive connection -> 5 frames -> drop -> placeholder -> reconnect cycles.
    - Placeholder frames delivered during disconnection backoffs.
    - Zero uncaught exceptions.
    - All VideoCapture instances released (no handle/FD leak).
    - Stable memory allocation without leaks across all 10 cycles.
    """
    camera_id = "cam-flapping-adversarial-1"
    stream_path = "rtsp://simulated-flapping-edge-node:8554/live"

    live_stream_state.start(camera_id, "url", stream_path)

    SimulatedFlappingVideoCapture.active_instances.clear()
    gc.collect()
    tracemalloc.start()
    mem_snapshot_before = tracemalloc.take_snapshot()

    captured_live_chunks = 0
    captured_placeholder_chunks = 0
    total_chunks = 0

    def video_capture_factory(path):
        return SimulatedFlappingVideoCapture(path, frames_before_drop=5, frame_shape=(480, 640, 3))

    # Deterministic virtual clock to simulate real-time progression precisely
    simulated_clock = [1000.0]

    def mock_time():
        return simulated_clock[0]

    def mock_sleep(duration):
        simulated_clock[0] += duration

    def hw_cap_factory(p, **kwargs):
        return video_capture_factory(p), "software"

    with patch("modules.streaming.mjpeg.create_hw_videocapture", side_effect=hw_cap_factory), \
         patch("modules.streaming.mjpeg.time.time", side_effect=mock_time), \
         patch("modules.streaming.mjpeg.time.sleep", side_effect=mock_sleep):

        gen = mjpeg_frame_generator(
            camera_id=camera_id,
            path=stream_path,
            loop_file=False,
            initial_backoff=1.0,
            max_backoff=16.0,
        )

        try:
            # Run until 10 full disconnect cycles have completed
            while True:
                chunk = next(gen)
                total_chunks += 1

                # Validate chunk format & decode JPEG
                assert isinstance(chunk, bytes)
                assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                assert chunk.endswith(b"\r\n")
                
                decoded_img = extract_jpeg_from_mjpeg_chunk(chunk)
                h, w, c = decoded_img.shape

                if (h, w) == (480, 640):
                    captured_live_chunks += 1
                elif (h, w) == (360, 640):
                    captured_placeholder_chunks += 1

                released_count = len([inst for inst in SimulatedFlappingVideoCapture.active_instances if inst.released])
                if released_count >= 10:
                    # 10 full disconnect-release cycles verified!
                    break

        finally:
            live_stream_state.stop()
            try:
                for _ in gen:
                    pass
            except StopIteration:
                pass
            gen.close()

    mem_snapshot_after = tracemalloc.take_snapshot()
    top_stats = mem_snapshot_after.compare_to(mem_snapshot_before, "lineno")
    tracemalloc.stop()

    # Empirical Assertions
    instances = SimulatedFlappingVideoCapture.active_instances
    assert len(instances) >= 10, f"Expected at least 10 disconnect cycles, observed {len(instances)}"
    assert all(inst.released for inst in instances), f"Leaked VideoCapture instances detected! Unreleased: {[i for i in instances if not i.released]}"
    assert captured_placeholder_chunks >= 10, f"Expected >=10 placeholder frames, got {captured_placeholder_chunks}"
    assert captured_live_chunks >= 10, f"Expected >=10 live frames across 10 cycles, got {captured_live_chunks}"
    assert total_chunks >= 20, f"Expected >=20 total chunks yielded, got {total_chunks}"

    # Verify memory growth is strictly bounded (< 5MB diff after 10 full cycles)
    total_mem_diff = sum(stat.size_diff for stat in top_stats)
    assert total_mem_diff < 5 * 1024 * 1024, f"Memory leak detected: {total_mem_diff / (1024*1024):.2f} MB growth"


def test_concurrent_generator_stop_20_instances_latency():
    """Adversarial Test 2: Concurrent Generator Stop (20 parallel streams).

    Verifies:
    - 20 concurrent mjpeg_frame_generator instances running against invalid/disconnecting streams.
    - All 20 threads are actively consuming placeholder/backoff frames.
    - live_stream_state.stop() is signaled.
    - Shutdown latency across all 20 threads is strictly measured and MUST be < 1.0s.
    - Zero uncaught exceptions or thread deadlocks.
    """
    camera_id = "cam-concurrent-20-test"
    invalid_path_template = "rtsp://non-existent-camera-{i}.sentinel.internal:8554/live"
    live_stream_state.start(camera_id, "url", invalid_path_template.format(i=0))

    num_threads = 20
    threads: list[threading.Thread] = []
    thread_errors: list[Exception] = []
    first_frame_received: list[bool] = [False] * num_threads
    thread_exit_times: list[float] = [0.0] * num_threads

    ready_barrier = threading.Barrier(num_threads + 1)

    def generator_consumer_worker(idx: int):
        stream_url = invalid_path_template.format(i=idx)
        # Configure generator with long backoff so it stays in the backoff sleep loop
        gen = mjpeg_frame_generator(
            camera_id=camera_id,
            path=stream_url,
            loop_file=False,
            initial_backoff=5.0,
            max_backoff=16.0,
        )
        try:
            # Read first placeholder frame to confirm active running state
            frame = next(gen)
            assert b"Content-Type: image/jpeg" in frame
            first_frame_received[idx] = True

            # Synchronize with main test thread
            ready_barrier.wait(timeout=5.0)

            # Continue consuming until stop signal terminates the generator
            for chunk in gen:
                pass
        except StopIteration:
            pass
        except Exception as exc:
            thread_errors.append(exc)
        finally:
            thread_exit_times[idx] = time.perf_counter()

    for i in range(num_threads):
        t = threading.Thread(target=generator_consumer_worker, args=(i,), daemon=True, name=f"mjpeg-worker-{i}")
        threads.append(t)
        t.start()

    # Wait until all 20 workers have acquired their initial placeholder frames
    ready_barrier.wait(timeout=8.0)
    assert all(first_frame_received), "Not all 20 generator threads became active before stop signal."

    # Allow threads to settle into their backoff sleep loops
    time.sleep(0.1)

    # Trigger stop signal and measure total latency for all 20 threads to exit
    t_stop_start = time.perf_counter()
    stopped_cam = live_stream_state.stop()
    assert stopped_cam == camera_id

    # Join all 20 threads with timeout
    for t in threads:
        t.join(timeout=1.5)

    t_stop_end = time.perf_counter()
    shutdown_latency = t_stop_end - t_stop_start

    # Empirical Assertions
    assert len(thread_errors) == 0, f"Encountered thread errors during concurrent run: {thread_errors}"
    assert all(not t.is_alive() for t in threads), "One or more generator threads hung/deadlocked after stop()."
    assert shutdown_latency < 1.0, (
        f"Concurrent stop latency violation: took {shutdown_latency:.3f}s, requirement is < 1.0s"
    )


def test_concurrent_active_stream_stop_20_instances_latency():
    """Adversarial Test 3: Concurrent Active Stream Stop (20 parallel streams on live video).

    Verifies:
    - 20 concurrent mjpeg_frame_generator instances running against simulated active streams.
    - live_stream_state.stop() is signaled while reading live frames.
    - Shutdown latency across all 20 threads is strictly measured and MUST be < 1.0s.
    """
    camera_id = "cam-concurrent-live-20"
    stream_path = "rtsp://simulated-live-node:8554/live"
    live_stream_state.start(camera_id, "url", stream_path)

    num_threads = 20
    threads: list[threading.Thread] = []
    thread_errors: list[Exception] = []
    frames_received = [0] * num_threads

    def infinite_active_video_capture(path):
        return SimulatedFlappingVideoCapture(path, frames_before_drop=999999)

    ready_barrier = threading.Barrier(num_threads + 1)

    def live_consumer_worker(idx: int):
        gen = mjpeg_frame_generator(
            camera_id=camera_id,
            path=stream_path,
            loop_file=False,
            initial_backoff=1.0,
            max_backoff=5.0,
        )
        try:
            # Read first frame
            frame = next(gen)
            frames_received[idx] += 1
            ready_barrier.wait(timeout=5.0)

            for _ in gen:
                frames_received[idx] += 1
        except StopIteration:
            pass
        except Exception as exc:
            thread_errors.append(exc)

    def hw_infinite_factory(p, **kwargs):
        return infinite_active_video_capture(p), "software"

    with patch("modules.streaming.mjpeg.create_hw_videocapture", side_effect=hw_infinite_factory):
        for i in range(num_threads):
            t = threading.Thread(target=live_consumer_worker, args=(i,), daemon=True, name=f"live-worker-{i}")
            threads.append(t)
            t.start()

        ready_barrier.wait(timeout=5.0)
        time.sleep(0.1)

        t_stop_start = time.perf_counter()
        live_stream_state.stop()

        for t in threads:
            t.join(timeout=1.5)

        t_stop_end = time.perf_counter()
        shutdown_latency = t_stop_end - t_stop_start

    assert len(thread_errors) == 0, f"Encountered thread errors during active stop: {thread_errors}"
    assert all(not t.is_alive() for t in threads), "One or more live generator threads deadlocked."
    assert shutdown_latency < 1.0, (
        f"Active stream concurrent stop latency violation: took {shutdown_latency:.3f}s, requirement is < 1.0s"
    )
