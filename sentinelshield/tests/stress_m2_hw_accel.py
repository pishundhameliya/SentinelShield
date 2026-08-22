"b""Empirical Stress Test Harness for Milestone 2: Hardware Acceleration Probing and Resource Integrity."""
from __future__ import annotations

import ctypes
import gc
import os
import sys
import tempfile
import threading
import time
from typing import Any, List, Optional, Tuple
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

# Ensure sentinelshield base directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from modules.streaming.hw_accel import (
    create_hw_videocapture,
    get_available_hw_accelerations,
)


def get_process_memory_rss_bytes() -> int:
    """Get current process working set / RSS memory in bytes via Windows API or psutil."""
    try:
        import psutil
        return psutil.Process().memory_info().rss
    except Exception:
        pass

    try:
        import ctypes.wintypes
        class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
                ("PrivateUsage", ctypes.c_size_t),
            ]

        counters = PROCESS_MEMORY_COUNTERS_EX()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
        kernel32 = ctypes.windll.kernel32
        psapi = ctypes.windll.psapi
        kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(PROCESS_MEMORY_COUNTERS_EX), ctypes.wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = ctypes.wintypes.BOOL

        proc = kernel32.GetCurrentProcess()
        if psapi.GetProcessMemoryInfo(proc, ctypes.byref(counters), counters.cb):
            return int(counters.WorkingSetSize)
    except Exception:
        pass
    return 0


def get_process_handle_count() -> int:
    """Get current process OS handle count via Windows API or psutil."""
    try:
        import psutil
        return psutil.Process().num_handles()
    except Exception:
        pass

    try:
        import ctypes.wintypes
        kernel32 = ctypes.windll.kernel32
        count = ctypes.wintypes.DWORD()
        kernel32.GetCurrentProcess.restype = ctypes.wintypes.HANDLE
        kernel32.GetProcessHandleCount.argtypes = [ctypes.wintypes.HANDLE, ctypes.POINTER(ctypes.wintypes.DWORD)]
        kernel32.GetProcessHandleCount.restype = ctypes.wintypes.BOOL

        proc = kernel32.GetCurrentProcess()
        if kernel32.GetProcessHandleCount(proc, ctypes.byref(count)):
            return int(count.value)
    except Exception:
        pass
    return 0


