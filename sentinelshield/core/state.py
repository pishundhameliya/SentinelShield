"""Concurrency-safe global state managers for SentinelShield."""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

try:
    from fastapi import WebSocket
except ImportError:
    WebSocket = Any  # type: ignore


class LiveStreamState:
    """Thread-safe manager for the active live video stream."""

    def __init__(self):
        self._lock = threading.RLock()
        self._on: bool = False
        self._camera_id: str | None = None
        self._source_mode: str | None = None
        self._path: str | None = None
        self._frame: np.ndarray | None = None

    def start(self, camera_id: str, source_mode: str, path: str) -> dict[str, Any]:
        with self._lock:
            self._on = True
            self._camera_id = camera_id
            self._source_mode = source_mode
            self._path = path
            return {
                "on": True,
                "camera_id": camera_id,
                "source": source_mode,
                "path": path,
            }

    def stop(self) -> str | None:
        with self._lock:
            prev_cam = self._camera_id
            self._on = False
            self._camera_id = None
            self._source_mode = None
            self._path = None
            self._frame = None
            return prev_cam

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "on": self._on,
                "camera_id": self._camera_id,
                "source": self._source_mode,
                "path": self._path,
            }

    def set_frame(self, frame: np.ndarray) -> None:
        with self._lock:
            self._frame = frame.copy() if frame is not None else None

    def get_frame(self) -> np.ndarray | None:
        with self._lock:
            return self._frame.copy() if self._frame is not None else None

    @property
    def is_active(self) -> bool:
        with self._lock:
            return self._on

    @property
    def current_camera_id(self) -> str | None:
        with self._lock:
            return self._camera_id

    @property
    def current_path(self) -> str | None:
        with self._lock:
            return self._path


class AIGuardianState:
    """Thread-safe state for background continuous AI monitoring."""

    def __init__(self):
        self._lock = threading.RLock()
        self._on: bool = True
        self._last_cam: str = ""
        self._last_at: str = ""
        self._cycles: int = 0
        self._plates_last: list[str] = []

    def set_active(self, active: bool) -> None:
        with self._lock:
            self._on = active

    def record_cycle(self, camera_name: str, plates: list[str], timestamp: str) -> None:
        with self._lock:
            self._last_cam = camera_name
            self._last_at = timestamp
            self._cycles += 1
            self._plates_last = list(plates)

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "on": self._on,
                "last_cam": self._last_cam,
                "last_at": self._last_at,
                "cycles": self._cycles,
                "plates_last": list(self._plates_last),
            }

    @property
    def is_enabled(self) -> bool:
        with self._lock:
            return self._on


class LiveTrackingState:
    """Thread-safe state manager for multi-frame vehicle centroid tracking."""

    def __init__(self):
        self._lock = threading.RLock()
        self._camera_tracks: dict[str, dict[str, Any]] = {}

    def init_camera(self, camera_id: str) -> None:
        with self._lock:
            if camera_id not in self._camera_tracks:
                self._camera_tracks[camera_id] = {
                    "tracks": {},
                    "next_id": 1,
                    "count": 0,
                    "prev_gray": None,
                }

    def get_camera_state(self, camera_id: str) -> dict[str, Any]:
        with self._lock:
            self.init_camera(camera_id)
            return self._camera_tracks[camera_id]

    def update_camera_state(
        self,
        camera_id: str,
        tracks: dict[str, Any],
        count: int,
        next_id: int,
        prev_gray: np.ndarray | None = None,
    ) -> None:
        with self._lock:
            st = self._camera_tracks.setdefault(camera_id, {})
            st["tracks"] = tracks
            st["count"] = count
            st["next_id"] = next_id
            if prev_gray is not None:
                st["prev_gray"] = prev_gray


class TemporaryRelayState:
    """Thread-safe buffer for mobile phone webcam relay testing."""

    def __init__(self):
        self._lock = threading.RLock()
        self._jpeg: bytes | None = None
        self._timestamp: float = 0.0

    def set_frame(self, jpeg_data: bytes) -> None:
        with self._lock:
            self._jpeg = jpeg_data
            self._timestamp = time.time()

    def get_frame(self) -> tuple[bytes | None, float]:
        with self._lock:
            return self._jpeg, self._timestamp


class WebSocketConnectionHub:
    """Async-safe connection hub for WebSocket broadcasting."""

    def __init__(self):
        self._sockets: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self._sockets.append(websocket)

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._sockets:
                self._sockets.remove(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        async with self._lock:
            dead: list[WebSocket] = []
            for ws in list(self._sockets):
                try:
                    await ws.send_json(message)
                except Exception:
                    dead.append(ws)
            for d in dead:
                if d in self._sockets:
                    self._sockets.remove(d)


live_stream_state = LiveStreamState()
ai_state = AIGuardianState()
tracking_state = LiveTrackingState()
relay_state = TemporaryRelayState()
ws_hub = WebSocketConnectionHub()
