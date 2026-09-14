"""CyberShield Integrity Subsystem."""
from sentinelshield.modules.integrity.hash_chain import HashChainManager, BulkHashBatcher, sha256_bytes
from sentinelshield.modules.integrity.tamper_detector import TamperDetector, MultiCameraTamperPool, is_black_frame, frame_difference_score
from sentinelshield.modules.integrity.service import integrity_service, IntegrityService
from sentinelshield.modules.integrity.lsb_watermark import embed_lsb_timestamp, extract_lsb_timestamp

__all__ = [
    "HashChainManager",
    "BulkHashBatcher",
    "sha256_bytes",
    "TamperDetector",
    "MultiCameraTamperPool",
    "is_black_frame",
    "frame_difference_score",
    "integrity_service",
    "IntegrityService",
    "embed_lsb_timestamp",
    "extract_lsb_timestamp",
]
