from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping

import numpy as np


SCENE_INFO = {
    "Climate": {
        "scene": 1,
        "features": ["Pressure", "Potential temperature", "Humidity", "Air density", "Wind direction"],
        "processed_records": 420_551,
    },
    "Traffic": {
        "scene": 2,
        "features": ["Medium", "Heavy", "Micro", "Long", "Total", "Light vehicle flow"],
        "processed_records": 809,
    },
    "Water": {
        "scene": 3,
        "features": ["pH", "Hardness", "Solids", "Chloramines", "Sulfate", "Conductivity", "Organic carbon", "Trihalomethanes", "Turbidity"],
        "processed_records": 2_089,
    },
}


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
        return np.vstack([submission.values for submission in self.submissions])

    @property
    def worker_ids(self) -> np.ndarray:
        return np.asarray([submission.worker_id for submission in self.submissions], dtype=int)


@dataclass(frozen=True)
class Workload:
    key: str
    scene: str
    target_workers: int
    path: Path
    tasks: tuple[Task, ...]
    sha256: str

    @property
    def dimension(self) -> int:
        return int(self.tasks[0].truth.size)

    @property
    def participant_counts(self) -> np.ndarray:
        return np.asarray([len(task.submissions) for task in self.tasks], dtype=int)


@dataclass(frozen=True)
class RobustScaler:
    center: np.ndarray
    scale: np.ndarray

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (np.asarray(values, dtype=float) - self.center) / self.scale

    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        return np.asarray(values, dtype=float) * self.scale + self.center


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _parse_key(key: str) -> tuple[str, int]:
    scene, worker_token = key.rsplit("_n", 1)
    if scene not in SCENE_INFO:
        raise ValueError(f"Unknown scene in workload key: {key}")
    return scene, int(worker_token)


def load_workload(key: str, path: Path) -> Workload:
    scene, target_workers = _parse_key(key)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    tasks: List[Task] = []
    for task_key in sorted(payload["task_worker_data"], key=lambda item: int(item)):
        record = payload["task_worker_data"][task_key]
        truth = np.asarray(record["task_true_data"], dtype=float)
        submissions = tuple(
            Submission(int(item["worker_id"]), np.asarray(item["submitted_data"], dtype=float))
            for item in record["worker_submissions"]
        )
        if not submissions:
            raise ValueError(f"{path.name}: task {task_key} has no submissions")
        if any(sub.values.shape != truth.shape for sub in submissions):
            raise ValueError(f"{path.name}: task {task_key} has inconsistent dimensions")
        tasks.append(Task(int(task_key), truth, submissions))
    if len(tasks) != 100:
        raise ValueError(f"{path.name}: expected 100 tasks, found {len(tasks)}")
    return Workload(key, scene, target_workers, path, tuple(tasks), sha256_file(path))


def load_workloads(config: Mapping) -> Dict[str, Workload]:
    algorithm_root = Path(config["data_root"])
    return {
        key: load_workload(key, algorithm_root / filename)
        for key, filename in config["data_files"].items()
    }


def fit_scene_scalers(workloads: Mapping[str, Workload], calibration_tasks: int) -> Dict[str, RobustScaler]:
    scalers: Dict[str, RobustScaler] = {}
    for scene in SCENE_INFO:
        matrices = []
        for workload in workloads.values():
            if workload.scene != scene:
                continue
            matrices.extend(task.report_matrix for task in workload.tasks[:calibration_tasks])
        values = np.vstack(matrices)
        center = np.median(values, axis=0)
        q05, q95 = np.quantile(values, [0.05, 0.95], axis=0)
        scale = q95 - q05
        fallback = np.std(values, axis=0)
        scale = np.where(scale > 1e-12, scale, np.where(fallback > 1e-12, fallback, 1.0))
        scalers[scene] = RobustScaler(center=center, scale=scale)
    return scalers


def workload_manifest(workloads: Mapping[str, Workload], scalers: Mapping[str, RobustScaler]) -> dict:
    records = {}
    for key, workload in workloads.items():
        counts = workload.participant_counts
        records[key] = {
            "path": str(workload.path),
            "sha256": workload.sha256,
            "scene": workload.scene,
            "target_workers": workload.target_workers,
            "task_count": len(workload.tasks),
            "dimension": workload.dimension,
            "participants_min": int(counts.min()),
            "participants_mean": float(counts.mean()),
            "participants_median": float(np.median(counts)),
            "participants_max": int(counts.max()),
            "feature_names": SCENE_INFO[workload.scene]["features"],
            "processed_records": SCENE_INFO[workload.scene]["processed_records"],
            "normalization_center": scalers[workload.scene].center.tolist(),
            "normalization_scale_q95_minus_q05": scalers[workload.scene].scale.tolist(),
        }
    return records


def dump_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
