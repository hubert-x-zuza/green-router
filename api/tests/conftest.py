"""Fixtures: a small synthetic network (no data files needed) and, when present, the real store."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
import shapely
from scipy.spatial import cKDTree

from api.store import AirCache, Network, Store, load_cfg
from etl.common import PROCESSED


def grid_network(n: int = 6, seed: int = 0, spacing: float = 100.0) -> Network:
    """n x n grid of nodes in EPSG:2178 around Kraków, both directions per street, random
    lengths (100-160 m) and random penalties."""
    import igraph as ig

    rng = np.random.default_rng(seed)
    x0, y0 = 7423000.0, 5546000.0
    xy = np.array([(x0 + i * spacing, y0 + j * spacing) for j in range(n) for i in range(n)])
    pairs = []
    for j in range(n):
        for i in range(n):
            k = j * n + i
            if i + 1 < n:
                pairs.append((k, k + 1))
            if j + 1 < n:
                pairs.append((k, k + n))
    edges = pairs + [(b, a) for a, b in pairs]
    m = len(pairs)
    base_len = spacing * (1 + 0.6 * rng.random(m))
    length = np.concatenate([base_len, base_len])
    keys = ("noise", "noise_night", "traffic", "green", "fountain", "cycleway")
    pen = {k: np.concatenate([v, v]) for k, v in {k: rng.random(m) for k in keys}.items()}
    g = ig.Graph(n=n * n, edges=edges, directed=True)
    coords = [
        np.array([[19.9 + xy[a][0] * 1e-6, 50.0], [19.9 + xy[b][0] * 1e-6, 50.0]]) for a, b in edges
    ]
    raw = pd.DataFrame(
        {
            "noise_ldwn_mean": 45 + 30 * pen["noise"],
            "noise_ln_mean": 40 + 25 * pen["noise_night"],
            "green_score": 1 - pen["green"],
            "traffic_prox": pen["traffic"],
            "fountain_dist_m": 500 * pen["fountain"],
            "data_coverage": True,
            "highway": "footway",
            "cycle_separated": 1 - pen["cycleway"],
            "cycle_on_street": 0.0,
        }
    )
    return Network(
        "walk", g, length, pen, raw, np.array([None] * len(edges)), coords, xy, cKDTree(xy)
    )


@pytest.fixture
def net() -> Network:
    return grid_network()


@pytest.fixture
def fake_store(net: Network) -> Store:
    xy = net.node_xy
    area = shapely.box(
        xy[:, 0].min() - 50, xy[:, 1].min() - 50, xy[:, 0].max() + 50, xy[:, 1].max() + 50
    )
    air_cfg = load_cfg("air_stations.yml")
    store = Store(
        networks={"walk": net},
        profiles=load_cfg("profiles.yml"),
        air_cfg=air_cfg,
        air=AirCache(PROCESSED / "does-not-exist.sqlite", air_cfg),
        geocoder=None,
        coverage_area=area,
        city=area,
        fountains_xy=np.empty((0, 2)),
        fountain_tree=None,
        manifest={"datasets": {"x": {"title": "Test", "provider": "P", "citation_pl": "C"}}},
        overlays={},
        planner={},
    )
    return store


@pytest.fixture(scope="session")
def real_store():
    if not (PROCESSED / "network_walk.parquet").exists():
        pytest.skip("processed data not built (run make data)")
    from api.store import load_store

    return load_store()
