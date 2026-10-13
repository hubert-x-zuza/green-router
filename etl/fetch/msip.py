"""Download the city's spatial datasets: MSIP zip files and ArcGIS REST feature layers.

Run:  python -m etl.fetch.msip                 (everything except large files)
      python -m etl.fetch.msip --large         (also the 614 MB noise map)
      python -m etl.fetch.msip green_map       (named sources only)

Sources and URLs come from config/sources.yml. Each output directory gets a `source.json` with the
URL, the server's Last-Modified (date of data creation, as far as the server tells) and the UTC
time obtained; the portal terms ask for both dates.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import yaml

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
CONFIG_PATH = ROOT / "config" / "sources.yml"
log = logging.getLogger("etl.fetch.msip")


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_source(d: Path, info: dict[str, Any]) -> None:
    (d / "source.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")


def fetch_zip(http: httpx.Client, key: str, url: str, out: Path) -> None:
    d = out / key
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / "download.zip"
    with http.stream("GET", url) as r:
        r.raise_for_status()
        last_modified = r.headers.get("last-modified")
        with tmp.open("wb") as f:
            for chunk in r.iter_bytes(1 << 20):
                f.write(chunk)
    with zipfile.ZipFile(tmp) as z:
        names = z.namelist()
        z.extractall(d)
    tmp.unlink()
    write_source(
        d, {"url": url, "last_modified": last_modified, "obtained_utc": now_utc(), "files": names}
    )
    log.info("%s: %d files", key, len(names))


def resolve_layer_id(http: httpx.Client, service: str, layer_name: str) -> int:
    meta = http.get(service, params={"f": "json"}).raise_for_status().json()
    ids = [lyr["id"] for lyr in meta.get("layers", []) if lyr["name"] == layer_name]
    if len(ids) != 1:
        raise RuntimeError(f"layer {layer_name!r} not found once in {service}")
    return ids[0]


def fetch_layer(http: httpx.Client, key: str, cfg: dict[str, Any], page: int, out: Path) -> None:
    lid = resolve_layer_id(http, cfg["service"], cfg["layer_name"])
    url = f"{cfg['service']}/{lid}/query"
    base = {
        "where": "1=1",
        "outFields": cfg.get("out_fields", "*"),
        "orderByFields": cfg.get("order_by", "objectid"),
        "outSR": 2178,
        "f": "geojson",
        "resultRecordCount": page,
    }
    count = http.get(url, params={"where": "1=1", "returnCountOnly": "true", "f": "json"})
    expected = count.raise_for_status().json()["count"]
    features: list[dict[str, Any]] = []
    while True:
        r = http.get(url, params={**base, "resultOffset": len(features)}).raise_for_status()
        batch = r.json().get("features", [])
        features += batch
        if len(batch) < page:
            break
    if len(features) != expected:
        raise RuntimeError(f"{key}: got {len(features)} features, service reports {expected}")
    d = out / key
    d.mkdir(parents=True, exist_ok=True)
    fc = {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::2178"}},
        "features": features,
    }
    (d / f"{key}.geojson").write_text(json.dumps(fc, ensure_ascii=False), encoding="utf-8")
    layer_meta = http.get(f"{cfg['service']}/{lid}", params={"f": "json"}).json()
    write_source(
        d,
        {
            "url": f"{cfg['service']}/{lid}",
            "layer_name": cfg["layer_name"],
            "n_features": len(features),
            "service_edit_date": (layer_meta.get("editingInfo") or {}).get("lastEditDate"),
            "obtained_utc": now_utc(),
        },
    )
    log.info("%s: %d features", key, len(features))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("keys", nargs="*")
    ap.add_argument("--large", action="store_true", help="include sources marked large")
    ap.add_argument("--out", type=Path, default=RAW)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    cfg = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
    http = httpx.Client(timeout=300, follow_redirects=True)
    failed = 0
    for key, src in cfg["msip_zip"].items():
        if (a.keys and key not in a.keys) or (not a.keys and src.get("large") and not a.large):
            continue
        try:
            fetch_zip(http, key, src["url"], a.out)
        except (httpx.HTTPError, zipfile.BadZipFile, OSError) as exc:
            log.error("%s: %s", key, exc)
            failed += 1
    for key, src in cfg["arcgis"].items():
        if a.keys and key not in a.keys:
            continue
        try:
            fetch_layer(http, key, src, cfg["page_size"], a.out)
        except (httpx.HTTPError, RuntimeError, KeyError) as exc:
            log.error("%s: %s", key, exc)
            failed += 1
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
