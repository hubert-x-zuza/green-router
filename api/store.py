"""In-memory data loaded once at API start: routing networks, geocoder, air index, planner."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import geopandas as gpd
import igraph as ig
import numpy as np
import pandas as pd
import shapely
import yaml
from pyproj import Transformer
from scipy.spatial import cKDTree

from etl import air as air_mod
from etl.common import CONFIG, PROCESSED, RAW, city_boundary
from etl.geocoder import Geocoder

log = logging.getLogger("api.store")
TO_2178 = Transformer.from_crs("EPSG:4326", "EPSG:2178", always_xy=True)
TO_4326 = Transformer.from_crs("EPSG:2178", "EPSG:4326", always_xy=True)


def load_cfg(name: str) -> dict[str, Any]:
    return yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))


@dataclass
class Network:
    mode: str
    graph: ig.Graph
    length: np.ndarray
    penalties: dict[
        str, np.ndarray
    ]  # static penalties: noise, noise_night, traffic, green, fountain
    raw: pd.DataFrame  # raw exposure values for metrics
    names: np.ndarray
    coords: list[np.ndarray]  # per edge lon/lat vertices
    node_xy: np.ndarray
    node_tree: cKDTree


def load_network(mode: str, path: Path) -> Network:
    t0 = time.time()
    net = gpd.read_parquet(path)
    n_nodes = int(max(net.u.max(), net.v.max())) + 1
    g = ig.Graph(n=n_nodes, edges=np.column_stack([net.u, net.v]).tolist(), directed=True)
    nodes = pd.read_parquet(PROCESSED / f"nodes_{mode}.parquet").sort_values("node_id")
    xy = nodes[["x", "y"]].to_numpy()
    pts, idx = shapely.get_coordinates(net.geometry.to_numpy(), return_index=True)
    lon, lat = TO_4326.transform(pts[:, 0], pts[:, 1])
    ll = np.round(np.column_stack([lon, lat]), 6)
    splits = np.flatnonzero(np.diff(idx)) + 1
    coords = np.split(ll, splits)
    pen = {
        "noise": net.p_noise.to_numpy(),
        "noise_night": net.p_noise_night.to_numpy(),
        "traffic": net.p_traffic.to_numpy(),
        "green": net.p_green.to_numpy(),
        "fountain": net.p_fountain.to_numpy(),
        # bike: ZTP cycle roads/lanes; walk: shared foot-and-cycle paths (config/etl.yml)
        "cycleway": net.p_cycleway.to_numpy(),
    }
    raw = net[["noise_ldwn_mean", "noise_ln_mean", "green_score", "traffic_prox",
               "fountain_dist_m", "data_coverage", "highway", "cycle_separated",
               "cycle_on_street"]].reset_index(drop=True)  # fmt: skip
    log.info("%s network: %d nodes, %d edges in %.1f s", mode, n_nodes, len(net), time.time() - t0)
    return Network(mode, g, net.length_m.to_numpy(), pen, raw, net.name.to_numpy(), coords, xy,
                   cKDTree(xy))  # fmt: skip


@dataclass
class AirCache:
    db_path: Path
    cfg: dict[str, Any]
    ttl_s: float = 300
    _value: dict[str, Any] | None = None
    _at: float = 0.0

    def get(self) -> dict[str, Any]:
        if self._value is None or time.time() - self._at > self.ttl_s:
            if not self.db_path.exists():
                self._value = {"available": False}
            else:
                con = sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
                try:
                    self._value = air_mod.city_level(con, self.cfg, datetime.now(timezone.utc))
                finally:
                    con.close()
            self._at = time.time()
        return self._value


@dataclass
class Store:
    networks: dict[str, Network]
    profiles: dict[str, Any]
    air_cfg: dict[str, Any]
    air: AirCache
    geocoder: Geocoder | None
    coverage_area: shapely.Geometry
    city: shapely.Geometry
    fountains_xy: np.ndarray
    fountain_tree: cKDTree | None
    manifest: dict[str, Any]
    overlays: dict[str, Any]
    planner: dict[str, Any] = field(default_factory=dict)
    snap_max_m: float = 300.0
    cycleways: dict[str, Any] | None = None
    poi_tree: cKDTree | None = None


def load_store(processed: Path = PROCESSED) -> Store:
    etl_cfg = load_cfg("etl.yml")
    profiles = load_cfg("profiles.yml")
    air_cfg = load_cfg("air_stations.yml")
    nets = {}
    for mode in etl_cfg["graph"]["modes"]:
        p = processed / f"network_{mode}.parquet"
        if p.exists():
            nets[mode] = load_network(mode, p)
    city = city_boundary()
    fpath = RAW / "fountains_outdoor" / "Pitniki_zewnetrzne.geojson"
    fxy = np.empty((0, 2))
    if fpath.exists():
        f = gpd.read_file(fpath)
        fxy = shapely.get_coordinates(f.geometry.to_numpy())
    geo_path = processed / "geocoder.sqlite"
    overlays_path = processed / "overlays" / "overlays.json"
    planner = {}
    for name in ("planner_hotspots", "planner_districts"):
        p = processed / f"{name}.json"
        if p.exists():
            planner[name] = json.loads(p.read_text(encoding="utf-8"))
    return Store(
        networks=nets,
        profiles=profiles,
        air_cfg=air_cfg,
        air=AirCache(processed / "air_history.sqlite", air_cfg),
        geocoder=Geocoder(geo_path) if geo_path.exists() else None,
        coverage_area=city.buffer(etl_cfg["graph"]["boundary_buffer_m"]),
        city=city,
        fountains_xy=fxy,
        fountain_tree=cKDTree(fxy) if len(fxy) else None,
        manifest=yaml.safe_load((Path(CONFIG).parent / "data" / "manifest.yml").read_text("utf-8")),
        overlays=json.loads(overlays_path.read_text("utf-8")) if overlays_path.exists() else {},
        planner=planner,
        snap_max_m=etl_cfg["coverage"]["snap_max_m"],
        cycleways=load_cycleways(etl_cfg),
        poi_tree=load_poi_tree(),
    )


def load_poi_tree() -> cKDTree | None:
    """OSM venues (not stops or areas): Google snaps waypoints to these."""
    path = RAW / "osm" / "poi.parquet"
    if not path.exists():
        return None
    p = pd.read_parquet(path)
    skip = {"bus_stop", "tram_stop", "halt", "suburb", "quarter", "neighbourhood", "village",
            "hamlet", "square"}  # fmt: skip
    p = p[~p.category.isin(skip)]
    return cKDTree(p[["x", "y"]].to_numpy()) if len(p) else None


def load_cycleways(etl_cfg: dict[str, Any]) -> dict[str, Any] | None:
    path = RAW / "cycle_infra" / "cycle_infra.geojson"
    if not path.exists():
        return None
    g = gpd.read_file(path).set_crs("EPSG:2178", allow_override=True)
    ci = etl_cfg["cycle_infra"]["modes"]["bike"]
    on_street = np.where(g.rodzaj.isin(ci["on_street"]), "on_street", "other")
    g["kind"] = np.where(g.rodzaj.isin(ci["separated"]), "separated", on_street)
    g["geometry"] = g.geometry.simplify(2.0)
    g = g[["rodzaj", "kind", "geometry"]].to_crs("EPSG:4326")
    return json.loads(g.to_json(drop_id=True, to_wgs84=False))
