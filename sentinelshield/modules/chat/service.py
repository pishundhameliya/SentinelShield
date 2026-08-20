"""Team Chat Service and message persistence."""
from __future__ import annotations

import uuid
from typing import Any

from core.database import db_manager, utcnow


class ChatService:
    """Service managing team chat message persistence and history retrieval."""

    @staticmethod
    def get_messages(room: str = "team", limit: int = 80) -> list[dict[str, Any]]:
        return db_manager.query_rows(
            "SELECT * FROM messages WHERE room=? ORDER BY created ASC LIMIT ?", room, limit
        )

    @staticmethod
    def post_message(text: str, user_name: str = "Guest", user_role: str = "guest", room: str = "team") -> str:
        mid = "m-" + uuid.uuid4().hex[:8]
        db_manager.execute(
            "INSERT INTO messages VALUES(?,?,?,?,?,?)",
            mid, room, user_name, user_role, text.strip()[:500], utcnow(),
        )
        return mid


chat_service = ChatService()
