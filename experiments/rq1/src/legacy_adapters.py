from __future__ import annotations

import contextlib
import importlib.util
import io
import logging
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional

import numpy as np

from .data_utils import RobustScaler, Task, Workload, sha256_file


os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")


@dataclass(frozen=True)
class LegacyTaskResult:
    prediction: Optional[np.ndarray]
    runtime_s: float
    iterations: int = 0
    retained_count: int = 0


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class LegacySuite:
    """Adapters around the user's retained baseline implementations.

    The adapters do not edit the original files.  They standardize input, suppress
    diagnostic printing, and return a common prediction/runtime record.
    """

    def __init__(self, algorithm_root: Path, epsilon: float = 1e-5, max_iterations: int = 50):
        self.root = Path(algorithm_root)
        self.epsilon = float(epsilon)
        self.max_iterations = int(max_iterations)
        self.crh = _load_module("rq1_legacy_crh", self.root / "CRH" / "CRH.py")
        self.crhn = _load_module("rq1_legacy_crhn", self.root / "CRH" / "CRH-N.py")
        self.qe = _load_module("rq1_legacy_qe", self.root / "QE" / "main_system.py")
        self.blind = _load_module("rq1_legacy_blind", self.root / "BLAND" / "mian_system.py")
        self.prtd = _load_module("rq1_legacy_prtd", self.root / "PRTD" / "main_system.py")
        self.rtd = _load_module("rq1_legacy_rtd", self.root / "RTD" / "main_system.py")

        # RPPS-TDC uses local absolute imports; load those names only for its module.
        td_path = self.root / "RPPS-TDC" / "truth_discovery.py"
        rep_path = self.root / "RPPS-TDC" / "reputation_update.py"
        previous_td = sys.modules.get("truth_discovery")
        previous_rep = sys.modules.get("reputation_update")
        _load_module("truth_discovery", td_path)
        _load_module("reputation_update", rep_path)
        self.rpps = _load_module("rq1_legacy_rpps", self.root / "RPPS-TDC" / "main_system.py")
        if previous_td is not None:
            sys.modules["truth_discovery"] = previous_td
        else:
            sys.modules.pop("truth_discovery", None)
        if previous_rep is not None:
            sys.modules["reputation_update"] = previous_rep
        else:
            sys.modules.pop("reputation_update", None)
        logging.disable(logging.CRITICAL)

    def source_manifest(self) -> dict:
        paths = {
            "CRH": self.root / "CRH" / "CRH.py",
            "CRH-N": self.root / "CRH" / "CRH-N.py",
            "QE": self.root / "QE" / "main_system.py",
            "RTD": self.root / "RTD" / "main_system.py",
            "BLIND": self.root / "BLAND" / "mian_system.py",
            "PRTD": self.root / "PRTD" / "main_system.py",
            "RPPS-TDC-main": self.root / "RPPS-TDC" / "main_system.py",
            "RPPS-TDC-TD": self.root / "RPPS-TDC" / "truth_discovery.py",
            "RPPS-TDC-reputation": self.root / "RPPS-TDC" / "reputation_update.py",
        }
        return {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in paths.items()}

    @staticmethod
    def _task_dict(task: Task, reports: Optional[np.ndarray] = None, truth: Optional[np.ndarray] = None) -> dict:
        matrix = task.report_matrix if reports is None else np.asarray(reports, dtype=float)
        target = task.truth if truth is None else np.asarray(truth, dtype=float)
        return {
            "task_id": task.task_id,
            "task_true_data": target.tolist(),
            "worker_submissions": [
                {"worker_id": int(worker_id), "submitted_data": values.tolist()}
                for worker_id, values in zip(task.worker_ids, matrix)
            ],
        }

    def _run_prtd(self, workload: Workload) -> Dict[int, LegacyTaskResult]:
        analyzer = self.prtd.CrowdSensingTruthDiscoveryAnalysis(
            epsilon=self.epsilon, max_iterations=self.max_iterations
        )
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            results = analyzer.analyze_all_tasks(str(workload.path))
        output = {}
        for record in results["task_results"]:
            output[int(record["task_id"])] = LegacyTaskResult(
                prediction=np.asarray(record["predicted_value"], dtype=float),
                runtime_s=float(record["execution_time"]),
                iterations=int(record["iterations"]),
                retained_count=0,
            )
        return output

    def run_dataset(self, method: str, workload: Workload, scaler: RobustScaler) -> Dict[int, LegacyTaskResult]:
        if method == "PRTD":
            return self._run_prtd(workload)

        qe_system = None
        rtd_system = None
        rpps_system = None
        if method == "QE":
            qe_system = self.qe.CrowdSensingSystem(
                distance_threshold=4.0, proportion_threshold=0.31, epsilon=1e-12
            )
        elif method == "RTD":
            rtd_system = self.rtd.ReputationBasedTruthDiscovery(
                epsilon=self.epsilon, max_iterations=self.max_iterations
            )
        elif method == "RPPS-TDC":
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rpps_system = self.rpps.WorkerReputationSystem(str(workload.path))

        output: Dict[int, LegacyTaskResult] = {}
        for task_index, task in enumerate(workload.tasks):
            reports = task.report_matrix
            start = time.perf_counter()
            iterations = 0
            retained_count = 0
            prediction: Optional[np.ndarray]
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                if method == "Mean":
                    prediction = reports.mean(axis=0)
                elif method == "Median":
                    prediction = np.median(reports, axis=0)
                elif method == "CRH":
                    prediction, _, iterations, _, _ = self.crh.crh_algorithm_optimized(
                        reports.tolist(), epsilon=self.epsilon, max_iterations=self.max_iterations
                    )
                    prediction = np.asarray(prediction, dtype=float)
                elif method == "CRH-N":
                    prediction, _, iterations, _, _ = self.crhn.crh_algorithm_optimized(
                        reports.tolist(), epsilon=self.epsilon, max_iterations=self.max_iterations
                    )
                    prediction = np.asarray(prediction, dtype=float)
                elif method == "QE":
                    normalized_reports = scaler.transform(reports)
                    normalized_truth = scaler.transform(task.truth)
                    normalized_task = self._task_dict(task, normalized_reports, normalized_truth)
                    prediction_norm, metrics = qe_system.process_task(normalized_task, task.task_id)
                    prediction = scaler.inverse_transform(np.asarray(prediction_norm, dtype=float))
                    iterations = int(metrics.get("iterations", 0))
                    retained_count = int(metrics.get("normal_count", 0))
                elif method == "RTD":
                    prediction, _, history = rtd_system.process_single_task(
                        self._task_dict(task), task_index
                    )
                    prediction = np.asarray(prediction, dtype=float)
                    iterations = len(history)
                elif method == "BLIND":
                    record = self._task_dict(task)
                    normal_indices, iterations = self.blind.cluster_worker_data(record["worker_submissions"])
                    prediction = self.blind.calculate_aggregated_data(
                        record["worker_submissions"], normal_indices
                    )
                    prediction = None if prediction is None else np.asarray(prediction, dtype=float)
                    retained_count = len(normal_indices)
                elif method == "RPPS-TDC":
                    result = rpps_system.process_single_task(str(task.task_id))
                    error_metrics = result.get("error_metrics") or {}
                    good_average = error_metrics.get("good_workers_average")
                    if good_average is not None:
                        prediction = np.asarray(good_average, dtype=float)
                        retained_count = int(error_metrics.get("good_workers_count", 0))
                    else:
                        prediction = np.asarray(result["aggregated_truth"], dtype=float)
                    iterations = int(result.get("iteration_count", 0))
                else:
                    raise ValueError(f"Unknown baseline method: {method}")
            runtime = time.perf_counter() - start
            output[task.task_id] = LegacyTaskResult(
                prediction=prediction,
                runtime_s=float(runtime),
                iterations=int(iterations),
                retained_count=int(retained_count),
            )
        return output
