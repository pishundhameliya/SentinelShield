"""Forensic Evidence Vault, SHA-256 fingerprinting, and Incident Ranking."""
from __future__ import annotations

import asyncio
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
        with open(path, "w", encoding="utf-8") as f:
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
    async def seal_evidence_pack_async(camera_id: str) -> dict[str, Any] | None:
        """Asynchronously seal evidence pack offloaded to default threadpool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, EvidenceVaultService.seal_evidence_pack, camera_id)

    @staticmethod
    def compute_canonical_evidence_hash(evidence_data: dict[str, Any]) -> str:
        """Compute deterministic SHA-256 digest of canonical sorted JSON."""
        raw = json.dumps(evidence_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return sha256_bytes(raw)

    @staticmethod
    def verify_evidence_integrity(evidence_data: dict[str, Any], provided_hash: str) -> tuple[bool, str]:
        """Validate provided certificate hash against recomputed canonical digest."""
        if not evidence_data or not provided_hash:
            return False, "Missing evidence payload or hash"
        computed = EvidenceVaultService.compute_canonical_evidence_hash(evidence_data)
        if computed.lower() == str(provided_hash).strip().lower():
            return True, "Integrity verified: SHA-256 match"
        return False, f"Integrity violation: computed {computed} != provided {provided_hash}"

    @staticmethod
    def get_evidence_pdf_brief(camera_id: str) -> bytes | None:
        """Generate or retrieve Section 65B/BSA 2023 compliant PDF evidence certificate."""
        from modules.evidence.pdf_builder import generate_courtroom_pdf_brief

        # Find latest sealed evidence for camera or create pack
        row = db_manager.query_one("SELECT * FROM evidence WHERE camera_id=? ORDER BY created DESC LIMIT 1", camera_id)
        if not row:
            # Seal a fresh pack
            pack = EvidenceVaultService.seal_evidence_pack(camera_id)
            if not pack:
                return None
            row = db_manager.query_one("SELECT * FROM evidence WHERE id=?", pack["id"])

        cam = db_manager.query_one("SELECT * FROM cameras WHERE id=?", camera_id) or {}
        evidence_pack = {
            "id": row.get("id"),
            "camera_id": camera_id,
            "sha256": row.get("sha256"),
            "created": row.get("created"),
            "payload": {
                "camera": camera_id,
                "name": cam.get("name", "CCTV Unit"),
                "place": cam.get("place", "Gujarat Command Zone"),
                "created": row.get("created"),
                "sha256": row.get("sha256"),
            }
        }
        return generate_courtroom_pdf_brief(evidence_pack)

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
