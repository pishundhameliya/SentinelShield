"""CCTV cybersecurity monitoring, decoy trap, and threat scoring service."""
from __future__ import annotations

import json
import uuid
import threading
import time
from typing import Any

from sentinelshield.core.database import db_manager, utcnow
from sentinelshield.modules.alerts.service import AlertService


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
        
        # Thread safety lock and detection states
        self._lock = threading.RLock()
        self._failed_logins: dict[str, list[float]] = {}
        self._requests: dict[str, list[float]] = {}
        self._scans: dict[str, dict[str, float]] = {}  # source_ip -> {camera_id_or_port: timestamp}
        
        # Configuration thresholds
        self.FAILED_LOGIN_THRESHOLD = 5
        self.REPEATED_REQUESTS_THRESHOLD = 20
        self.PORT_SCAN_THRESHOLD = 3

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
        
        # Explicitly mark simulation description if simulated
        if simulated and not description.startswith("SIMULATION:"):
            description = f"SIMULATION: {description}"
            
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

    def track_auth_attempt(self, source_ip: str, camera_id: str, success: bool, username: str | None = None) -> dict[str, Any]:
        source = _source_ip(source_ip)
        if success:
            with self._lock:
                self._failed_logins.pop(source, None)
            return {"status": "success", "message": "Auth attempt successful"}

        now = time.time()
        with self._lock:
            if source not in self._failed_logins:
                self._failed_logins[source] = []
            self._failed_logins[source].append(now)
            self._failed_logins[source] = [t for t in self._failed_logins[source] if now - t <= WINDOW_SECONDS]
            count = len(self._failed_logins[source])
            
            event = None
            if count >= self.FAILED_LOGIN_THRESHOLD:
                description = f"Repeated failed camera login attempts from IP. User attempted: '{username or 'unknown'}'. Consecutive failures: {count}."
                event = self.record_event(
                    "failed_login", description, camera_id, source,
                    score=EVENT_POINTS["failed_login"]
                )
                self._failed_logins.pop(source, None)
        
        return {
            "status": "failed",
            "consecutive_failures": count,
            "threshold_breached": event is not None,
            "event": event
        }

    def track_request(self, source_ip: str, camera_id: str, endpoint: str) -> dict[str, Any]:
        source = _source_ip(source_ip)
        now = time.time()
        
        # Check for unauthorized endpoints
        unauthorized_patterns = ("/admin", "/setup", "/config", "/etc/", "/proc/", ".php", "wp-", "/onvif")
        is_unauthorized = any(pattern in endpoint.lower() for pattern in unauthorized_patterns)
        
        unauthorized_event = None
        repeated_event = None
        
        if is_unauthorized:
            unauthorized_event = self.record_event(
                "unauthorized_endpoint",
                f"Unauthorized access attempt to CCTV endpoint: '{endpoint}'",
                camera_id, source, score=EVENT_POINTS["unauthorized_endpoint"]
            )
            
        with self._lock:
            if source not in self._requests:
                self._requests[source] = []
            self._requests[source].append(now)
            self._requests[source] = [t for t in self._requests[source] if now - t <= WINDOW_SECONDS]
            count = len(self._requests[source])
            
            if count >= self.REPEATED_REQUESTS_THRESHOLD:
                repeated_event = self.record_event(
                    "repeated_requests",
                    f"Abnormal request rate: {count} requests within window of {WINDOW_SECONDS} seconds.",
                    camera_id, source, score=EVENT_POINTS["repeated_requests"]
                )
                self._requests.pop(source, None)
                
        return {
            "source_ip": source,
            "request_count": count,
            "unauthorized_access": is_unauthorized,
            "unauthorized_event": unauthorized_event,
            "repeated_event": repeated_event
        }

    def track_connection(self, source_ip: str, camera_id: str, port: int | None = None) -> dict[str, Any]:
        source = _source_ip(source_ip)
        now = time.time()
        key = f"{camera_id}:{port}" if port is not None else camera_id
        
        event = None
        with self._lock:
            if source not in self._scans:
                self._scans[source] = {}
            self._scans[source][key] = now
            self._scans[source] = {k: t for k, t in self._scans[source].items() if now - t <= WINDOW_SECONDS}
            unique_targets = len(self._scans[source])
            
            if unique_targets >= self.PORT_SCAN_THRESHOLD:
                targets_str = ", ".join(self._scans[source].keys())
                event = self.record_event(
                    "port_scan",
                    f"CCTV camera scan / sweep detected. Accessed {unique_targets} unique targets: [{targets_str}].",
                    camera_id, source, score=EVENT_POINTS["port_scan"]
                )
                self._scans.pop(source, None)
                
        return {
            "source_ip": source,
            "unique_targets": unique_targets,
            "port_scan_detected": event is not None,
            "event": event
        }

    def trigger_honeypot_incident(
        self,
        source_ip: str | None = None,
        action: str = "request",
        simulated: bool = False,
        request: Any = None,
    ) -> dict[str, Any]:
        cid = "honeypot-cam"
        source = _source_ip(source_ip)
        
        username = None
        auth_attempted = False
        
        if request is not None:
            headers = getattr(request, "headers", {})
            auth_header = headers.get("authorization", "")
            if auth_header and auth_header.lower().startswith("basic "):
                auth_attempted = True
                try:
                    import base64
                    encoded = auth_header.split(" ", 1)[1]
                    decoded = base64.b64decode(encoded).decode("utf-8", errors="ignore")
                    if ":" in decoded:
                        username, _ = decoded.split(":", 1)
                except Exception:
                    pass

        event_type = "failed_login" if auth_attempted else "unauthorized_endpoint"
        desc_prefix = "SIMULATION: " if simulated else ""
        if auth_attempted:
            description = f"{desc_prefix}Decoy CCTV decoy trap triggered: Unauthorized credential authentication attempt from IP. Attempted user: '{username or 'unknown'}'."
            score_points = EVENT_POINTS["failed_login"]
        else:
            description = f"{desc_prefix}Decoy CCTV decoy trap triggered: Unauthorized connection request: '{action}'."
            score_points = EVENT_POINTS["unauthorized_endpoint"]
            
        event = self.record_event(
            event_type, description, cid, source,
            score=score_points, simulated=simulated
        )
        
        activity_id = "ca-" + uuid.uuid4().hex[:10]
        db_manager.execute(
            "INSERT INTO cyber_activity VALUES(?,?,?,?,?,?,?,?,?)",
            activity_id, event["timestamp"], event["source_ip"], "honeypot",
            "CAM-HONEYPOT-01", f"{action} [Auth: {username}]" if username else action,
            event["score"], event["severity"], int(simulated),
        )
        return {
            "ok": False,
            "error": "Unauthorized",
            "camera": "CAM-HONEYPOT-01",
            "event": event,
            "decoy": True
        }

    def update_camera_health(self, camera_id: str, state: str, source_ip: str | None = None) -> dict[str, Any]:
        previous = db_manager.query_one(
            "SELECT state, source_ip FROM cyber_camera_health WHERE camera_id=?", camera_id
        )
        source = _source_ip(source_ip)
        suspicious = bool(previous and previous.get("source_ip") not in (None, source))
        event = None
        
        prev_state = previous.get("state") if previous else None
        if prev_state != state:
            if state == "disconnected":
                event_type = "connection_anomaly" if suspicious else "repeated_connection"
                event = self.record_event(
                    event_type,
                    f"Unexpected camera disconnect. State changed from {prev_state or 'unknown'} to {state}.",
                    camera_id, source, score=EVENT_POINTS[event_type],
                )
            elif state == "reconnected":
                event_type = "repeated_connection"
                event = self.record_event(
                    event_type,
                    f"Camera reconnected. State changed from {prev_state or 'unknown'} to {state}.",
                    camera_id, source, score=EVENT_POINTS[event_type],
                )
            elif state == "connected" and prev_state == "disconnected":
                event_type = "repeated_connection"
                event = self.record_event(
                    event_type,
                    f"Camera connection restored. State changed from {prev_state} to {state}.",
                    camera_id, source, score=EVENT_POINTS[event_type],
                )
                
        db_manager.execute(
            "INSERT OR REPLACE INTO cyber_camera_health VALUES(?,?,?,?,?,?)",
            camera_id, state, source, prev_state,
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
