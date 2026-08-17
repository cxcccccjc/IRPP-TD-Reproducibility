from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Mapping, Optional

import numpy as np

from irpp_core.reputation import HybridDirichletReputation

from .data_utils import RobustScaler, Task


HIGH = 0
UNCERTAIN = 1
LOW = 2


@dataclass(frozen=True)
class IRPPParameters:
    zeta: float = 0.25
    theta: float = 0.35
    mu1: float = 1e-5
    mu2: float = 1e-8
    e_b: int = 5
    q_b: int = 2
    n_b: int = 5
    s_0: int = 5
    delta_max: int = 20
    epsilon_d: float = 1e-12
    epsilon_w: float = 1e-12
    epsilon: float = 1e-5
    max_iterations: int = 50
    tv_samples: int = 1024
    tv_family_delta: float = 0.05
    tv_max_task_horizon: int = 100
    tv_quad_tolerance: float = 1e-6

    @classmethod
    def from_mapping(cls, values: Mapping) -> "IRPPParameters":
        fields = cls.__dataclass_fields__
        return cls(**{key: values[key] for key in fields if key in values})


@dataclass(frozen=True)
class TaskResult:
    truth: Optional[np.ndarray]
    iterations: int
    converged: bool
    retained_count: int
    participant_count: int
    high_count: int
    uncertain_count: int
    low_count: int
    mature_anchor_count: int
    active_anchor_count: int
    seed_count: int
    angular_available: bool
    mean_rabod_score: float


def _candidate_seed(base_seed: int, task_id: int, worker_id: int) -> int:
    return int(
        np.random.SeedSequence([int(base_seed), int(task_id), int(worker_id), 0xA60D])
        .generate_state(1, dtype=np.uint32)[0]
    )


def rabod_scores(
    normalized_reports: np.ndarray,
    worker_ids: np.ndarray,
    anchor_worker_ids: set[int],
    task_id: int,
    base_seed: int,
    delta_max: int,
    epsilon_d: float,
) -> tuple[np.ndarray, bool]:
    """Compute the paper's bounded reputation-guided angular variance scores."""
    reports = np.asarray(normalized_reports, dtype=float)
    n = reports.shape[0]
    scores = np.full(n, np.nan, dtype=float)
    if n < 3:
        return scores, False
    centered = reports - reports.mean(axis=0, keepdims=True)
    if np.linalg.matrix_rank(centered, tol=epsilon_d) < 2:
        return scores, False
    anchor_indices = np.asarray(
        [idx for idx, worker_id in enumerate(worker_ids) if int(worker_id) in anchor_worker_ids],
        dtype=int,
    )
    delta0 = min(int(delta_max), max(3, int(math.ceil(math.sqrt(n)))))
    any_valid = False
    for candidate_idx, worker_id in enumerate(worker_ids):
        candidates = anchor_indices[anchor_indices != candidate_idx]
        if candidates.size < 3:
            continue
        if candidates.size > delta0:
            rng = np.random.default_rng(_candidate_seed(base_seed, task_id, int(worker_id)))
            candidates = np.sort(rng.choice(candidates, size=delta0, replace=False))
        vectors = reports[candidates] - reports[candidate_idx]
        norms = np.linalg.norm(vectors, axis=1)
        valid = norms > epsilon_d
        vectors = vectors[valid]
        norms = norms[valid]
        if vectors.shape[0] < 3:
            continue
        left, right = np.triu_indices(vectors.shape[0], k=1)
        if left.size < 2:
            continue
        dot = np.einsum("ij,ij->i", vectors[left], vectors[right])
        cosines = np.clip(dot / (norms[left] * norms[right]), -1.0, 1.0)
        pair_weights = 1.0 / (
            (norms[left] ** 2 + epsilon_d**2) * (norms[right] ** 2 + epsilon_d**2)
        )
        weight_sum = float(pair_weights.sum())
        if not np.isfinite(weight_sum) or weight_sum <= 0.0:
            continue
        mean_cosine = float(np.dot(pair_weights, cosines) / weight_sum)
        score = float(np.dot(pair_weights, (cosines - mean_cosine) ** 2) / weight_sum)
        scores[candidate_idx] = float(np.clip(score, 0.0, 1.0))
        any_valid = True
    return scores, any_valid


def bounded_truth_discovery(
    reports: np.ndarray,
    epsilon: float,
    epsilon_w: float,
    max_iterations: int,
) -> tuple[np.ndarray, int, bool]:
    values = np.asarray(reports, dtype=float)
    if values.shape[0] == 1:
        return values[0].copy(), 0, True
    if np.allclose(values, values[0], rtol=0.0, atol=epsilon_w):
        return values[0].copy(), 0, True
    truth = values.mean(axis=0)
    converged = False
    for iteration in range(1, max_iterations + 1):
        residuals = np.sum((values - truth) ** 2, axis=1)
        mean_residual = float(np.mean(residuals))
        raw = np.log1p((mean_residual + epsilon_w) / (residuals + mean_residual + epsilon_w))
        raw = np.where(np.isfinite(raw) & (raw > 0.0), raw, 1.0)
        weights = raw / raw.sum()
        updated = weights @ values
        if np.linalg.norm(updated - truth) <= epsilon * (1.0 + np.linalg.norm(truth)):
            truth = updated
            converged = True
            return truth, iteration, converged
        truth = updated
    return truth, max_iterations, converged


