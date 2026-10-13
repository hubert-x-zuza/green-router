"""Waypoint choice for the Google Maps link (synthetic network)."""

import numpy as np
from scipy.spatial import cKDTree

from api import google_link, routing
from api.costs import edge_cost
from api.store import load_cfg
from api.tests.conftest import grid_network

CFG = load_cfg("profiles.yml")["google_link"]


def test_detours_split_and_minimum_length():
    dev = np.array([0, 0, 50, 60, 0, 0, 45, 0], dtype=float)
    along = np.arange(8) * 100.0
    d = google_link.detours(dev, along, CFG)
    assert [list(x.nodes) for x in d] == [[2, 3], [6]]


def _routes(seed):
    net = grid_network(n=8, seed=seed, spacing=150)
    pen = routing.penalties_for(net, 0.0, 0.3, night=False)
    zero = {k: 0.0 for k in ("noise", "air", "traffic", "green", "fountain", "cycleway")}
    src, dst = 0, net.graph.vcount() - 1
    fast = routing.shortest(net, src, dst, edge_cost(net.length, 1.0, pen, zero))
    healthy = routing.shortest(
        net, src, dst, edge_cost(net.length, 1.0, pen, {**zero, "noise": 30.0, "green": 30.0})
    )
    return net, fast, healthy


def test_no_waypoints_when_route_is_the_fastest():
    net, fast, _ = _routes(1)
    assert google_link.waypoints(net, fast, fast, None, CFG) == []


def test_waypoints_lie_on_the_route_and_respect_the_limit():
    for seed in range(6):
        net, fast, healthy = _routes(seed)
        wps = google_link.waypoints(net, healthy, fast, None, CFG)
        assert len(wps) <= CFG["max_waypoints"]
        route_nodes = google_link.route_nodes(net, healthy)
        from api.store import TO_4326

        lon, lat = TO_4326.transform(*net.node_xy[route_nodes].T)
        on_route = {(round(a, 6), round(b, 6)) for a, b in zip(lon, lat, strict=True)}
        assert all((p[0], p[1]) in on_route for p in wps)


def test_venues_push_waypoints_away():
    net, fast, healthy = _routes(3)
    free = google_link.waypoints(net, healthy, fast, None, CFG)
    if not free:
        return
    from api.store import TO_2178

    x, y = TO_2178.transform(free[0][0], free[0][1])
    tree = cKDTree(np.array([[x, y]]))  # a venue exactly at the first pick
    moved = google_link.waypoints(net, healthy, fast, tree, CFG)
    assert moved and moved[0] != free[0]
