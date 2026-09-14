# SentinelShield — REST & WebSocket API Catalog

> **Base URL**: `http://localhost:8000`  
> **Documentation UI**: `http://localhost:8000/docs` (Swagger UI) / `http://localhost:8000/redoc`

---

## 1. Streaming & Health Endpoints

### `GET /api/health`
Returns overall system status, AI daemon state, and server UTC clock.
- **Response**:
  ```json
  {
    "ok": true,
    "ai": {"active": true, "interval": 12.0},
    "clock": "2026-08-22 13:00:00 UTC"
  }
  ```

### `GET /video_feed`
Streams live MJPEG multipart video feed for the currently active or requested camera with dynamic client backpressure.
- **Query Params**: `camera_id` (optional), `max_fps` (optional, default 25)
- **Response**: `multipart/x-mixed-replace; boundary=frame`

### `POST /api/stream/start`
Activates live streaming mode for a camera.
- **Body / Form**: `camera_id` (str), `source_mode` (`auto` / `loop` / `url`)
- **Response**: `{"ok": true, "camera_id": "cam-01", "mode": "url"}`

### `POST /api/stream/stop`
Stops the active live stream.

---

## 2. Forensic Evidence & Digital Custody

### `GET /api/evidence`
Lists sealed forensic evidence packages.
- **Response**: `{"packs": [{"id": "evd-1234", "camera_id": "cam-01", "sha256": "...", "created": "..."}]}`

### `POST /api/evidence/{camera_id}`
Seals a new forensic digital custody evidence pack for the specified camera.
- **Response**:
  ```json
  {
    "ok": true,
    "id": "evd-a1b2c3d4",
    "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "file": "/media/vault/cam-01_e3b0c44298.json"
  }
  ```

### `GET /api/evidence/{camera_id}/pdf`
Downloads Section 65B (IEA) / Section 63 (BSA 2023) court-admissible PDF evidence certificate with QR code.
- **Response**: `application/pdf` attachment (`evidence_{camera_id}.pdf`)

### `POST /api/evidence/verify`
Forensically verifies provided JSON evidence manifest against certificate hash.
- **Body (JSON)**: `{"payload": {...}, "sha256": "..."}`
- **Response**:
  ```json
  {
    "valid": true,
    "message": "Integrity verified: SHA-256 match",
    "provided_hash": "...",
    "computed_hash": "..."
  }
  ```

---

## 3. Vehicle Tracking & Route Reconstruction

### `GET /api/vehicle`
Searches sightings for a specific license plate.
- **Query Params**: `plate` (e.g. `GJ05SS2026`)
- **Response**: `{"plate": "GJ05SS2026", "found": true, "last": {...}, "history": [...]}`

### `GET /api/route`
Reconstructs multi-hop geospatial trajectory across Gujarat CCTV estate.
- **Query Params**: `plate` (str)
- **Response**: `{"plate": "...", "points": [{"lat": 21.17, "lng": 72.83, "camera": "...", "time": "..."}]}`

---

## 4. Alerts, Watchlist & Operator Webhooks

### `POST /api/watchlist`
Adds vehicle license plate to threat watchlist.
- **Form Params**: `plate` (str), `kind` (`stolen`, `wanted`, `suspect`), `priority` (`HIGH`, `CRITICAL`), `note` (str)

### `DELETE /api/watchlist/{wid}`
Removes plate from watchlist.

### `POST /api/webhooks`
Registers an external HTTP webhook for automated threat alert dispatch.
- **Form Params**: `url` (str), `secret` (str, optional), `events` (`all` / `watchlist` / `critical`)
- **Response**: `{"ok": true, "id": "whk-1234", "url": "https://...", "secret": "..."}`

### `GET /api/webhooks`
Lists all active dispatch webhooks.

### `DELETE /api/webhooks/{wid}`
Deletes a dispatch webhook by ID.

---

## 5. Camera Estate & CSV Bulk Importer

### `GET /api/cities`
Returns Gujarat cities, zones, and total CCTV camera count.

### `GET /api/cameras`
Queries camera inventory with city/area filters.
- **Query Params**: `city` (str), `area` (str), `owner` (str)

### `POST /api/cameras/import-csv`
Transactionally imports camera definitions from CSV text with Gujarat coordinate bounding box validation.
- **Form Params**: `csv_text` (str), `mode` (`update` / `ignore`)
- **Response**: `{"total": 150, "imported": 150, "skipped": 0, "errors": []}`

---

## 6. Real-Time WebSocket Channel

### `WS /ws`
Bi-directional real-time communication channel for team chat, real-time alert broadcasts, and drone dispatch tracking.
- **JSON Message Format**:
  ```json
  {
    "type": "chat",
    "token": "session_token",
    "room": "team",
    "text": "Patrol dispatched to Surat Ring Road North"
  }
  ```
- **Broadcast Format**:
  ```json
  {
    "type": "chat",
    "id": "msg-1234",
    "user": "Officer Patel",
    "role": "police",
    "text": "Patrol dispatched to Surat Ring Road North",
    "created": "2026-08-22 13:05:00 UTC"
  }
  ```
