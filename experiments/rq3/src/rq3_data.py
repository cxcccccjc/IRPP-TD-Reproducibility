from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping

import numpy as np


SCENE_DIMENSIONS = {"Climate": 5, "Traffic": 6, "Water": 9}
RQ3_ROOT = Path(__file__).resolve().parents[1]


def resolve_config_path(config: Mapping, key: str) -> Path:
    path = Path(config[key])
    return path if path.is_absolute() else (RQ3_ROOT / path).resolve()


@dataclass(frozen=True)
class Scaler:
    center: np.ndarray
    scale: np.ndarray

    def transform(self, values: np.ndarray) -> np.ndarray:
        return (np.asarray(values, dtype=float) - self.center) / self.scale

    def inverse_transform(self, values: np.ndarray) -> np.ndarray:
        return np.asarray(values, dtype=float) * self.scale + self.center


@dataclass(frozen=True)
class IncidenceTask:
    task_id: int
    truth: np.ndarray
    worker_ids: np.ndarray
    original_reports: np.ndarray


@dataclass(frozen=True)
class IncidenceWorkload:
    key: str
    scene: str
    target_workers: int
    path: Path
    sha256: str
    tasks: tuple[IncidenceTask, ...]


@dataclass(frozen=True)
class AttackReport:
    worker_id: int
    values: np.ndarray
    coalition_member: bool
    attack_active: bool
    report_role: str

    @property
    def is_poisoned(self) -> bool:
        return bool(self.attack_active)

    @property
    def scheduled_p(self) -> float:
        """Compatibility flag used by the frozen RQ2 implementation.

        RQ3 has deterministic worker roles instead of a scheduled error
        probability: zero denotes an honest report and one an active poison.
        """
        return 1.0 if self.attack_active else 0.0

    @property
    def is_bad(self) -> bool:
        return bool(self.attack_active)

    @property
    def error_mask(self) -> np.ndarray:
        return np.full(self.values.size, self.attack_active, dtype=bool)


@dataclass(frozen=True)
class AttackTask:
    task_id: int
    truth: np.ndarray
    ordinary: tuple[AttackReport, ...]
    hq_seeds: tuple[AttackReport, ...]

    @property
    def report_matrix(self) -> np.ndarray:
        return np.vstack([item.values for item in self.ordinary])

    @property
    def worker_ids(self) -> np.ndarray:
        return np.asarray([item.worker_id for item in self.ordinary], dtype=int)

    @property
    def seeds(self) -> tuple[AttackReport, ...]:
        return self.hq_seeds


