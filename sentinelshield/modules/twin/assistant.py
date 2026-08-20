"""Natural Language Operator Assistant Intent Parser."""
from __future__ import annotations

from typing import Any
from core.database import db_manager


class AssistantNLPService:
    """Parses natural language operator queries and dispatches target tab actions."""

    @staticmethod
    def parse_query(query: str) -> dict[str, Any]:
        text = (query or "").lower()
        if "blacklist" in text or "blacklisted" in text or "કાળી" in text:
            return {"intent": "watchlist", "tab": "watch", "data": db_manager.query_rows("SELECT * FROM watchlist")}
        if "alert" in text or "last hour" in text or "એલર્ટ" in text:
            return {"intent": "alerts", "tab": "alerts", "data": db_manager.query_rows("SELECT * FROM alerts ORDER BY created DESC LIMIT 15")}
        if "camera 12" in text or "cam-12" in text or "find camera" in text:
            return {"intent": "camera", "tab": "home", "data": db_manager.query_rows("SELECT id,name,place FROM cameras LIMIT 8")}
        if "white car" in text or "motorcycle" in text or "railway" in text:
            return {"intent": "search", "tab": "events", "data": db_manager.query_rows("SELECT * FROM events ORDER BY created DESC LIMIT 10"),
                    "note": "Demo: no colour/time filter yet — showing latest vehicle events."}
        if "honeypot" in text or "hack" in text or "cyber" in text:
            return {"intent": "cyber", "tab": "cyber", "data": db_manager.query_rows("SELECT * FROM cyber ORDER BY created DESC LIMIT 10")}
        if "gj" in text.replace(" ", "") or "plate" in text or "vehicle" in text:
            return {"intent": "vehicle", "tab": "find", "hint": "Type the plate in Find, e.g. GJ05SS2026"}
        return {"intent": "help", "tab": "help", "note": "Try: show blacklisted vehicles; show alerts; find GJ05SS2026; show cyber attacks."}


assistant_service = AssistantNLPService()
