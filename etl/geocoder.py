"""Local geocoder: SQLite FTS5 index of the city's address points, streets, districts and named
places (no Nominatim). Places: venues, restaurants, museums, parks, stops, neighbourhoods from
OpenStreetMap (etl/fetch/osm_poi.py) and schools/kindergartens/nurseries from the city portal.

Build: python -m etl.geocoder      -> data/processed/geocoder.sqlite
Use:   Geocoder(path).search("al. Pokoju 5")

Normalisation (index and query alike): lower case, Polish diacritics removed (ł -> l included),
punctuation dropped, "ul."/"ulica" dropped, abbreviations expanded (al. -> aleja, os. -> osiedle,
pl. -> plac, ...). Every word of the query must prefix-match a word of the street name, so
"dietla 5" finds "Józefa Dietla 5". A house number in the query is matched against the number
column (exact first, then the street itself if the number does not exist). Places are found by
name ("tauron") or category ("kino", "restauracja kazimierz"); whole-word name matches rank first.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from etl.common import PROCESSED, RAW, city_boundary, etl_config, read_geojson

log = logging.getLogger("etl.geocoder")
DB_PATH = PROCESSED / "geocoder.sqlite"

DROP = {"ul", "ulica", "krakow", "m"}
EXPAND = {"al": "aleja", "aleje": "aleja", "os": "osiedle", "pl": "plac",
          "swietego": "sw", "swietej": "sw", "swietych": "sw", "generala": "gen",
          "ksiedza": "ks", "profesora": "prof", "doktora": "dr", "marszalka": "marsz"}  # fmt: skip
NUMBER_RE = re.compile(r"^\d+[a-z]?$")


def strip_diacritics(s: str) -> str:
    s = s.replace("ł", "l").replace("Ł", "L")
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def tokens(s: str) -> list[str]:
    s = strip_diacritics(s.lower())
    s = re.sub(r"(\d)\s*/\s*\d+\w*", r"\1", s)  # "12/4" (flat) -> "12"
    words = re.findall(r"[a-z0-9]+", s)
    return [EXPAND.get(w, w) for w in words if w not in DROP]


def normalise(s: str) -> str:
    return " ".join(tokens(s))


def split_query(q: str) -> tuple[list[str], str | None]:
    """Street words and the house number (the last token, if it looks like one).
    Numbers inside a street name ("29 listopada", "3 maja") stay words."""
    toks = tokens(q)
    if len(toks) > 1 and NUMBER_RE.match(toks[-1]):
        return toks[:-1], toks[-1]
    return toks, None


SCHEMA = """
DROP TABLE IF EXISTS places;
CREATE VIRTUAL TABLE places USING fts5(
  name_norm, cat_norm, label UNINDEXED, kind UNINDEXED, number UNINDEXED, district UNINDEXED,
  category UNINDEXED, category_pl UNINDEXED, category_en UNINDEXED, lon UNINDEXED, lat UNINDEXED,
  tokenize = 'unicode61');
