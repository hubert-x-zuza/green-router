import numpy as np
import pytest

from api import routing
from api.costs import edge_cost
from api.models import RouteRequest
from api.tests.conftest import grid_network

ZERO = {"noise": 0.0, "air": 0.0, "traffic": 0.0, "green": 0.0, "fountain": 0.0}


def pens(net):
    return routing.penalties_for(net, 0.2, 0.3, night=False)


@pytest.mark.parametrize("seed", range(5))
def test_zero_weights_give_the_shortest_path(seed):
    net = grid_network(n=7, seed=seed)
    src, dst = 0, net.graph.vcount() - 1
    p = routing.shortest(net, src, dst, edge_cost(net.length, 1.33, pens(net), ZERO))
    ref = net.graph.distances(src, dst, weights=net.length)[0][0]
    assert net.length[p].sum() == pytest.approx(ref)


@pytest.mark.parametrize("seed", range(8))
def test_high_noise_weight_never_increases_mean_noise(seed):
    net = grid_network(n=7, seed=seed)
    pen = pens(net)
    src, dst = 0, net.graph.vcount() - 1
    prev = None
    for w in (0.0, 0.5, 1.0, 3.0, 10.0, 50.0):
        e = routing.shortest(net, src, dst, edge_cost(net.length, 1.33, pen, {**ZERO, "noise": w}))
        mean = (pen["noise"][e] * net.length[e]).sum() / net.length[e].sum()
        if prev is not None:
            assert mean <= prev + 1e-9
        prev = mean


def test_detour_guard_respects_limit():
    net = grid_network(n=8, seed=3)
    pen = pens(net)
    src, dst = 0, net.graph.vcount() - 1
    fast = routing.shortest(net, src, dst, edge_cost(net.length, 1.0, pen, ZERO))
    t_fast = routing.travel_s(net, fast, 1.0)
    for pct in (0, 5, 30):
        limit = t_fast * (1 + pct / 100)
        p = routing.guarded(net, src, dst, pen, {**ZERO, "noise": 20.0, "green": 20.0}, 1.0, limit)
        assert routing.travel_s(net, p.edges, 1.0) <= limit + 1e-6


def test_plan_returns_three_routes(fake_store):
    xy = fake_store.networks["walk"].node_xy
    from api.store import TO_4326

    o = TO_4326.transform(*xy[0])
    d = TO_4326.transform(*xy[-1])
    req = RouteRequest(origin={"lon": o[0], "lat": o[1]}, destination={"lon": d[0], "lat": d[1]})
    r = routing.plan(fake_store, req)
    assert [x["kind"] for x in r["routes"]] == ["fastest", "healthiest", "balanced"]
    fastest = r["routes"][0]["metrics"]
    for x in r["routes"][1:]:
        assert x["metrics"]["duration_min"] <= fastest["duration_min"] * 1.3 + 0.1
    assert "air_unavailable" in r["warnings"]  # no air database in the fake store


def test_outside_city_is_rejected(fake_store):
    req = RouteRequest(origin={"lon": 21.0, "lat": 52.2}, destination={"lon": 19.94, "lat": 50.06})
    with pytest.raises(routing.RouteError) as e:
        routing.plan(fake_store, req)
    assert e.value.code == "outside_city"


def test_tradeoff_text():
    t = {"extra_min": 4.2, "noise_pct": -18.0, "green_pct": 25.0}
    assert routing.tradeoff_text(t, "pl") == "+4 min, -18 % hałasu, +25 % zieleni"
    assert routing.tradeoff_text(t, "en") == "+4 min, -18 % noise, +25 % greenery"
    assert np.isfinite(t["extra_min"])