def create_synthetic_video(file_path: str, num_frames: int = 30, width: int = 320, height: int = 240, fps: float = 30.0) -> None:
    """Generate a synthetic test MP4 video file with valid color bars and noise."""
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(file_path, fourcc, fps, (width, height))
    try:
        for i in range(num_frames):
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            frame[:, :, 0] = (i * 8) % 256
            frame[:, :, 1] = np.linspace(0, 255, height, dtype=np.uint8)[:, None]
            frame[:, :, 2] = np.linspace(0, 255, width, dtype=np.uint8)[None, :]
            cv2.putText(frame, f'F:{i}', (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2)
            writer.write(frame)
    finally:
        writer.release()


def test_probe_rapid_sequential_50_cycles_synthetic_video():
    """Stress Test: 50 rapid sequential open/read/close calls across multiple backend preferences."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tf:
        temp_path = tf.name

    try:
        create_synthetic_video(temp_path, num_frames=20)
        assert os.path.exists(temp_path)
        assert os.path.getsize(temp_path) > 0

        backends_to_test = ['auto', 'software', 'cuda', 'msmf', 'd3d11', 'dshow', 'ffmpeg']
        successful_reads = 0
        total_cycles = 50

        for i in range(total_cycles):
            backend_pref = backends_to_test[i % len(backends_to_test)]
            cap, selected_backend = create_hw_videocapture(temp_path, preferred_accel=backend_pref)
            assert cap is not None, f'Cycle {i}: VideoCapture should not be None'
            assert isinstance(selected_backend, str), f'Cycle {i}: Backend should be string'

            if cap.isOpened():
                ret, frame = cap.read()
                assert ret is True, f'Cycle {i}: Failed to read frame from valid video via {selected_backend}'
                assert frame is not None
                assert frame.shape == (240, 320, 3)
                successful_reads += 1
            cap.release()
            del cap

        assert successful_reads == total_cycles, f'Expected {total_cycles} successful reads, got {successful_reads}'
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def test_probe_non_existent_video_files():
    """Stress Test: Non-existent files across multiple backends must return gracefully without crashing."""
    fake_paths = [
        'non_existent_file_xyz_12345.mp4',
        'C:\\iNvalid_drive_dir_9999\\fake_video.avi',
        'D:\\Projects\\SentinelShield\\ghost_feed_xyz.mkv'
    ]
    backends = ['auto', 'cuda', 'msmf', 'software', 'NON_EXISTENT_GPU']

    for path in fake_paths:
        for backend in backends:
            cap, selected_backend = create_hw_videocapture(path, preferred_accel=backend)
            assert cap is not None
            assert isinstance(selected_backend, str)
            assert not cap.isOpened(), f'Non-existent file {path} unexpectedly reported opened'
            cap.release()


def test_probe_corrupt_and_malformed_stream_urls():
    """Stress Test: Corrupt, malformed, and unreachable stream URLs must fall back gracefully."""
    corrupt_urls = [
        'rtsp://256.256.256.256:9999/live',
        'http://0.0.0.0:1/corrupt_feed',
        ':::invalid_uri_protocol:::',
        'rtmp://malformed-url-format:abc/stream',
        '',
        '   '
    ]
    for url in corrupt_urls:
        cap, selected_backend = create_hw_videocapture(url, preferred_accel='auto')
        assert cap is not None
        assert isinstance(selected_backend, str)
        assert not cap.isOpened()
        cap.release()


def test_probe_forced_non_existent_backend_names():
    """Stress Test: Arbitrary non-existent backend names must cleanly fallback to software CPU decoding."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tf:
        temp_path = tf.name

    try:
        create_synthetic_video(temp_path, num_frames=10)
        bogus_backends = [
            'NON_EXISTENT_GPU',
            'VULKAN_MAGIC_ACCEL',
            'TPU_V5E_ACCELERATOR',
            'CUDA_FAKE_V99',
            '12345678',
            '!@#$%^&*()',
            '   MSMF   ',
            '  SoFtWaRe  '
        ]

        for bogus in bogus_backends:
            cap, selected_backend = create_hw_videocapture(temp_path, preferred_accel=bogus)
            assert cap is not None
            assert cap.isOpened()
            ret, frame = cap.read()
            assert ret is True
            assert frame.shape == (240, 320, 3)
            if bogus.strip().lower() in ('msmf', 'software'):
                assert selected_backend in ('msmf', 'software')
            else:
                assert selected_backend in ('cuda', 'msmf', 'dshow', 'ffmpeg', 'software')
            cap.release()
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def test_probe_simulated_backend_exceptions():
    """Stress Test: When OpenCV throws driver/hardware exceptions during init, fallback must succeed."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tf:
        temp_path = tf.name

    try:
        create_synthetic_video(temp_path, num_frames=10)
        original_vc = cv2.VideoCapture

        def crashing_videocapture_constructor(src, api_pref=0):
            if api_pref != getattr(cv2, 'CAP_ANY', 0):
                raise RuntimeError('Simulated GPU driver crash / NVDEO OOM!')
            return original_vc(src, getattr(cv2, 'CAP_ANY', 0))

        with patch.object(cv2, 'VideoCapture', side_effect=crashing_videocapture_constructor):
            cap, backend = create_hw_videocapture(temp_path, preferred_accel='cuda')
            assert cap is not None
            assert backend == 'software'
            assert cap.isOpened()
            ret, frame = cap.read()
            assert ret is True
            cap.release()
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def test_resource_leakage_100_sequential_handles_memory_and_descriptors():
    """Stress Test: Open and close 100 synthetic video capture handles in a tight loop; measure memory delta (< 5 MB) and handle retention."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tf:
        temp_path = tf.name

    try:
        create_synthetic_video(temp_path, num_frames=30)

        # Warm-up phase: initialize dynamic hardware backends and driver contexts
        for _ in range(15):
            c, b = create_hw_videocapture(temp_path, preferred_accel='auto')
            if c.isOpened():
                for _ in range(3):
                    c.read()
            c.release()
            del c

        gc.collect()
        time.sleep(0.2)

        initial_memory_bytes = get_process_memory_rss_bytes()
        initial_handles = get_process_handle_count()

        loop_count = 100
        for i in range(loop_count):
            cap, backend = create_hw_videocapture(temp_path, preferred_accel='auto')
            assert cap is not None
            assert cap.isOpened(), f'Iteration {i}: Capture failed to open'
            for _ in range(3):
                ret, frame = cap.read()
                assert ret is True
                assert frame is not None
            cap.release()
            del cap

        gc.collect()
        time.sleep(0.2)

        final_memory_bytes = get_process_memory_rss_bytes()
        final_handles = get_process_handle_count()

        memory_delta_bytes = final_memory_bytes - initial_memory_bytes
        memory_delta_mb = memory_delta_bytes / (1024.0 * 1024.0)
        handle_delta = final_handles - initial_handles

        print(f'\n[EMPIRICAL 100-HANDLE RESOURCE METRICS]')
        print(f'Initial Memory: {initial_memory_bytes / (1024*1024):.2f} MB')
        print(f'Final Memory:   {final_memory_bytes / (1024*1024):.2f} MB')
        print(f'Memory Delta:   {memory_delta_mb:+.3f} MB (Threshold: < 5.0 MB)')
        print(f'Initial Handles: {initial_handles}')
        print(f'Final Handles:   {final_handles}')
        print(f'Handle Delta:    {handle_delta:+d} (Threshold: <= 5 handles)')

        assert memory_delta_mb < 5.0, f'Memory leaked: {memory_delta_mb:.2f} MB exceeds 5 MB limit!'
        if initial_handles > 0:
            assert handle_delta <= 5, f'Handle leak detected: {handle_delta} unclosed OS handles retained!'
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


def test_concurrent_multithreaded_capture_probing():
    """Stress Test: 10 concurrent threads opening/reading/closing video captures simultaneously."""
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as tf:
        temp_path = tf.name

    try:
        create_synthetic_video(temp_path, num_frames=20)
        errors: List[str] = []
        thread_count = 10
        ops_per_thread = 10

        def worker_task(thread_id: int):
            try:
                for op in range(ops_per_thread):
                    pref = ['auto', 'software', 'cuda', 'msmf'][op % 4]
                    cap, backend = create_hw_videocapture(temp_path, preferred_accel=pref)
                    if not cap.isOpened():
                        errors.append(f'Thread {thread_id} Op {op}: Failed to open with backend {backend}')
                        cap.release()
                        continue
                    ret, frame = cap.read()
                    if not ret or frame is None or frame.shape != (240, 320, 3):
                        errors.append(f'Thread {thread_id} Op {op}: Corrupt frame read')
                    cap.release()
                    del cap
            except Exception as exc:
                errors.append(f'Thread {thread_id} Exception: {exc}')

        threads = [threading.Thread(target=worker_task, args=(i,)) for i in range(thread_count)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f'Concurrent probing errors: {errors}'
    finally:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
