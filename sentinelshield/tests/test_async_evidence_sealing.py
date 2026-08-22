"""Unit test for asynchronous non-blocking evidence vault sealing."""
from __future__ import annotations

import sys
import os
import asyncio

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core.database import db_manager
from modules.evidence.vault import evidence_vault_service


async def async_test_runner():
    db_manager.init_schema()
    db_manager.execute("INSERT OR REPLACE INTO cameras(id, name, place) VALUES(?,?,?)", "cam-async-test", "Async Gate 1", "North Ring")

    res = await evidence_vault_service.seal_evidence_pack_async("cam-async-test")
    assert res is not None, "Expected valid result from async seal"
    assert res["ok"] is True
    assert "evd-" in res["id"]
    assert len(res["sha256"]) == 64

    # Verify invalid camera returns None
    bad_res = await evidence_vault_service.seal_evidence_pack_async("cam-non-existent")
    assert bad_res is None

    print("[PASS] Task 4 Verified: Asynchronous non-blocking evidence pack sealing working!")


def test_async_evidence_sealing():
    asyncio.run(async_test_runner())


if __name__ == "__main__":
    test_async_evidence_sealing()
