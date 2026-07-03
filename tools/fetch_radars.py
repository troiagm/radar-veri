#!/usr/bin/env python3
"""
Tum ulkenin radar verisini Overpass'tan TEK sorguyla ceker ve
kompakt bir JSON dosyasina yazar. GitHub Actions gecede bir calistirir.

Kullanim: python tools/fetch_radars.py TR docs/radars_tr.json
"""
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

COUNTRY = sys.argv[1] if len(sys.argv) > 1 else "TR"
OUT = sys.argv[2] if len(sys.argv) > 2 else "docs/radars_tr.json"

QUERY = f"""
[out:json][timeout:300];
area["ISO3166-1"="{COUNTRY}"][admin_level=2]->.c;
relation["type"="enforcement"](area.c)->.enf;
(
  node["highway"="speed_camera"](area.c);
  node(r.enf)(area.c);
);
out body;
"""

MIRRORS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]


def parse_maxspeed(raw):
    if not raw:
        return None
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        return None
    value = int(digits)
    if "mph" in raw.lower():
        value = round(value * 1.609)
    return value


def fetch(url):
    data = urllib.parse.urlencode({"data": QUERY}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "User-Agent": "RadarUyari-DataBot/1.0 (nightly build)",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=320) as res:
        return json.load(res)


def main():
    last_err = None
    payload = None
    for mirror in MIRRORS:
        try:
            print(f"Deneniyor: {mirror}")
            payload = fetch(mirror)
            break
        except Exception as e:  # noqa: BLE001
            print(f"  basarisiz: {e}")
            last_err = e
    if payload is None:
        print(f"HATA: tum aynalar basarisiz: {last_err}")
        sys.exit(1)

    by_id = {}
    for e in payload.get("elements", []):
        if e.get("type") != "node":
            continue
        if e.get("lat") is None or e.get("lon") is None:
            continue
        node_id = str(e["id"])
        ms = parse_maxspeed((e.get("tags") or {}).get("maxspeed"))
        existing = by_id.get(node_id)
        if existing is None or (existing.get("ms") is None and ms is not None):
            cam = {
                "id": node_id,
                "lat": round(e["lat"], 6),
                "lon": round(e["lon"], 6),
            }
            if ms is not None:
                cam["ms"] = ms
            by_id[node_id] = cam

    cameras = list(by_id.values())
    if len(cameras) < 50:
        # Bariz bozuk/eksik veri: mevcut dosyanin uzerine yazma
        print(f"HATA: sadece {len(cameras)} radar geldi, suphe verici. Cikiliyor.")
        sys.exit(1)

    out = {
        "updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "country": COUNTRY,
        "count": len(cameras),
        "cameras": cameras,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"OK: {len(cameras)} radar -> {OUT}")


if __name__ == "__main__":
    main()
