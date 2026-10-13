"""Build the walk and bike graphs from OpenStreetMap (plan 5.1).

Run:  python -m etl.graph            (uses the cached OSM download if present)
      python -m etl.graph --refresh  (download OSM again)

Area: city boundary (MSIP) + `graph.boundary_buffer_m`. Source: Overpass API through osmnx, raw
graphs cached as data/raw/osm/<mode>.graphml (the download date is recorded in source.json).
Output, all in EPSG:2178:
  data/processed/nodes_<mode>.parquet   node_id, osmid, x, y, lon, lat
  data/processed/edges_<mode>.parquet   edge_id, u, v, osmid, highway, name, surface, lit,
                                        length_m, contraflow, geometry (GeoParquet)
  data/processed/roads.parquet          OSM roads used for the traffic-proximity proxy
Edges are directed. Walk edges exist in both directions (osmnx default). Bike edges respect one-way
streets, plus a reverse edge where OSM allows contraflow cycling (`graph.bike_contraflow`).
Only the largest strongly connected component is kept, so every node can reach every other.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime, timezone

import geopandas as gpd
import networkx as nx
import numpy as np
import osmnx as ox
import pandas as pd
from shapely import reverse

from etl.common import PROCESSED, RAW, city_boundary, etl_config, write_json

log = logging.getLogger("etl.graph")
OSM_DIR = RAW / "osm"


def area_wgs84(buffer_m: float):
    poly = city_boundary().buffer(buffer_m)
    return gpd.GeoSeries([poly], crs="EPSG:2178").to_crs("EPSG:4326").iloc[0]


def download(mode: str, polygon, refresh: bool) -> nx.MultiDiGraph:
    path = OSM_DIR / f"{mode}.graphml"
    if path.exists() and not refresh:
        return ox.load_graphml(path)
    log.info("downloading OSM %s graph (Overpass)...", mode)
    g = ox.graph_from_polygon(polygon, network_type=mode, simplify=True, retain_all=True)
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    ox.save_graphml(g, path)
    return g


def _first(v):
    if isinstance(v, list):
        return "|".join(str(x) for x in v)
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)


def contraflow_mask(edges: pd.DataFrame, rules: dict[str, list[str]]) -> np.ndarray:
    """One-way edges on which OSM allows cycling against the flow."""
    oneway = edges.get("oneway", pd.Series(False, index=edges.index)).fillna(False).astype(bool)
    allowed = np.zeros(len(edges), dtype=bool)
    for tag, values in rules.items():
        if tag in edges:
            col = edges[tag].map(lambda v: _first(v) or "")
            ok = set(values)
            allowed |= col.map(lambda s, ok=ok: bool(ok & set(s.split("|")))).to_numpy()
    return oneway.to_numpy() & allowed


def to_tables(g: nx.MultiDiGraph, mode: str, cfg: dict) -> tuple[pd.DataFrame, gpd.GeoDataFrame]:
    g = ox.truncate.largest_component(g, strongly=True)
    nodes, edges = ox.graph_to_gdfs(g)
    nodes = nodes.to_crs(cfg["crs"])
    edges = edges.to_crs(cfg["crs"]).reset_index()
    ll = nodes.geometry.to_crs("EPSG:4326")
    node_ids = {osmid: i for i, osmid in enumerate(nodes.index)}
    nodes_df = pd.DataFrame(
        {
            "node_id": np.arange(len(nodes), dtype=np.int64),
            "osmid": nodes.index.to_numpy(dtype=np.int64),
            "x": nodes.geometry.x.to_numpy(),
            "y": nodes.geometry.y.to_numpy(),
            "lon": ll.x.to_numpy(),
            "lat": ll.y.to_numpy(),
        }
    )
    out = gpd.GeoDataFrame(
        {
            "u": edges["u"].map(node_ids).to_numpy(dtype=np.int64),
            "v": edges["v"].map(node_ids).to_numpy(dtype=np.int64),
            "osmid": edges["osmid"].map(_first),
            "highway": edges["highway"].map(_first),
            "name": edges.get("name", pd.Series(None, index=edges.index)).map(_first),
            "surface": edges.get("surface", pd.Series(None, index=edges.index)).map(_first),
            "lit": edges.get("lit", pd.Series(None, index=edges.index)).map(_first),
            "contraflow": False,
        },
        geometry=edges.geometry.to_numpy(),
        crs=cfg["crs"],
    )
    if mode == "bike":
        cf = contraflow_mask(edges, cfg["graph"]["bike_contraflow"])
        rev = out[cf].copy()
        rev[["u", "v"]] = rev[["v", "u"]].to_numpy()
        rev["geometry"] = reverse(rev.geometry.to_numpy())
        rev["contraflow"] = True
        # skip reverse edges that already exist
        have = set(zip(out.u, out.v, strict=True))
        rev = rev[[(a, b) not in have for a, b in zip(rev.u, rev.v, strict=True)]]
        out = pd.concat([out, rev], ignore_index=True)
        log.info("bike: %d contraflow edges added", len(rev))
    out["length_m"] = out.geometry.length
    out.insert(0, "edge_id", np.arange(len(out), dtype=np.int64))
    return nodes_df, out


def roads(polygon, refresh: bool, cfg: dict) -> gpd.GeoDataFrame:
    path = OSM_DIR / "roads.parquet"
    if path.exists() and not refresh:
        return gpd.read_parquet(path)
    classes = list(cfg["traffic"]["class_weights"])
    log.info("downloading OSM roads for the traffic proxy (Overpass)...")
    f = ox.features_from_polygon(polygon, tags={"highway": classes})
    f = f[f.geom_type.isin(["LineString", "MultiLineString"])].reset_index()
    f = f[["highway", "geometry"]].copy()
    f["highway"] = f["highway"].map(_first)
    f = f[f["highway"].isin(classes)].to_crs(cfg["crs"])
    OSM_DIR.mkdir(parents=True, exist_ok=True)
    f.to_parquet(path)
    return f


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--refresh", action="store_true", help="download OSM again")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = etl_config()
    ox.settings.useful_tags_way = cfg["graph"]["useful_tags_way"]
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(OSM_DIR / "cache")
    ox.settings.requests_timeout = 600
    polygon = area_wgs84(cfg["graph"]["boundary_buffer_m"])
    downloaded = not (OSM_DIR / "walk.graphml").exists() or a.refresh
    PROCESSED.mkdir(parents=True, exist_ok=True)
    for mode in cfg["graph"]["modes"]:
        g = download(mode, polygon, a.refresh)
        nodes, edges = to_tables(g, mode, cfg)
        nodes.to_parquet(PROCESSED / f"nodes_{mode}.parquet", index=False)
        edges.to_parquet(PROCESSED / f"edges_{mode}.parquet", index=False)
        km = edges.length_m.sum() / 1000
        log.info(
            "%s: %d nodes, %d directed edges, %.0f km of edges", mode, len(nodes), len(edges), km
        )
    r = roads(polygon, a.refresh, cfg)
    r.to_parquet(PROCESSED / "roads.parquet")
    log.info("roads: %d lines", len(r))
    if downloaded:
        write_json(
            OSM_DIR / "source.json",
            {
                "source": "OpenStreetMap via Overpass API (osmnx)",
                "area": "MSIP city boundary + buffer",
                "obtained_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "licence": "ODbL 1.0, © OpenStreetMap contributors",
            },
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
