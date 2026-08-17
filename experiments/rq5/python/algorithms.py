"""Frozen analytical kernels used inside the complete RQ5 protocol paths."""

from __future__ import annotations

import math
import numpy as np


def rabod_scores(reports: np.ndarray, delta_max: int = 20, epsilon_d: float = 1e-12, seed: int = 0):
    values = np.asarray(reports, dtype=float)
    n = values.shape[0]
    scores = np.full(n, np.nan, dtype=float)
    if n < 3 or np.linalg.matrix_rank(values - values.mean(axis=0), tol=epsilon_d) < 2:
        return scores, False
    delta0 = min(delta_max, max(3, int(math.ceil(math.sqrt(n)))))
    all_indices = np.arange(n)
    any_valid = False
    for i in range(n):
        anchors = all_indices[all_indices != i]
        if anchors.size > delta0:
            rng = np.random.default_rng(np.random.SeedSequence([seed, i, 0xA60D]))
            anchors = np.sort(rng.choice(anchors, size=delta0, replace=False))
        vectors = values[anchors] - values[i]
        norms = np.linalg.norm(vectors, axis=1)
        valid = norms > epsilon_d
        vectors, norms = vectors[valid], norms[valid]
        if len(norms) < 3:
            continue
        left, right = np.triu_indices(len(norms), 1)
        dots = np.einsum("ij,ij->i", vectors[left], vectors[right])
        cosines = np.clip(dots / (norms[left] * norms[right]), -1.0, 1.0)
        weights = 1.0 / ((norms[left] ** 2 + epsilon_d**2) * (norms[right] ** 2 + epsilon_d**2))
        total = float(weights.sum())
        if not np.isfinite(total) or total <= 0:
            continue
        mean = float(np.dot(weights, cosines) / total)
        scores[i] = float(np.clip(np.dot(weights, (cosines - mean) ** 2) / total, 0.0, 1.0))
        any_valid = True
    return scores, any_valid


def bounded_truth_discovery(values: np.ndarray, epsilon: float = 1e-5, epsilon_w: float = 1e-12, max_iter: int = 50):
    values = np.asarray(values, dtype=float)
    if len(values) == 1:
        return values[0].copy(), 0
    truth = values.mean(axis=0)
    for iteration in range(1, max_iter + 1):
        residuals = np.sum((values - truth) ** 2, axis=1)
        mean_residual = float(np.mean(residuals))
        raw = np.log1p((mean_residual + epsilon_w) / (residuals + mean_residual + epsilon_w))
        raw = np.where(np.isfinite(raw) & (raw > 0), raw, 1.0)
        updated = (raw / raw.sum()) @ values
        if np.linalg.norm(updated - truth) <= epsilon * (1.0 + np.linalg.norm(truth)):
            return updated, iteration
        truth = updated
    return truth, max_iter


def irpp_filter_and_td(reports: np.ndarray, seed: int):
    reports = np.asarray(reports, dtype=float)
    scale = np.maximum(np.quantile(reports, 0.75, axis=0) - np.quantile(reports, 0.25, axis=0), 1e-6)
    normalized = (reports - np.median(reports, axis=0)) / scale
    scores, angular = rabod_scores(normalized, seed=seed)
    labels = np.full(len(reports), 1, dtype=int)
    if angular:
        labels[np.isfinite(scores) & (scores >= 1e-5)] = 0
        labels[np.isfinite(scores) & (scores < 1e-8)] = 2
        # At the matched mature operating point, uncertain workers with the
        # frozen reputation threshold remain eligible; only low labels drop.
        retained = labels != 2
    else:
        retained = np.ones(len(reports), dtype=bool)
    if not retained.any():
        retained[:] = True
    truth, iterations = bounded_truth_discovery(reports[retained])
    return truth, labels, retained, iterations


def dbcrh(reports: np.ndarray, reputations: np.ndarray, max_iter: int = 30, epsilon: float = 1e-5):
    reports = np.asarray(reports, dtype=float)
    reputations = np.asarray(reputations, dtype=float)
    truth = reports.mean(axis=0)
    for iteration in range(1, max_iter + 1):
        dist = np.sum((reports - truth) ** 2, axis=1) + 1e-12
        share = np.clip(dist / dist.sum(), 1e-12, 1.0)
        raw = np.maximum(-np.log(share), 1e-12) * np.maximum(reputations, 1e-3)
        weights = raw / raw.sum()
        updated = weights @ reports
        if np.linalg.norm(updated - truth) <= epsilon * (1.0 + np.linalg.norm(truth)):
            return updated, weights, iteration
        truth = updated
    return truth, weights, max_iter


def update_rpps_reputation(old: np.ndarray, weights: np.ndarray):
    median = float(np.median(weights))
    good = weights >= median
    updated = old.copy()
    updated[good] = 0.6 * old[good] + 0.4 / (1.0 + np.exp(-4.0 * old[good]))
    updated[~good] = 0.6 * old[~good] * np.exp(-0.35) + 0.4 * old[~good]
    return np.clip(updated, 0.0, 1.0)


def bsif_quality(reports: np.ndarray):
    reports = np.asarray(reports, dtype=float)
    # Eq. (3) is an L1 baseline; coordinate-wise median is its minimizer.
    baseline = np.median(reports, axis=0)
    distances = np.linalg.norm(reports - baseline, axis=1)
    denom = float(distances.sum()) + 1e-12
    quality = np.clip(1.0 - distances / denom, 0.0, 1.0)
    return baseline, quality
