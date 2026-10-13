"""Waypoints for the Google Maps link (decision D-030).

Google Maps takes only origin, destination and up to 3 waypoints (mobile browsers) and routes
between them itself, turning each waypoint into the nearest address or venue. So:
1. split our route into *detours*: runs of nodes farther than `min_deviation_m` from the fastest
   route (Google's own choice is close to our fastest one);
2. keep the most important detours (length x mean deviation), at most `max_waypoints`, one
   waypoint each. Spare waypoints are NOT used: measured against Google on 9 routes, giving long
   detours 2-3 anchors made the routes worse (every waypoint is snapped to an address and adds a
   spur), see D-030;
3. in each detour pick one node, preferring named streets, nodes away from venues (OSM places
   within `poi_radius_m`) and the middle of the detour.
No detour means no waypoint: Google's route is then already ours.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import shapely
from scipy.spatial import cKDTree

from api.store import TO_4326, Network


@dataclass
class Detour:
    nodes: np.ndarray  # indices into the route node arrays
    length: float
    weight: float


def route_nodes(net: Network, edges: list[int]) -> np.ndarray:
    """Node ids along the route: the source of each edge plus the final target."""
    es = net.graph.es
    ids = [es[int(e)].source for e in edges]
    if edges:
        ids.append(es[int(edges[-1])].target)
    return np.asarray(ids, dtype=np.int64)


def detours(dev: np.ndarray, along: np.ndarray, cfg: dict[str, Any]) -> list[Detour]:
    out: list[Detour] = []
    far = dev >= cfg["min_deviation_m"]
    i, n = 0, len(dev)
    while i < n:
        if not far[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and far[j + 1]:
            j += 1
        idx = np.arange(i, j + 1)
        length = float(along[min(j + 1, n - 1)] - along[max(i - 1, 0)])
        if length >= cfg["min_detour_m"]:
            out.append(Detour(idx, length, length * float(dev[idx].mean())))
        i = j + 1
    return out


def node_factor(net: Network, edges: list[int], cfg: dict[str, Any]) -> np.ndarray:
    """Per route node: how well Google will keep a waypoint there (named street best)."""
    streets = set(cfg["street_classes"])
    f = cfg["class_factor"]
    per_edge = []
    for e in edges:
        name = net.names[e]
        hw = str(net.raw.highway.iat[e])
        named = isinstance(name, str) and bool(name)
        is_street = any(h in streets for h in hw.split("|"))
        per_edge.append(f["street_named"] if named and is_street
                        else f["path_named"] if named else f["unnamed"])  # fmt: skip
    per_edge = np.asarray(per_edge or [f["unnamed"]])
    # a node takes the better of its two adjacent edges
    left = np.concatenate([[per_edge[0]], per_edge])
    right = np.concatenate([per_edge, [per_edge[-1]]])
    return np.maximum(left, right)


def waypoints(
    net: Network,
    edges: list[int],
    fastest: list[int],
    poi_tree: cKDTree | None,
    cfg: dict[str, Any],
) -> list[list[float]]:
    """Up to `max_waypoints` [lon, lat] points, in route order."""
    if not edges or list(edges) == list(fastest):
        return []
    nodes = route_nodes(net, edges)
    xy = net.node_xy[nodes]
    seg = np.hypot(*np.diff(xy, axis=0).T)
    along = np.concatenate([[0.0], np.cumsum(seg)])
    fast_xy = net.node_xy[route_nodes(net, fastest)]
    line = shapely.LineString(fast_xy) if len(fast_xy) > 1 else shapely.Point(fast_xy[0])
    dev = shapely.distance(shapely.points(xy), line)
    dets = sorted(detours(dev, along, cfg), key=lambda d: -d.weight)[: cfg["max_waypoints"]]
    if not dets:
        return []
    factor = node_factor(net, edges, cfg)
    if poi_tree is not None:
        near = np.array([len(h) > 0 for h in poi_tree.query_ball_point(xy, cfg["poi_radius_m"])])
        factor = factor * np.where(near, cfg["poi_factor"], 1.0)
    picks = []
    for d in dets:
        pos = np.linspace(0, 1, len(d.nodes)) if len(d.nodes) > 1 else np.array([0.5])
        middle = 0.5 + 0.5 * (1 - np.abs(pos - 0.5) * 2)  # 1 in the middle, 0.5 at the ends
        score = dev[d.nodes] * factor[d.nodes] * middle
        picks.append(int(d.nodes[int(np.argmax(score))]))
    picks.sort()
    lon, lat = TO_4326.transform(xy[picks, 0], xy[picks, 1])
    return [[round(float(a), 6), round(float(b), 6)] for a, b in zip(lon, lat, strict=True)]
