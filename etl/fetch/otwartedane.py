"""Download every dataset table from the Kraków open-data portal (otwartedane.um.krakow.pl).

Run:  python -m etl.fetch.otwartedane            (the datasets listed in config/otwartedane.yml)
      python -m etl.fetch.otwartedane parki-miejskie-w-krakowie   (named datasets)
      python -m etl.fetch.otwartedane --all      (every dataset in the portal)

How the portal works (verified 2026-10-13):
* The listing `/zbiory-danych?p=N` links every dataset page `/zbiory-danych/<slug>`.
* A dataset page embeds `window.WEB_COMPONENTS = [...]`; each `data-exporter` component carries
  the table's `apiUrl` on `https://api.um.krakow.pl/...` (no key needed). `metadata-prefetch`
  carries a `metaUrl` with the view name, refresh time and row count.
* The API returns `{"value": [...rows], "nextLink": ...}` in pages of 100. `nextLink` points to an
  internal host, so only its `$after` parameter is reused against the public URL.
* Some datasets (ZTP: transit, bikes, city signage) have no tables, only ArcGIS Hub map links.
  Those links are recorded in dataset.json; the layers are not downloaded here.

Output: data/raw/otwartedane/<slug>/<table>.json (list of rows) + dataset.json (page metadata,
sources, fetch time), and data/raw/otwartedane/index.json. Re-running overwrites (idempotent).
Terms (portal, point 4): cite "Gmina Miejska Kraków, otwartedane.um.krakow.pl" with the time the
data were created and obtained. See docs/licences/otwartedane_warunki.md.
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx
import yaml

PORTAL = "https://otwartedane.um.krakow.pl"
ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "raw" / "otwartedane"
CONFIG_PATH = ROOT / "config" / "otwartedane.yml"
PAUSE_S = 0.3  # portal terms, point 7: do not disrupt access for others
MAX_LISTING_PAGES = 50
log = logging.getLogger("etl.fetch.otwartedane")


# ---- pure parsers -------------------------------------------------------------------------


def parse_listing(page_html: str) -> list[str]:
    """Dataset slugs linked from one listing page, in page order, without duplicates."""
    slugs = re.findall(r'href="/zbiory-danych/([^"?#/]+)"', page_html)
    return list(dict.fromkeys(slugs))


def _text(fragment: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", fragment)).split())


def parse_dataset_page(page_html: str) -> dict[str, Any]:
    """Title, metadata table, tables (title, update date, apiUrl, metaUrl) and external links."""
    m = re.search(r"window\.WEB_COMPONENTS\s*=\s*(\[.*?\]);\s*</script>", page_html, re.S)
    components = json.loads(m.group(1)) if m else []
    meta_urls = [c["options"]["metaUrl"] for c in components if c["name"] == "metadata-prefetch"]
    exporters = {c["id"]: c["options"] for c in components if c["name"] == "data-exporter"}

    title_m = re.search(r"<title>(.*?) — Otwarte Dane</title>", page_html, re.S)
    pub_m = re.search(r"Data publikacji:\s*([0-9.]+,\s*[0-9:]+)", page_html)
    info = dict(
        (_text(k), _text(v))
        for k, v in re.findall(
            r'<td class="py-1 pr-4[^"]*">(.*?)</td>\s*<td class="py-1">(.*?)</td>', page_html, re.S
        )
    )

    tables = []
    pos = 0
    for div_id, opts in exporters.items():
        idx = page_html.find(f'id="{div_id}"', pos)
        if idx < 0:
            continue
        segment = page_html[pos:idx]
        titles = re.findall(r"<h5[^>]*>(.*?)</h5>", segment, re.S)
        updated = re.findall(r"Data aktualizacji:\s*([0-9.]+)", segment)
        tables.append(
            {
                "title": _text(titles[-1]) if titles else None,
                "data_updated": updated[-1] if updated else None,
                "api_url": opts["apiUrl"],
            }
        )
        pos = idx

    links = sorted(set(re.findall(r'href="(https://[^"]*hub\.arcgis\.com/[^"]+)"', page_html)))
    return {
        "title": _text(title_m.group(1)) if title_m else None,
        "published": pub_m.group(1) if pub_m else None,
        "provider": info.get("Dostawca danych"),
        "publisher": info.get("Publikujący dane"),
        "category": info.get("Kategoria"),
        "update_frequency": info.get("Częstotliwość aktualizacji danych"),
        "page_created": info.get("Data utworzenia witryny"),
        "page_updated": info.get("Data aktualizacji witryny"),
        "meta_urls": meta_urls,
        "tables": tables,
        "external_links": links,
    }


def next_after(payload: dict[str, Any]) -> str | None:
    """The `$after` cursor from `nextLink` (whose host is internal), or None on the last page."""
    link = payload.get("nextLink")
    if not link:
        return None
    return parse_qs(urlsplit(link).query).get("$after", [None])[0]


# ---- HTTP ---------------------------------------------------------------------------------


class Portal:
    def __init__(self, http: httpx.Client | None = None, pause_s: float = PAUSE_S) -> None:
        self.http = http or httpx.Client(
            timeout=60, follow_redirects=True, headers={"User-Agent": "zdrowa-trasa-etl"}
        )
        self.pause_s = pause_s

    def _get(self, url: str, params: dict[str, str] | None = None) -> httpx.Response:
        for attempt in range(3):
            try:
                r = self.http.get(url, params=params)
                if r.status_code < 500:
                    r.raise_for_status()
                    time.sleep(self.pause_s)
                    return r
            except httpx.TransportError:
                pass
            time.sleep(2.0 * (attempt + 1))
        raise RuntimeError(f"giving up on {url}")

    def slugs(self) -> list[str]:
        out: list[str] = []
        for p in range(1, MAX_LISTING_PAGES + 1):
            found = parse_listing(self._get(f"{PORTAL}/zbiory-danych", {"p": str(p)}).text)
            new = [s for s in found if s not in out]
            if not new:
                return out
            out += new
        raise RuntimeError("listing did not end; raise MAX_LISTING_PAGES")

    def dataset(self, slug: str) -> dict[str, Any]:
        return parse_dataset_page(self._get(f"{PORTAL}/zbiory-danych/{slug}").text)

    def table(self, api_url: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        after: str | None = None
        while True:
            payload = self._get(api_url, {"$after": after} if after else None).json()
            rows += payload["value"]
            after = next_after(payload)
            if after is None:
                return rows

    def metadata(self, meta_url: str) -> list[dict[str, Any]]:
        return self._get(meta_url).json().get("value", [])


# ---- main ---------------------------------------------------------------------------------


def fetch_dataset(portal: Portal, slug: str, out_dir: Path) -> dict[str, Any]:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    ds = portal.dataset(slug)
    d = out_dir / slug
    d.mkdir(parents=True, exist_ok=True)
    views = [v for u in ds["meta_urls"] for v in portal.metadata(u)]
    for t in ds["tables"]:
        name = t["api_url"].rstrip("/").rsplit("/", 1)[-1]
        rows = portal.table(t["api_url"])
        (d / f"{name}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        t.update(file=f"{name}.json", n_rows=len(rows), fields=list(rows[0]) if rows else [])
        log.info("%s / %s: %d rows", slug, name, len(rows))
    ds.update(slug=slug, page=f"{PORTAL}/zbiory-danych/{slug}", fetched_utc=now, views=views)
    (d / "dataset.json").write_text(json.dumps(ds, ensure_ascii=False, indent=1), encoding="utf-8")
    return ds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("slugs", nargs="*", help="dataset slugs; default: config/otwartedane.yml")
    ap.add_argument("--all", action="store_true", help="every dataset listed in the portal")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    portal = Portal()
    if a.all:
        slugs = portal.slugs()
    elif a.slugs:
        slugs = a.slugs
    else:
        slugs = list(yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))["datasets"])
    log.info("%d datasets", len(slugs))
    index, failed = [], []
    for slug in slugs:
        try:
            ds = fetch_dataset(portal, slug, a.out)
        except (RuntimeError, httpx.HTTPError, KeyError, ValueError) as exc:
            log.error("%s: %s", slug, exc)
            failed.append({"slug": slug, "error": str(exc)[:300]})
            continue
        index.append(
            {k: ds[k] for k in ("slug", "title", "provider", "page_updated", "fetched_utc")}
            | {"tables": [t["file"] for t in ds["tables"]], "external_links": ds["external_links"]}
        )
    if not a.slugs:
        a.out.mkdir(parents=True, exist_ok=True)
        (a.out / "index.json").write_text(
            json.dumps({"datasets": index, "failed": failed}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    log.info("done: %d ok, %d failed", len(index), len(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
