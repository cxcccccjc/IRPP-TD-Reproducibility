from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional

import numpy as np
from scipy.special import gammaln


HIGH = 0
UNCERTAIN = 1
LOW = 2
RQ4_ROOT = Path(__file__).resolve().parents[1]


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
class Submission:
    worker_id: int
    values: np.ndarray


@dataclass(frozen=True)
class Task:
    task_id: int
    truth: np.ndarray
    submissions: tuple[Submission, ...]

    @property
    def report_matrix(self) -> np.ndarray:
        return np.vstack([item.values for item in self.submissions])

    @property
    def worker_ids(self) -> np.ndarray:
        return np.asarray([item.worker_id for item in self.submissions], dtype=int)


@dataclass(frozen=True)
class Workload:
    key: str
    scene: str
    target_workers: int
    path: Path
    tasks: tuple[Task, ...]
    sha256: str


@dataclass(frozen=True)
class Scaler:
    center: np.ndarray
    scale: np.ndarray

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (np.asarray(values, dtype=float) - self.center) / self.scale


@dataclass(frozen=True)
class AngularDiagnostics:
    mode: str
    effective_budget: int
    pair_evaluations: int
    valid_candidates: int
    fallback: bool
    estimated_peak_bytes: int


@dataclass(frozen=True)
class TDResult:
    truth: Optional[np.ndarray]
    iterations: int
    converged: bool
    finite: bool
    max_raw_weight: float
    normalization_error: float


@dataclass(frozen=True)
class SequentialResult:
    truth: Optional[np.ndarray]
    iterations: int
    converged: bool
    scores: np.ndarray
    labels: np.ndarray
    retained: np.ndarray
    angular_available: bool
    angular: AngularDiagnostics
    td: TDResult


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_config_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (RQ4_ROOT / path).resolve()


def load_workloads(config: Mapping) -> Dict[str, Workload]:
    root = resolve_config_path(config["workload_root"])
    output: Dict[str, Workload] = {}
    for key, filename in config["data_files"].items():
        scene, n_token = key.rsplit("_n", 1)
        path = root / filename
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        tasks = []
        for task_key in sorted(payload["task_worker_data"], key=lambda value: int(value)):
            record = payload["task_worker_data"][task_key]
            truth = np.asarray(record["task_true_data"], dtype=float)
            submissions = tuple(
                Submission(int(item["worker_id"]), np.asarray(item["submitted_data"], dtype=float))
                for item in record["worker_submissions"]
            )
            if not submissions or any(item.values.shape != truth.shape for item in submissions):
                raise ValueError(f"Invalid task {task_key} in {path}")
            tasks.append(Task(int(task_key), truth, submissions))
        if len(tasks) != 100:
            raise ValueError(f"Expected 100 tasks in {path}; found {len(tasks)}")
        output[key] = Workload(key, scene, int(n_token), path, tuple(tasks), sha256_file(path))
    return output


def fit_scene_scalers(workloads: Mapping[str, Workload], calibration_tasks: int) -> Dict[str, Scaler]:
    output: Dict[str, Scaler] = {}
    for scene in sorted({item.scene for item in workloads.values()}):
        values = np.vstack(
            [task.report_matrix for workload in workloads.values() if workload.scene == scene for task in workload.tasks[:calibration_tasks]]
        )
        center = np.median(values, axis=0)
        q05, q95 = np.quantile(values, [0.05, 0.95], axis=0)
        scale = q95 - q05
        fallback = np.std(values, axis=0)
        scale = np.where(scale > 1e-12, scale, np.where(fallback > 1e-12, fallback, 1.0))
        output[scene] = Scaler(center, scale)
    return output


