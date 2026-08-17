from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, Iterable, Mapping, Optional

import numpy as np
from scipy.special import betaln, gammaln


HIGH = 0
UNCERTAIN = 1
LOW = 2
LABEL_NAMES = {HIGH: "h", UNCERTAIN: "u", LOW: "l"}


@dataclass(frozen=True)
class Parameters:
    zeta: float = 0.25
    theta: float = 0.35
    mu1: float = 0.0582258516167486
    mu2: float = 0.001722719501825485
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

    @classmethod
    def from_mapping(cls, values: Mapping) -> "Parameters":
        fields = cls.__dataclass_fields__
        return cls(**{key: values[key] for key in fields if key in values})


@dataclass(frozen=True)
class ScoreDetails:
    phi_h: float
    phi_u: float
    phi_l: float
    uncertainty: float
    score: float


@dataclass(frozen=True)
class AngularDiagnostics:
    mode: str
    elapsed_ms: float
    selection_ms: float
    kernel_ms: float
    candidate_count: int
    valid_candidate_count: int
    pair_evaluations: int
    anchor_candidates_sum: int
    max_anchor_candidates: int
    estimated_peak_bytes: int


class ReputationScorer:
    """The manuscript score and preregistered RQ2 replacements."""

    _DIRICHLET_CACHE: Dict[tuple[int, int, int, int], float] = {(1024, 1, 1, 1): 0.0}
    _BETA_CACHE: Dict[tuple[float, float], float] = {}

    def __init__(self, parameters: Parameters, mode: str = "full"):
        if mode not in {"full", "no_u", "beta"}:
            raise ValueError(f"Unknown reputation mode: {mode}")
        self.parameters = parameters
        self.mode = mode

    def _dirichlet_uncertainty(self, alpha: np.ndarray) -> float:
        key = (self.parameters.tv_samples, *(int(value) for value in alpha))
        if key in self._DIRICHLET_CACHE:
            return 1.0 - self._DIRICHLET_CACHE[key]
        _, ah, au, al = key
        seed = (ah * 73_856_093 ^ au * 19_349_663 ^ al * 83_492_791 ^ 0x5EED2026) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        half = self.parameters.tv_samples // 2
        samples = np.vstack(
            [rng.dirichlet(np.asarray([ah, au, al], dtype=float), size=half), rng.dirichlet(np.ones(3), size=half)]
        )
        samples = np.clip(samples, np.finfo(float).tiny, 1.0)
        log_norm = gammaln(ah + au + al) - gammaln(ah) - gammaln(au) - gammaln(al)
        log_p = log_norm + np.sum((np.asarray([ah, au, al]) - 1.0) * np.log(samples), axis=1)
        tv = float(np.clip(np.mean(np.abs(np.tanh(0.5 * (log_p - math.log(2.0))))), 0.0, 1.0))
        self._DIRICHLET_CACHE[key] = tv
        return 1.0 - tv

    def _beta_uncertainty(self, a: float, b: float) -> float:
        key = (round(float(a), 8), round(float(b), 8))
        if key in self._BETA_CACHE:
            return self._BETA_CACHE[key]
        # Deterministic midpoint quadrature avoids endpoint singularities.
        x = (np.arange(2048, dtype=float) + 0.5) / 2048.0
        log_pdf = (a - 1.0) * np.log(x) + (b - 1.0) * np.log1p(-x) - betaln(a, b)
        pdf = np.exp(np.clip(log_pdf, -745.0, 709.0))
        tv = float(np.clip(0.5 * np.mean(np.abs(pdf - 1.0)), 0.0, 1.0))
        uncertainty = 1.0 - tv
        self._BETA_CACHE[key] = uncertainty
        return uncertainty

    def details(self, alpha: np.ndarray) -> ScoreDetails:
        alpha = np.asarray(alpha, dtype=int)
        phi = alpha / float(alpha.sum())
        zeta = self.parameters.zeta
        if self.mode == "full":
            uncertainty = self._dirichlet_uncertainty(alpha)
            credit = (1.0 - uncertainty) * (phi[HIGH] + zeta * phi[UNCERTAIN])
            credit += uncertainty * (1.0 + zeta) / 3.0
            penalty = 1.0 - (1.0 - uncertainty) * phi[LOW]
            score = credit * penalty
        elif self.mode == "no_u":
            uncertainty = 0.0
            score = (phi[HIGH] + zeta * phi[UNCERTAIN]) * (1.0 - phi[LOW])
        else:
            counts = alpha.astype(float) - 1.0
            good = 1.0 + counts[HIGH] + zeta * counts[UNCERTAIN]
            bad = 1.0 + counts[LOW] + (1.0 - zeta) * counts[UNCERTAIN]
            uncertainty = self._beta_uncertainty(good, bad)
            p_good = good / (good + bad)
            credit = (1.0 - uncertainty) * p_good + uncertainty * 0.5
            penalty = 1.0 - (1.0 - uncertainty) * (1.0 - p_good)
            score = credit * penalty
        return ScoreDetails(float(phi[0]), float(phi[1]), float(phi[2]), float(uncertainty), float(np.clip(score, 0.0, 1.0)))


