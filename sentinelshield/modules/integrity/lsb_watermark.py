"""Vectorized LSB Steganographic Frame Watermarking with CRC32 Verification."""
from __future__ import annotations

import struct
import zlib
from typing import Any

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

MAGIC = b"SNTL"  # 4 bytes magic signature


def embed_lsb_timestamp(
    frame: Any,
    timestamp_epoch: float,
    camera_id: str,
    frame_seq: int = 0,
) -> Any:
    """Embed binary watermark into blue-channel least significant bits of frame.
    
    Watermark layout (32 bytes = 256 bits):
    [0:4]   Magic: b'SNTL'
    [4:12]  Timestamp: double (8 bytes)
    [12:20] Camera ID Hash: 8 bytes (truncated sha256)
    [20:28] Frame Seq: uint64 (8 bytes)
    [28:32] CRC32: uint32 (4 bytes)
    """
    if frame is None or np is None or not hasattr(frame, "shape"):
        return frame

    if len(frame.shape) < 3 or frame.shape[0] < 2 or frame.shape[1] < 128:
        return frame

    import hashlib
    cam_hash = hashlib.sha256(camera_id.encode("utf-8")).digest()[:8]
    payload_raw = struct.pack(">4sd8sQ", MAGIC, float(timestamp_epoch), cam_hash, int(frame_seq))
    checksum = zlib.crc32(payload_raw)
    packet = payload_raw + struct.pack(">I", checksum)  # 32 bytes = 256 bits

    # Convert packet to 256 boolean bit array
    bits = np.unpackbits(np.frombuffer(packet, dtype=np.uint8))
    if len(bits) > frame.shape[1]:
        return frame

    # Embed bits into LSB of first row, blue channel (channel 0)
    frame_out = frame.copy()
    row0 = frame_out[0, :256, 0]
    frame_out[0, :256, 0] = (row0 & 0xFE) | bits
    return frame_out


def extract_lsb_timestamp(frame: Any) -> dict[str, Any] | None:
    """Extract and verify 256-bit LSB watermark from first row of frame."""
    if frame is None or np is None or not hasattr(frame, "shape"):
        return None

    if len(frame.shape) < 3 or frame.shape[0] < 1 or frame.shape[1] < 256:
        return None

    try:
        bits = frame[0, :256, 0] & 1
        packet = np.packbits(bits).tobytes()
        if len(packet) != 32:
            return None

        magic, ts, cam_hash, seq, expected_crc = struct.unpack(">4sd8sQI", packet)
        if magic != MAGIC:
            return None

        computed_crc = zlib.crc32(packet[:28])
        if computed_crc != expected_crc:
            return None

        return {
            "valid": True,
            "timestamp": ts,
            "camera_hash": cam_hash.hex(),
            "frame_seq": seq,
        }
    except Exception:
        return None
