"""Comprehensive Unit and Integration Test Suite for Milestone 2: High-Density Video Acceleration & Adaptive Backpressure."""
from __future__ import annotations

import gc
import os
import sys
import time
from typing import Any, List, Optional
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# Ensure sentinelshield base directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import db_manager
from core.state import live_stream_state
from modules.streaming.hw_accel import (
    create_hw_videocapture,
    get_available_hw_accelerations,
)
from modules.streaming.mjpeg import (
    create_reconnect_placeholder_frame,
    mjpeg_frame_generator,
)
from modules.streaming.stream_pool import StreamWorkerPool


@pytest.fixture(autouse=True)
def cleanup_stream_state():
    """Ensure clean stream and database state before and after each test."""
    db_manager.init_schema()
    if live_stream_state.is_active:
        live_stream_state.stop()
    yield
    if live_stream_state.is_active:
        live_stream_state.stop()


# ---------------------------------------------------------------------------
# 1. Hardware Acceleration Detection Tests
# ---------------------------------------------------------------------------


def test_get_available_hw_accelerations_default():
    """Verify get_available_hw_accelerations returns a valid list of backends including software."""
    accels = get_available_hw_accelerations()
    assert isinstance(accels, list)
    assert len(accels) >= 1
    assert "software" in accels

    # On Windows, MSMF, DShow, and FFmpeg should be detected
    if sys.platform == "win32":
        assert "msmf" in accels or "ffmpeg" in accels


def test_get_available_hw_accelerations_with_mocked_cuda():
    """Verify CUDA acceleration is detected when cv2.cuda has enabled devices."""
    mock_cuda = MagicMock()
    mock_cuda.getCudaEnabledDeviceCount.return_value = 2

    with patch.object(cv2, "cuda", mock_cuda, create=True):
        accels = get_available_hw_accelerations()
        assert "cuda" in accels
        assert "software" in accels


def test_get_available_hw_accelerations_with_env_cuda():
    """Verify CUDA acceleration is detected via CUDA_VISIBLE_DEVICES environment variable."""
    with patch.dict(os.environ, {"CUDA_VISIBLE_DEVICES": "0,1"}):
        accels = get_available_hw_accelerations()
        assert "cuda" in accels


# ---------------------------------------------------------------------------
# 2. Hardware VideoCapture Probing and Fallback Tests
# ---------------------------------------------------------------------------


def test_create_hw_videocapture_software_fallback():
    """Verify create_hw_videocapture successfully opens standard software capture."""
    cap, backend = create_hw_videocapture("http://synthetic-camera-source:8080/feed", preferred_accel="software")
    assert cap is not None
    assert backend == "software"
    assert cap.isOpened()
    cap.release()


def test_create_hw_videocapture_auto_mode():
    """Verify auto mode selects an available backend and opens capture."""
    cap, backend = create_hw_videocapture("http://synthetic-camera-source:8080/feed", preferred_accel="auto")
    assert cap is not None
    assert isinstance(backend, str)
    assert backend in ("cuda", "msmf", "dshow", "ffmpeg", "software")
    assert cap.isOpened()
    cap.release()


def test_create_hw_videocapture_graceful_hardware_error_fallback():
    """Verify that when a preferred hardware backend throws an exception, it cleanly falls back to software."""
    original_vc = cv2.VideoCapture

    def failing_videocapture_constructor(src, api_pref=0):
        if api_pref != getattr(cv2, "CAP_ANY", 0):
            raise RuntimeError("Hardware decode initialization failed (simulated CUDA/MSMF crash)")
        return original_vc(src, getattr(cv2, "CAP_ANY", 0))

    with patch.object(cv2, "VideoCapture", side_effect=failing_videocapture_constructor):
        cap, backend = create_hw_videocapture("http://synthetic-test:8080/live", preferred_accel="cuda")
        assert cap is not None
        assert backend == "software"
        assert cap.isOpened()
        cap.release()


def test_create_hw_videocapture_invalid_source_unopened():
    """Verify invalid stream source cleanly returns unopened capture without crashing."""
    cap, backend = create_hw_videocapture("rtsp://invalid-offline-stream.local:9999/feed", preferred_accel="auto")
    assert cap is not None
    assert not cap.isOpened()
    assert backend == "software"
    cap.release()