def candidate_seed(base_seed: int, task_id: int, worker_id: int) -> int:
    return int(np.random.SeedSequence([int(base_seed), int(task_id), int(worker_id), 0xA60D]).generate_state(1, dtype=np.uint32)[0])


def angular_scores(
    normalized_reports: np.ndarray,
    worker_ids: np.ndarray,
    anchor_worker_ids: set[int],
    task_id: int,
    base_seed: int,
    delta_max: int,
    epsilon_d: float,
    mode: str = "rabod",
) -> tuple[np.ndarray, bool, AngularDiagnostics]:
    """Compute matched RABOD or exact-ABOD scores and resource counters.

    Both modes use the same reputation-guided anchor set and weighted angular
    variance. RABOD samples at most ``min(delta_max, ceil(sqrt(n)))`` anchors
    per candidate; exact-ABOD evaluates every available anchor. Thus the mode
    switch changes only approximation, not geometry, preprocessing, or score
    definition.
    """
    if mode not in {"rabod", "exact_abod"}:
        raise ValueError(f"Unknown angular mode: {mode}")
    started = time.perf_counter()
    reports = np.asarray(normalized_reports, dtype=float)
    n = reports.shape[0]
    scores = np.full(n, np.nan, dtype=float)
    pair_evaluations = 0
    anchor_candidates_sum = 0
    max_anchor_candidates = 0
    estimated_peak_bytes = 0
    selection_seconds = 0.0
    kernel_seconds = 0.0

    def finish(any_valid: bool) -> tuple[np.ndarray, bool, AngularDiagnostics]:
        diagnostics = AngularDiagnostics(
            mode=mode,
            elapsed_ms=1000.0 * (time.perf_counter() - started),
            selection_ms=1000.0 * selection_seconds,
            kernel_ms=1000.0 * kernel_seconds,
            candidate_count=int(n),
            valid_candidate_count=int(np.isfinite(scores).sum()),
            pair_evaluations=int(pair_evaluations),
            anchor_candidates_sum=int(anchor_candidates_sum),
            max_anchor_candidates=int(max_anchor_candidates),
            estimated_peak_bytes=int(estimated_peak_bytes),
        )
        return scores, any_valid, diagnostics

    if n < 3:
        return finish(False)
    centered = reports - reports.mean(axis=0, keepdims=True)
    if np.linalg.matrix_rank(centered, tol=epsilon_d) < 2:
        return finish(False)
    anchor_indices = np.asarray([idx for idx, wid in enumerate(worker_ids) if int(wid) in anchor_worker_ids], dtype=int)
    delta0 = min(int(delta_max), max(3, int(math.ceil(math.sqrt(n)))))
    any_valid = False
    for candidate_idx, worker_id in enumerate(worker_ids):
        candidates = anchor_indices[anchor_indices != candidate_idx]
        if candidates.size < 3:
            continue
        if mode == "rabod" and candidates.size > delta0:
            selection_started = time.perf_counter()
            rng = np.random.default_rng(candidate_seed(base_seed, task_id, int(worker_id)))
            candidates = np.sort(rng.choice(candidates, size=delta0, replace=False))
            selection_seconds += time.perf_counter() - selection_started
        kernel_started = time.perf_counter()
        anchor_candidates_sum += int(candidates.size)
        max_anchor_candidates = max(max_anchor_candidates, int(candidates.size))
        vectors = reports[candidates] - reports[candidate_idx]
        norms = np.linalg.norm(vectors, axis=1)
        valid = norms > epsilon_d
        vectors, norms = vectors[valid], norms[valid]
        if vectors.shape[0] < 3:
            continue
        left, right = np.triu_indices(vectors.shape[0], k=1)
        if left.size < 2:
            continue
        pair_evaluations += int(left.size)
        dot = np.einsum("ij,ij->i", vectors[left], vectors[right])
        cosines = np.clip(dot / (norms[left] * norms[right]), -1.0, 1.0)
        pair_weights = 1.0 / ((norms[left] ** 2 + epsilon_d**2) * (norms[right] ** 2 + epsilon_d**2))
        estimated_peak_bytes = max(
            estimated_peak_bytes,
            int(
                vectors.nbytes
                + norms.nbytes
                + left.nbytes
                + right.nbytes
                + dot.nbytes
                + cosines.nbytes
                + pair_weights.nbytes
            ),
        )
        weight_sum = float(pair_weights.sum())
        if not np.isfinite(weight_sum) or weight_sum <= 0.0:
            continue
        mean_cosine = float(np.dot(pair_weights, cosines) / weight_sum)
        score = float(np.dot(pair_weights, (cosines - mean_cosine) ** 2) / weight_sum)
        scores[candidate_idx] = float(np.clip(score, 0.0, 1.0))
        kernel_seconds += time.perf_counter() - kernel_started
        any_valid = True
    return finish(any_valid)


