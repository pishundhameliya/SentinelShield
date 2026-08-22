"""CCTV cybersecurity monitoring, decoy trap, and threat scoring service."""
from __future__ import annotations

import json
import uuid
from typing import Any

from core.database import db_manager, utcnow
from modules.alerts.service import AlertService


SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
EVENT_POINTS = {
    "failed_login": 10,
    "repeated_requests": 8,
    "port_scan": 20,
    "unauthorized_endpoint": 15,
    "repeated_connection": 12,
    "connection_anomaly": 15,
    "request_anomaly": 10,
}
THRESHOLDS = {"MEDIUM": 15, "HIGH": 30, "CRITICAL": 60}
WINDOW_SECONDS = 300


def _severity(score: int) -> str:
    if score >= THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


def _source_ip(source_ip: str | None) -> str:
    return source_ip or "unknown"


class CyberHoneypotService:
    """Cyber-only interface for sensors, simulations, and the isolated decoy."""

    def __init__(self) -> None:
        db_manager.execute(
            """CREATE TABLE IF NOT EXISTS cyber_events (
                event_id TEXT PRIMARY KEY, timestamp TEXT, camera_id TEXT,
                source_ip TEXT, event_type TEXT, severity TEXT,
                description TEXT, status TEXT, score INTEGER, simulated INTEGER,
                points INTEGER
            )"""
        )
        with db_manager.connection() as con:
            columns = {row[1] for row in con.execute("PRAGMA table_info(cyber_events)")}
            if "points" not in columns:
                con.execute("ALTER TABLE cyber_events ADD COLUMN points INTEGER DEFAULT 0")
                con.commit()
        db_manager.execute(
            """CREATE TABLE IF NOT EXISTS cyber_activity (
                activity_id TEXT PRIMARY KEY, timestamp TEXT, source_ip TEXT,
                event_type TEXT, target_decoy TEXT, action TEXT,
                score INTEGER, severity TEXT, simulated INTEGER
            )"""
        )
        db_manager.execute(
            """CREATE TABLE IF NOT EXISTS cyber_camera_health (
                camera_id TEXT PRIMARY KEY, state TEXT, source_ip TEXT,
                previous_state TEXT, updated TEXT, suspicious INTEGER
            )"""
        )

    def _recent_score(self, source_ip: str, camera_id: str | None) -> int:
        rows = db_manager.query_rows(
            """SELECT COALESCE(points, score, 0) AS points FROM cyber_events
               WHERE source_ip=? AND (? IS NULL OR camera_id=?)
               AND timestamp >= datetime('now', ?)""",
            source_ip, camera_id, camera_id, f"-{WINDOW_SECONDS} seconds",
        )
        return sum(int(row.get("points") or 0) for row in rows)

    def record_event(
        self,
        event_type: str,
        description: str,
        camera_id: str = "unknown-camera",
        source_ip: str | None = None,
        status: str = "new",
        score: int | None = None,
        simulated: bool = False,
    ) -> dict[str, Any]:
        source = _source_ip(source_ip)
        points = int(score if score is not None else EVENT_POINTS.get(event_type, 5))
        total = self._recent_score(source, camera_id) + points
        severity = _severity(total)
        event_id = "cy-" + uuid.uuid4().hex[:12]
        timestamp = utcnow()
        self._insert_event(event_id, timestamp, camera_id, source, event_type, severity,
                   description, status, total, simulated, points)
        if severity in ("HIGH", "CRITICAL"):
            AlertService.create_alert_with_cooldown(
                camera_id, "cyber", f"Cybersecurity {severity.lower()} event",
                f"{description} Source IP: {source}. Threat score: {total}.",
                severity=severity, trust=max(0, 100 - min(total, 100)),
            )
        return {
            "event_id": event_id, "timestamp": timestamp, "camera_id": camera_id,
            "source_ip": source, "event_type": event_type, "severity": severity,
            "description": description, "status": status, "score": total,
            "simulated": simulated,
        }

    @staticmethod
    def _insert_event(event_id: str, timestamp: str, camera_id: str, source_ip: str,
                      event_type: str, severity: str, description: str, status: str,
                      score: int, simulated: bool, points: int) -> None:
        db_manager.execute(
            "INSERT INTO cyber_events VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            event_id, timestamp, camera_id, source_ip, event_type, severity,
            description, status, score, int(simulated), points,
        )
        db_manager.execute(
            "INSERT INTO cyber VALUES(?,?,?,?,?,?)",
            event_id, event_type, json.dumps({"description": description, "source_ip": source_ip,
                                               "severity": severity, "score": score,
                                               "points": points, "simulated": simulated}),
            camera_id, timestamp, status,
        )

    def trigger_honeypot_incident(self, source_ip: str | None = None, action: str = "request",
                                  simulated: bool = False) -> dict[str, Any]:
        cid = "honeypot-cam"
        event = self.record_event(
            "unauthorized_endpoint", "Unauthorized access to isolated decoy CCTV endpoint",
            cid, source_ip, score=EVENT_POINTS["unauthorized_endpoint"], simulated=simulated,
        )
        activity_id = "ca-" + uuid.uuid4().hex[:10]
        db_manager.execute(
            "INSERT INTO cyber_activity VALUES(?,?,?,?,?,?,?,?,?)",
            activity_id, event["timestamp"], event["source_ip"], "honeypot",
            "CAM-HONEYPOT-01", action, event["score"], event["severity"], int(simulated),
        )
        return {"ok": False, "error": "Unauthorized", "camera": "CAM-HONEYPOT-01",
                "event": event, "decoy": True}

    def update_camera_health(self, camera_id: str, state: str, source_ip: str | None = None) -> dict[str, Any]:
        previous = db_manager.query_one(
            "SELECT state, source_ip FROM cyber_camera_health WHERE camera_id=?", camera_id
        )
        source = _source_ip(source_ip)
        suspicious = bool(previous and previous.get("source_ip") not in (None, source))
        event = None
        if previous and previous.get("state") != state:
            event_type = "connection_anomaly" if suspicious else "repeated_connection"
            event = self.record_event(
                event_type, f"Camera connection changed from {previous['state']} to {state}",
                camera_id, source, score=EVENT_POINTS[event_type],
            )
        db_manager.execute(
            "INSERT OR REPLACE INTO cyber_camera_health VALUES(?,?,?,?,?,?)",
            camera_id, state, source, previous.get("state") if previous else None,
            utcnow(), int(suspicious),
        )
        return {"camera_id": camera_id, "state": state, "source_ip": source,
                "suspicious": suspicious, "event": event}

    def get_honeypot_hits(self, limit: int = 30) -> list[dict[str, Any]]:
        return db_manager.query_rows(
            "SELECT * FROM cyber_activity WHERE event_type='honeypot' ORDER BY timestamp DESC LIMIT ?", limit
        )

    def get_all_cyber_incidents(self, limit: int = 30) -> list[dict[str, Any]]:
        # The existing cyber dashboard consumes the legacy table shape.
        return db_manager.query_rows("SELECT * FROM cyber ORDER BY created DESC LIMIT ?", limit)

    def get_cyber_events(self, limit: int = 30) -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM cyber_events ORDER BY timestamp DESC LIMIT ?", limit)

    def get_activity(self, limit: int = 30) -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM cyber_activity ORDER BY timestamp DESC LIMIT ?", limit)

    def get_camera_health(self) -> list[dict[str, Any]]:
        return db_manager.query_rows("SELECT * FROM cyber_camera_health ORDER BY updated DESC")

    def simulate(self, event_type: str, source_ip: str = "198.51.100.42",
                 camera_id: str = "cam-ring") -> dict[str, Any]:
        descriptions = {
            "failed_login": "SIMULATION: repeated failed camera login",
            "request_anomaly": "SIMULATION: abnormal CCTV request frequency",
            "port_scan": "SIMULATION: port-scan indicator detected",
            "unauthorized_endpoint": "SIMULATION: unauthorized camera endpoint access",
        }
        if event_type not in descriptions:
            raise ValueError(f"Unsupported simulation event: {event_type}")
        return self.record_event(event_type, descriptions[event_type], camera_id, source_ip, simulated=True)


cyber_service = CyberHoneypotService()
