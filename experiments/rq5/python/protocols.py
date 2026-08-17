"""Complete off-chain protocol reproductions for the matched RQ5 workload."""

from __future__ import annotations

import math
import os
import struct
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from phe import paillier

from algorithms import bsif_quality, dbcrh, irpp_filter_and_td, update_rpps_reputation
from crypto_utils import (
    DSAGroup,
    NTRUPlus768,
    fixed_int,
    generate_ed25519_pairs,
    generate_paillier,
    generate_rsa_envelopes,
    h256,
    merkle_root,
    paillier_width,
    rsa_hybrid_open,
    rsa_hybrid_seal,
    serialize_paillier,
)


SCALE = 1_000_000


def now_ns() -> int:
    return time.perf_counter_ns()


def ms(delta_ns: int) -> float:
    return delta_ns / 1_000_000.0


def add_time(bucket: dict[str, int], key: str, start_ns: int):
    bucket[key] = bucket.get(key, 0) + now_ns() - start_ns


@dataclass
class Workload:
    n: int
    dimension: int
    payload_bytes: int
    seed: int
    truth: np.ndarray
    reports: np.ndarray
    payloads: list[bytes]


def make_workload(n: int, dimension: int, payload_bytes: int, seed: int) -> Workload:
    if payload_bytes < dimension * 8:
        raise ValueError("payload too short for the sensing vector")
    rng = np.random.default_rng(seed)
    truth = rng.uniform(0.25, 0.75, size=dimension)
    reports = truth + rng.normal(0, 0.025, size=(n, dimension))
    malicious = rng.choice(n, size=max(1, int(round(0.3 * n))), replace=False)
    reports[malicious] += rng.normal(0.22, 0.03, size=(len(malicious), dimension))
    reports = np.clip(reports, 0.0, 1.0)
    payloads = []
    for i, report in enumerate(reports):
        head = np.asarray(report, dtype=">f8").tobytes()
        pad = hashlib_shake(h256(b"PAYLOAD", seed.to_bytes(8, "big"), i.to_bytes(4, "big")), payload_bytes - len(head))
        payloads.append(head + pad)
    return Workload(n, dimension, payload_bytes, seed, truth, reports, payloads)


def hashlib_shake(seed: bytes, length: int) -> bytes:
    import hashlib

    return hashlib.shake_256(seed).digest(length)


