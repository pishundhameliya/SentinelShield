"""Streaming, Video Jobs, and AI Guardian Subsystem."""
from sentinelshield.modules.streaming.worker import process_video, run_video_job
from sentinelshield.modules.streaming.mjpeg import (
    create_reconnect_placeholder_frame,
    live_analytics_frame,
    mjpeg_frame_generator,
)
from sentinelshield.modules.streaming.hw_accel import (
    create_hw_videocapture,
    get_available_hw_accelerations,
)
from sentinelshield.modules.streaming.ai_daemon import ai_guardian_daemon, AIGuardianDaemon
from sentinelshield.modules.streaming.stream_pool import StreamWorkerPool
from sentinelshield.modules.streaming.service import streaming_service, StreamingService
from sentinelshield.modules.streaming.router import router as streaming_router

__all__ = [
    "process_video",
    "run_video_job",
    "create_hw_videocapture",
    "get_available_hw_accelerations",
    "create_reconnect_placeholder_frame",
    "live_analytics_frame",
    "mjpeg_frame_generator",
    "ai_guardian_daemon",
    "AIGuardianDaemon",
    "streaming_service",
    "StreamingService",
    "StreamWorkerPool",
    "streaming_router",
]
