from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
import time
from pathlib import Path

import numpy as np

from .rq3_data import AttackReplay, Scaler
from .rq3_model import error_fields


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class RQ3Baselines:
    """In-memory adapters around the unchanged RQ1 baseline sources."""

    def __init__(self, root: Path, epsilon: float = 1e-5, max_iterations: int = 50):
        self.root = Path(root)
        self.epsilon = float(epsilon)
        self.max_iterations = int(max_iterations)
        self.crhn = _load_module("rq3_legacy_crhn", self.root / "CRH" / "CRH-N.py")
        self.qe = _load_module("rq3_legacy_qe", self.root / "QE" / "main_system.py")
        self.prtd = _load_module("rq3_legacy_prtd", self.root / "PRTD" / "main_system.py")

    @staticmethod
    def _task_dict(task, reports: np.ndarray, truth: np.ndarray) -> dict:
        return {
            "task_id": int(task.task_id),
            "task_true_data": np.asarray(truth, dtype=float).tolist(),
            "worker_submissions": [
                {"worker_id": int(report.worker_id), "submitted_data": values.tolist()}
                for report, values in zip(task.ordinary, np.asarray(reports, dtype=float))
            ],
        }

    def run(self, method: str, replay: AttackReplay, scaler: Scaler) -> tuple[dict, ...]:
        if method not in {"CRH-N", "QE", "PRTD"}:
            raise ValueError(method)
        qe_system = None
        prtd_system = None
        gamma_by_worker = None
        if method == "QE":
            qe_system = self.qe.CrowdSensingSystem(distance_threshold=4.0, proportion_threshold=0.31, epsilon=1e-12)
        elif method == "PRTD":
            prtd_system = self.prtd.CrowdSensingTruthDiscoveryAnalysis(
                epsilon=self.epsilon, max_iterations=self.max_iterations
            )
            all_workers = sorted({int(report.worker_id) for task in replay.tasks for report in task.ordinary})
            rng_state = np.random.get_state()
            np.random.seed(42)
            reputations = {worker_id: 0.6 + 0.3 * np.random.random() for worker_id in all_workers}
            np.random.set_state(rng_state)
            gamma = prtd_system.compute_reliability(np.asarray([reputations[wid] for wid in all_workers]))
            gamma_by_worker = dict(zip(all_workers, gamma))

        output = []
        for task in replay.tasks:
            reports = task.report_matrix
            prediction = None
            iterations = 0
            retained_count = 0
            started = time.perf_counter()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                if method == "CRH-N":
                    prediction, _, iterations, _, _ = self.crhn.crh_algorithm_optimized(
                        reports.tolist(), epsilon=self.epsilon, max_iterations=self.max_iterations
                    )
                    prediction = np.asarray(prediction, dtype=float)
                elif method == "QE":
                    normalized_reports = scaler.transform(reports)
                    normalized_truth = scaler.transform(task.truth)
                    record = self._task_dict(task, normalized_reports, normalized_truth)
                    prediction_norm, metrics = qe_system.process_task(record, task.task_id)
                    prediction = scaler.inverse_transform(np.asarray(prediction_norm, dtype=float)) if len(prediction_norm) else None
                    iterations = int(metrics.get("iterations", 0))
                    retained_count = int(metrics.get("normal_count", 0))
                else:
                    gamma = np.asarray([gamma_by_worker[int(report.worker_id)] for report in task.ordinary])
                    result = prtd_system.iterative_truth_discovery_single_task(reports, gamma, task.truth)
                    prediction = np.asarray(result["final_truth"], dtype=float)
                    iterations = int(result["iterations"])
                    retained_count = len(reports)
            runtime_s = time.perf_counter() - started
            output.append(
                {
                    "method": method,
                    "variant": method,
                    "scene": replay.scene,
                    "target_workers": replay.target_workers,
                    "seed": replay.seed,
                    "mode": replay.mode,
                    "malicious_ratio": replay.malicious_ratio,
                    "strength": replay.strength,
                    "task_id": task.task_id,
                    "participant_count": len(task.ordinary),
                    "runtime_s": float(runtime_s),
                    "iterations": int(iterations),
                    "retained_count": int(retained_count),
                    **error_fields(prediction, task.truth, scaler.scale),
                }
            )
        return tuple(output)