class ExperimentSuite:
    """Long-lived setup shared by all repetitions; per-task methods are timed."""

    def __init__(self, max_workers: int = 50, auditors: int = 5):
        self.max_workers = max_workers
        self.auditors = auditors
        self.setup_rows: list[dict[str, Any]] = []
        self.ntru = NTRUPlus768()

        self.irpp_dr_kem = self._timed("IRPP", "NTRU+768 DR keygen", self.ntru.keypair)
        self.irpp_worker_kem = [self._timed("IRPP", "NTRU+768 worker keygen", self.ntru.keypair) for _ in range(max_workers)]
        self.irpp_auditor_kem = [self._timed("IRPP", "NTRU+768 auditor keygen", self.ntru.keypair) for _ in range(auditors)]
        self.irpp_worker_sig = self._timed("IRPP", "Ed25519 worker keygen batch", lambda: generate_ed25519_pairs(max_workers))
        self.irpp_dr_sig = self._timed("IRPP", "Ed25519 DR keygen", lambda: generate_ed25519_pairs(1)[0])
        self.irpp_tp_sig = self._timed("IRPP", "Ed25519 TP keygen", lambda: generate_ed25519_pairs(1)[0])
        self.irpp_auditor_sig = self._timed("IRPP", "Ed25519 auditor keygen batch", lambda: generate_ed25519_pairs(auditors))

        self.bsif_paillier = self._timed("BSIF", "Paillier-3072 keygen", generate_paillier)
        self.bsif_outer = self._timed("BSIF", "RSA-3072 worker envelope keygen batch", lambda: generate_rsa_envelopes(max_workers))
        self.rpps_paillier = self._timed("RPPS-TDC", "Paillier-3072 DR keygen", generate_paillier)
        self.rpps_rc_paillier = self._timed("RPPS-TDC", "Paillier-3072 RC keygen", generate_paillier)
        self.prtd_paillier = self._timed("PRTD", "Paillier-3072 two-cloud keygen", generate_paillier)
        self.prtd_group = self._timed("PRTD", "3072-bit DSA-group setup", DSAGroup.generate)

        self.irpp_states = np.ones((max_workers, 3), dtype=np.int64)
        self.rpps_reputations = np.full(max_workers, 0.7, dtype=float)
        self.bsif_reputations = np.full(max_workers, 0.7, dtype=float)
        self.prtd_reputations = np.full(max_workers, 0.7, dtype=float)

    def reset_state(self, n: int | None = None):
        """Reset mutable history to the frozen mature matched-load state."""
        limit = self.max_workers if n is None else int(n)
        self.irpp_states[:limit] = np.asarray([10, 2, 1], dtype=np.int64)
        self.rpps_reputations[:limit] = 0.7
        self.bsif_reputations[:limit] = 0.7
        self.prtd_reputations[:limit] = 0.7

    def _timed(self, protocol: str, operation: str, fn):
        t0 = now_ns()
        result = fn()
        self.setup_rows.append({"protocol": protocol, "operation": operation, "setup_ms": ms(now_ns() - t0)})
        return result

    def run_irpp(self, w: Workload, audit_mode: str = "normal") -> dict[str, Any]:
        if audit_mode not in {"normal", "proactive", "challenged", "delayed"}:
            raise ValueError(audit_mode)
        times: dict[str, int] = {}
        traffic = 0
        t_all = now_ns()
        n = w.n
        ctx = h256(b"AUTHCTX", w.seed.to_bytes(8, "big"), n.to_bytes(4, "big"))

        # P2: signed authorization and fixed-format hidden selection tickets.
        t0 = now_ns()
        auth_body = ctx + os.urandom(max(0, w.payload_bytes - 32))
        auth_sig = self.irpp_dr_sig[0].sign(auth_body)
        tickets = []
        for i in range(n):
            body = ctx + i.to_bytes(4, "big") + h256(b"SEL", ctx, i.to_bytes(4, "big")) + os.urandom(60)
            tickets.append(body + self.irpp_dr_sig[0].sign(body))
        add_time(times, "dr", t0)
        traffic += n * (len(auth_body) + len(auth_sig)) + n * n * len(tickets[0])

        t0 = now_ns()
        self.irpp_dr_sig[1].verify(auth_sig, auth_body)
        for _worker in range(n):
            for ticket in tickets:
                self.irpp_dr_sig[1].verify(ticket[-64:], ticket[:-64])
        add_time(times, "worker", t0)

        # P3: context-bound NTRU+ KEM--AES-GCM submission and two-hop relay.
        envelopes: list[bytes] = []
        recovered: list[bytes] = []
        log_leaves: list[bytes] = []
        submission_sizes = []
        for i in range(n):
            aad = ctx + i.to_bytes(4, "big") + h256(tickets[i])
            t0 = now_ns()
            sealed = self.ntru.seal(self.irpp_dr_kem[0], w.payloads[i], aad)
            signed = aad + sealed
            signature = self.irpp_worker_sig[i][0].sign(signed)
            add_time(times, "worker", t0)
            envelope = aad + sealed + signature
            envelopes.append(envelope)
            submission_sizes.append(len(envelope))
            traffic += 2 * len(envelope)

            t0 = now_ns()
            self.irpp_worker_sig[i][1].verify(signature, signed)
            log_leaves.append(h256(b"SUBLOG", aad, h256(sealed), signature))
            add_time(times, "tp_sp", t0)

            t0 = now_ns()
            self.irpp_worker_sig[i][1].verify(signature, signed)
            plain = self.ntru.open(self.irpp_dr_kem[1], sealed, aad)
            if plain != w.payloads[i]:
                raise RuntimeError("IRPP submission mismatch")
            recovered.append(plain)
            add_time(times, "dr", t0)

        # P4: verify prior credentials, RABOD, bounded TD, and Dirichlet update.
        t0 = now_ns()
        previous_bodies = []
        for i in range(n):
            body = ctx + b"PREV" + i.to_bytes(4, "big") + bytes(self.irpp_states[i].tolist())
            previous_bodies.append(body + self.irpp_dr_sig[0].sign(body))
        for body in previous_bodies:
            self.irpp_dr_sig[1].verify(body[-64:], body[:-64])
        truth, labels, retained, iterations = irpp_filter_and_td(w.reports, w.seed)
        analytics_ns = now_ns() - t0
        for i, label in enumerate(labels):
            self.irpp_states[i, int(label)] += 1
        add_time(times, "dr", t0)

        # P5--P6: randomized owner-free refresh, sealed feedback, worker checks.
        transition_leaves = []
        feedback_sizes = []
        for i in range(n):
            t0 = now_ns()
            salt = os.urandom(32)
            cid = os.urandom(32)
            state = bytes(int(x) & 0xFF for x in self.irpp_states[i])
            commitment = h256(b"REP", ctx, cid, state, salt)
            predecessor = h256(b"RID-PREV", i.to_bytes(4, "big"), ctx)
            transition = predecessor + ctx + cid + commitment
            transition_sig = self.irpp_dr_sig[0].sign(transition)
            successor = h256(b"RID", transition, transition_sig)
            feedback_plain = state + salt + cid + successor + truth.astype(">f8").tobytes()
            aad = ctx + successor
            feedback = self.ntru.seal(self.irpp_worker_kem[i][0], feedback_plain, aad)
            fb_sig = self.irpp_dr_sig[0].sign(aad + feedback)
            transition_leaves.append(transition + transition_sig)
            add_time(times, "dr", t0)

            t0 = now_ns()
            self.irpp_dr_sig[1].verify(transition_sig, transition)
            self.irpp_dr_sig[1].verify(fb_sig, aad + feedback)
            opened = self.ntru.open(self.irpp_worker_kem[i][1], feedback, aad)
            if opened != feedback_plain:
                raise RuntimeError("IRPP feedback mismatch")
            # Merkle inclusion verification has ceil(log2 n)+2 hashes.
            x = h256(transition_leaves[-1])
            for depth in range(int(math.ceil(math.log2(max(n, 2)))) + 2):
                x = h256(x, depth.to_bytes(2, "big"))
            add_time(times, "worker", t0)
            feedback_sizes.append(len(feedback) + len(fb_sig) + len(transition))
            traffic += 2 * feedback_sizes[-1]

        input_root = merkle_root(log_leaves)
        output_root = merkle_root(transition_leaves)
        package = b"".join(h256(item) for item in envelopes + transition_leaves) + truth.astype(">f8").tobytes()
        _ = h256(b"IN", input_root), h256(b"OUT", output_root, h256(package))
        traffic += n * (32 + 32 * int(math.ceil(math.log2(max(n, 2)))))

        # P7: triggered confidential re-execution. Delayed challenge has the
        # same active work; its declared waiting component is recorded later.
        if audit_mode != "normal":
            if audit_mode in {"challenged", "delayed"}:
                t0 = now_ns()
                challenge = ctx + output_root + h256(transition_leaves[0]) + h256(b"WRONG-LABEL")
                challenge_sig = self.irpp_worker_sig[0][0].sign(challenge)
                add_time(times, "worker", t0)
                traffic += len(challenge) + len(challenge_sig)
            for j in range(self.auditors):
                aad = ctx + j.to_bytes(2, "big") + b"AUDIT"
                t0 = now_ns()
                sealed_pkg = self.ntru.seal(self.irpp_auditor_kem[j][0], package, aad)
                add_time(times, "dr", t0)
                traffic += len(sealed_pkg)
                t0 = now_ns()
                opened = self.ntru.open(self.irpp_auditor_kem[j][1], sealed_pkg, aad)
                if opened != package:
                    raise RuntimeError("audit package mismatch")
                audit_truth, _, _, _ = irpp_filter_and_td(w.reports, w.seed)
                verdict = ctx + h256(audit_truth.astype(">f8").tobytes()) + output_root
                verdict_sig = self.irpp_auditor_sig[j][0].sign(verdict)
                self.irpp_auditor_sig[j][1].verify(verdict_sig, verdict)
                add_time(times, "auditor", t0)
                traffic += len(verdict) + len(verdict_sig)

        active_ns = now_ns() - t_all
        wait_ms = 0.0 if audit_mode != "delayed" else 500.0
        return self._result(
            "IRPP-TD",
            w,
            audit_mode,
            active_ns,
            times,
            analytics_ns,
            traffic,
            float(np.mean(submission_sizes)),
            iterations,
            int(retained.sum()),
            declared_wait_ms=wait_ms,
        )

    def run_bsif(self, w: Workload) -> dict[str, Any]:
        times: dict[str, int] = {}
        traffic = 0
        t_all = now_ns()
        pub, priv = self.bsif_paillier
        location_key = h256(b"BSIF-LOCATION", w.seed.to_bytes(8, "big"))
        nonce = os.urandom(12)

        t0 = now_ns()
        encrypted_task = nonce + AESGCM(location_key).encrypt(nonce, os.urandom(w.payload_bytes), b"BSIF-TASK")
        add_time(times, "dr", t0)
        t0 = now_ns()
        for _ in range(w.n):
            AESGCM(location_key).decrypt(encrypted_task[:12], encrypted_task[12:], b"BSIF-TASK")
        add_time(times, "worker", t0)
        traffic += w.n * (len(encrypted_task) + 96)

        inner_objects = []
        outer_reports = []
        scaled_reports = np.rint(w.reports * SCALE).astype(np.int64)
        for i in range(w.n):
            t0 = now_ns()
            inner = [pub.encrypt(int(x)) for x in scaled_reports[i]]
            serialized = serialize_paillier(inner, pub)
            aad = h256(b"BSIF-UPLOAD", w.seed.to_bytes(8, "big"), i.to_bytes(4, "big"))
            outer = rsa_hybrid_seal(self.bsif_outer[i].public, serialized, aad)
            add_time(times, "worker", t0)
            inner_objects.append(inner)
            outer_reports.append((outer, aad))
            traffic += len(outer) + 96

        # Fully trusted SP removes the worker envelope and applies the native
        # trusted-worker coarse filter before forwarding inner ciphertexts.
        t0 = now_ns()
        decrypted = []
        for i, (outer, aad) in enumerate(outer_reports):
            serialized = rsa_hybrid_open(self.bsif_outer[i].private, outer, aad)
            if len(serialized) != len(serialize_paillier(inner_objects[i], pub)):
                raise RuntimeError("BSIF outer envelope mismatch")
            decrypted.append([priv.decrypt(x) / SCALE for x in inner_objects[i]])
        decrypted = np.asarray(decrypted, dtype=float)
        deviation = np.linalg.norm(decrypted - decrypted[0], axis=1)
        med = float(np.median(deviation))
        mad = float(np.median(np.abs(deviation - med))) + 1e-12
        retained = deviation <= med + 3.0 * 1.4826 * mad
        retained[0] = True
        add_time(times, "tp_sp", t0)

        traffic += int(retained.sum()) * (w.dimension * paillier_width(pub) + 64)
        t0 = now_ns()
        baseline, quality = bsif_quality(decrypted[retained])
        analytics_ns = now_ns() - t0
        encrypted_quality = [pub.encrypt(int(round(q * SCALE))) for q in quality]
        add_time(times, "dr", t0)
        traffic += len(serialize_paillier(encrypted_quality, pub)) + 64

        t0 = now_ns()
        quality_plain = np.asarray([priv.decrypt(x) / SCALE for x in encrypted_quality])
        retained_indices = np.where(retained)[0]
        self.bsif_reputations[retained_indices] = np.clip(quality_plain, 0.0, 1.0)
        _payments = quality_plain / max(float(quality_plain.sum()), 1e-12)
        add_time(times, "tp_sp", t0)

        active_ns = now_ns() - t_all
        return self._result(
            "BSIF",
            w,
            "normal",
            active_ns,
            times,
            analytics_ns,
            traffic,
            float(np.mean([len(x[0]) for x in outer_reports])),
            1,
            int(retained.sum()),
        )

    def run_rpps(self, w: Workload) -> dict[str, Any]:
        times: dict[str, int] = {}
        traffic = 0
        t_all = now_ns()
        pub, priv = self.rpps_paillier
        rc_pub, rc_priv = self.rpps_rc_paillier
        key = h256(b"RPPS-GEOHASH", w.seed.to_bytes(8, "big"))
        nonce = os.urandom(12)

        t0 = now_ns()
        encrypted_task = nonce + AESGCM(key).encrypt(nonce, os.urandom(w.payload_bytes), b"RPPS-TASK")
        add_time(times, "dr", t0)
        t0 = now_ns()
        for _ in range(w.n):
            AESGCM(key).decrypt(encrypted_task[:12], encrypted_task[12:], b"RPPS-TASK")
        add_time(times, "worker", t0)
        traffic += w.n * (len(encrypted_task) + 96)

        scaled = np.rint(w.reports * SCALE).astype(np.int64)
        encrypted_reports = []
        serialized_sizes = []
        for i in range(w.n):
            t0 = now_ns()
            row = [pub.encrypt(int(x)) for x in scaled[i]]
            add_time(times, "worker", t0)
            encrypted_reports.append(row)
            size = len(serialize_paillier(row, pub))
            serialized_sizes.append(size)
            traffic += size + 96

        # Mining-node scrambling and requester DBCRH.
        blind = 7
        t0 = now_ns()
        blinded = [[cipher * blind for cipher in row] for row in encrypted_reports]
        add_time(times, "tp_sp", t0)
        traffic += sum(serialized_sizes)
        t0 = now_ns()
        recovered = np.asarray([[priv.decrypt(x) / (blind * SCALE) for x in row] for row in blinded])
        truth, weights, iterations = dbcrh(recovered, self.rpps_reputations[: w.n])
        analytics_ns = now_ns() - t0
        add_time(times, "dr", t0)

        # Encrypted weights to RC, RUBS update, trust-max-heap selection.
        t0 = now_ns()
        encrypted_weights = [rc_pub.encrypt(int(round(x * SCALE))) for x in weights]
        add_time(times, "dr", t0)
        traffic += len(serialize_paillier(encrypted_weights, rc_pub)) + 64
        t0 = now_ns()
        weight_plain = np.asarray([rc_priv.decrypt(x) / SCALE for x in encrypted_weights])
        self.rpps_reputations[: w.n] = update_rpps_reputation(self.rpps_reputations[: w.n], weight_plain)
        trust = weight_plain * self.rpps_reputations[: w.n]
        selected_count = max(1, int(math.ceil(0.8 * w.n)))
        selected = np.argsort(trust)[-selected_count:]
        add_time(times, "rb_rc", t0)
        traffic += selected_count * 48 + w.n * 8

        # Mining nodes homomorphically weight selected reports; requester decrypts.
        weight_int = np.maximum(1, np.rint(trust[selected] * 10_000).astype(np.int64))
        t0 = now_ns()
        aggregates = []
        for d in range(w.dimension):
            total = pub.encrypt(0)
            for pos, idx in enumerate(selected):
                total = total + encrypted_reports[int(idx)][d] * int(weight_int[pos])
            aggregates.append(total)
        add_time(times, "tp_sp", t0)
        traffic += len(serialize_paillier(aggregates, pub)) + 64
        t0 = now_ns()
        final = np.asarray([priv.decrypt(x) for x in aggregates], dtype=float) / (float(weight_int.sum()) * SCALE)
        if not np.all(np.isfinite(final)):
            raise RuntimeError("RPPS final truth invalid")
        add_time(times, "dr", t0)

        active_ns = now_ns() - t_all
        return self._result(
            "RPPS-TDC",
            w,
            "normal",
            active_ns,
            times,
            analytics_ns,
            traffic,
            float(np.mean(serialized_sizes)),
            iterations,
            selected_count,
        )

    def run_prtd(self, w: Workload) -> dict[str, Any]:
        times: dict[str, int] = {}
        traffic = 0
        t_all = now_ns()
        pub, priv = self.prtd_paillier
        group = self.prtd_group
        context = h256(b"PRTD", w.seed.to_bytes(8, "big"))
        scaled = np.rint(w.reports * SCALE).astype(np.int64)

        # RZKPV and encrypted report submission.
        report_ciphertexts = []
        commitments = []
        proofs = []
        secure_report_sizes = []
        for i in range(w.n):
            t0 = now_ns()
            rep_int = int(round(self.prtd_reputations[i] * 1000))
            randomness = int.from_bytes(os.urandom(64), "big") % group.q
            commitment = group.commit(rep_int, randomness)
            proof = group.prove_opening(commitment, rep_int, randomness, context + i.to_bytes(4, "big"))
            encrypted = [pub.encrypt(int(x)) for x in scaled[i]]
            add_time(times, "worker", t0)
            commitments.append(commitment)
            proofs.append(proof)
            report_ciphertexts.append(encrypted)
            proof_bytes = 2 * group.element_bytes + 2 * ((group.q.bit_length() + 7) // 8)
            size = proof_bytes + len(serialize_paillier(encrypted, pub)) + 64
            secure_report_sizes.append(size)
            traffic += size

        t0 = now_ns()
        for i in range(w.n):
            if not group.verify_opening(commitments[i], proofs[i], context + i.to_bytes(4, "big")):
                raise RuntimeError("PRTD reputation proof failed")
        reliability = 1 + np.rint(4 * self.prtd_reputations[: w.n]).astype(np.int64)
        add_time(times, "tp_sp", t0)

        # Two-cloud encrypted TD. Reports are encrypted once; encrypted
        # distances and homomorphic weighted sums are exchanged each round.
        truth = w.reports.mean(axis=0)
        iterations = 0
        analytics_ns = 0
        for iteration in range(1, 9):
            iterations = iteration
            t0 = now_ns()
            distance_plain = np.sum((w.reports - truth) ** 2, axis=1)
            encrypted_distance = [pub.encrypt(int(round(x * SCALE))) for x in distance_plain]
            add_time(times, "worker", t0)
            traffic += len(serialize_paillier(encrypted_distance, pub))

            t0 = now_ns()
            distance_at_b = np.asarray([priv.decrypt(x) / SCALE for x in encrypted_distance])
            raw = reliability / np.maximum(distance_at_b + 1e-6, 1e-6)
            raw = raw / raw.sum()
            weights = np.maximum(1, np.rint(raw * 100_000).astype(np.int64))
            add_time(times, "dr", t0)  # second cloud
            traffic += w.n * 8

            t0 = now_ns()
            aggregates = []
            for d in range(w.dimension):
                total = pub.encrypt(0)
                for i in range(w.n):
                    total = total + report_ciphertexts[i][d] * int(weights[i])
                aggregates.append(total)
            add_time(times, "tp_sp", t0)  # first cloud
            traffic += len(serialize_paillier(aggregates, pub))

            t0 = now_ns()
            updated = np.asarray([priv.decrypt(x) for x in aggregates], dtype=float) / (float(weights.sum()) * SCALE)
            analytics_ns += now_ns() - t0
            add_time(times, "dr", t0)
            if np.linalg.norm(updated - truth) <= 1e-5 * (1.0 + np.linalg.norm(truth)):
                truth = updated
                break
            truth = updated

        # Requester reconstruction/quality and TA commitment refresh.
        t0 = now_ns()
        sealed_reports = [group.elgamal_seal(w.payloads[i], context + i.to_bytes(4, "big")) for i in range(w.n)]
        sealed_truth = group.elgamal_seal(truth.astype(">f8").tobytes(), context + b"TRUTH")
        add_time(times, "tp_sp", t0)
        traffic += sum(map(len, sealed_reports)) + len(sealed_truth)
        t0 = now_ns()
        for i, sealed in enumerate(sealed_reports):
            if group.elgamal_open(sealed, context + i.to_bytes(4, "big")) != w.payloads[i]:
                raise RuntimeError("PRTD requester reconstruction failed")
        group.elgamal_open(sealed_truth, context + b"TRUTH")
        quality = np.exp(-np.linalg.norm(w.reports - truth, axis=1))
        add_time(times, "dr", t0)  # requester
        traffic += w.n * 8

        t0 = now_ns()
        self.prtd_reputations[: w.n] = np.clip(0.8 * self.prtd_reputations[: w.n] + 0.2 * quality, 0.0, 1.0)
        refreshed = []
        for i in range(w.n):
            randomness = int.from_bytes(os.urandom(64), "big") % group.q
            refreshed.append(group.commit(int(round(self.prtd_reputations[i] * 1000)), randomness))
        add_time(times, "rb_rc", t0)  # TA
        traffic += len(refreshed) * group.element_bytes

        active_ns = now_ns() - t_all
        return self._result(
            "PRTD",
            w,
            "normal",
            active_ns,
            times,
            analytics_ns,
            traffic,
            float(np.mean(secure_report_sizes)),
            iterations,
            w.n,
        )

    @staticmethod
    def _result(
        protocol: str,
        w: Workload,
        audit_mode: str,
        active_ns: int,
        times: dict[str, int],
        analytics_ns: int,
        traffic: int,
        report_bytes: float,
        iterations: int,
        retained: int,
        declared_wait_ms: float = 0.0,
    ) -> dict[str, Any]:
        active_ms = ms(active_ns)
        analytics_ms = ms(analytics_ns)
        return {
            "protocol": protocol,
            "n": w.n,
            "dimension": w.dimension,
            "payload_bytes": w.payload_bytes,
            "seed": w.seed,
            "audit_mode": audit_mode,
            "offchain_active_ms": active_ms,
            "declared_wait_ms": declared_wait_ms,
            "offchain_final_ms": active_ms + declared_wait_ms,
            "worker_ms": ms(times.get("worker", 0)),
            "tp_sp_cloudA_ms": ms(times.get("tp_sp", 0)),
            "dr_cloudB_ms": ms(times.get("dr", 0)),
            "rb_rc_ta_ms": ms(times.get("rb_rc", 0)),
            "auditor_ms": ms(times.get("auditor", 0)),
            "analytics_ms": analytics_ms,
            "crypto_and_protocol_ms": max(0.0, active_ms - analytics_ms),
            "traffic_task_bytes": int(traffic),
            "traffic_report_bytes": float(report_bytes),
            "iterations": int(iterations),
            "retained_count": int(retained),
            "valid": True,
        }
