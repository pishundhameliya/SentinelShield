"""Cybersecurity and Decoy Trap Subsystem."""
from sentinelshield.modules.cyber.honeypot import cyber_service, CyberHoneypotService
from sentinelshield.modules.cyber.router import router as cyber_router

__all__ = [
    "cyber_service",
    "CyberHoneypotService",
    "cyber_router",
]
