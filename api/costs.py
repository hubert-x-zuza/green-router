"""Edge cost (plan 5.4): cost(e) = length_m / speed_mps * (1 + sum_k w_k * p_k(e, t))."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

PENALTY_KEYS = ("noise", "air", "traffic", "green", "fountain", "cycleway")


def air_penalty(level: float, traffic: np.ndarray, a: float) -> np.ndarray:
    """air_penalty = clamp(level(t) * (a + (1 - a) * traffic_proximity), 0, 1) (plan 3c)."""
    return np.clip(level * (a + (1.0 - a) * traffic), 0.0, 1.0)


def edge_cost(
    length_m: np.ndarray,
    speed_mps: float,
    penalties: Mapping[str, np.ndarray],
    weights: Mapping[str, float],
) -> np.ndarray:
    """Travel time in seconds, inflated by the weighted penalties. Unknown keys are an error;
    weights left out count as 0."""
    unknown = set(weights) - set(PENALTY_KEYS)
    if unknown:
        raise ValueError(f"unknown penalty weights: {sorted(unknown)}")
    factor = np.ones_like(length_m, dtype="float64")
    for k, w in weights.items():
        if w < 0:
            raise ValueError(f"weight {k} must be >= 0")
        if w:
            p = penalties[k]
            if np.any((p < 0) | (p > 1)) or np.any(~np.isfinite(p)):
                raise ValueError(f"penalty {k} outside [0, 1]")
            factor += w * p
    return length_m / speed_mps * factor
