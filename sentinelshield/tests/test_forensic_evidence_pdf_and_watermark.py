"""Unit tests for Section 65B/BSA 2023 Courtroom PDF Brief, Canonical Hashing, and LSB Watermark."""
from __future__ import annotations

import os
import sys
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import db_manager
from modules.evidence.vault import evidence_vault_service
from modules.evidence.pdf_builder import generate_courtroom_pdf_brief
from modules.integrity.lsb_watermark import embed_lsb_timestamp, extract_lsb_timestamp


def test_canonical_evidence_hashing_and_verification():
    payload = {
        "camera": "cam-surat-01",
        "name": "Surat Ring Road North",
        "created": "2026-08-22T10:00:00Z",
        "algo": "SHA-256",
    }
    h1 = evidence_vault_service.compute_canonical_evidence_hash(payload)
    assert len(h1) == 64, "Expected 64-char hex SHA-256"

    # Determinism: different key order in dict must produce identical hash
    payload_reordered = {
        "algo": "SHA-256",
        "created": "2026-08-22T10:00:00Z",
        "name": "Surat Ring Road North",
        "camera": "cam-surat-01",
    }
    h2 = evidence_vault_service.compute_canonical_evidence_hash(payload_reordered)
    assert h1 == h2, "Canonical JSON hashing must be order-invariant"

    # Verification check
    valid, msg = evidence_vault_service.verify_evidence_integrity(payload, h1)
    assert valid is True, f"Integrity check failed: {msg}"

    # Tampered payload check
    tampered = dict(payload)
    tampered["camera"] = "cam-hacked"
    invalid, msg2 = evidence_vault_service.verify_evidence_integrity(tampered, h1)
    assert invalid is False, "Tampered payload must fail verification"
    print("[PASS] Canonical evidence hashing and verification verified!")


def test_courtroom_pdf_brief_generation():
    db_manager.init_schema()
    db_manager.execute("INSERT OR REPLACE INTO cameras(id, name, place) VALUES(?,?,?)", "cam-pdf-test", "Gandhi Ashram Gate", "Ahmedabad")

    pack = evidence_vault_service.seal_evidence_pack("cam-pdf-test")
    assert pack is not None

    pdf_bytes = evidence_vault_service.get_evidence_pdf_brief("cam-pdf-test")
    assert pdf_bytes is not None
    assert len(pdf_bytes) > 500, "PDF bytes should be substantial"
    assert pdf_bytes.startswith(b"%PDF"), "Must be a valid PDF format"
    print(f"[PASS] Courtroom forensic PDF brief generated ({len(pdf_bytes):,} bytes)!")


def test_lsb_frame_watermarking():
    # Create test image 480x640x3
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:, :] = [128, 128, 128]

    ts = 1755860000.5
    cam_id = "cam-surat-01"
    seq = 42

    # Embed watermark
    watermarked = embed_lsb_timestamp(img, timestamp_epoch=ts, camera_id=cam_id, frame_seq=seq)
    assert watermarked is not None
    assert watermarked.shape == img.shape

    # Extract watermark
    extracted = extract_lsb_timestamp(watermarked)
    assert extracted is not None, "Failed to extract watermark"
    assert extracted["valid"] is True
    assert abs(extracted["timestamp"] - ts) < 0.001
    assert extracted["frame_seq"] == seq

    # Tamper test: modify one bit in watermarked row
    corrupted = watermarked.copy()
    corrupted[0, 5, 0] ^= 1  # Flip a bit in the header
    tampered_result = extract_lsb_timestamp(corrupted)
    assert tampered_result is None, "Tampered watermark must fail CRC32 verification"
    print("[PASS] Vectorized LSB steganographic watermarking and CRC32 verification verified!")


if __name__ == "__main__":
    test_canonical_evidence_hashing_and_verification()
    test_courtroom_pdf_brief_generation()
    test_lsb_frame_watermarking()
    print("\n[ALL PASS] Milestone 3 (Forensic Evidence & Watermark) 100% Verified!")
