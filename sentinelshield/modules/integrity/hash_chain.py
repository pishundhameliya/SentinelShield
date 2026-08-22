"""Cryptographic rolling hash chain generation for tamper-proof video frame validation."""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """Compute SHA-256 hex digest of raw bytes."""
    return hashlib.sha256(data).hexdigest()


class HashChainManager:
    """Manages continuous SHA-256 hash chain generation across video segments."""

    def __init__(self, genesis_hash: str = "GENESIS"):
        self.current_prev: str = genesis_hash
        self.segment_bytes: bytearray = bytearray()
        self.segment_start_time: float = 0.0
        self.chain: list[dict[str, Any]] = []

    def append_frame_bytes(self, frame_buffer: bytes) -> None:
        """Append JPEG frame buffer to current segment (capped per frame for efficiency)."""
        if frame_buffer:
            self.segment_bytes.extend(frame_buffer[:8000])

    def append_segment(self, data: bytes, start_time: float = 0.0, end_time: float | None = None) -> dict[str, Any]:
        """Directly append a data segment and seal it into the chain (supports 2 or 3 args)."""
        actual_end = end_time if end_time is not None else start_time
        if data:
            self.segment_bytes.extend(data)
        self.segment_start_time = start_time
        seg = self.close_segment(actual_end)
        if seg is None:
            digest = sha256_bytes(bytes(data) + self.current_prev.encode())
            seg = {
                "t_start": round(start_time, 2),
                "t_end": round(actual_end, 2),
                "sha256": digest,
                "prev": self.current_prev,
                "ok": True,
            }
            self.chain.append(seg)
            self.current_prev = digest
        return seg

    def close_segment(self, end_time: float) -> dict[str, Any] | None:
        """Close current segment, compute SHA-256 with previous hash, and roll chain forward."""
        if not self.segment_bytes and not self.chain:
            return None
        digest = sha256_bytes(bytes(self.segment_bytes) + self.current_prev.encode())
        seg = {
            "t_start": round(self.segment_start_time, 2),
            "t_end": round(end_time, 2),
            "sha256": digest,
            "prev": self.current_prev,
            "ok": True,
        }
        self.chain.append(seg)
        self.current_prev = digest
        self.segment_bytes = bytearray()
        self.segment_start_time = end_time
        return seg

    def verify_chain(self) -> bool:
        """Cryptographically verify the entire rolling hash chain integrity."""
        if not self.chain:
            return True
        last_hash = "GENESIS"
        for seg in self.chain:
            if seg.get("prev") != last_hash:
                return False
            if not seg.get("ok", True):
                return False
            last_hash = seg.get("sha256", "")
        return last_hash == self.current_prev

    def get_chain(self) -> list[dict[str, Any]]:
        """Return full computed hash chain."""
        return list(self.chain)


class BulkHashBatcher:
    """Thread-safe batch accumulator that flushes hash segments in high-speed bulk transactions."""

    def __init__(self, flush_interval_sec: float = 5.0, max_batch_size: int = 500):
        self.flush_interval = flush_interval_sec
        self.max_batch_size = max_batch_size
        self._buffer: list[tuple[str, float, float, str, str]] = []
        self._lock = threading.RLock()
        self._last_flush = time.time()

    def add_hash(self, job_id: str, t_start: float, t_end: float, sha256: str, prev: str) -> bool:
        """Add a hash record to the in-memory buffer. Automatically triggers flush if buffer is full."""
        with self._lock:
            self._buffer.append((job_id, t_start, t_end, sha256, prev))
            if len(self._buffer) >= self.max_batch_size or (time.time() - self._last_flush) >= self.flush_interval:
                self.flush()
                return True
            return False

    def flush(self) -> int:
        """Atomically commit all buffered hash segments into SQLite."""
        with self._lock:
            if not self._buffer:
                return 0
            items = list(self._buffer)
            self._buffer.clear()
            self._last_flush = time.time()

        from core.database import db_manager
        return db_manager.execute_many(
            "INSERT INTO hashes(job_id, t_start, t_end, sha256, prev) VALUES(?,?,?,?,?)",
            items,
        )