class DirichletReputation:
    _GLOBAL_TV_CACHE: Dict[tuple[int, int, int, int], float] = {(1024, 1, 1, 1): 0.0}

    def __init__(self, zeta: float, samples: int):
        self.zeta = float(zeta)
        self.samples = int(samples + samples % 2)

    def tv_distance(self, alpha: np.ndarray) -> float:
        key = (self.samples, *(int(value) for value in alpha))
        if key in self._GLOBAL_TV_CACHE:
            return self._GLOBAL_TV_CACHE[key]
        counts = key[1:]
        seed = (counts[0] * 73_856_093 ^ counts[1] * 19_349_663 ^ counts[2] * 83_492_791 ^ 0x5EED2026) & 0xFFFFFFFF
        rng = np.random.default_rng(seed)
        half = self.samples // 2
        samples = np.vstack([rng.dirichlet(np.asarray(counts, dtype=float), size=half), rng.dirichlet(np.ones(3), size=half)])
        log_norm = gammaln(sum(counts)) - sum(gammaln(value) for value in counts)
        log_p = log_norm + np.sum((np.asarray(counts) - 1.0) * np.log(samples), axis=1)
        tv = float(np.clip(np.mean(np.abs(np.tanh(0.5 * (log_p - math.log(2.0))))), 0.0, 1.0))
        self._GLOBAL_TV_CACHE[key] = tv
        return tv

    def score(self, alpha: np.ndarray) -> float:
        alpha = np.asarray(alpha, dtype=int)
        phi = alpha / float(alpha.sum())
        uncertainty = 1.0 - self.tv_distance(alpha)
        quality = (1.0 - uncertainty) * (phi[HIGH] + self.zeta * phi[UNCERTAIN])
        quality += uncertainty * (1.0 + self.zeta) / 3.0
        penalty = 1.0 - (1.0 - uncertainty) * phi[LOW]
        return float(np.clip(quality * penalty, 0.0, 1.0))


def candidate_seed(base_seed: int, task_id: int, worker_id: int) -> int:
    return int(np.random.SeedSequence([int(base_seed), int(task_id), int(worker_id), 0xA60D]).generate_state(1, dtype=np.uint32)[0])


def angular_scores(
    normalized_reports: np.ndarray,
    worker_ids: np.ndarray,
    anchor_worker_ids: set[int],
    task_id: int,
    base_seed: int,
    delta_cap: int,
    epsilon_d: float,
    mode: str = "rabod",
    guarded: bool = True,
) -> tuple[np.ndarray, bool, AngularDiagnostics]:
    if mode not in {"rabod", "exact_abod"}:
        raise ValueError(mode)
    reports = np.asarray(normalized_reports, dtype=float)
    ids = np.asarray(worker_ids, dtype=int)
    n = reports.shape[0]
    scores = np.full(n, np.nan, dtype=float)
    pair_evaluations = 0
    estimated_peak = 0
    effective_budget = n if mode == "exact_abod" else min(int(delta_cap), max(3, int(math.ceil(math.sqrt(n)))))
    if n < 3:
        return scores, False, AngularDiagnostics(mode, effective_budget, 0, 0, True, 0)
    centered = reports - reports.mean(axis=0, keepdims=True)
    if guarded and np.linalg.matrix_rank(centered, tol=epsilon_d) < 2:
        return scores, False, AngularDiagnostics(mode, effective_budget, 0, 0, True, centered.nbytes)
    anchor_indices = np.asarray([idx for idx, wid in enumerate(ids) if int(wid) in anchor_worker_ids], dtype=int)
    any_valid = False
    with np.errstate(all="ignore"):
        for candidate_idx, worker_id in enumerate(ids):
            candidates = anchor_indices[anchor_indices != candidate_idx]
            if candidates.size < 3:
                continue
            if mode == "rabod" and candidates.size > effective_budget:
                rng = np.random.default_rng(candidate_seed(base_seed, task_id, int(worker_id)))
                candidates = np.sort(rng.choice(candidates, size=effective_budget, replace=False))
            vectors = reports[candidates] - reports[candidate_idx]
            norms = np.linalg.norm(vectors, axis=1)
            if guarded:
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
            if guarded:
                pair_weights = 1.0 / ((norms[left] ** 2 + epsilon_d**2) * (norms[right] ** 2 + epsilon_d**2))
            else:
                pair_weights = 1.0 / ((norms[left] ** 2) * (norms[right] ** 2))
            estimated_peak = max(estimated_peak, vectors.nbytes + norms.nbytes + left.nbytes + right.nbytes + dot.nbytes + cosines.nbytes + pair_weights.nbytes)
            weight_sum = float(pair_weights.sum())
            if guarded and (not np.isfinite(weight_sum) or weight_sum <= 0.0):
                continue
            mean_cosine = float(np.dot(pair_weights, cosines) / weight_sum)
            score = float(np.dot(pair_weights, (cosines - mean_cosine) ** 2) / weight_sum)
            if guarded:
                if not np.isfinite(score):
                    continue
                score = float(np.clip(score, 0.0, 1.0))
            scores[candidate_idx] = score
            any_valid = any_valid or np.isfinite(score)
    available = bool(any_valid)
    return scores, available, AngularDiagnostics(mode, effective_budget, pair_evaluations, int(np.isfinite(scores).sum()), not available, int(estimated_peak))


