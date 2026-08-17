from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping

import numpy as np


SCENES = {"Climate": 5, "Traffic": 6, "Water": 9}


@dataclass(frozen=True)
class IncidenceTask:
    task_id: int
    truth: np.ndarray
    worker_ids: np.ndarray


@dataclass(frozen=True)
class IncidenceWorkload:
    key: str
    scene: str
    target_workers: int
    path: Path
    sha256: str
    tasks: tuple[IncidenceTask, ...]


@dataclass(frozen=True)
class Report:
    worker_id: int
    values: np.ndarray
    error_mask: np.ndarray
    true_low: bool
    report_role: str

    @property
    def is_bad(self) -> bool:
        return bool(np.any(self.error_mask))


@dataclass(frozen=True)
class ReorganizedTask:
    task_id: int
    truth: np.ndarray
    ordinary: tuple[Report, ...]
    hq_seeds: tuple[Report, ...]
    random_extra: tuple[Report, ...]


@dataclass(frozen=True)
class ReorganizedReplay:
    key: str
    scene: str
    target_workers: int
    seed: int
    profile: str
    malicious_ratio: float
    switch_fraction: float
    switch_task: int
    tasks: tuple[ReorganizedTask, ...]
    initial_low_ids: frozenset[int]
    switched_ids: frozenset[int]
    final_low_ids: frozenset[int]
    activity_counts: Mapping[int, int]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_key(key: str) -> tuple[str, int]:
    scene, token = key.rsplit("_n", 1)
    if scene not in SCENES:
        raise ValueError(key)
    return scene, int(token)


def load_incidence(key: str, path: Path) -> IncidenceWorkload:
    scene, target = parse_key(key)
    payload = json.loads(path.read_text(encoding="utf-8"))
    tasks = []
    for task_key in sorted(payload["task_worker_data"], key=lambda x: int(x)):
        record = payload["task_worker_data"][task_key]
        truth = np.asarray(record["task_true_data"], dtype=float)
        ids = np.asarray([int(item["worker_id"]) for item in record["worker_submissions"]], dtype=int)
        if truth.size != SCENES[scene] or ids.size == 0:
            raise ValueError(f"Invalid workload record {key}/{task_key}")
        if np.any(ids < 1) or np.any(ids > 100):
            raise ValueError(f"Worker ID outside 1--100 in {key}/{task_key}")
        tasks.append(IncidenceTask(int(task_key), truth, ids))
    if len(tasks) != 100:
        raise ValueError(f"{key}: expected 100 ordered tasks")
    return IncidenceWorkload(key, scene, target, path, sha256_file(path), tuple(tasks))


def load_workloads(config: Mapping) -> Dict[str, IncidenceWorkload]:
    root = Path(config["data_root"])
    return {key: load_incidence(key, root / filename) for key, filename in config["data_files"].items()}


def activity_counts(workload: IncidenceWorkload, worker_ids: Iterable[int] = range(1, 101)) -> Dict[int, int]:
    counts = {int(worker_id): 0 for worker_id in worker_ids}
    for task in workload.tasks:
        for worker_id in task.worker_ids:
            if int(worker_id) in counts:
                counts[int(worker_id)] += 1
    return counts


def derived_seed(base_seed: int, *tokens: object) -> int:
    digest = hashlib.sha256("|".join(map(str, tokens)).encode("utf-8")).digest()
    token = int.from_bytes(digest[:4], "little")
    return int(np.random.SeedSequence([int(base_seed), token, 0x52513252]).generate_state(1, dtype=np.uint32)[0])


def activity_balanced_order(workload: IncidenceWorkload, seed: int, candidates: Iterable[int] = range(1, 101)) -> list[int]:
    """Return a deterministic order whose prefixes are activity-balanced.

    Workers are sorted by realized SUMO participation, split into up to ten
    adjacent strata, independently permuted, and then interleaved. For the
    100-worker pool, every 10-worker prefix contains one worker from each
    activity stratum; ratios in multiples of 0.1 are therefore exactly balanced.
    """
    candidate_list = sorted(set(int(x) for x in candidates))
    counts = activity_counts(workload, candidate_list)
    ordered = sorted(candidate_list, key=lambda wid: (counts[wid], wid))
    stratum_count = min(10, len(ordered))
    strata = [list(x) for x in np.array_split(np.asarray(ordered, dtype=int), stratum_count) if len(x)]
    rng = np.random.default_rng(derived_seed(seed, workload.key, "activity-label-order", tuple(candidate_list)))
    for stratum in strata:
        rng.shuffle(stratum)
    result = []
    for rank in range(max(map(len, strata))):
        for stratum in strata:
            if rank < len(stratum):
                result.append(int(stratum[rank]))
    return result


def choose_low_workers(workload: IncidenceWorkload, seed: int, ratio: float) -> frozenset[int]:
    if not 0.0 <= ratio <= 1.0:
        raise ValueError(ratio)
    count = int(round(100 * float(ratio)))
    return frozenset(activity_balanced_order(workload, seed)[:count])


