"""Per-edge exposure values (plan 5.2): noise, greenery, fountains, traffic proximity.

Run:  python -m etl.enrich     (after etl.graph and the noise grids)

Method. Every layer becomes a 10 m grid in EPSG:2178 (`etl.layers` builds them):
  noise    LDWN / LN grids from etl/noise_to_grid.py (dB; nodata outside the city)
  green    share of each "Mapa zieleni" class within `green.buffer_m` of the cell (disc filter),
           green_score = sum(class weight * share), clamped to [0, 1]
  fountain distance (m) to the nearest outdoor fountain
  traffic  max over road classes of weight * max(0, 1 - distance / reach)
Each edge is sampled every `grid.sample_spacing_m` (at least 2 points, at segment midpoints so
crossings at the ends do not dominate). Per edge: mean (and max for noise) over the samples.
Points outside the city have no noise/green data: `coverage` is the share of samples inside, and
`data_coverage = coverage >= 0.5`. Missing values stay NaN here; normalise.py decides what to do.
Output: data/processed/exposure_<mode>.parquet (edge_id + raw values).
"""

from __future__ import annotations

import logging
import sys

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from etl.common import PROCESSED, etl_config
from etl.layers import load_layers

log = logging.getLogger("etl.enrich")


def sample_points(geoms: np.ndarray, lengths: np.ndarray, spacing: float):
    """Return (edge_index, x, y) of sample points: n = max(2, ceil(L / spacing)) per edge, placed
    at the midpoints of n equal parts."""
    n = np.maximum(2, np.ceil(lengths / spacing)).astype(np.int64)
    idx = np.repeat(np.arange(len(geoms)), n)
    starts = np.repeat(np.cumsum(n) - n, n)
    k = np.arange(len(idx)) - starts
    frac = (k + 0.5) / n[idx]
    pts = shapely.line_interpolate_point(geoms[idx], frac, normalized=True)
    return idx, shapely.get_x(pts), shapely.get_y(pts)


def reduce_mean(idx: np.ndarray, values: np.ndarray, n_edges: int) -> np.ndarray:
    """Mean per edge over finite values; NaN where an edge has none."""
    ok = np.isfinite(values)
    s = np.bincount(idx[ok], weights=values[ok], minlength=n_edges)
    c = np.bincount(idx[ok], minlength=n_edges)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where(c > 0, s / c, np.nan)


def reduce_max(idx: np.ndarray, values: np.ndarray, n_edges: int) -> np.ndarray:
    out = np.full(n_edges, -np.inf)
    ok = np.isfinite(values)
    np.maximum.at(out, idx[ok], values[ok])
    return np.where(np.isfinite(out), out, np.nan)


def reduce_min(idx: np.ndarray, values: np.ndarray, n_edges: int) -> np.ndarray:
    return -reduce_max(idx, -values, n_edges)


def enrich(edges: gpd.GeoDataFrame, layers: dict, cfg: dict) -> pd.DataFrame:
    grid = layers["grid"]
    geoms = edges.geometry.to_numpy()
    idx, x, y = sample_points(geoms, edges.length_m.to_numpy(), cfg["grid"]["sample_spacing_m"])
    n = len(edges)
    inside = grid.sample(layers["inside"], x, y, nodata=0) > 0
    out = pd.DataFrame({"edge_id": edges.edge_id.to_numpy()})
    for ind in cfg["noise"]["indicators"]:
        g, arr = layers[f"noise_{ind}"]
        v = g.sample(arr, x, y, nodata=np.nan)
        v[(v < 0) | ~inside] = np.nan  # -9999 nodata outside the noise model
        out[f"noise_{ind.lower()}_mean"] = reduce_mean(idx, v, n)
        out[f"noise_{ind.lower()}_max"] = reduce_max(idx, v, n)
    for name in ("green_score", "green_tall", "green_low", "green_sports"):
        v = grid.sample(layers[name], x, y, nodata=np.nan)
        v[~inside] = np.nan
        out[name] = reduce_mean(idx, v, n)
    out["fountain_dist_m"] = reduce_min(idx, grid.sample(layers["fountain_dist"], x, y, np.nan), n)
    out["traffic_prox"] = reduce_mean(idx, grid.sample(layers["traffic"], x, y, np.nan), n)
    out["coverage"] = reduce_mean(idx, inside.astype(float), n)
    out["data_coverage"] = out["coverage"] >= 0.5
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = etl_config()
    layers = load_layers()
    for mode in cfg["graph"]["modes"]:
        edges = gpd.read_parquet(PROCESSED / f"edges_{mode}.parquet")
        exp = enrich(edges, layers, cfg)
        exp.to_parquet(PROCESSED / f"exposure_{mode}.parquet", index=False)
        log.info(
            "%s: %d edges, %.1f %% covered, mean LDWN %.1f dB, mean green %.2f",
            mode, len(exp), 100 * exp.data_coverage.mean(),
            exp.noise_ldwn_mean.mean(), exp.green_score.mean(),
        )  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
