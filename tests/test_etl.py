"""ETL unit tests on synthetic inputs (no downloads)."""

import numpy as np
import pandas as pd
import pytest
import shapely

from etl import enrich, geocoder, normalise
from etl.common import Grid


def test_sample_points_midpoints_and_minimum_two():
    lines = np.array([shapely.LineString([(0, 0), (10, 0)]), shapely.LineString([(0, 0), (0, 60)])])
    idx, x, y = enrich.sample_points(lines, np.array([10.0, 60.0]), spacing=15)
    assert list(np.bincount(idx)) == [2, 4]
    assert np.allclose(x[:2], [2.5, 7.5]) and np.allclose(y[2:], [7.5, 22.5, 37.5, 52.5])


def test_reducers_keep_missing_as_nan():
    idx = np.array([0, 0, 1])
    v = np.array([1.0, 3.0, np.nan])
    assert np.allclose(enrich.reduce_mean(idx, v, 2)[:1], [2.0])
    assert np.isnan(enrich.reduce_mean(idx, v, 2)[1])
    assert enrich.reduce_max(idx, v, 2)[0] == 3.0


def test_grid_sample_outside_is_nodata():
    g = Grid(0.0, 100.0, 10.0, 10, 10)
    arr = np.arange(100, dtype=float).reshape(10, 10)
    out = g.sample(arr, np.array([5.0, 95.0, -1.0]), np.array([95.0, 5.0, 50.0]), nodata=-1)
    assert list(out) == [0.0, 99.0, -1.0]


def test_penalties_neutral_outside_coverage():
    cfg = {"coverage": {"neutral_penalty": 0.5},
           "noise": {"LDWN": {"zero_db": 45, "one_db": 75}, "LN": {"zero_db": 40, "one_db": 65}},
           "fountains": {"near_m": 100, "far_m": 500}}  # fmt: skip
    exp = pd.DataFrame({"noise_ldwn_mean": [60.0, np.nan], "noise_ln_mean": [52.5, np.nan],
                        "green_score": [0.25, np.nan], "fountain_dist_m": [300.0, 900.0],
                        "traffic_prox": [0.4, 0.1], "data_coverage": [True, False]})  # fmt: skip
    p = normalise.penalties(exp, cfg)
    assert p.loc[0, "p_noise"] == pytest.approx(0.5)
    assert p.loc[0, "p_noise_night"] == pytest.approx(0.5)
    assert p.loc[0, "p_green"] == pytest.approx(0.75)
    assert p.loc[0, "p_fountain"] == pytest.approx(0.5)
    assert (p.loc[1, ["p_noise", "p_green", "p_fountain"]] == 0.5).all()
    assert p.loc[1, "p_traffic"] == pytest.approx(0.1)


@pytest.mark.parametrize(
    ("q", "words", "number"),
    [
        ("ul. Floriańska 15", ["florianska"], "15"),
        ("al. Mickiewicza 30", ["aleja", "mickiewicza"], "30"),
        ("os. Piastów 20/4", ["osiedle", "piastow"], "20"),
        ("Aleja 29 Listopada", ["aleja", "29", "listopada"], None),
        ("Łobzowska 5a", ["lobzowska"], "5a"),
        ("świętego Filipa", ["sw", "filipa"], None),
    ],
)
def test_geocoder_query_normalisation(q, words, number):
    assert geocoder.split_query(q) == (words, number)