class IRPPTD:
    """Sequential IRPP-TD implementation matching the revised manuscript equations."""

    def __init__(self, parameters: IRPPParameters, scaler: RobustScaler, seed: int):
        if not 0.0 <= parameters.mu2 < parameters.mu1 <= 1.0:
            raise ValueError("Require 0 <= mu2 < mu1 <= 1")
        self.parameters = parameters
        self.scaler = scaler
        self.seed = int(seed)
        self.states: Dict[int, np.ndarray] = {}
        self.reputation = HybridDirichletReputation(
            zeta=parameters.zeta,
            theta=parameters.theta,
            tv_samples=parameters.tv_samples,
            family_delta=parameters.tv_family_delta,
            max_task_horizon=parameters.tv_max_task_horizon,
            quadrature_tolerance=parameters.tv_quad_tolerance,
        )

    def _state(self, worker_id: int) -> np.ndarray:
        if worker_id not in self.states:
            self.states[worker_id] = np.ones(3, dtype=int)
        return self.states[worker_id]

    def _score(self, worker_id: int) -> float:
        return self.reputation.score(self._state(worker_id))

    def process_task(self, task: Task) -> TaskResult:
        params = self.parameters
        worker_ids = task.worker_ids
        raw_reports = task.report_matrix
        normalized = self.scaler.transform(raw_reports)
        scores_before = {int(worker_id): self._score(int(worker_id)) for worker_id in worker_ids}

        mature = {
            int(worker_id)
            for worker_id in worker_ids
            if scores_before[int(worker_id)] >= params.theta
            and int(self._state(int(worker_id)).sum() - 3) >= params.e_b
            and int(self._state(int(worker_id))[HIGH] - self._state(int(worker_id))[LOW]) >= params.q_b
        }
        provisional = {
            int(worker_id)
            for worker_id in worker_ids
            if int(self._state(int(worker_id))[HIGH] - self._state(int(worker_id))[LOW]) >= params.q_b
            and int(worker_id) not in mature
        }
        # IDs 1--50 are the zero-error-probability registry in the retained simulator.
        trusted_present = sorted(int(worker_id) for worker_id in worker_ids if int(worker_id) <= 50)
        seed_rng = np.random.default_rng(
            int(np.random.SeedSequence([self.seed, task.task_id, 0x5EED]).generate_state(1)[0])
        )
        if len(trusted_present) > params.s_0:
            seed_workers = set(
                int(item) for item in seed_rng.choice(trusted_present, size=params.s_0, replace=False)
            )
        else:
            seed_workers = set(trusted_present)
        if len(mature) < params.n_b:
            anchors = seed_workers | mature | provisional
        else:
            anchors = mature

        angle_scores, angular_available = rabod_scores(
            normalized,
            worker_ids,
            anchors,
            task.task_id,
            self.seed,
            params.delta_max,
            params.epsilon_d,
        )
        labels = np.full(worker_ids.size, UNCERTAIN, dtype=int)
        if angular_available:
            valid = np.isfinite(angle_scores)
            labels[valid & (angle_scores >= params.mu1)] = HIGH
            labels[valid & (angle_scores < params.mu2)] = LOW

        if not angular_available:
            retained = np.ones(worker_ids.size, dtype=bool)
        else:
            reputations = np.asarray([scores_before[int(worker_id)] for worker_id in worker_ids])
            retained = (labels == HIGH) | ((labels == UNCERTAIN) & (reputations >= params.theta))

        if retained.any():
            truth, iterations, converged = bounded_truth_discovery(
                raw_reports[retained], params.epsilon, params.epsilon_w, params.max_iterations
            )
        else:
            truth, iterations, converged = None, 0, False

        # The current labels affect only the next task's anchor and retention decision.
        for worker_id, label in zip(worker_ids, labels):
            self._state(int(worker_id))[int(label)] += 1

        finite_scores = angle_scores[np.isfinite(angle_scores)]
        return TaskResult(
            truth=truth,
            iterations=iterations,
            converged=converged,
            retained_count=int(retained.sum()),
            participant_count=int(worker_ids.size),
            high_count=int(np.sum(labels == HIGH)),
            uncertain_count=int(np.sum(labels == UNCERTAIN)),
            low_count=int(np.sum(labels == LOW)),
            mature_anchor_count=len(mature),
            active_anchor_count=len(anchors),
            seed_count=len(seed_workers) if len(mature) < params.n_b else 0,
            angular_available=angular_available,
            mean_rabod_score=float(np.mean(finite_scores)) if finite_scores.size else float("nan"),
        )
