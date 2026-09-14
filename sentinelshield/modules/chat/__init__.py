"""Team Chat Subsystem."""
from sentinelshield.modules.chat.service import chat_service, ChatService
from sentinelshield.modules.chat.router import router as chat_router

__all__ = [
    "chat_service",
    "ChatService",
    "chat_router",
]
