"""Asynchronous Operator Dispatch Webhook Service with HMAC SHA-256 Signatures."""
from __future__ import annotations

import hmac
import hashlib
import json
import threading
import time
import urllib.request
import urllib.error
import uuid
from typing import Any

from sentinelshield.core.database import db_manager, utcnow


class WebhookDispatchService:
    """Service managing dispatch webhooks for police/patrol notification integration."""

    def __init__(self):
        self._queue: list[dict[str, Any]] = []
        self._lock = threading.RLock()
        self._stop_event = threading.Event()
        self._worker_thread: threading.Thread | None = None
        self._init_schema()

    def _init_schema(self) -> None:
        """Initialize webhooks table if not exists."""
        db_manager.execute("""
            CREATE TABLE IF NOT EXISTS webhooks (
                id TEXT PRIMARY KEY,
                url TEXT NOT NULL,
                secret TEXT,
                events TEXT DEFAULT 'all',
                status TEXT DEFAULT 'active',
                created TEXT,
                last_dispatched TEXT
            )
        """)

    def register_webhook(
        self,
        url: str,
        secret: str | None = None,
        events: list[str] | str = "all",
    ) -> dict[str, Any]:
        """Register or update a webhook endpoint."""
        url = (url or "").strip()
        if not url.startswith("http://") and not url.startswith("https://"):
            return {"ok": False, "error": "URL must start with http:// or https://"}

        wid = "whk-" + uuid.uuid4().hex[:8]
        sec = secret or ("sec_" + uuid.uuid4().hex[:16])
        events_str = json.dumps(events) if isinstance(events, list) else str(events)

        db_manager.execute(
            "INSERT INTO webhooks VALUES(?,?,?,?,?,?,?)",
            wid, url, sec, events_str, "active", utcnow(), None,
        )
        return {"ok": True, "id": wid, "url": url, "secret": sec, "events": events_str}

    def list_webhooks(self) -> list[dict[str, Any]]:
        """List all active webhook configurations."""
        return db_manager.query_rows("SELECT id, url, events, status, created, last_dispatched FROM webhooks ORDER BY created DESC")

    def delete_webhook(self, wid: str) -> bool:
        """Delete a webhook by ID."""
        db_manager.execute("DELETE FROM webhooks WHERE id=?", wid)
        return True

    def dispatch_alert(self, alert_dict: dict[str, Any]) -> None:
        """Enqueue alert for asynchronous webhook broadcast."""
        with self._lock:
            self._queue.append({
                "alert": alert_dict,
                "timestamp": utcnow(),
                "attempts": 0,
            })

    def start_worker(self) -> None:
        """Start the background dispatch worker thread."""
        if self._worker_thread and self._worker_thread.is_alive():
            return
        self._stop_event.clear()
        self._worker_thread = threading.Thread(target=self._run_loop, daemon=True, name="WebhookDispatchWorker")
        self._worker_thread.start()

    def stop_worker(self) -> None:
        """Signal the dispatch worker thread to stop."""
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=2.0)

    def _run_loop(self) -> None:
        """Background queue processor delivering alerts to registered webhooks."""
        while not self._stop_event.is_set():
            items_to_send = []
            with self._lock:
                if self._queue:
                    items_to_send = self._queue[:]
                    self._queue.clear()

            if not items_to_send:
                time.sleep(0.5)
                continue

            webhooks = db_manager.query_rows("SELECT * FROM webhooks WHERE status='active'")
            if not webhooks:
                continue

            for item in items_to_send:
                payload_json = json.dumps(item["alert"], sort_keys=True)
                payload_bytes = payload_json.encode("utf-8")

                for whk in webhooks:
                    self._send_http_post(whk, payload_bytes)

    def _send_http_post(self, whk: dict[str, Any], payload_bytes: bytes) -> bool:
        """Deliver HTTP payload with HMAC SHA-256 signature."""
        url = whk["url"]
        secret = (whk.get("secret") or "").encode("utf-8")
        signature = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()

        req = urllib.request.Request(
            url,
            data=payload_bytes,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "SentinelShield-Dispatch/1.0",
                "X-Sentinel-Signature": signature,
                "X-Sentinel-Event": "alert",
            },
            method="POST",
        )

        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=3.0) as resp:
                    if 200 <= resp.status < 300:
                        db_manager.execute("UPDATE webhooks SET last_dispatched=? WHERE id=?", utcnow(), whk["id"])
                        return True
            except Exception:
                time.sleep(0.2 * (2 ** attempt))

        return False


webhook_dispatch_service = WebhookDispatchService()