def rabod_scores(
    normalized_reports: np.ndarray,
    worker_ids: np.ndarray,
    anchor_worker_ids: set[int],
    task_id: int,
    base_seed: int,
    delta_max: int,
    epsilon_d: float,
) -> tuple[np.ndarray, bool]:
    scores, available, _ = angular_scores(
        normalized_reports,
        worker_ids,
        anchor_worker_ids,
        task_id,
        base_seed,
        delta_max,
        epsilon_d,
        mode="rabod",
    )
    return scores, available


def bounded_truth_discovery(reports: np.ndarray, parameters: Parameters) -> tuple[np.ndarray, int, bool]:
    values = np.asarray(reports, dtype=float)
    if values.shape[0] == 1 or np.allclose(values, values[0], rtol=0.0, atol=parameters.epsilon_w):
        return values[0].copy(), 0, True
    truth = values.mean(axis=0)
    for iteration in range(1, parameters.max_iterations + 1):
        residuals = np.sum((values - truth) ** 2, axis=1)
        mean_residual = float(np.mean(residuals))
        raw = np.log1p((mean_residual + parameters.epsilon_w) / (residuals + mean_residual + parameters.epsilon_w))
        raw = np.where(np.isfinite(raw) & (raw > 0.0), raw, 1.0)
        weights = raw / raw.sum()
        updated = weights @ values
        if np.linalg.norm(updated - truth) <= parameters.epsilon * (1.0 + np.linalg.norm(truth)):
            return updated, iteration, True
        truth = updated
    return truth, parameters.max_iterations, False