def bounded_truth_discovery(
    reports: np.ndarray,
    epsilon: float,
    epsilon_w: float,
    max_iterations: int,
    protected: bool = True,
) -> TDResult:
    values = np.asarray(reports, dtype=float)
    if values.ndim != 2 or values.shape[0] == 0:
        return TDResult(None, 0, False, False, float("nan"), float("nan"))
    if protected and (values.shape[0] == 1 or np.allclose(values, values[0], rtol=0.0, atol=epsilon_w)):
        return TDResult(values[0].copy(), 0, True, bool(np.isfinite(values[0]).all()), 0.0, 0.0)
    truth = values.mean(axis=0)
    max_raw = 0.0
    norm_error = float("nan")
    with np.errstate(all="ignore"):
        for iteration in range(1, int(max_iterations) + 1):
            residuals = np.sum((values - truth) ** 2, axis=1)
            mean_residual = float(np.mean(residuals))
            floor = float(epsilon_w) if protected else 0.0
            raw = np.log1p((mean_residual + floor) / (residuals + mean_residual + floor))
            if protected:
                raw = np.where(np.isfinite(raw) & (raw > 0.0), raw, 1.0)
            raw_sum = float(raw.sum())
            weights = raw / raw_sum
            updated = weights @ values
            max_raw = max(max_raw, float(np.nanmax(raw)) if raw.size and np.isfinite(raw).any() else float("inf"))
            norm_error = float(abs(np.sum(weights) - 1.0))
            finite = bool(np.isfinite(updated).all() and np.isfinite(weights).all() and np.isfinite(raw).all())
            if not finite:
                return TDResult(None, iteration, False, False, max_raw, norm_error)
            if np.linalg.norm(updated - truth) <= epsilon * (1.0 + np.linalg.norm(truth)):
                return TDResult(updated, iteration, True, True, max_raw, norm_error)
            truth = updated
    finite = bool(np.isfinite(truth).all())
    return TDResult(truth if finite else None, int(max_iterations), False, finite, max_raw, norm_error)


class SequentialIRPP:
    def __init__(
        self,
        parameters: Parameters,
        scaler: Scaler,
        seed: int,
        delta_cap: Optional[int] = None,
        angular_mode: str = "rabod",
        thresholds: Optional[tuple[float, float]] = None,
    ):
        self.p = parameters
        self.scaler = scaler
        self.seed = int(seed)
        self.delta_cap = int(parameters.delta_max if delta_cap is None else delta_cap)
        self.angular_mode = angular_mode
        self.mu1, self.mu2 = thresholds if thresholds is not None else (parameters.mu1, parameters.mu2)
        self.states: Dict[int, np.ndarray] = {}
        self.reputation = DirichletReputation(parameters.zeta, parameters.tv_samples)

    def state(self, worker_id: int) -> np.ndarray:
        if worker_id not in self.states:
            self.states[worker_id] = np.ones(3, dtype=int)
        return self.states[worker_id]

    def score(self, worker_id: int) -> float:
        return self.reputation.score(self.state(worker_id))

    def process_task(self, task: Task) -> SequentialResult:
        p = self.p
        worker_ids = task.worker_ids
        raw = task.report_matrix
        normalized = self.scaler.transform(raw)
        before = {int(wid): self.score(int(wid)) for wid in worker_ids}
        mature = {
            int(wid) for wid in worker_ids
            if before[int(wid)] >= p.theta and int(self.state(int(wid)).sum() - 3) >= p.e_b
            and int(self.state(int(wid))[HIGH] - self.state(int(wid))[LOW]) >= p.q_b
        }
        provisional = {
            int(wid) for wid in worker_ids
            if int(self.state(int(wid))[HIGH] - self.state(int(wid))[LOW]) >= p.q_b and int(wid) not in mature
        }
        trusted = sorted(int(wid) for wid in worker_ids if int(wid) <= 50)
        seed_rng = np.random.default_rng(int(np.random.SeedSequence([self.seed, task.task_id, 0x5EED]).generate_state(1)[0]))
        seed_workers = set(int(x) for x in (seed_rng.choice(trusted, size=p.s_0, replace=False) if len(trusted) > p.s_0 else trusted))
        anchors = (seed_workers | mature | provisional) if len(mature) < p.n_b else mature
        scores, available, diagnostics = angular_scores(
            normalized, worker_ids, anchors, task.task_id, self.seed, self.delta_cap, p.epsilon_d, self.angular_mode, True
        )
        labels = np.full(worker_ids.size, UNCERTAIN, dtype=int)
        if available:
            valid = np.isfinite(scores)
            labels[valid & (scores >= self.mu1)] = HIGH
            labels[valid & (scores < self.mu2)] = LOW
        if available:
            reputations = np.asarray([before[int(wid)] for wid in worker_ids], dtype=float)
            retained = (labels == HIGH) | ((labels == UNCERTAIN) & (reputations >= p.theta))
        else:
            retained = np.ones(worker_ids.size, dtype=bool)
        td = bounded_truth_discovery(raw[retained], p.epsilon, p.epsilon_w, p.max_iterations, True) if retained.any() else TDResult(None, 0, False, False, 0.0, 0.0)
        for wid, label in zip(worker_ids, labels):
            self.state(int(wid))[int(label)] += 1
        return SequentialResult(td.truth, td.iterations, td.converged, scores, labels, retained, available, diagnostics, td)


