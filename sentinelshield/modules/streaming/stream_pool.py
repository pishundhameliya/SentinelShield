"""Multi-process stream multiplexing and hardware-adaptive autotuning engine for SentinelShield."""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple


class StreamWorkerPool:
    """Orchestrates multi-process CCTV stream ingestion, backpressure calculation, and dynamic hardware autotuning."""

    def __init__(self, num_workers: int | None = None):
        self.cpu_count = os.cpu_count() or 4
        self.num_workers = num_workers or max(2, min(8, self.cpu_count))

    def partition_cameras(self, cameras: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
        """Evenly divide cameras across worker slots to prevent GIL and core starvation."""
        if not cameras:
            return [[] for _ in range(self.num_workers)]
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

    def get_hardware_profile(self) -> dict[str, Any]:
        """Auto-probe host hardware topology and provide recommended execution parameters."""
        return {
            "cpu_cores": self.cpu_count,
            "recommended_workers": self.num_workers,
            "gpu_acceleration_recommended": True,
            "optimal_hash_interval_sec": 3.0,
            "max_concurrent_streams": self.num_workers * 25,
        }

    def compute_adaptive_throttle(self, active_streams: int, cpu_percent: float = 0.0) -> float:
        """Compute dynamic FPS sampling throttle (1.0 = full rate, 0.3 = conservative rate)."""
        throttle = 1.0
        if active_streams > 100 or cpu_percent > 80.0:
            throttle = 0.3
        elif active_streams > 50 or cpu_percent > 60.0:
            throttle = 0.6
        return throttle

    def compute_backpressure_policy(
        self,
        active_streams: int = 1,
        client_latency_ms: float = 0.0,
        cpu_percent: float = 0.0,
    ) -> dict[str, Any]:
        """Compute holistic dynamic backpressure degradation policy based on network latency and system load.

        Tiers:
        - Nominal (<=40ms latency, <=50 streams, <=60% CPU): Send 1:1 frames, 25 FPS, 75 quality.
        - Moderate (40-120ms latency, 51-100 streams, or 60-80% CPU): Send 1:2 frames, 12.5 FPS, 65 quality.
        - Heavy (120-300ms latency, 101-180 streams, or 80-90% CPU): Send 1:3 frames, 8 FPS, 55 quality.
        - Critical (>300ms latency, >180 streams, or >90% CPU): Send 1:4 frames, 6 FPS, 45 quality.
        """
        resolution = self.get_optimal_substream_resolution(active_streams)
        throttle = self.compute_adaptive_throttle(active_streams, cpu_percent)

        if client_latency_ms > 300.0 or active_streams > 180 or cpu_percent > 90.0:
            drop_ratio = 4
            target_fps = 6.0
            jpeg_quality = 45
            degradation_tier = "critical"
        elif client_latency_ms > 120.0 or active_streams > 100 or cpu_percent > 80.0:
            drop_ratio = 3
            target_fps = 8.0
            jpeg_quality = 55
            degradation_tier = "heavy"
        elif client_latency_ms > 40.0 or active_streams > 50 or cpu_percent > 60.0:
            drop_ratio = 2
            target_fps = 12.5
            jpeg_quality = 65
            degradation_tier = "moderate"
        else:
            drop_ratio = 1
            target_fps = 25.0
            jpeg_quality = 75
            degradation_tier = "nominal"

        return {
            "drop_ratio": drop_ratio,
            "target_fps": target_fps,
            "jpeg_quality": jpeg_quality,
            "substream_resolution": resolution,
            "throttle": throttle,
            "degradation_tier": degradation_tier,
            "active_streams": active_streams,
            "client_latency_ms": round(client_latency_ms, 2),
            "cpu_percent": round(cpu_percent, 2),
        }

    def should_drop_frame(
        self,
        frame_index: int,
        active_streams: int = 1,
        client_latency_ms: float = 0.0,
        cpu_percent: float = 0.0,
    ) -> bool:
        """Determine if a specific frame index should be dropped according to active backpressure policy."""
        policy = self.compute_backpressure_policy(
            active_streams=active_streams,
            client_latency_ms=client_latency_ms,
            cpu_percent=cpu_percent,
        )
        drop_ratio = policy["drop_ratio"]
        if drop_ratio <= 1:
            return False
        return (frame_index % drop_ratio) != 0
