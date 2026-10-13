"""Golden routes between Kraków landmarks on the real data (skipped without `make data`).

`fastest_m` was recorded on 2026-10-13 (OSM extract of that day). The tolerance absorbs small OSM
edits; a large change means the graph or the cost function changed and must be looked at.
"""

import json
import math
from pathlib import Path

import pytest

from api import routing
from api.models import RouteRequest

GOLDEN = json.loads((Path(__file__).parent / "golden_routes.json").read_text())
TOLERANCE = 0.05


def crow_m(a, b):
    k = 111_320
    return math.hypot((a[0] - b[0]) * k * math.cos(math.radians(50.06)), (a[1] - b[1]) * k)


@pytest.mark.parametrize("g", GOLDEN, ids=lambda g: f"{g['from']}-{g['to']}-{g['mode']}")
def test_golden_route(real_store, g):
    req = RouteRequest(
        origin={"lon": g["origin"][0], "lat": g["origin"][1]},
        destination={"lon": g["destination"][0], "lat": g["destination"][1]},
        mode=g["mode"],
        profile="quiet",
    )
    r = routing.plan(real_store, req)
    fast, healthy = r["routes"][0]["metrics"], r["routes"][1]["metrics"]
    assert fast["distance_m"] == pytest.approx(g["fastest_m"], rel=TOLERANCE)
    # the network is plausible: the fastest route is 1.0-1.8 x the straight line on foot; by bike
    # one-way streets make short trips longer (Czyżyny -> Tauron Arena is 2.05 x)
    max_ratio = 1.8 if g["mode"] == "walk" else 2.2
    assert 1.0 <= fast["distance_m"] / crow_m(g["origin"], g["destination"]) <= max_ratio
    # the quiet route is within the detour limit and not noisier than the fastest one
    assert healthy["duration_min"] <= fast["duration_min"] * 1.3 + 0.1
    assert healthy["exposure_noise"] <= fast["exposure_noise"] + 1e-9
