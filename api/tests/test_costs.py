import numpy as np
import pytest

from api.costs import air_penalty, edge_cost


def test_zero_weights_is_travel_time():
    L = np.array([100.0, 250.0])
    pen = {"noise": np.array([1.0, 0.5])}
    assert np.allclose(edge_cost(L, 2.0, pen, {"noise": 0.0}), [50.0, 125.0])


def test_weighted_penalties_inflate_time():
    L = np.array([100.0])
    pen = {"noise": np.array([0.5]), "green": np.array([1.0])}
    # 100 / 1 * (1 + 2 * 0.5 + 0.5 * 1.0) = 250
    assert edge_cost(L, 1.0, pen, {"noise": 2.0, "green": 0.5})[0] == pytest.approx(250.0)


def test_rejects_bad_inputs():
    L = np.array([1.0])
    with pytest.raises(ValueError):
        edge_cost(L, 1.0, {"noise": np.array([1.5])}, {"noise": 1.0})
    with pytest.raises(ValueError):
        edge_cost(L, 1.0, {"noise": np.array([0.5])}, {"noise": -1.0})
    with pytest.raises(ValueError):
        edge_cost(L, 1.0, {"noise": np.array([0.5])}, {"bogus": 1.0})


def test_air_penalty_shape():
    traffic = np.array([0.0, 1.0])
    assert np.allclose(air_penalty(0.0, traffic, 0.3), [0, 0])  # clean day: no air penalty
    assert np.allclose(air_penalty(0.5, traffic, 0.3), [0.15, 0.5])
    assert np.allclose(air_penalty(5.0, traffic, 0.3), [1.0, 1.0])  # clamped
