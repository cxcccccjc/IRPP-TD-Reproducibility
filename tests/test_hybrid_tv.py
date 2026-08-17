"""Focused checks for the shared Dirichlet-TV implementation."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from irpp_core.reputation import HybridDirichletReputation


def make_scorer() -> HybridDirichletReputation:
    return HybridDirichletReputation(
        zeta=0.25,
        theta=0.35,
        tv_samples=1024,
        family_delta=0.05,
        max_task_horizon=100,
        quadrature_tolerance=1e-6,
    )


def test_uniform_prior_is_exact() -> None:
    result = make_scorer().evaluation(np.asarray([1, 1, 1]))
    assert result.method == "exact"
    assert result.tv == 0.0


def test_threshold_near_state_uses_converged_quadrature() -> None:
    result = make_scorer().evaluation(np.asarray([1, 1, 2]))
    assert result.method == "quadrature"
    assert result.quadrature_converged
    assert result.quadrature_delta <= 1e-6
    assert abs(result.tv - 8.0 / 27.0) < 1e-7


def test_state_seed_and_cache_are_deterministic() -> None:
    HybridDirichletReputation.reset_global_state()
    first = make_scorer().evaluation(np.asarray([1, 2, 1]))
    second = make_scorer().evaluation(np.asarray([1, 2, 1]))
    counts = HybridDirichletReputation.global_counts()
    assert first == second
    assert first.method == "mc"
    assert counts["misses"] == 1
    assert counts["global_hits"] == 1


if __name__ == "__main__":
    test_uniform_prior_is_exact()
    test_threshold_near_state_uses_converged_quadrature()
    test_state_seed_and_cache_are_deterministic()
    print("Hybrid Dirichlet-TV tests passed.")
