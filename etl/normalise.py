"""Penalties p_k in [0, 1] per edge (plan 5.2) and the routing table the API loads.

Run:  python -m etl.normalise   (after etl.enrich)

Penalties (thresholds in config/etl.yml):
  p_noise        LDWN mean, linear zero_db -> 0 ... one_db -> 1
  p_noise_night  LN mean, same with the LN thresholds
  p_green        1 - green_score
  p_fountain     0 within near_m of a fountain, 1 beyond far_m, linear in between
  p_traffic      traffic_prox (already in [0, 1]); the API derives the live air penalty from it
Edges without data (outside the city) get `coverage.neutral_penalty` for noise and green; the raw
value stays NaN so the UI can say "no data" instead of showing a made-up number.
Output: data/processed/network_<mode>.parquet (GeoParquet, EPSG:2178).
"""

from __future__ import annotations

import logging
import sys

import geopandas as gpd
import numpy as np
import pandas as pd

from etl.common import PROCESSED, etl_config

log = logging.getLogger("etl.normalise")
PENALTIES = ["p_noise", "p_noise_night", "p_green", "p_fountain", "p_traffic"]


def linear(x: np.ndarray, zero: float, one: float) -> np.ndarray:
    return np.clip((x - zero) / (one - zero), 0.0, 1.0)


def penalties(exp: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    neutral = cfg["coverage"]["neutral_penalty"]
    n = cfg["noise"]
    out = pd.DataFrame(index=exp.index)
    out["p_noise"] = linear(exp.noise_ldwn_mean, n["LDWN"]["zero_db"], n["LDWN"]["one_db"])
    out["p_noise_night"] = linear(exp.noise_ln_mean, n["LN"]["zero_db"], n["LN"]["one_db"])
    out["p_green"] = 1.0 - np.clip(exp.green_score, 0, 1)
    f = cfg["fountains"]
    out["p_fountain"] = linear(exp.fountain_dist_m, f["near_m"], f["far_m"])
    out["p_traffic"] = np.clip(exp.traffic_prox.fillna(0.0), 0, 1)
    for c in ("p_noise", "p_noise_night", "p_green", "p_fountain"):
        out[c] = out[c].where(exp.data_coverage & out[c].notna(), neutral)
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = etl_config()
    for mode in cfg["graph"]["modes"]:
        edges = gpd.read_parquet(PROCESSED / f"edges_{mode}.parquet")
        exp = pd.read_parquet(PROCESSED / f"exposure_{mode}.parquet")
        assert (edges.edge_id.to_numpy() == exp.edge_id.to_numpy()).all()
        net = edges.join(exp.drop(columns="edge_id")).join(penalties(exp, cfg))
        bad = net[PENALTIES].isna().sum()
        if bad.any():
            raise ValueError(f"{mode}: NaN penalties {bad[bad > 0].to_dict()}")
        net.to_parquet(PROCESSED / f"network_{mode}.parquet", index=False)
        log.info("%s: %d edges, %.1f %% without data coverage", mode, len(net),
                 100 * (~net.data_coverage).mean())  # fmt: skip
    return 0


if __name__ == "__main__":
    sys.exit(main())
