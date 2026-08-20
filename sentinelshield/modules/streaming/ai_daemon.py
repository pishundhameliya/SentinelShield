"""Background continuous AI Guardian daemon."""
from __future__ import annotations

import os
import threading
import time
import uuid

from core.database import db_manager, utcnow
from core.state import ai_state
from modules.registry.estate_data import DEMO_CAMS
from modules.streaming.worker import process_video
from modules.vision.alpr_ocr import normalize_plate


class AIGuardianDaemon:
    """Continuous background worker monitoring camera feeds for plates and tampers."""

    def __init__(self, interval_seconds: float = 12.0):
        self.interval = interval_seconds
        self._running = False
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread is None or not self._thread.is_alive():
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        idx = 0
        while self._running:
            time.sleep(self.interval)
            if not ai_state.is_enabled:
                continue

            cams = db_manager.query_rows(
                "SELECT * FROM cameras WHERE kind='recorded' AND source IS NOT NULL AND source != ''"
            )
            cams = [c for c in cams if c.get("source") and os.path.isfile(c["source"])]
            if not cams:
                continue

            cam = cams[idx % len(cams)]
            idx += 1

            try:
                hints = []
                for d in DEMO_CAMS:
                    if d["id"] == cam["id"]:
                        hints.append(d["hint"])

                result = process_video(cam["source"], cam.get("name") or "", hints)
                plates = [normalize_plate(x) for x in (result.get("plates") or [])]
                ts = utcnow()
                ai_state.record_cycle(cam["name"], plates, ts)

                with db_manager.transaction() as con:
                    watch = {normalize_plate(r["plate"]): dict(r) for r in con.execute("SELECT * FROM watchlist")}

                    for plate in plates:
                        con.execute(
                            "INSERT INTO events VALUES(?,?,?,?,?,?,?)",
                            ("ev-" + uuid.uuid4().hex[:8], "vehicle",
                             f"Plate {plate} at {cam.get('name')}", cam["id"],
                             cam.get("place"), plate, ts),
                        )
                        con.execute(
                            "INSERT INTO sightings VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            ("see-" + uuid.uuid4().hex[:10], plate, cam["id"], cam.get("name"),
                             cam.get("place"), cam.get("city_id"), cam.get("area_id"),
                             cam.get("lat"), cam.get("lng"), ts, "continuous-ai"),
                        )
                        if plate in watch:
                            recent = con.execute(
                                "SELECT id FROM alerts WHERE camera_id=? AND title LIKE ? AND created > datetime('now','-3 minutes')",
                                (cam["id"], f"%{plate}%"),
                            ).fetchone()
                            if not recent:
                                w = watch[plate]
                                con.execute(
                                    "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                                    ("al-" + uuid.uuid4().hex[:10], cam["id"], "watchlist",
                                     f"Watchlist hit {plate}",
                                     f"{w['kind'].upper()} — last seen {cam.get('name')} · AI continuous",
                                     w.get("priority") or "HIGH", result.get("trust") or 80,
                                     0, ts, "new"),
                                )

                    for tp in result.get("tampers") or []:
                        con.execute(
                            "INSERT INTO alerts VALUES(?,?,?,?,?,?,?,?,?,?)",
                            ("al-" + uuid.uuid4().hex[:10], cam["id"], "tamper",
                             f"Video tamper: {tp['type']}", tp["detail"], "CRITICAL",
                             result.get("trust") or 40, tp.get("t") or 0, ts, "new"),
                        )

                    note = f"AI watch · {ts} · plates {', '.join(plates) or 'none'}"
                    con.execute(
                        "UPDATE cameras SET last_note=?, trust=? WHERE id=?",
                        (note, result.get("trust") or 80, cam["id"]),
                    )
            except Exception:
                continue


ai_guardian_daemon = AIGuardianDaemon()