"""
# place categories that name an area: listed before streets and venues of the same name
AREA_CATEGORIES = {"district", "suburb", "quarter", "neighbourhood", "village", "hamlet"}
STOP_CATEGORIES = {"bus_stop", "tram_stop", "halt"}
SITE_LABELS = {"school": ("szkoła", "school"), "kindergarten": ("przedszkole", "kindergarten"),
               "nursery": ("żłobek", "nursery")}  # fmt: skip


def _nice(name: str) -> str:
    """Portal school names are in capitals: "SZKOŁA PODSTAWOWA NR 4" -> "Szkoła Podstawowa Nr 4"."""
    return name.title().replace(" W Krakowie", " w Krakowie") if name.isupper() else name


def place_rows(districts: gpd.GeoDataFrame) -> list[tuple]:
    """Districts, OSM places and the city's sensitive sites as geocoder rows."""
    frames = []
    d = districts.copy()
    d["geometry"] = d.representative_point()
    frames.append(gpd.GeoDataFrame({"name": d.nazwa, "category": "district",
                                    "category_pl": "dzielnica", "category_en": "district"},
                                   geometry=d.geometry, crs=districts.crs))  # fmt: skip
    poi_path = RAW / "osm" / "poi.parquet"
    if poi_path.exists():
        p = pd.read_parquet(poi_path)
        cols = ["name", "alt_names", "category", "category_pl", "category_en", "category_terms"]
        frames.append(gpd.GeoDataFrame(p[cols],
                                       geometry=gpd.points_from_xy(p.x, p.y),
                                       crs=districts.crs))  # fmt: skip
    sites_path = PROCESSED / "planner_sites.parquet"
    if sites_path.exists():
        st = pd.read_parquet(sites_path)
        frames.append(gpd.GeoDataFrame({
            "name": st["name"].astype(str).map(_nice), "category": st["kind"],
            "category_pl": st["kind"].map(lambda k: SITE_LABELS[k][0]),
            "category_en": st["kind"].map(lambda k: SITE_LABELS[k][1])},
            geometry=gpd.points_from_xy(st.x, st.y), crs=districts.crs))  # fmt: skip
    allp = pd.concat(frames, ignore_index=True)
    allp["alt_names"] = allp.get("alt_names", pd.Series(dtype=object)).fillna("")
    allp["category_terms"] = allp.get("category_terms", pd.Series(dtype=object)).fillna("")
    allp = gpd.GeoDataFrame(allp, geometry="geometry", crs=districts.crs)
    # only places a route can reach: inside the graph area and near the walk network
    cfg = etl_config()
    nodes = pd.read_parquet(PROCESSED / "nodes_walk.parquet")
    dist, _ = cKDTree(nodes[["x", "y"]].to_numpy()).query(
        np.column_stack([allp.geometry.x, allp.geometry.y])
    )
    area = city_boundary().buffer(cfg["graph"]["boundary_buffer_m"])
    ok = (dist <= cfg["coverage"]["snap_max_m"]) & allp.geometry.within(area).to_numpy()
    log.info("places: %d indexed, %d unreachable left out", int(ok.sum()), int((~ok).sum()))
    allp = allp[ok].reset_index(drop=True)
    j = gpd.sjoin(allp, districts[["nazwa_peln", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    ll = allp.geometry.to_crs("EPSG:4326")
    return [
        (normalise(f"{r.name} {r.alt_names}"),
         normalise(f"{r.category_pl} {r.category_en} {r.category_terms}"), r.name, "poi", "",
         dist if isinstance(dist, str) else None, r.category, r.category_pl, r.category_en,
         g.x, g.y)
        for r, dist, g in zip(allp.itertuples(), j.nazwa_peln, ll, strict=True)
    ]  # fmt: skip


def build(out: Path = DB_PATH) -> int:
    addr = read_geojson(RAW / "address_points" / "Adresy.geojson")
    streets = read_geojson(RAW / "streets" / "Ulice.geojson")
    addr_ll = addr.geometry.to_crs("EPSG:4326")
    rows = [
        (normalise(p.nazwa_ulicy), "", f"{p.nazwa_ulicy} {p.numer_adresowy}", "address",
         strip_diacritics(str(p.numer_adresowy).lower()), p.nazwa_dzielnicy, None, None, None,
         g.x, g.y)
        for p, g in zip(addr.itertuples(), addr_ll, strict=True)
    ]  # fmt: skip
    # one point per street name: the middle of its longest piece
    streets = streets.explode(index_parts=False)
    streets["len"] = streets.length
    longest = streets.sort_values("len").groupby("nazwa_ulicy").tail(1)
    mid = gpd.GeoSeries(longest.geometry.interpolate(0.5, normalized=True), crs=streets.crs)
    mid = mid.to_crs("EPSG:4326")
    rows += [
        (normalise(n), "ulica street", n, "street", "", d, None, "ulica", "street", g.x, g.y)
        for n, d, g in zip(longest.nazwa_ulicy, longest.nazwa_dzielnicy, mid, strict=True)
    ]
    rows += place_rows(read_geojson(RAW / "districts" / "Dzielnice.geojson"))
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    tmp.replace(out)
    return len(rows)


@dataclass
class Place:
    label: str
    kind: str
    district: str | None
    lon: float
    lat: float
    category: str | None = None
    category_pl: str | None = None
    category_en: str | None = None


class Geocoder:
    COLS = "label, kind, district, lon, lat, category, category_pl, category_en, name_norm"

    def __init__(self, path: Path = DB_PATH) -> None:
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)

    def _query(self, words: list[str], where: str, args: tuple, pool: int) -> list[tuple]:
        match = " ".join(f'"{w}"*' for w in words)
        sql = (f"SELECT {self.COLS} FROM places WHERE places MATCH ? AND {where} "
               "ORDER BY rank, length(label) LIMIT ?")  # fmt: skip
        return self.con.execute(sql, (match, *args, pool)).fetchall()

    def search(self, q: str, limit: int = 8) -> list[Place]:
        words, number = split_query(q)
        if not words:
            return []
        pool = limit * 6
        out: list[Place] = []
        if number:
            rows = self._query(words, "kind = 'address' AND number = ?", (number,), pool)
            if not rows and number.isdigit():  # "5" also finds "5a", never "51"
                rows = self._query(words, "kind = 'address' AND number GLOB ?",
                                   (number + "[a-z]",), pool)  # fmt: skip
            out += self._ranked(rows, words)[:limit]
            if not rows:  # the number may belong to a name ("Klub 303")
                words = [*words, number]
        rows = self._query(words, "kind != 'address'", (), pool)
        out += self._ranked(rows, words)
        return out[:limit]

    @staticmethod
    def _ranked(rows: list[tuple], words: list[str]) -> list[Place]:
        """Order: more query words matching a whole word of the name ("wawel" prefers "Zamek
        Wawel" to "Wawelska"); a match in the name before a match in the category only ("kino
        pod baranami" before any cinema); areas (districts, neighbourhoods) before streets and
        venues, stops last; then the FTS order (stable sort)."""

        def key(r: tuple) -> tuple[int, int, int]:
            toks = r[8].split()
            whole = sum(w in toks for w in words)
            in_name = all(any(t.startswith(w) for t in toks) for w in words)
            cat = r[5]
            kind_rank = 0 if cat in AREA_CATEGORIES else 2 if cat in STOP_CATEGORIES else 1
            return (-whole, 0 if in_name else 1, kind_rank)

        rows = sorted(rows, key=key)
        return [Place(*r[:8]) for r in rows]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = build()
    log.info("geocoder: %d places -> %s", n, DB_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
