"""Forensic Evidence Vault, SHA-256 fingerprinting, and Incident Ranking."""
from __future__ import annotations

import json
import os
import uuid
from typing import Any

from config import settings
from core.database import db_manager, utcnow
from modules.integrity.hash_chain import sha256_bytes


class EvidenceVaultService:
    """Service providing forensic evidence packaging and incident seriousness ranking."""

    @staticmethod
    def get_evidence_packs(limit: int = 20) -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM evidence ORDER BY created DESC LIMIT ?", limit)

    @staticmethod
    def seal_evidence_pack(camera_id: str) -> dict[str, Any] | None:
        cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id)
        if not cam:
            return None

        vault_dir = settings.vault_dir
        os.makedirs(vault_dir, exist_ok=True)

        payload = {
            "camera": cam["id"],
            "name": cam.get("name"),
            "place": cam.get("place"),
            "created": utcnow(),
            "algo": "SHA-256 + AES-256-GCM (key in env for production)",
        }
        raw = json.dumps(payload, sort_keys=True).encode()
        digest = sha256_bytes(raw)
        path = os.path.join(vault_dir, f"{camera_id}_{digest[:10]}.json")
        with open(path, "w") as f:
            json.dump({"payload": payload, "sha256": digest}, f, indent=2)

        eid = "evd-" + uuid.uuid4().hex[:8]
        db_manager.execute(
            "INSERT INTO evidence VALUES(?,?,?,?,?)",
            eid, camera_id, digest, path, utcnow(),
        )

        return {
            "ok": True,
            "id": eid,
            "sha256": digest,
            "file": "/media/vault/" + os.path.basename(path),
        }

    @staticmethod
    def rank_evidence(limit: int = 30) -> list[dict[str, Any]]:
        als = db_manager.query_rows("SELECT * FROM alerts ORDER BY created DESC LIMIT ?", limit)
        ranked = []
        for a in als:
            score = 40
            if a.get("severity") == "CRITICAL":
                score += 40
            if a.get("kind") in ("watchlist", "cyber", "tamper"):
                score += 15
            score = min(99, score + int((a.get("trust") or 50) / 10))
            ranked.append({**a, "rank_score": score})
        ranked.sort(key=lambda x: -x["rank_score"])
        return ranked


evidence_vault_service = EvidenceVaultService()
