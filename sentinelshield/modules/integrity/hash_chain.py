"""SHA-256 video segment hashing and blockchain-lite tamper-evident verification."""
from __future__ import annotations

import hashlib
from typing import Any


def sha256_bytes(data: bytes) -> str:
    """Return lowercase hex SHA-256 hash of bytes data."""
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

    def append_segment(self, data: bytes, start_time: float = 0.0, end_time: float | None = None) -> dict[str, Any] | None:
        """Backward-compatible helper expected by the integrity tests and legacy scripts."""
        if data:
            self.segment_bytes.extend(data)
        self.segment_start_time = start_time
        return self.close_segment(end_time if end_time is not None else start_time)

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
        """Validate that each linked segment points to the previous hash in order."""
        if not self.chain:
            return True

        expected_prev = self.current_prev if self.chain and self.chain[-1].get("sha256") == self.current_prev else "GENESIS"
        last_hash = "GENESIS"
        for seg in self.chain:
            if seg.get("prev") != last_hash:
                return False
            last_hash = seg.get("sha256", "")
        return last_hash == self.current_prev

    def get_chain(self) -> list[dict[str, Any]]:
        """Return full computed hash chain."""
        return list(self.chain)