@dataclass(frozen=True)
class ProcessResult:
    prediction: Optional[np.ndarray]
    iterations: int
    converged: bool
    task_record: dict
    report_records: tuple[dict, ...]


class InstrumentedIRPPTD:
    """Sequential implementation of Algorithm 1 with disjoint external seeds."""

    def __init__(
        self,
        parameters: Parameters,
        center: np.ndarray,
        scale: np.ndarray,
        seed: int,
        score_mode: str,
        anchor_mode: str,
        seed_mode: str,
        reliable_probability_max: float = 0.0,
        forced_low_participations: Iterable[int] = (),
    ):
        if anchor_mode not in {"guided", "all", "sequential"}:
            raise ValueError(anchor_mode)
        if seed_mode not in {"adaptive", "none", "always"}:
            raise ValueError(seed_mode)
        self.parameters = parameters
        self.center = np.asarray(center, dtype=float)
        self.scale = np.asarray(scale, dtype=float)
        self.seed = int(seed)
        self.scorer = ReputationScorer(parameters, score_mode)
        self.anchor_mode = anchor_mode
        self.seed_mode = seed_mode
        self.reliable_probability_max = float(reliable_probability_max)
        self.forced_low_participations = set(int(x) for x in forced_low_participations)
        self.states: Dict[int, np.ndarray] = {}
        self.participations: Dict[int, int] = {}

    def state(self, worker_id: int) -> np.ndarray:
        if worker_id not in self.states:
            self.states[worker_id] = np.ones(3, dtype=int)
        return self.states[worker_id]

    def reset_workers(self, worker_ids: Iterable[int]) -> None:
        for worker_id in worker_ids:
            self.states[int(worker_id)] = np.ones(3, dtype=int)
            self.participations[int(worker_id)] = 0

    def process_task(self, task, reset_worker_ids: Iterable[int] = ()) -> ProcessResult:
        self.reset_workers(reset_worker_ids)
        p = self.parameters
        ordinary = tuple(task.ordinary)
        ordinary_ids = np.asarray([r.worker_id for r in ordinary], dtype=int)
        details_before = {wid: self.scorer.details(self.state(wid)) for wid in ordinary_ids}
        mature = {
            int(wid)
            for wid in ordinary_ids
            if details_before[int(wid)].score >= p.theta
            and int(self.state(int(wid)).sum() - 3) >= p.e_b
            and int(self.state(int(wid))[HIGH] - self.state(int(wid))[LOW]) >= p.q_b
        }
        provisional = {
            int(wid)
            for wid in ordinary_ids
            if int(self.state(int(wid))[HIGH] - self.state(int(wid))[LOW]) >= p.q_b and int(wid) not in mature
        }
        seed_active = self.seed_mode == "always" or (self.seed_mode == "adaptive" and len(mature) < p.n_b)
        seeds = tuple(task.seeds[: p.s_0]) if seed_active else tuple()
        reports = ordinary + seeds
        worker_ids = np.asarray([r.worker_id for r in reports], dtype=int)
        seed_ids = {int(r.worker_id) for r in seeds}

        if self.anchor_mode in {"all", "sequential"}:
            anchors = set(int(x) for x in worker_ids)
        elif len(mature) < p.n_b:
            anchors = seed_ids | mature | provisional
        else:
            anchors = mature | (seed_ids if self.seed_mode == "always" else set())

        raw = np.vstack([r.values for r in reports])
        normalized = (raw - self.center) / self.scale
        angle_scores, angular_available = rabod_scores(
            normalized, worker_ids, anchors, task.task_id, self.seed, p.delta_max, p.epsilon_d
        )
        labels = np.full(worker_ids.size, UNCERTAIN, dtype=int)
        if angular_available:
            valid = np.isfinite(angle_scores)
            labels[valid & (angle_scores >= p.mu1)] = HIGH
            labels[valid & (angle_scores < p.mu2)] = LOW

        retained = np.ones(worker_ids.size, dtype=bool)
        if angular_available:
            retained[:] = False
            for idx, wid in enumerate(worker_ids):
                if int(wid) in seed_ids:
                    retained[idx] = True
                elif self.anchor_mode == "sequential":
                    retained[idx] = labels[idx] != LOW and details_before[int(wid)].score >= p.theta
                else:
                    retained[idx] = labels[idx] == HIGH or (
                        labels[idx] == UNCERTAIN and details_before[int(wid)].score >= p.theta
                    )

        if retained.any():
            prediction, iterations, converged = bounded_truth_discovery(raw[retained], p)
        else:
            prediction, iterations, converged = None, 0, False

        report_records = []
        for idx, report in enumerate(ordinary):
            wid = int(report.worker_id)
            before = self.state(wid).copy()
            self.participations[wid] = self.participations.get(wid, 0) + 1
            update_label = int(labels[idx])
            forced = self.participations[wid] in self.forced_low_participations and report.scheduled_p <= self.reliable_probability_max
            if forced:
                update_label = LOW
            self.state(wid)[update_label] += 1
            after = self.state(wid).copy()
            after_details = self.scorer.details(after)
            report_records.append(
                {
                    "worker_id": wid,
                    "participation_index": self.participations[wid],
                    "scheduled_p": float(report.scheduled_p),
                    "is_reliable_worker": bool(report.scheduled_p <= self.reliable_probability_max),
                    "is_bad_report": bool(report.is_bad),
                    "bad_coordinate_count": int(np.sum(report.error_mask)),
                    "angular_score": float(angle_scores[idx]) if np.isfinite(angle_scores[idx]) else np.nan,
                    "angular_valid": bool(np.isfinite(angle_scores[idx])),
                    "predicted_low": bool(labels[idx] == LOW),
                    "retained": bool(retained[idx]),
                    "mature_before": bool(wid in mature),
                    "provisional_before": bool(wid in provisional),
                    "anchor_before": bool(wid in anchors),
                    "forced_low_update": bool(forced),
                    "update_label": LABEL_NAMES[update_label],
                    "alpha_h_before": int(before[0]),
                    "alpha_u_before": int(before[1]),
                    "alpha_l_before": int(before[2]),
                    "psi_before": float(details_before[wid].score),
                    "uncertainty_before": float(details_before[wid].uncertainty),
                    "phi_h_before": float(details_before[wid].phi_h),
                    "phi_u_before": float(details_before[wid].phi_u),
                    "phi_l_before": float(details_before[wid].phi_l),
                    "alpha_h_after": int(after[0]),
                    "alpha_u_after": int(after[1]),
                    "alpha_l_after": int(after[2]),
                    "psi_after": float(after_details.score),
                    "uncertainty_after": float(after_details.uncertainty),
                }
            )

        ordinary_mask = np.arange(worker_ids.size) < len(ordinary)
        ordinary_valid = ordinary_mask & np.isfinite(angle_scores)
        active_anchor_records = [r for r in ordinary if int(r.worker_id) in anchors]
        task_record = {
            "participant_count": len(ordinary),
            "seed_count": len(seeds),
            "active_anchor_count": len(anchors),
            "ordinary_anchor_count": len(active_anchor_records),
            "reliable_anchor_count": int(sum(r.scheduled_p <= self.reliable_probability_max for r in active_anchor_records)),
            "mature_anchor_count": len(mature),
            "provisional_anchor_count": len(provisional),
            "angular_available": bool(angular_available),
            "angular_valid_count": int(np.sum(ordinary_valid)),
            "retained_ordinary_count": int(np.sum(retained[: len(ordinary)])),
            "retained_seed_count": int(np.sum(retained[len(ordinary) :])),
            "iterations": int(iterations),
            "converged": bool(converged),
        }
        return ProcessResult(prediction, iterations, converged, task_record, tuple(report_records))
