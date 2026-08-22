"""Integrity Service orchestrating hash chains, tamper detection, and trust scoring."""
from __future__ import annotations

from typing import Any
from modules.integrity.hash_chain import HashChainManager
from modules.integrity.tamper_detector import TamperDetector


class IntegrityService:
    """Service providing video integrity verification and forensic trust assessment."""

    @staticmethod
    def calculate_trust_score(tampers: list[dict[str, Any]], threats: list[dict[str, Any]]) -> int:
        """Calculate overall 0-100 authenticity trust score based on tamper and threat evidence."""
        trust = 100
        if tampers:
            trust = max(15, 100 - 28 * len(tampers))
        if threats:
            trust = min(trust, 70)
        return trust

    @staticmethod
    def create_hash_chain_manager(genesis_hash: str = "GENESIS") -> HashChainManager:
        return HashChainManager(genesis_hash)

    @staticmethod
    def create_tamper_detector(fps: float = 12.0) -> TamperDetector:
        return TamperDetector(fps)


integrity_service = IntegrityService()
