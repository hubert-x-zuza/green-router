"""Named places from OpenStreetMap for the geocoder: venues (e.g. TAURON Arena), restaurants, cafés,
museums, parks, stations and stops, neighbourhoods.

Run:  python -m etl.fetch.osm_poi            (cached in data/raw/osm/poi_raw.parquet)
      python -m etl.fetch.osm_poi --refresh

Area: city boundary + graph buffer (same as the street graph). Categories and labels come from
config/sources.yml (`osm_poi`). Output: data/raw/osm/poi.parquet with name, category, lon/lat and
x/y in EPSG:2178. Licence: ODbL, © OpenStreetMap contributors (as the graph).
Duplicates are merged: the same name and category within 50 m (a node and its building), and stops
of the same name (platform number "01", "02" removed) within `merge_stops_m`.
"""

from __future__ import annotations

import argparse
import logging
import sys

import geopandas as gpd
import numpy as np
import osmnx as ox
import pandas as pd

from etl.common import CONFIG, RAW, etl_config, load_yaml
from etl.graph import area_wgs84

log = logging.getLogger("etl.fetch.osm_poi")
OSM_DIR = RAW / "osm"
STOP_CATEGORIES = {"tram_stop", "bus_stop", "halt"}
# other names people search for ("Kościół Mariacki", "Wawel"): indexed, not displayed
ALT_NAME_TAGS = ["alt_name", "short_name", "official_name", "old_name", "name:en"]
PLACE_CATEGORIES = {"suburb", "quarter", "neighbourhood", "village", "hamlet"}
SAME_PLACE_M = 50


def categorise(df: pd.DataFrame, tags: dict) -> pd.Series:
    """First matching (key, value) in config order -> category value (e.g. 'restaurant')."""
    cat = pd.Series(None, index=df.index, dtype=object)
    for key, values in tags.items():
        if key not in df:
            continue
        col = df[key].astype(str)  # None -> "None", never equal to a config value
        for value in values:
            cat = cat.where(cat.notna() | (col != value), value)
    return cat


def merge_close(gdf: gpd.GeoDataFrame, radius: float) -> gpd.GeoDataFrame:
    """Within each (name, category) group keep one point per cluster of points closer than radius
    (greedy, deterministic: input sorted by name, category, x, y)."""
    keep = []
    for _, g in gdf.groupby(["name", "category"], sort=True):
        centres: list[tuple[float, float]] = []
        for idx, x, y in zip(g.index, g.x, g.y, strict=True):
            if all(np.hypot(x - cx, y - cy) > radius for cx, cy in centres):
                centres.append((x, y))
                keep.append(idx)
    return gdf.loc[sorted(keep)]


def build(refresh: bool) -> gpd.GeoDataFrame:
    cfg = load_yaml("sources.yml")["osm_poi"]
    etl = etl_config()
    tags = cfg["tags"]
    raw_path = OSM_DIR / "poi_raw.parquet"
    if raw_path.exists() and not refresh:
        f = gpd.read_parquet(raw_path)
    else:
        ox.settings.use_cache = True
        ox.settings.cache_folder = str(OSM_DIR / "cache")
        ox.settings.requests_timeout = 600
        polygon = area_wgs84(etl["graph"]["boundary_buffer_m"])
        log.info("downloading OSM places (Overpass)...")
        f = ox.features_from_polygon(polygon, tags={k: list(v) for k, v in tags.items()})
        keep = ["name", "geometry"] + [k for k in [*tags, *ALT_NAME_TAGS] if k in f]
        f = f.reset_index()[keep]
        f = f[f["name"].notna()]
        for k in [*tags, *ALT_NAME_TAGS]:
            if k in f:
                f[k] = f[k].where(f[k].notna(), None).astype(object)
        OSM_DIR.mkdir(parents=True, exist_ok=True)
        f.to_parquet(raw_path)
    f = f.copy()
    f["category"] = categorise(f, tags)
    f = f[f.category.notna()]
    labels = {v: lab for vals in tags.values() for v, lab in vals.items()}
    pts = f.geometry.to_crs(etl["crs"]).representative_point()
    alt = f.reindex(columns=ALT_NAME_TAGS).apply(
        lambda r: "; ".join(sorted({str(v) for v in r if isinstance(v, str) and v})), axis=1
    )
    out = gpd.GeoDataFrame({"name": f["name"].str.strip(), "category": f.category.to_numpy(),
                            "alt_names": alt.to_numpy()},
                           geometry=pts.to_numpy(), crs=etl["crs"])  # fmt: skip
    out["x"], out["y"] = out.geometry.x, out.geometry.y
    stops = out.category.isin(STOP_CATEGORIES)
    # ZTP names each platform "Rondo Mogilskie 01", "... 02": one entry per stop
    out.loc[stops, "name"] = out.loc[stops, "name"].str.replace(r"\s+\d{2}$", "", regex=True)
    out = out.sort_values(["name", "category", "x", "y"]).reset_index(drop=True)
    stops = out.category.isin(STOP_CATEGORIES)
    # "Nowa Huta" is tagged both suburb and quarter: one entry per place name
    places = out[out.category.isin(PLACE_CATEGORIES)].drop_duplicates("name")
    other = out[~stops & ~out.category.isin(PLACE_CATEGORIES)]
    out = pd.concat([merge_close(other, SAME_PLACE_M), places,
                     merge_close(out[stops], cfg["merge_stops_m"])])  # fmt: skip
    ll = out.geometry.to_crs("EPSG:4326")
    out["lon"], out["lat"] = ll.x.round(6), ll.y.round(6)
    out["category_pl"] = out.category.map(lambda c: labels[c][0])
    out["category_en"] = out.category.map(lambda c: labels[c][1])
    # search-only synonyms of the category (third and later items in the config)
    out["category_terms"] = out.category.map(lambda c: " ".join(labels[c][2:]))
    return out.drop(columns="geometry").reset_index(drop=True)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    assert CONFIG.exists()
    poi = build(a.refresh)
    pd.DataFrame(poi).to_parquet(OSM_DIR / "poi.parquet", index=False)
    counts = poi.category.value_counts()
    log.info("%d places: %s", len(poi), ", ".join(f"{k} {v}" for k, v in counts.head(12).items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