def test_create_hw_videocapture_integer_device_index():
    """Verify device index (0 or "0") is handled properly."""
    cap, backend = create_hw_videocapture(0, preferred_accel="auto")
    assert cap is not None
    assert cap.isOpened()
    cap.release()

    cap2, backend2 = create_hw_videocapture("0", preferred_accel="auto")
    assert cap2 is not None
    assert cap2.isOpened()
    cap2.release()


# ---------------------------------------------------------------------------
# 3. StreamWorkerPool Backpressure Policies Tests
# ---------------------------------------------------------------------------


def test_stream_worker_pool_backpressure_policy_tiers():
    """Verify StreamWorkerPool computes correct degradation policies across all latency/load tiers."""
    pool = StreamWorkerPool(num_workers=4)

    # 1. Nominal Tier (<=40ms latency, <=50 streams, <=60% CPU)
    p_nominal = pool.compute_backpressure_policy(active_streams=20, client_latency_ms=15.0, cpu_percent=30.0)
    assert p_nominal["degradation_tier"] == "nominal"
    assert p_nominal["drop_ratio"] == 1
    assert p_nominal["target_fps"] == 25.0
    assert p_nominal["jpeg_quality"] == 75
    assert p_nominal["substream_resolution"] == (640, 360)
    assert p_nominal["throttle"] == 1.0

    # 2. Moderate Tier (40-120ms latency, 51-100 streams, or 60-80% CPU)
    p_moderate = pool.compute_backpressure_policy(active_streams=65, client_latency_ms=70.0, cpu_percent=70.0)
    assert p_moderate["degradation_tier"] == "moderate"
    assert p_moderate["drop_ratio"] == 2
    assert p_moderate["target_fps"] == 12.5
    assert p_moderate["jpeg_quality"] == 65
    assert p_moderate["substream_resolution"] == (480, 270)
    assert p_moderate["throttle"] == 0.6

    # 3. Heavy Tier (120-300ms latency, 101-180 streams, or 80-90% CPU)
    p_heavy = pool.compute_backpressure_policy(active_streams=130, client_latency_ms=200.0, cpu_percent=85.0)
    assert p_heavy["degradation_tier"] == "heavy"
    assert p_heavy["drop_ratio"] == 3
    assert p_heavy["target_fps"] == 8.0
    assert p_heavy["jpeg_quality"] == 55
    assert p_heavy["substream_resolution"] == (320, 180)
    assert p_heavy["throttle"] == 0.3

    # 4. Critical Tier (>300ms latency, >180 streams, or >90% CPU)
    p_critical = pool.compute_backpressure_policy(active_streams=195, client_latency_ms=450.0, cpu_percent=95.0)
    assert p_critical["degradation_tier"] == "critical"
    assert p_critical["drop_ratio"] >= 4
    assert p_critical["target_fps"] <= 6.0
    assert p_critical["jpeg_quality"] <= 45
    assert p_critical["substream_resolution"] == (320, 180)
    assert p_critical["throttle"] == 0.3


def test_stream_worker_pool_should_drop_frame_logic():
    """Verify should_drop_frame correctly calculates frame dropping decisions."""
    pool = StreamWorkerPool()

    # Nominal load: no frames should be dropped (drop_ratio=1)
    for i in range(1, 10):
        assert not pool.should_drop_frame(frame_index=i, active_streams=10, client_latency_ms=20.0)

    # Moderate load (drop_ratio=2): send odd/even depending on modulo (1 in 2)
    assert pool.should_drop_frame(frame_index=1, active_streams=60, client_latency_ms=70.0) is True
    assert pool.should_drop_frame(frame_index=2, active_streams=60, client_latency_ms=70.0) is False
    assert pool.should_drop_frame(frame_index=3, active_streams=60, client_latency_ms=70.0) is True
    assert pool.should_drop_frame(frame_index=4, active_streams=60, client_latency_ms=70.0) is False

    # Heavy load (drop_ratio=3): send 1 in every 3 frames
    assert pool.should_drop_frame(frame_index=1, active_streams=120, client_latency_ms=180.0) is True
    assert pool.should_drop_frame(frame_index=2, active_streams=120, client_latency_ms=180.0) is True
    assert pool.should_drop_frame(frame_index=3, active_streams=120, client_latency_ms=180.0) is False


# ---------------------------------------------------------------------------
# 4. Dynamic Frame-Dropping Backpressure Integration in MJPEG Generator
# ---------------------------------------------------------------------------


