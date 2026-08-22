---
description: Fetch live Gujarat CCTV camera metadata from live.corp8.cloud and sync database
---

Sync the estate catalog with live streams:
```bash
python sentinelshield/fetch_31.py
python sentinelshield/import_all_31_cams.py
```
Updates `sentinel_all_31.json` and imports all live stream endpoints (HLS, WebRTC, RTSP) into SQLite.
