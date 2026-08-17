from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from dataclasses import dataclass
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


@dataclass(frozen=True)
class GateCalibration:
    target_acceptance: float
    qe_radius: float
    qe_clean_acceptance: float
    prtd_relative_weight: float
    prtd_clean_acceptance: float


class CalibratedBaselineGates:
    """Calibration-only screening adapters for QE and PRTD.

    Each gate is fitted on clean tasks 1--20 and then frozen.  QE retains its
    native support rule and calibrates only the distance radius.  PRTD gates
    the normalized effective weight produced by its own final update, then
    reruns the unchanged aggregator on the retained reports.
    """

    def __init__(self, root: Path, epsilon: float = 1e-5, max_iterations: int = 50):
        self.root = Path(root)
        self.epsilon = float(epsilon)
        self.max_iterations = int(max_iterations)
        self.qe = _load_module("rq3_calibrated_qe", self.root / "QE" / "main_system.py")
        self.prtd = _load_module("rq3_calibrated_prtd", self.root / "PRTD" / "main_system.py")

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

    @staticmethod
    def qe_retained_mask(normalized_reports: np.ndarray, radius: float, mu: float = 0.31) -> np.ndarray:
        reports = np.asarray(normalized_reports, dtype=float)
        n = len(reports)
        if n <= 2:
            return np.ones(n, dtype=bool)
        squared = np.sum((reports[:, None, :] - reports[None, :, :]) ** 2, axis=2)
        close = np.count_nonzero(squared <= float(radius) ** 2, axis=1) - 1
        return close / (n - 1) > float(mu)

    def _prtd_system(self):
        return self.prtd.CrowdSensingTruthDiscoveryAnalysis(
            epsilon=self.epsilon, max_iterations=self.max_iterations
        )

    def _gamma_by_worker(self, replay: AttackReplay) -> dict[int, float]:
        system = self._prtd_system()
        all_workers = sorted({int(report.worker_id) for task in replay.tasks for report in task.ordinary})
        rng_state = np.random.get_state()
        np.random.seed(42)
        reputations = np.asarray([0.6 + 0.3 * np.random.random() for _ in all_workers])
        np.random.set_state(rng_state)
        gamma = system.compute_reliability(reputations)
        return dict(zip(all_workers, gamma))

    @staticmethod
    def prtd_relative_weights(
        reports: np.ndarray, gamma: np.ndarray, final_truth: np.ndarray, eps: float = 1e-12
    ) -> np.ndarray:
        reports = np.asarray(reports, dtype=float)
        gamma = np.asarray(gamma, dtype=float)
        final_truth = np.asarray(final_truth, dtype=float)
        distances = np.maximum(np.sum(np.abs(reports - final_truth), axis=1), eps)
        total = max(float(np.sum(gamma * distances)), eps)
        omega = np.zeros(len(reports), dtype=float)
        valid = gamma > 0
        omega[valid] = np.log(total) - np.log(np.maximum(gamma[valid] * distances[valid], eps))
        if np.any(valid):
            omega -= float(np.min(omega[valid]))
        weights = np.maximum(gamma * omega, 0.0)
        weight_sum = float(weights.sum())
        if weight_sum <= eps:
            return np.ones(len(reports), dtype=float)
        return len(reports) * weights / weight_sum

    def calibrate(
        self, clean_replay: AttackReplay, scaler: Scaler, target_acceptance: float = 0.96
    ) -> GateCalibration:
        if clean_replay.mode != "clean" or clean_replay.malicious_ratio != 0.0:
            raise ValueError("Calibration requires a clean replay")
        calibration_tasks = clean_replay.tasks[:20]

        normalized = [scaler.transform(task.report_matrix) for task in calibration_tasks]
        max_distance = 0.0
        for reports in normalized:
            if len(reports) > 1:
                distances = np.sqrt(np.sum((reports[:, None, :] - reports[None, :, :]) ** 2, axis=2))
                max_distance = max(max_distance, float(np.max(distances)))
        low, high = 0.0, max(max_distance, 1e-12)
        for _ in range(60):
            radius = (low + high) / 2.0
            accepted = np.concatenate([self.qe_retained_mask(x, radius) for x in normalized]).mean()
            if accepted >= target_acceptance:
                high = radius
            else:
                low = radius
        qe_radius = float(np.nextafter(high, np.inf))
        qe_acceptance = float(
            np.concatenate([self.qe_retained_mask(x, qe_radius) for x in normalized]).mean()
        )

        prtd = self._prtd_system()
        gamma_by_worker = self._gamma_by_worker(clean_replay)
        relative_weights = []
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for task in calibration_tasks:
                gamma = np.asarray([gamma_by_worker[int(report.worker_id)] for report in task.ordinary])
                result = prtd.iterative_truth_discovery_single_task(task.report_matrix, gamma, task.truth)
                relative_weights.extend(
                    self.prtd_relative_weights(task.report_matrix, gamma, result["final_truth"]).tolist()
                )
        relative_weights = np.asarray(relative_weights, dtype=float)
        # ``higher`` avoids a zero threshold when one zero-weight report per
        # task creates a calibration tie; the resulting acceptance is the
        # nearest conservative realization of the declared 96% budget.
        threshold = float(np.quantile(relative_weights, 1.0 - target_acceptance, method="higher"))
        prtd_acceptance = float(np.mean(relative_weights >= threshold))
        return GateCalibration(
            float(target_acceptance), qe_radius, qe_acceptance, threshold, prtd_acceptance
        )

    @staticmethod
    def _count_roles(task, retained: np.ndarray) -> dict[str, int]:
        active = np.asarray([report.attack_active for report in task.ordinary], dtype=bool)
        honest = ~active
        return {
            "malicious_total": int(active.sum()),
            "malicious_retained": int(np.count_nonzero(active & retained)),
            "honest_total": int(honest.sum()),
            "honest_retained": int(np.count_nonzero(honest & retained)),
            "retained_count": int(retained.sum()),
        }

    def run(
        self, method: str, replay: AttackReplay, scaler: Scaler, calibration: GateCalibration
    ) -> tuple[dict, ...]:
        if method not in {"QE", "PRTD"}:
            raise ValueError(method)
        output = []
        if method == "QE":
            system = self.qe.CrowdSensingSystem(
                distance_threshold=calibration.qe_radius,
                proportion_threshold=0.31,
                epsilon=1e-12,
            )
            for task in replay.tasks:
                normalized_reports = scaler.transform(task.report_matrix)
                normalized_truth = scaler.transform(task.truth)
                record = self._task_dict(task, normalized_reports, normalized_truth)
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    prediction_norm, metrics = system.process_task(record, task.task_id)
                outliers = set(int(i) for i in metrics.get("outlier_indices", []))
                retained = np.asarray([i not in outliers for i in range(len(task.ordinary))], dtype=bool)
                if not np.any(retained):
                    retained[:] = True  # QE's declared all-outlier fallback uses all reports.
                prediction = (
                    scaler.inverse_transform(np.asarray(prediction_norm, dtype=float))
                    if len(prediction_norm)
                    else None
                )
                output.append({
                    "method": method,
                    "variant": "Clean-Calibrated",
                    "scene": replay.scene,
                    "target_workers": replay.target_workers,
                    "seed": replay.seed,
                    "mode": replay.mode,
                    "malicious_ratio": replay.malicious_ratio,
                    "strength": replay.strength,
                    "task_id": task.task_id,
                    "gate_threshold": calibration.qe_radius,
                    "calibration_acceptance": calibration.qe_clean_acceptance,
                    **self._count_roles(task, retained),
                    **error_fields(prediction, task.truth, scaler.scale),
                })
            return tuple(output)

        prtd = self._prtd_system()
        gamma_by_worker = self._gamma_by_worker(replay)
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            for task in replay.tasks:
                reports = task.report_matrix
                gamma = np.asarray([gamma_by_worker[int(report.worker_id)] for report in task.ordinary])
                first = prtd.iterative_truth_discovery_single_task(reports, gamma, task.truth)
                score = self.prtd_relative_weights(reports, gamma, first["final_truth"])
                retained = score >= calibration.prtd_relative_weight
                if not np.any(retained):
                    retained[int(np.argmax(score))] = True
                second = prtd.iterative_truth_discovery_single_task(
                    reports[retained], gamma[retained], task.truth
                )
                output.append({
                    "method": method,
                    "variant": "Clean-Calibrated",
                    "scene": replay.scene,
                    "target_workers": replay.target_workers,
                    "seed": replay.seed,
                    "mode": replay.mode,
                    "malicious_ratio": replay.malicious_ratio,
                    "strength": replay.strength,
                    "task_id": task.task_id,
                    "gate_threshold": calibration.prtd_relative_weight,
                    "calibration_acceptance": calibration.prtd_clean_acceptance,
                    **self._count_roles(task, retained),
                    **error_fields(second["final_truth"], task.truth, scaler.scale),
                })
        return tuple(output)
