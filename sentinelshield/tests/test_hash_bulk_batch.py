"""Unit test for BulkHashBatcher and SQLite batch transactions."""
from __future__ import annotations

import sys
import os
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import db_manager
from modules.integrity.hash_chain import HashChainManager, BulkHashBatcher


def test_bulk_hash_batch_flush():
    db_manager.init_schema()
    batcher = BulkHashBatcher(flush_interval_sec=0.2, max_batch_size=50)

    initial_count = db_manager.query_one("SELECT COUNT(*) as cnt FROM hashes")["cnt"]

    # Add 120 simulated segment hashes across 40 cameras
    for i in range(120):
        batcher.add_hash(
            job_id=f"job-{i % 40}",
            t_start=float(i),
            t_end=float(i + 3),
            sha256=f"hash_{i}_" + "a" * 50,
            prev="GENESIS" if i == 0 else f"hash_{i-1}_" + "a" * 50,
        )

    # Force flush any remaining in buffer
    flushed_count = batcher.flush()
    assert flushed_count >= 0

    after_count = db_manager.query_one("SELECT COUNT(*) as cnt FROM hashes")["cnt"]
    assert after_count == initial_count + 120, f"Expected {initial_count + 120} rows, got {after_count}"

    print("[PASS] Task 2 Verified: BulkHashBatcher high-throughput SQLite batching working!")


if __name__ == "__main__":
    test_bulk_hash_batch_flush()