class MockLiveStreamCapture:
    """Mock VideoCapture generating a stream of synthetic frames."""
    def __init__(self, path: str, total_frames: int = 50):
        self.path = path
        self.total_frames = total_frames
        self.current_frame = 0
        self.released = False

    def isOpened(self) -> bool:
        return not self.released and self.current_frame < self.total_frames

    def read(self) -> tuple[bool, Optional[np.ndarray]]:
        if not self.isOpened():
            return False, None
        self.current_frame += 1
        frame = np.zeros((360, 640, 3), dtype=np.uint8)
        cv2.putText(frame, f"Frame {self.current_frame}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
        return True, frame

    def release(self) -> None:
        self.released = True

    def set(self, propId: int, value: float) -> bool:
        return True


def test_dynamic_frame_dropping_under_simulated_consumer_latency():
    """Verify that slow consumer delivery latency triggers dynamic frame dropping in mjpeg_frame_generator."""
    cam_id = "cam-backpressure-test-1"
    stream_url = "rtsp://live-test-edge:554/cam1"

    live_stream_state.start(cam_id, "url", stream_url)
    mock_cap = MockLiveStreamCapture(stream_url, total_frames=40)

    with patch("modules.streaming.mjpeg.create_hw_videocapture", return_value=(mock_cap, "cuda")):
        gen = mjpeg_frame_generator(
            camera_id=cam_id,
            path=stream_url,
            loop_file=False,
            adaptive_backpressure=True,
        )

        yielded_chunks = []
        try:
            # Read first 3 frames with fast reader (<1ms)
            for _ in range(3):
                chunk = next(gen)
                yielded_chunks.append(chunk)
                assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")
                assert b"\xff\xd8" in chunk

            # Simulate high consumer backpressure (slow client reading frames with 150ms delay)
            slow_yielded_chunks = []
            for _ in range(5):
                chunk = next(gen)
                slow_yielded_chunks.append(chunk)
                time.sleep(0.15)

            total_yielded = len(yielded_chunks) + len(slow_yielded_chunks)
            # Verify that mock capture was read for more frames than were yielded due to dynamic frame dropping
            assert mock_cap.current_frame > total_yielded, f"Expected frames dropped: read={mock_cap.current_frame}, yielded={total_yielded}"

        finally:
            live_stream_state.stop()
            try:
                for _ in gen:
                    pass
            except StopIteration:
                pass


def test_mjpeg_frame_generator_hardware_acceleration_parameter():
    """Verify mjpeg_frame_generator passes preferred_accel to create_hw_videocapture."""
    cam_id = "cam-hw-param-test"
    stream_url = "rtsp://edge-node-cam:8554/feed"

    live_stream_state.start(cam_id, "url", stream_url)
    mock_cap = MockLiveStreamCapture(stream_url, total_frames=10)

    with patch("modules.streaming.mjpeg.create_hw_videocapture", return_value=(mock_cap, "msmf")) as mock_factory:
        gen = mjpeg_frame_generator(
            camera_id=cam_id,
            path=stream_url,
            preferred_accel="msmf",
            adaptive_backpressure=True,
        )

        chunk = next(gen)
        assert chunk is not None
        assert chunk.startswith(b"--frame\r\nContent-Type: image/jpeg\r\n\r\n")

        mock_factory.assert_called_once_with(stream_url, preferred_accel="msmf")

        live_stream_state.stop()
        try:
            for _ in gen:
                pass
        except StopIteration:
            pass


def test_mjpeg_frame_generator_loop_file_no_dropping():
    """Verify that local video loop playback (loop_file=True) preserves all frames without dropping."""
    cam_id = "cam-local-loop-test"
    stream_url = "synthetic_feed.mp4"

    live_stream_state.start(cam_id, "file", stream_url)
    mock_cap = MockLiveStreamCapture(stream_url, total_frames=6)

    with patch("modules.streaming.mjpeg.create_hw_videocapture", return_value=(mock_cap, "software")):
        gen = mjpeg_frame_generator(
            camera_id=cam_id,
            path=stream_url,
            loop_file=True,
        )

        read_count = 0
        try:
            for chunk in gen:
                read_count += 1
                if read_count >= 5:
                    break
        finally:
            live_stream_state.stop()

        assert read_count >= 5


if __name__ == "__main__":
    pytest.main(["-v", __file__])
