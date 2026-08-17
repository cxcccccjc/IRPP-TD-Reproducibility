from __future__ import annotations

import contextlib
import importlib.util
import io
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .rq3_data import AttackReplay


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@dataclass(frozen=True)
class RPPSThresholdCalibration:
    target_acceptance: float
    threshold: float
    clean_acceptance: float
    clean_retained: int
    clean_total: int
    policy: str = "clean-calibrated"


class CalibratedRPPSTDCFilter:
    """Sequential adapter for RPPS-TDC's native report-quality decision.

    The retained legacy TD and reputation-update modules are loaded unchanged.
    Only the native quality threshold ``p`` is selected on a separate clean
    replay (tasks 1--20); the selected value is then frozen for the complete
    attacked replay.  This adapter records report decisions and does not alter
    RPPS-TDC's reputation feedback.
    """

    def __init__(self, algorithm_root: Path):
        root = Path(algorithm_root) / "RPPS-TDC"
        self.truth_module = _load_module(
            "rq3_legacy_rpps_truth_discovery", root / "truth_discovery.py"
        )
        self.reputation_module = _load_module(
            "rq3_legacy_rpps_reputation_update", root / "reputation_update.py"
        )

    @staticmethod
    def _initial_state() -> dict[int, dict[str, float | int]]:
        return {
            worker_id: {
                "historical_reputation": 0.7,
                "non_updated_reputation": 0.7,
                "cheating_count": 0,
                "consecutive_good_tasks": 0,
            }
            for worker_id in range(1, 101)
        }

    def _native_weights(self, task) -> np.ndarray:
        worker_data = {
            int(report.worker_id): np.asarray(report.values, dtype=float).tolist()
            for report in task.ordinary
        }
        # Aggregation weights do not depend on reputation in the retained
        # RPPS-TDC implementation.  Equal placeholder reputations therefore
        # recover its exact native weights without affecting the later,
        # stateful quality assessment reproduced below.
        reputations = {worker_id: 0.7 for worker_id in worker_data}
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = self.truth_module.truth_discovery(
                worker_data=worker_data,
                worker_reputations=reputations,
                ground_truth=None,
                p=0.3,
                epsilon=1e-3,
                max_iterations=100,
            )
        weights = result[1]
        return np.asarray([weights[int(report.worker_id)] for report in task.ordinary], dtype=float)

    def precompute_weights(self, replay: AttackReplay) -> tuple[np.ndarray, ...]:
        return tuple(self._native_weights(task) for task in replay.tasks)

    @staticmethod
    def _retained_mask(task, weights: np.ndarray, state: dict, threshold: float) -> np.ndarray:
        worker_ids = [int(report.worker_id) for report in task.ordinary]
        reputations = np.asarray(
            [state[worker_id]["historical_reputation"] for worker_id in worker_ids],
            dtype=float,
        )
        max_reputation = float(np.max(reputations))
        highest = np.isclose(reputations, max_reputation, rtol=0.0, atol=0.0)
        highest_weight = float(np.mean(np.asarray(weights, dtype=float)[highest]))
        retained = np.empty(len(worker_ids), dtype=bool)
        for index, is_highest in enumerate(highest):
            if highest_weight != 0.0:
                relative_difference = abs(highest_weight - float(weights[index])) / abs(highest_weight)
            else:
                relative_difference = 0.0 if bool(is_highest) else float("inf")
            retained[index] = relative_difference < float(threshold)
        return retained

    def _update_state(self, task, retained: np.ndarray, state: dict) -> None:
        for report, is_good in zip(task.ordinary, retained):
            worker_id = int(report.worker_id)
            record = state[worker_id]
            if bool(is_good):
                record["consecutive_good_tasks"] += 1
                if record["consecutive_good_tasks"] >= 3:
                    if record["cheating_count"] > 0:
                        record["cheating_count"] -= 1
                    record["consecutive_good_tasks"] = 0
            else:
                record["consecutive_good_tasks"] = 0
                record["cheating_count"] += 1

            current, updated = self.reputation_module.reputation_update(
                is_good_data=bool(is_good),
                historical_reputation=float(record["historical_reputation"]),
                non_updated_reputation=float(record["non_updated_reputation"]),
                cheating_count=int(record["cheating_count"]),
                alpha=0.3,
                k1=1,
                k2=20,
            )
            record["historical_reputation"] = float(current)
            record["non_updated_reputation"] = float(updated)

    def _clean_acceptance(
        self, replay: AttackReplay, weights: tuple[np.ndarray, ...], threshold: float
    ) -> tuple[float, int, int]:
        state = self._initial_state()
        retained_count = 0
        total_count = 0
        for task, task_weights in zip(replay.tasks[:20], weights[:20]):
            retained = self._retained_mask(task, task_weights, state, threshold)
            retained_count += int(np.count_nonzero(retained))
            total_count += int(len(retained))
            self._update_state(task, retained, state)
        return retained_count / total_count, retained_count, total_count

    def calibrate(
        self,
        clean_replay: AttackReplay,
        target_acceptance: float = 0.96,
    ) -> tuple[RPPSThresholdCalibration, tuple[np.ndarray, ...]]:
        if clean_replay.mode != "clean" or clean_replay.malicious_ratio != 0.0:
            raise ValueError("RPPS-TDC calibration requires a separate clean replay")
        weights = self.precompute_weights(clean_replay)

        # The quality/reputation feedback makes the acceptance path piecewise
        # rather than a single static score quantile.  Search the native p-axis
        # sequentially and take the smallest clean-only threshold that reaches
        # the common acceptance target.
        coarse = np.concatenate(
            [np.arange(0.0, 2.0001, 0.005), np.arange(2.025, 10.0001, 0.025), [20.0, 50.0, 100.0]]
        )
        selected = None
        previous = 0.0
        for threshold in coarse:
            acceptance, retained, total = self._clean_acceptance(clean_replay, weights, float(threshold))
            if acceptance >= target_acceptance:
                selected = (float(threshold), acceptance, retained, total, previous)
                break
            previous = float(threshold)
        if selected is None:
            raise RuntimeError("RPPS-TDC clean acceptance target is unreachable")

        threshold, acceptance, retained, total, lower = selected
        if threshold > lower:
            for candidate in np.linspace(lower, threshold, 101)[1:]:
                candidate_acceptance, candidate_retained, candidate_total = self._clean_acceptance(
                    clean_replay, weights, float(candidate)
                )
                if candidate_acceptance >= target_acceptance:
                    threshold = float(candidate)
                    acceptance = float(candidate_acceptance)
                    retained = int(candidate_retained)
                    total = int(candidate_total)
                    break

        return (
            RPPSThresholdCalibration(
                float(target_acceptance), threshold, float(acceptance), int(retained), int(total),
                "clean-calibrated",
            ),
            weights,
        )

    def evaluate_fixed_threshold(
        self, clean_replay: AttackReplay, threshold: float
    ) -> RPPSThresholdCalibration:
        """Measure a declared native threshold on clean tasks without tuning it."""
        if clean_replay.mode != "clean" or clean_replay.malicious_ratio != 0.0:
            raise ValueError("RPPS-TDC threshold evaluation requires a clean replay")
        weights = self.precompute_weights(clean_replay)
        acceptance, retained, total = self._clean_acceptance(
            clean_replay, weights, float(threshold)
        )
        return RPPSThresholdCalibration(
            float("nan"), float(threshold), float(acceptance), int(retained), int(total),
            "native-fixed",
        )

    def run(
        self,
        replay: AttackReplay,
        calibration: RPPSThresholdCalibration,
    ) -> tuple[dict, ...]:
        weights = self.precompute_weights(replay)
        state = self._initial_state()
        output = []
        for task, task_weights in zip(replay.tasks, weights):
            retained = self._retained_mask(task, task_weights, state, calibration.threshold)
            active = np.asarray([report.attack_active for report in task.ordinary], dtype=bool)
            honest = ~active
            output.append(
                {
                    "method": "RPPS-TDC",
                    "variant": (
                        "Native-p=0.3" if calibration.policy == "native-fixed"
                        else "Clean-Calibrated-p"
                    ),
                    "scene": replay.scene,
                    "target_workers": replay.target_workers,
                    "seed": replay.seed,
                    "mode": replay.mode,
                    "malicious_ratio": replay.malicious_ratio,
                    "strength": replay.strength,
                    "task_id": task.task_id,
                    "gate_threshold": calibration.threshold,
                    "calibration_acceptance": calibration.clean_acceptance,
                    "malicious_total": int(np.count_nonzero(active)),
                    "malicious_retained": int(np.count_nonzero(active & retained)),
                    "honest_total": int(np.count_nonzero(honest)),
                    "honest_retained": int(np.count_nonzero(honest & retained)),
                }
            )
            self._update_state(task, retained, state)
        return tuple(output)
