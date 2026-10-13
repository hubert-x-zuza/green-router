"""Route search (plan 5.4): fastest, healthiest within the detour limit, balanced; with metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from api.costs import air_penalty, edge_cost
from api.store import Network

BISECT_STEPS = 8


class RouteError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class Path:
    edges: list[int]
    weights: dict[str, float]
    scale: float  # 1.0 unless the detour guard scaled the weights down


def penalties_for(net: Network, level: float, a: float, night: bool) -> dict[str, np.ndarray]:
    return {
        "noise": net.penalties["noise_night" if night else "noise"],
        "air": air_penalty(level, net.penalties["traffic"], a),
        "traffic": net.penalties["traffic"],
        "green": net.penalties["green"],
        "fountain": net.penalties["fountain"],
    }


def shortest(net: Network, src: int, dst: int, cost: np.ndarray) -> list[int]:
    epath = net.graph.get_shortest_path(src, to=dst, weights=cost, output="epath")
    if src != dst and not epath:
        raise RouteError("no_route", "no route between these points")
    return list(epath)


def travel_s(net: Network, edges: list[int], speed: float) -> float:
    return float(net.length[edges].sum() / speed)


def guarded(
    net: Network, src: int, dst: int, pen: dict, weights: dict, speed: float, limit_s: float
) -> Path:
    """Path for `weights`; if it takes longer than `limit_s`, scale the weights down (bisection)
    to the largest scale that keeps the route within the limit."""
    full = shortest(net, src, dst, edge_cost(net.length, speed, pen, weights))
    if travel_s(net, full, speed) <= limit_s:
        return Path(full, weights, 1.0)
    lo, hi, best = 0.0, 1.0, None
    for _ in range(BISECT_STEPS):
        mid = (lo + hi) / 2
        w = {k: v * mid for k, v in weights.items()}
        p = shortest(net, src, dst, edge_cost(net.length, speed, pen, w))
        if travel_s(net, p, speed) <= limit_s:
            lo, best = mid, Path(p, w, mid)
        else:
            hi = mid
    if best is None:
        zero = {k: 0.0 for k in weights}
        best = Path(shortest(net, src, dst, edge_cost(net.length, speed, pen, zero)), zero, 0.0)
    return best


def _wmean(values: np.ndarray, w: np.ndarray) -> float | None:
    ok = np.isfinite(values)
    if not ok.any() or w[ok].sum() == 0:
        return None
    return float((values[ok] * w[ok]).sum() / w[ok].sum())


def metrics(
    net: Network, edges: list[int], speed: float, pen: dict, fountain_xy, fountain_tree, near_m
) -> dict[str, Any]:
    e = np.asarray(edges, dtype=np.int64)
    L = net.length[e]
    raw = net.raw.iloc[e]
    noise = raw.noise_ldwn_mean.to_numpy(dtype=float)
    covered = raw.data_coverage.to_numpy(dtype=bool)
    out: dict[str, Any] = {
        "distance_m": round(float(L.sum()), 0),
        "duration_min": round(float(L.sum() / speed / 60), 1),
        "noise_mean_db": _wmean(noise, L),
        "noise_night_mean_db": _wmean(raw.noise_ln_mean.to_numpy(dtype=float), L),
        "share_loud": _wmean(np.where(np.isfinite(noise), (noise >= 65).astype(float), np.nan), L),
        "exposure_noise": _wmean(pen["noise"][e], L),
        "green_mean": _wmean(raw.green_score.to_numpy(dtype=float), L),
        "traffic_mean": _wmean(raw.traffic_prox.to_numpy(dtype=float), L),
        "air_index": _wmean(pen["air"][e], L),
        "coverage": float(L[covered].sum() / L.sum()) if L.sum() else 1.0,
        "fountains_near": 0,
    }
    if fountain_tree is not None and len(e):
        node_xy = net.node_xy
        verts = np.vstack([node_xy[net.graph.es[int(i)].source] for i in e] +
                          [node_xy[net.graph.es[int(e[-1])].target]])  # fmt: skip
        hits = fountain_tree.query_ball_point(verts, r=near_m)
        out["fountains_near"] = len({i for h in hits for i in h})
    # exposure index 0-100: length-weighted mean of the balanced combination of penalties
    for k in ("noise_mean_db", "noise_night_mean_db", "share_loud", "exposure_noise",
              "green_mean", "traffic_mean", "air_index"):  # fmt: skip
        if out[k] is not None:
            out[k] = round(out[k], 3 if k not in ("noise_mean_db", "noise_night_mean_db") else 1)
    return out


def exposure_index(net: Network, edges: list[int], pen: dict, weights: dict) -> float | None:
    """0 = no exposure, 100 = worst on every term (weighted like `weights`)."""
    tot = sum(weights.values())
    if not tot or not edges:
        return None
    e = np.asarray(edges, dtype=np.int64)
    comb = sum(w * pen[k][e] for k, w in weights.items()) / tot
    return round(100 * float((comb * net.length[e]).sum() / net.length[e].sum()), 1)


def tradeoff(base: dict, alt: dict) -> dict[str, Any]:
    """Differences of `alt` against the fastest route `base` (for the trade-off sentence)."""

    def pct(a, b):
        if a is None or b is None or b == 0:
            return None
        return round(100 * (a - b) / b, 0)

    return {
        "extra_min": round(alt["duration_min"] - base["duration_min"], 1),
        "noise_pct": pct(alt.get("exposure_noise"), base.get("exposure_noise")),
        "exposure_pct": pct(alt["exposure_index"], base["exposure_index"]),
        "green_pct": pct(alt["green_mean"], base["green_mean"]),
        "air_pct": pct(alt["air_index"], base["air_index"]),
    }


def tradeoff_text(t: dict, lang: str) -> str:
    parts = []
    m = t["extra_min"]
    parts.append(f"{m:+.0f} min" if abs(m) >= 0.5 else ("±0 min"))
    labels = {
        "pl": {"noise_pct": "hałasu", "exposure_pct": "ekspozycji", "green_pct": "zieleni"},
        "en": {"noise_pct": "noise", "exposure_pct": "exposure", "green_pct": "greenery"},
    }
    for k in ("exposure_pct", "noise_pct", "green_pct"):
        if t.get(k) is not None and abs(t[k]) >= 1:
            parts.append(f"{t[k]:+.0f} % {labels[lang][k]}")
    return ", ".join(parts)


# ---- request -> three routes ---------------------------------------------------------------


def snap(store, net: Network, lon: float, lat: float, which: str) -> int:
    from shapely import Point

    from api.store import TO_2178

    x, y = TO_2178.transform(lon, lat)
    if not store.coverage_area.contains(Point(x, y)):
        raise RouteError("outside_city", f"{which} is outside Kraków")
    d, i = net.node_tree.query([x, y])
    if d > store.snap_max_m:
        raise RouteError("far_from_network", f"{which} is {d:.0f} m from the nearest path")
    return int(i)


def features(net: Network, edges: list[int], pen: dict) -> dict[str, Any]:
    feats = []
    raw = net.raw
    for e in edges:
        noise = raw.noise_ldwn_mean.iat[e]
        green = raw.green_score.iat[e]
        feats.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": net.coords[e].tolist()},
                "properties": {
                    "noise_db": None if np.isnan(noise) else round(float(noise), 1),
                    "green": None if np.isnan(green) else round(float(green), 2),
                    "air": round(float(pen["air"][e]), 3),
                    "covered": bool(raw.data_coverage.iat[e]),
                    "name": net.names[e] if isinstance(net.names[e], str) else None,
                },
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def plan(store, req) -> dict[str, Any]:
    net = store.networks.get(req.mode)
    if net is None:
        raise RouteError("mode_unavailable", f"{req.mode} network is not built")
    src = snap(store, net, req.origin.lon, req.origin.lat, "origin")
    dst = snap(store, net, req.destination.lon, req.destination.lat, "destination")
    if src == dst:
        raise RouteError("same_point", "origin and destination are the same place")
    profiles = store.profiles["profiles"]
    speed = store.profiles["speeds_mps"][req.mode]
    air = store.air.get()
    level = air["level"] if air.get("available") and not air.get("stale") else 0.0
    warnings = []
    if not air.get("available") or air.get("stale"):
        warnings.append("air_unavailable")
    pen = penalties_for(net, level, store.air_cfg["index"]["air_a"], req.night)
    zero = {k: 0.0 for k in profiles["fastest"]}
    fastest = shortest(net, src, dst, edge_cost(net.length, speed, pen, zero))
    limit = travel_s(net, fastest, speed) * (1 + req.max_detour_pct / 100)
    chosen = req.weights.model_dump() if req.weights else profiles[req.profile]
    healthy_name = req.profile
    if not req.weights and req.profile in ("fastest", "balanced"):
        chosen, healthy_name = profiles["healthiest"], "healthiest"
    paths = {
        "fastest": ("fastest", Path(fastest, zero, 1.0)),
        "healthiest": (healthy_name, guarded(net, src, dst, pen, chosen, speed, limit)),
        "balanced": (
            "balanced",
            guarded(net, src, dst, pen, profiles["balanced"], speed, limit),
        ),
    }
    exp_w = profiles["balanced"]
    near = store.profiles.get("fountain_near_m", 100)
    out, seen = [], {}
    base = None
    for kind, (pname, p) in paths.items():
        m = metrics(net, p.edges, speed, pen, store.fountains_xy, store.fountain_tree, near)
        m["exposure_index"] = exposure_index(net, p.edges, pen, exp_w)
        if kind == "fastest":
            base = m
        key = tuple(p.edges)
        t = None
        if kind != "fastest":
            t = tradeoff(base, m)
            t["text"] = tradeoff_text(t, req.lang)
        out.append(
            {
                "kind": kind,
                "profile": pname,
                "weights_scale": round(p.scale, 3),
                "limited_by_detour": p.scale < 1.0,
                "metrics": m,
                "tradeoff": t,
                "same_as": seen.get(key),
                "geometry": features(net, p.edges, pen),
            }
        )
        seen.setdefault(key, kind)
    if any(r["metrics"]["coverage"] < 0.9 for r in out):
        warnings.append("partial_coverage")
    if (
        air.get("available")
        and air["pollutants"].get("PM10", {}).get("mean", 0) > store.profiles["smog_hint_pm10"]
    ):
        warnings.append("smog_hint")
    return {"mode": req.mode, "profile": req.profile, "air": _air_brief(air), "routes": out,
            "warnings": warnings}  # fmt: skip


def _air_brief(air: dict) -> dict:
    if not air.get("available"):
        return {"available": False}
    keys = ("available", "level", "band", "band_pl", "band_en", "data_ts_utc", "stale")
    return {k: air[k] for k in keys}