def error_components(prediction: Optional[np.ndarray], truth: np.ndarray, scale: np.ndarray) -> tuple[float, int]:
    if prediction is None:
        return float("nan"), int(truth.size)
    normalized = (np.asarray(prediction, dtype=float) - truth) / scale
    return float(np.square(normalized).sum()), int(truth.size)


def screening_macro_f1(labels: np.ndarray, worker_ids: np.ndarray) -> float:
    true = np.where(np.asarray(worker_ids) <= 50, HIGH, LOW)
    pred = np.asarray(labels)
    values = []
    for target in (HIGH, LOW):
        tp = np.sum((pred == target) & (true == target))
        fp = np.sum((pred == target) & (true != target))
        fn = np.sum((pred != target) & (true == target))
        denom = 2 * tp + fp + fn
        values.append(0.0 if denom == 0 else 2.0 * tp / denom)
    return float(np.mean(values))


def synthetic_reports(n: int, dimension: int, seed: int, anchor_ratio: float = 0.7) -> tuple[np.ndarray, np.ndarray, set[int], np.ndarray]:
    rng = np.random.default_rng(int(seed))
    truth = rng.normal(0.0, 0.4, size=dimension)
    reports = truth + rng.normal(0.0, 0.08, size=(n, dimension))
    bad_count = max(1, int(round(0.12 * n)))
    reports[-bad_count:] += rng.normal(0.0, 0.55, size=(bad_count, dimension))
    ids = np.arange(1, n + 1, dtype=int)
    anchor_count = max(3, min(n, int(round(anchor_ratio * n))))
    anchors = set(int(x) for x in ids[:anchor_count])
    reputation = np.linspace(0.95, 0.2, n)
    return reports, ids, anchors, reputation


def full_analytics_once(reports: np.ndarray, ids: np.ndarray, anchors: set[int], reputation: np.ndarray, parameters: Parameters, seed: int = 20260808) -> tuple[TDResult, AngularDiagnostics]:
    scores, available, diagnostics = angular_scores(reports, ids, anchors, 1, seed, parameters.delta_max, parameters.epsilon_d, "rabod", True)
    labels = np.full(ids.size, UNCERTAIN, dtype=int)
    if available:
        valid = np.isfinite(scores)
        labels[valid & (scores >= parameters.mu1)] = HIGH
        labels[valid & (scores < parameters.mu2)] = LOW
        retained = (labels == HIGH) | ((labels == UNCERTAIN) & (reputation >= parameters.theta))
    else:
        retained = np.ones(ids.size, dtype=bool)
    if not retained.any():
        retained[:] = True
    return bounded_truth_discovery(reports[retained], parameters.epsilon, parameters.epsilon_w, parameters.max_iterations, True), diagnostics