def choose_switch_workers(
    workload: IncidenceWorkload,
    seed: int,
    candidates: Iterable[int],
    fraction: float,
    direction: str,
) -> frozenset[int]:
    candidates = sorted(set(int(x) for x in candidates))
    count = int(round(len(candidates) * float(fraction)))
    order = activity_balanced_order(workload, derived_seed(seed, direction), candidates)
    return frozenset(order[:count])


def low_ids_for_task(
    profile: str,
    task_id: int,
    initial_low: frozenset[int],
    switched: frozenset[int],
    switch_task: int,
) -> frozenset[int]:
    if task_id < switch_task or profile in {"stable", "ratio"}:
        return initial_low
    if profile == "h_to_l":
        return frozenset(initial_low | switched)
    if profile == "l_to_h":
        return frozenset(initial_low - switched)
    raise ValueError(profile)


def generate_values(truth: np.ndarray, low: bool, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Regenerate a submission using the legacy good/bad coordinate rule.

    A good worker submits bounded Gaussian noise within +/-1% of truth. A bad
    worker corrupts every coordinate by a signed 5%--20% deviation, matching
    the user's stable good-only/bad-only RQ2 population definition.
    """
    truth = np.asarray(truth, dtype=float)
    mask = np.full(truth.size, bool(low), dtype=bool)
    values = np.empty_like(truth)
    for idx, true_value in enumerate(truth):
        if low:
            magnitude = rng.uniform(abs(true_value) * 0.05, abs(true_value) * 0.20)
            values[idx] = true_value + magnitude if rng.random() >= 0.5 else true_value - magnitude
        else:
            std = abs(true_value) * 0.01 / 3.0
            sample = rng.normal(true_value, std)
            a, b = true_value * 0.99, true_value * 1.01
            values[idx] = np.clip(sample, min(a, b), max(a, b))
    return np.round(values, 2), mask


def _report(
    truth: np.ndarray,
    worker_id: int,
    low: bool,
    role: str,
    seed: int,
    workload_key: str,
    task_id: int,
    profile_key: str,
) -> Report:
    rng = np.random.default_rng(derived_seed(seed, workload_key, task_id, worker_id, profile_key, role))
    values, mask = generate_values(truth, low, rng)
    return Report(int(worker_id), values, mask, bool(low), role)


def make_replay(
    workload: IncidenceWorkload,
    seed: int,
    profile: str,
    malicious_ratio: float,
    switch_fraction: float,
    switch_task: int,
    hq_seed_ids: Iterable[int],
    random_extra_ids: Iterable[int],
    random_extra_reports_per_task: int,
) -> ReorganizedReplay:
    if profile not in {"stable", "ratio", "h_to_l", "l_to_h"}:
        raise ValueError(profile)
    initial_low = choose_low_workers(workload, seed, malicious_ratio)
    if profile == "h_to_l":
        switched = choose_switch_workers(workload, seed, set(range(1, 101)) - set(initial_low), switch_fraction, profile)
    elif profile == "l_to_h":
        switched = choose_switch_workers(workload, seed, initial_low, switch_fraction, profile)
    else:
        switched = frozenset()
    final_low = low_ids_for_task(profile, 100, initial_low, switched, switch_task)

    random_ids = tuple(int(x) for x in random_extra_ids)
    random_order = list(random_ids)
    rng_labels = np.random.default_rng(derived_seed(seed, workload.key, "random-extra-labels"))
    rng_labels.shuffle(random_order)
    random_low = set(random_order[: len(random_order) // 2])

    tasks = []
    for task in workload.tasks:
        task_low = low_ids_for_task(profile, task.task_id, initial_low, switched, switch_task)
        ordinary = tuple(
            _report(task.truth, int(wid), int(wid) in task_low, "ordinary", seed, workload.key, task.task_id, "ordinary-shared")
            for wid in task.worker_ids
        )
        hq = tuple(
            _report(task.truth, int(wid), False, "hq", seed, workload.key, task.task_id, "shared-hq")
            for wid in hq_seed_ids
        )
        rng_pick = np.random.default_rng(derived_seed(seed, workload.key, task.task_id, "random-extra-pick"))
        picked = rng_pick.choice(np.asarray(random_ids, dtype=int), size=random_extra_reports_per_task, replace=False)
        random_extra = tuple(
            _report(task.truth, int(wid), int(wid) in random_low, "random-extra", seed, workload.key, task.task_id, "shared-random-extra")
            for wid in picked
        )
        tasks.append(ReorganizedTask(task.task_id, task.truth, ordinary, hq, random_extra))

    return ReorganizedReplay(
        workload.key,
        workload.scene,
        workload.target_workers,
        int(seed),
        profile,
        float(malicious_ratio),
        float(switch_fraction),
        int(switch_task),
        tuple(tasks),
        initial_low,
        switched,
        final_low,
        activity_counts(workload),
    )


def load_frozen_context(config: Mapping) -> tuple[dict, dict]:
    rq1 = Path(config["rq1_root"])
    frozen = json.loads((rq1 / "results" / "frozen_parameters.json").read_text(encoding="utf-8"))
    manifest = json.loads((rq1 / "metadata" / "workload_manifest.json").read_text(encoding="utf-8"))
    return frozen, manifest
