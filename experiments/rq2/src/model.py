from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional

import numpy as np

from .core_base import (
    HIGH,
    LOW,
    UNCERTAIN,
    LABEL_NAMES,
    Parameters,
    ReputationScorer,
    bounded_truth_discovery,
    rabod_scores,
)


PREDICTED_HIGH = 0
PREDICTED_LOW = 1
PREDICTED_UNCERTAIN = -1


@dataclass(frozen=True)
class ProcessResult:
    prediction: Optional[np.ndarray]
    iterations: int
    converged: bool
    task_record: dict
    report_records: tuple[dict, ...]


def worker_class(alpha: np.ndarray, scorer: ReputationScorer, parameters: Parameters) -> int:
    alpha = np.asarray(alpha, dtype=int)
    evidence = int(alpha.sum() - 3)
    if evidence < parameters.e_b:
        return PREDICTED_UNCERTAIN
    details = scorer.details(alpha)
    if details.score >= parameters.theta and int(alpha[HIGH] - alpha[LOW]) >= parameters.q_b:
        return PREDICTED_HIGH
    if int(alpha[LOW] - alpha[HIGH]) >= parameters.q_b:
        return PREDICTED_LOW
    return PREDICTED_UNCERTAIN


class ReorganizedIRPPTD:
    """Closed-loop IRPP-TD with three explicit cold-start policies.

    Adaptive-HQ is the manuscript system. No-Extra replaces external high-
    quality reports with an all-ordinary temporary-anchor fallback only while
    fewer than n_b mature anchors exist. Random-Extra adds the same number of
    ordinary-quality reports as Adaptive-HQ but does not mark them as trusted.
    """

    STRATEGIES = {"Adaptive-HQ", "No-Extra", "Random-Extra"}

    def __init__(
        self,
        parameters: Parameters,
        center: np.ndarray,
        scale: np.ndarray,
        seed: int,
        strategy: str,
        forced_low_participations: Iterable[int] = (),
    ):
        if strategy not in self.STRATEGIES:
            raise ValueError(strategy)
        self.parameters = parameters
        self.center = np.asarray(center, dtype=float)
        self.scale = np.asarray(scale, dtype=float)
        self.seed = int(seed)
        self.strategy = strategy
        self.scorer = ReputationScorer(parameters, "full")
        self.forced_low_participations = set(int(x) for x in forced_low_participations)
        self.states: Dict[int, np.ndarray] = {}
        self.participations: Dict[int, int] = {}

    def state(self, worker_id: int) -> np.ndarray:
        worker_id = int(worker_id)
        if worker_id not in self.states:
            self.states[worker_id] = np.ones(3, dtype=int)
        return self.states[worker_id]

    def all_worker_predictions(self) -> Dict[int, int]:
        return {
            wid: worker_class(self.state(wid), self.scorer, self.parameters)
            for wid in range(1, 101)
        }

    def process_task(self, task) -> ProcessResult:
        p = self.parameters
        ordinary = tuple(task.ordinary)
        ordinary_ids = np.asarray([r.worker_id for r in ordinary], dtype=int)
        details_before = {int(wid): self.scorer.details(self.state(int(wid))) for wid in ordinary_ids}
        mature = {
            int(wid)
            for wid in ordinary_ids
            if worker_class(self.state(int(wid)), self.scorer, p) == PREDICTED_HIGH
        }
        provisional = {
            int(wid)
            for wid in ordinary_ids
            if int(self.state(int(wid))[HIGH] - self.state(int(wid))[LOW]) >= p.q_b and int(wid) not in mature
        }
        bootstrap_active = len(mature) < p.n_b

        if self.strategy == "Adaptive-HQ":
            extra = tuple(task.hq_seeds[: p.s_0]) if bootstrap_active else tuple()
            trusted_ids = {int(r.worker_id) for r in extra}
            anchors = (trusted_ids | mature | provisional) if bootstrap_active else mature
            temporary_fallback = False
        elif self.strategy == "No-Extra":
            extra = tuple()
            trusted_ids = set()
            anchors = mature | provisional
            temporary_fallback = bootstrap_active and len(anchors) < 4
            if temporary_fallback:
                anchors = set(int(x) for x in ordinary_ids)
        else:
            extra = tuple(task.random_extra[: p.s_0]) if bootstrap_active else tuple()
            trusted_ids = set()
            extra_ids = {int(r.worker_id) for r in extra}
            anchors = (mature | provisional | extra_ids) if bootstrap_active else mature
            temporary_fallback = bootstrap_active and len(anchors) < 4
            if temporary_fallback:
                anchors = set(int(x) for x in ordinary_ids) | extra_ids

        reports = ordinary + extra
        worker_ids = np.asarray([r.worker_id for r in reports], dtype=int)
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
            for idx, report in enumerate(reports):
                wid = int(report.worker_id)
                if wid in trusted_ids:
                    retained[idx] = True
                elif report.report_role == "ordinary":
                    retained[idx] = labels[idx] == HIGH or (
                        labels[idx] == UNCERTAIN and details_before[wid].score >= p.theta
                    )
                else:
                    # Random extra workers have no privileged registry state.
                    prior_score = self.scorer.details(np.ones(3, dtype=int)).score
                    retained[idx] = labels[idx] == HIGH or (labels[idx] == UNCERTAIN and prior_score >= p.theta)

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
            forced = (not report.true_low) and self.participations[wid] in self.forced_low_participations
            if forced:
                update_label = LOW
            self.state(wid)[update_label] += 1
            after = self.state(wid).copy()
            after_details = self.scorer.details(after)
            report_records.append(
                {
                    "worker_id": wid,
                    "true_low": bool(report.true_low),
                    "is_bad_report": bool(report.is_bad),
                    "participation_index": int(self.participations[wid]),
                    "angular_score": float(angle_scores[idx]) if np.isfinite(angle_scores[idx]) else np.nan,
                    "angular_valid": bool(np.isfinite(angle_scores[idx])),
                    "predicted_low_report": bool(labels[idx] == LOW),
                    "retained": bool(retained[idx]),
                    "mature_before": bool(wid in mature),
                    "provisional_before": bool(wid in provisional),
                    "anchor_before": bool(wid in anchors),
                    "forced_low_update": bool(forced),
                    "update_label": LABEL_NAMES[update_label],
                    "alpha_h_after": int(after[HIGH]),
                    "alpha_u_after": int(after[UNCERTAIN]),
                    "alpha_l_after": int(after[LOW]),
                    "psi_after": float(after_details.score),
                    "worker_prediction_after": int(worker_class(after, self.scorer, p)),
                }
            )

        ordinary_valid = np.isfinite(angle_scores[: len(ordinary)])
        ordinary_anchors = [r for r in ordinary if int(r.worker_id) in anchors]
        task_record = {
            "participant_count": len(ordinary),
            "extra_report_count": len(extra),
            "trusted_hq_count": len(trusted_ids),
            "active_anchor_count": len(anchors),
            "ordinary_anchor_count": len(ordinary_anchors),
            "ordinary_anchor_purity": (
                float(np.mean([not r.true_low for r in ordinary_anchors])) if ordinary_anchors else np.nan
            ),
            "mature_anchor_count": len(mature),
            "provisional_anchor_count": len(provisional),
            "bootstrap_active": bool(bootstrap_active),
            "temporary_fallback": bool(temporary_fallback),
            "angular_available": bool(angular_available),
            "angular_valid_count": int(np.sum(ordinary_valid)),
            "retained_ordinary_count": int(np.sum(retained[: len(ordinary)])),
            "retained_extra_count": int(np.sum(retained[len(ordinary) :])),
            "iterations": int(iterations),
            "converged": bool(converged),
        }
        return ProcessResult(prediction, iterations, converged, task_record, tuple(report_records))