@dataclass(frozen=True)
class AttackReplay:
    key: str
    scene: str
    target_workers: int
    seed: int
    mode: str
    malicious_ratio: float
    strength: float
    malicious_ids: frozenset[int]
    tasks: tuple[AttackTask, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def derived_seed(base_seed: int, *tokens: object) -> int:
    payload = "|".join(map(str, tokens)).encode("utf-8")
    token = int.from_bytes(hashlib.sha256(payload).digest()[:4], "little")
    return int(np.random.SeedSequence([int(base_seed), token, 0x525133]).generate_state(1, dtype=np.uint32)[0])


def _parse_key(key: str) -> tuple[str, int]:
    scene, token = key.rsplit("_n", 1)
    if scene not in SCENE_DIMENSIONS:
        raise ValueError(key)
    return scene, int(token)


def load_workload(key: str, path: Path) -> IncidenceWorkload:
    scene, target = _parse_key(key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = []
    for task_key in sorted(payload["task_worker_data"], key=lambda item: int(item)):
        record = payload["task_worker_data"][task_key]
        truth = np.asarray(record["task_true_data"], dtype=float)
        ids = np.asarray([int(item["worker_id"]) for item in record["worker_submissions"]], dtype=int)
        reports = np.asarray([item["submitted_data"] for item in record["worker_submissions"]], dtype=float)
        if truth.size != SCENE_DIMENSIONS[scene] or reports.shape != (ids.size, truth.size):
            raise ValueError(f"Invalid record {key}/{task_key}")
        if np.any(ids < 1) or np.any(ids > 100):
            raise ValueError(f"Worker ID outside 1--100 in {key}/{task_key}")
        tasks.append(IncidenceTask(int(task_key), truth, ids, reports))
    if len(tasks) != 100:
        raise ValueError(f"{key}: expected 100 tasks")
    return IncidenceWorkload(key, scene, target, path, sha256_file(path), tuple(tasks))


def load_workloads(config: Mapping) -> Dict[str, IncidenceWorkload]:
    root = resolve_config_path(config, "workload_root")
    return {key: load_workload(key, root / filename) for key, filename in config["data_files"].items()}


def load_scalers(config: Mapping) -> Dict[str, Scaler]:
    manifest_path = resolve_config_path(config, "rq1_root") / "metadata" / "workload_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scalers = {}
    for scene in SCENE_DIMENSIONS:
        record = manifest[f"{scene}_n27"]
        scalers[scene] = Scaler(
            np.asarray(record["normalization_center"], dtype=float),
            np.asarray(record["normalization_scale_q95_minus_q05"], dtype=float),
        )
    return scalers


def calibration_directions(
    workloads: Mapping[str, IncidenceWorkload], scalers: Mapping[str, Scaler], calibration_tasks: int
) -> Dict[str, np.ndarray]:
    directions: Dict[str, np.ndarray] = {}
    for scene in SCENE_DIMENSIONS:
        rows = []
        for workload in workloads.values():
            if workload.scene == scene:
                rows.extend(scalers[scene].transform(task.original_reports) for task in workload.tasks[:calibration_tasks])
        matrix = np.vstack(rows)
        matrix -= matrix.mean(axis=0, keepdims=True)
        _, _, vt = np.linalg.svd(matrix, full_matrices=False)
        direction = vt[0].astype(float)
        if float(direction.sum()) < 0.0:
            direction *= -1.0
        direction *= np.sqrt(direction.size) / np.linalg.norm(direction)
        directions[scene] = direction
    return directions


def activity_counts(workload: IncidenceWorkload, candidates: Iterable[int] = range(1, 101)) -> Dict[int, int]:
    counts = {int(worker_id): 0 for worker_id in candidates}
    for task in workload.tasks:
        for worker_id in task.worker_ids:
            if int(worker_id) in counts:
                counts[int(worker_id)] += 1
    return counts


def activity_balanced_order(workload: IncidenceWorkload, seed: int) -> list[int]:
    counts = activity_counts(workload)
    ordered = sorted(counts, key=lambda wid: (counts[wid], wid))
    strata = [list(items) for items in np.array_split(np.asarray(ordered, dtype=int), 10)]
    rng = np.random.default_rng(derived_seed(seed, workload.key, "malicious-order"))
    for stratum in strata:
        rng.shuffle(stratum)
    result = []
    for rank in range(max(map(len, strata))):
        for stratum in strata:
            if rank < len(stratum):
                result.append(int(stratum[rank]))
    return result


def choose_malicious(workload: IncidenceWorkload, seed: int, ratio: float) -> frozenset[int]:
    if not 0.0 <= ratio <= 1.0:
        raise ValueError(ratio)
    count = int(round(100.0 * float(ratio)))
    return frozenset(activity_balanced_order(workload, seed)[:count])


def honest_value(truth: np.ndarray, seed: int, *tokens: object) -> np.ndarray:
    truth = np.asarray(truth, dtype=float)
    rng = np.random.default_rng(derived_seed(seed, *tokens, "honest"))
    sigma = np.maximum(np.abs(truth) * 0.01 / 3.0, 1e-12)
    sample = rng.normal(truth, sigma)
    lower = np.minimum(truth * 0.99, truth * 1.01)
    upper = np.maximum(truth * 0.99, truth * 1.01)
    return np.clip(sample, lower, upper)


def attack_is_active(mode: str, task_id: int, onoff_blocks: Iterable[Iterable[int]], mature_task: int) -> bool:
    if mode in {"independent", "compact"}:
        return True
    if mode == "onoff":
        return any(int(start) <= task_id <= int(end) for start, end in onoff_blocks)
    if mode == "mature_anchor":
        return task_id >= int(mature_task)
    if mode == "clean":
        return False
    raise ValueError(mode)


def make_replay(
    workload: IncidenceWorkload,
    scaler: Scaler,
    direction: np.ndarray,
    seed: int,
    mode: str,
    malicious_ratio: float,
    strength: float,
    hq_seed_ids: Iterable[int],
    onoff_blocks: Iterable[Iterable[int]],
    mature_task: int,
) -> AttackReplay:
    malicious_ids = choose_malicious(workload, seed, malicious_ratio)
    tasks = []
    for task in workload.tasks:
        honest = {
            int(wid): honest_value(task.truth, seed, workload.key, task.task_id, int(wid), "ordinary")
            for wid in task.worker_ids
        }
        active = attack_is_active(mode, task.task_id, onoff_blocks, mature_task)
        active_ids = [int(wid) for wid in task.worker_ids if int(wid) in malicious_ids and active]
        coalition_target = None
        if active_ids and mode in {"compact", "onoff", "mature_anchor"}:
            normalized_honest = np.vstack([scaler.transform(honest[wid]) for wid in active_ids])
            coalition_target = np.median(normalized_honest, axis=0) + float(strength) * direction

        ordinary = []
        for worker_id in task.worker_ids:
            wid = int(worker_id)
            value = honest[wid].copy()
            attack_active = wid in malicious_ids and active
            if attack_active and mode == "independent":
                rng = np.random.default_rng(derived_seed(seed, workload.key, task.task_id, wid, "independent"))
                attack_direction = rng.choice(np.asarray([-1.0, 1.0]), size=value.size)
                normalized = scaler.transform(value) + float(strength) * attack_direction
                value = scaler.inverse_transform(normalized)
            elif attack_active:
                rng = np.random.default_rng(derived_seed(seed, workload.key, task.task_id, wid, mode, "jitter"))
                jitter = rng.normal(0.0, max(1e-9, 0.02 * float(strength)), size=value.size)
                value = scaler.inverse_transform(coalition_target + jitter)
            ordinary.append(AttackReport(wid, value, wid in malicious_ids, attack_active, "ordinary"))

        hq = tuple(
            AttackReport(
                int(wid),
                honest_value(task.truth, seed, workload.key, task.task_id, int(wid), "hq"),
                False,
                False,
                "hq",
            )
            for wid in hq_seed_ids
        )
        tasks.append(AttackTask(task.task_id, task.truth, tuple(ordinary), hq))
    return AttackReplay(
        workload.key,
        workload.scene,
        workload.target_workers,
        int(seed),
        mode,
        float(malicious_ratio),
        float(strength),
        malicious_ids,
        tuple(tasks),
    )


def active_evaluation_tasks(mode: str) -> set[int]:
    if mode in {"independent", "compact", "clean"}:
        return set(range(21, 101))
    if mode == "onoff":
        return set(range(21, 31)) | set(range(41, 51)) | set(range(61, 71)) | set(range(81, 91))
    if mode == "mature_anchor":
        return set(range(41, 101))
    raise ValueError(mode)
