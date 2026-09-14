import urllib.request
import json
import ssl
import os

URLS = [
    "https://live.corp8.cloud/api/cameras",
    "https://live.sentinelgujarat.in/api/cameras",
]

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = None
cams = []

for url in URLS:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as res:
            data = json.loads(res.read().decode("utf-8"))
            cams = data.get("cameras", [])
            if cams:
                print(f"Successfully fetched {len(cams)} cameras from {url}:")
                break
    except Exception as e:
        print(f"Failed {url}: {e}")

if cams:
    for c in cams:
        print(f"ID: {str(c.get('id')):>2s} | Name: {c.get('name', ''):<12s} | Location: {c.get('location', '')}")

    with open("sentinel_all_31.json", "w") as f:
        json.dump(cams, f, indent=2)
    print("\nSaved catalog to sentinel_all_31.json")
