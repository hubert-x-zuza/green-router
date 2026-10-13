"""Local geocoder: SQLite FTS5 index of the city's address points and streets (no Nominatim).

Build: python -m etl.geocoder      -> data/processed/geocoder.sqlite
Use:   Geocoder(path).search("al. Pokoju 5")

Normalisation (index and query alike): lower case, Polish diacritics removed (ł -> l included),
punctuation dropped, "ul."/"ulica" dropped, abbreviations expanded (al. -> aleja, os. -> osiedle,
pl. -> plac, ...). Every word of the query must prefix-match a word of the street name, so
"dietla 5" finds "Józefa Dietla 5". A house number in the query is matched against the number
column (exact first, then the street itself if the number does not exist).
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

from etl.common import PROCESSED, RAW, read_geojson

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
    """Street words and the house number (the last token that looks like one), if any."""
    toks = tokens(q)
    number = None
    for i in range(len(toks) - 1, -1, -1):
        if NUMBER_RE.match(toks[i]) and i > 0:
            number = toks.pop(i)
            break
    # a street name may contain numbers ("3 maja", "29 listopada"): keep the rest as words
    return toks, number


SCHEMA = """
DROP TABLE IF EXISTS places;
CREATE VIRTUAL TABLE places USING fts5(
  name_norm, label UNINDEXED, kind UNINDEXED, number UNINDEXED, district UNINDEXED,
  lon UNINDEXED, lat UNINDEXED, tokenize = 'unicode61');
"""


def build(out: Path = DB_PATH) -> int:
    addr = read_geojson(RAW / "address_points" / "Adresy.geojson")
    streets = read_geojson(RAW / "streets" / "Ulice.geojson")
    addr_ll = addr.geometry.to_crs("EPSG:4326")
    rows = [
        (normalise(p.nazwa_ulicy), f"{p.nazwa_ulicy} {p.numer_adresowy}", "address",
         strip_diacritics(str(p.numer_adresowy).lower()), p.nazwa_dzielnicy, g.x, g.y)
        for p, g in zip(addr.itertuples(), addr_ll, strict=True)
    ]  # fmt: skip
    # one point per street name: the middle of its longest piece
    streets = streets.explode(index_parts=False)
    streets["len"] = streets.length
    longest = streets.sort_values("len").groupby("nazwa_ulicy").tail(1)
    mid = gpd.GeoSeries(longest.geometry.interpolate(0.5, normalized=True), crs=streets.crs)
    mid = mid.to_crs("EPSG:4326")
    rows += [
        (normalise(n), n, "street", "", d, g.x, g.y)
        for n, d, g in zip(longest.nazwa_ulicy, longest.nazwa_dzielnicy, mid, strict=True)
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO places VALUES (?,?,?,?,?,?,?)", rows)
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


class Geocoder:
    def __init__(self, path: Path = DB_PATH) -> None:
        self.con = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)

    def search(self, q: str, limit: int = 8) -> list[Place]:
        words, number = split_query(q)
        if not words:
            return []
        match = " ".join(f'"{w}"*' for w in words)
        sql = ("SELECT label, kind, district, lon, lat, number FROM places WHERE places MATCH ? "
               "AND kind = ? ORDER BY rank, length(label) LIMIT ?")  # fmt: skip
        out: list[Place] = []
        if number:
            rows = self.con.execute(sql.replace("ORDER BY", "AND number = ? ORDER BY"),
                                    (match, "address", number, limit)).fetchall()  # fmt: skip
            if not rows and number.isdigit():  # "5" also finds "5a", never "51"
                glob_sql = sql.replace("ORDER BY", "AND number GLOB ? ORDER BY")
                args = (match, "address", number + "[a-z]", limit)
                rows = self.con.execute(glob_sql, args).fetchall()
            out += [Place(r[0], r[1], r[2], r[3], r[4]) for r in rows]
        rows = self.con.execute(sql, (match, "street", limit)).fetchall()
        out += [Place(r[0], r[1], r[2], r[3], r[4]) for r in rows]
        return out[:limit]


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    n = build()
    log.info("geocoder: %d places -> %s", n, DB_PATH)
    return 0


if __name__ == "__main__":
    sys.exit(main())
