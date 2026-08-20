"""Authentication, RBAC and Session Management for SentinelShield."""
from __future__ import annotations

import secrets
import threading
from typing import Any

from config import settings


class SessionManager:
    """Thread-safe user session and token manager."""

    def __init__(self, users: dict[str, dict[str, Any]] = settings.users):
        self._users = users
        self._sessions: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()

    def authenticate(self, username: str, password: str) -> tuple[str | None, dict[str, Any] | None]:
        """Authenticate user credentials and return (session_token, user_dict)."""
        uname = (username or "").strip().lower()
        user_info = self._users.get(uname)
        if not user_info or user_info.get("password") != password:
            return None, None

        token = secrets.token_hex(16)
        user_payload = {
            "username": uname,
            "name": user_info.get("name", uname.title()),
            "role": user_info.get("role", "operator"),
        }
        with self._lock:
            self._sessions[token] = user_payload
        return token, dict(user_payload)

    def get_user(self, token: str | None) -> dict[str, Any] | None:
        """Get user payload from session token."""
        if not token:
            return None
        with self._lock:
            user = self._sessions.get(token)
            return dict(user) if user else None

    def destroy_session(self, token: str) -> None:
        """Destroy an active session."""
        with self._lock:
            self._sessions.pop(token, None)


session_manager = SessionManager()
