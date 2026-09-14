"""Alerts and Watchlist Service with deduplication and state updates."""
from __future__ import annotations

import uuid
from typing import Any

from sentinelshield.core.database import db_manager, utcnow
from sentinelshield.modules.alerts.fusion import translate_alert
from sentinelshield.modules.vision.alpr_ocr import normalize_plate


class AlertService:
    """Service managing watchlists, threat alerts, and demonstration triggers."""

    @staticmethod
    def get_watchlist() -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM watchlist ORDER BY priority")

    @staticmethod
    def add_watchlist_entry(plate: str, kind: str = "stolen", note: str = "", priority: str = "HIGH") -> str:
        pid = "wl-" + uuid.uuid4().hex[:8]
        db_manager.execute(
            "INSERT INTO watchlist VALUES(?,?,?,?,?)",
            pid, kind, normalize_plate(plate), note, priority,
        )
        return pid

    @staticmethod
    def delete_watchlist_entry(wid: str) -> None:
        db_manager.execute("DELETE FROM watchlist WHERE id=?", wid)

    @staticmethod
    def get_alerts(limit: int = 40, lang: str = "en") -> list[dict[str, Any]]:
        rows = db_manager.query_rows("SELECT * FROM alerts ORDER BY created DESC LIMIT ?", limit)
        return [translate_alert(r, lang) for r in rows]

    @staticmethod
    def update_alert_status(alert_id: str, status: str) -> None:
        db_manager.execute("UPDATE alerts SET status=? WHERE id=?", status, alert_id)

    @staticmethod
    def create_alert_with_cooldown(
        camera_id: str,
        kind: str,
        title: str,
        detail: str,
        severity: str = "HIGH",
        trust: int = 100,
        t: float = 0.0,
        cooldown_minutes: int = 3,
    ) -> str | None:
        """Create a new alert only if no identical alert was logged within the cooldown window."""
        recent = db_manager.query_one(
            "SELECT id FROM alerts WHERE camera_id=? AND title LIKE ? AND created > datetime('now', ?)",
            camera_id, f"%{title[:20]}%", f"-{cooldown_minutes} minutes",
        )
        if recent:
            return None

        aid = "al-" + uuid.uuid4().hex[:10]
        db_manager.execute(
            "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
            aid, camera_id, kind, title, detail, severity, trust, t, utcnow(), "new",
        )
        return aid

    @staticmethod
    def trigger_demo_panic() -> None:
        aid = "al-" + uuid.uuid4().hex[:10]
        db_manager.execute(
            "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
            aid, "cam-ring", "panic",
            "Panic: sudden crowd / running",
            "Motion burst — fight/rush cue (OpenCV). Confirm on Live.",
            "CRITICAL", 65, 0, utcnow(), "new",
        )
        db_manager.execute(
            "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
            "ev-" + uuid.uuid4().hex[:8], "panic", "Panic / rush at Ring Road", "cam-ring", "Surat", "crowd", utcnow(),
        )

    @staticmethod
    def trigger_demo_abandoned() -> None:
        aid = "al-" + uuid.uuid4().hex[:10]
        db_manager.execute(
            "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
            aid, "cam-park", "abandoned",
            "Abandoned object (bag/box) — no move 5 min",
            "Static object in parking deck. Dispatch check.",
            "HIGH", 70, 0, utcnow(), "new",
        )


alert_service = AlertService()
