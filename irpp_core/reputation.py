from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict

import numpy as np
from scipy.special import betainc, betaln, gammaln, roots_legendre


@dataclass(frozen=True)
class TVEvaluation:
    tv: float
    method: str
    quadrature_order: int
    quadrature_delta: float
    quadrature_converged: bool
    mc_score_margin: float
    certified_score_low: float
    certified_score_high: float


class SlicedDirichletTVQuadrature:
    """Deterministic simplex integration after analytic slicing at p_alpha=2."""

    _RULES: Dict[int, tuple[np.ndarray, np.ndarray]] = {}

    @classmethod
    def rule(cls, order: int) -> tuple[np.ndarray, np.ndarray]:
        cached = cls._RULES.get(order)
        if cached is None:
            nodes, weights = roots_legendre(order)
            cached = ((nodes + 1.0) / 2.0, weights / 2.0)
            cls._RULES[order] = cached
        return cached

    @staticmethod
    def _t_interval(
        base: np.ndarray, alpha_u: int, alpha_l: int
    ) -> tuple[np.ndarray, np.ndarray]:
        bu = float(alpha_u - 1)
        bl = float(alpha_l - 1)
        log_two = math.log(2.0)
        lower = np.zeros_like(base)
        upper = np.zeros_like(base)

        if bu == 0.0 and bl == 0.0:
            upper[base >= log_two] = 1.0
            return lower, upper
        if bu == 0.0:
            active = base >= log_two
            exponent = np.minimum(0.0, (log_two - base[active]) / bl)
            upper[active] = -np.expm1(exponent)
            return lower, upper
        if bl == 0.0:
            active = base >= log_two
            exponent = np.minimum(0.0, (log_two - base[active]) / bu)
            lower[active] = np.exp(exponent)
            upper[active] = 1.0
            return lower, upper

        peak = bu / (bu + bl)
        peak_shape = bu * math.log(peak) + bl * math.log1p(-peak)
        target = log_two - base
        active = target <= peak_shape
        if not np.any(active):
            return lower, upper
        active_target = target[active]

        lo = np.zeros(active_target.size)
        hi = np.full(active_target.size, peak)
        for _ in range(64):
            mid = (lo + hi) / 2.0
            value = bu * np.log(mid) + bl * np.log1p(-mid)
            move_lo = value < active_target
            lo[move_lo] = mid[move_lo]
            hi[~move_lo] = mid[~move_lo]
        lower[active] = (lo + hi) / 2.0

        lo = np.full(active_target.size, peak)
        hi = np.ones(active_target.size)
        for _ in range(64):
            mid = (lo + hi) / 2.0
            value = bu * np.log(mid) + bl * np.log1p(-mid)
            move_lo = value >= active_target
            lo[move_lo] = mid[move_lo]
            hi[~move_lo] = mid[~move_lo]
        upper[active] = (lo + hi) / 2.0
        return lower, upper

    @classmethod
    def evaluate(cls, alpha: tuple[int, int, int], order: int) -> float:
        if alpha == (1, 1, 1):
            return 0.0
        alpha_h, alpha_u, alpha_l = alpha
        x, weights = cls.rule(order)
        log_x = np.log(x)
        log_one_minus_x = np.log1p(-x)
        log_norm = gammaln(sum(alpha)) - sum(gammaln(value) for value in alpha)
        base = (
            log_norm
            + (alpha_h - 1.0) * log_x
            + (alpha_u + alpha_l - 2.0) * log_one_minus_x
        )
        t_lower, t_upper = cls._t_interval(base, alpha_u, alpha_l)
        active = t_upper > t_lower
        if not np.any(active):
            return 0.0

        conditional_mass = np.zeros_like(x)
        conditional_mass[active] = betainc(alpha_u, alpha_l, t_upper[active])
        conditional_mass[active] -= betainc(alpha_u, alpha_l, t_lower[active])
        log_marginal = (
            (alpha_h - 1.0) * log_x
            + (alpha_u + alpha_l - 1.0) * log_one_minus_x
            - betaln(alpha_h, alpha_u + alpha_l)
        )
        posterior_mass = float(np.dot(weights, np.exp(log_marginal) * conditional_mass))
        uniform_mass = float(
            np.dot(weights, 2.0 * (1.0 - x) * (t_upper - t_lower))
        )
        return float(np.clip(posterior_mass - uniform_mass, 0.0, 1.0))

    @classmethod
    def evaluate_adaptive(
        cls,
        alpha: tuple[int, int, int],
        tolerance: float,
        orders: tuple[int, ...],
    ) -> tuple[float, int, float, bool]:
        if alpha == (1, 1, 1):
            return 0.0, 0, 0.0, True
        previous = None
        last_delta = math.inf
        consecutive = 0
        value = math.nan
        for order in orders:
            value = cls.evaluate(alpha, order)
            if previous is not None:
                last_delta = abs(value - previous)
                consecutive = consecutive + 1 if last_delta <= tolerance else 0
                if consecutive >= 2:
                    return value, order, last_delta, True
            previous = value
        return value, orders[-1], last_delta, False


class HybridDirichletReputation:
    """M=1024 first stage with family-wise guarded quadrature fallback."""

    _GLOBAL_CACHE: Dict[tuple, TVEvaluation] = {}
    _GLOBAL_COUNTS: Dict[str, int] = {
        "accesses": 0,
        "local_hits": 0,
        "global_hits": 0,
        "misses": 0,
        "mc_states": 0,
        "quadrature_states": 0,
        "quadrature_converged": 0,
        "quadrature_max_order": 0,
    }

    def __init__(
        self,
        zeta: float,
        theta: float,
        tv_samples: int = 1024,
        family_delta: float = 0.05,
        max_task_horizon: int = 100,
        quadrature_tolerance: float = 1e-6,
        quadrature_orders: tuple[int, ...] = (128, 256, 512, 1024, 2048, 4096, 8192),
    ):
        if tv_samples < 128:
            raise ValueError("tv_samples must be at least 128")
        if not 0.0 < family_delta < 1.0:
            raise ValueError("family_delta must lie in (0,1)")
        if max_task_horizon < 1:
            raise ValueError("max_task_horizon must be positive")
        if quadrature_tolerance <= 0.0:
            raise ValueError("quadrature_tolerance must be positive")
        if not quadrature_orders or any(order < 2 for order in quadrature_orders):
            raise ValueError("quadrature_orders must contain positive rules")
        if any(left >= right for left, right in zip(quadrature_orders, quadrature_orders[1:])):
            raise ValueError("quadrature_orders must be strictly increasing")
        self.zeta = float(zeta)
        self.theta = float(theta)
        self.tv_samples = int(tv_samples + (tv_samples % 2))
        self.family_delta = float(family_delta)
        self.max_task_horizon = int(max_task_horizon)
        self.quadrature_tolerance = float(quadrature_tolerance)
        self.quadrature_orders = tuple(int(value) for value in quadrature_orders)
        self.max_state_count = math.comb(self.max_task_horizon + 3, 3)
        self.state_delta = self.family_delta / self.max_state_count
        self.u_radius = math.sqrt(
            math.log(2.0 / self.state_delta) / (2.0 * self.tv_samples)
        )
        self.score_guard = (5.0 / 3.0) * self.u_radius
        self._local_cache: Dict[tuple[int, int, int], TVEvaluation] = {
            (1, 1, 1): TVEvaluation(
                0.0,
                "exact",
                0,
                0.0,
                True,
                math.inf,
                (1.0 + self.zeta) / 3.0,
                (1.0 + self.zeta) / 3.0,
            )
        }

    @classmethod
    def reset_global_state(cls) -> None:
        cls._GLOBAL_CACHE = {}
        cls._GLOBAL_COUNTS = {
            "accesses": 0,
            "local_hits": 0,
            "global_hits": 0,
            "misses": 0,
            "mc_states": 0,
            "quadrature_states": 0,
            "quadrature_converged": 0,
            "quadrature_max_order": 0,
        }

    @classmethod
    def global_counts(cls) -> dict[str, int]:
        return dict(cls._GLOBAL_COUNTS)

    def _cache_key(self, alpha: tuple[int, int, int]) -> tuple:
        return (
            self.tv_samples,
            self.zeta,
            self.theta,
            self.family_delta,
            self.max_task_horizon,
            self.quadrature_tolerance,
            self.quadrature_orders,
            *alpha,
        )

    @staticmethod
    def _state_seed(alpha: tuple[int, int, int]) -> int:
        return (
            alpha[0] * 73_856_093
            ^ alpha[1] * 19_349_663
            ^ alpha[2] * 83_492_791
            ^ 0x5EED2026
        ) & 0xFFFFFFFF

    def _mc_tv(self, alpha: tuple[int, int, int]) -> float:
        rng = np.random.default_rng(self._state_seed(alpha))
        half = self.tv_samples // 2
        samples = np.vstack(
            [
                rng.dirichlet(np.asarray(alpha, dtype=float), size=half),
                rng.dirichlet(np.ones(3), size=half),
            ]
        )
        log_norm = gammaln(sum(alpha)) - sum(gammaln(value) for value in alpha)
        log_p = log_norm + np.sum(
            (np.asarray(alpha) - 1.0) * np.log(samples), axis=1
        )
        ratio = np.abs(np.tanh(0.5 * (log_p - math.log(2.0))))
        return float(np.clip(np.mean(ratio), 0.0, 1.0))

    def _score_from_tv(self, alpha: tuple[int, int, int], tv: float) -> float:
        phi = np.asarray(alpha, dtype=float) / float(sum(alpha))
        uncertainty = 1.0 - tv
        quality_credit = (1.0 - uncertainty) * (phi[0] + self.zeta * phi[1])
        quality_credit += uncertainty * (1.0 + self.zeta) / 3.0
        low_penalty = 1.0 - (1.0 - uncertainty) * phi[2]
        return float(np.clip(quality_credit * low_penalty, 0.0, 1.0))

    def _score_interval(
        self, alpha: tuple[int, int, int], uncertainty: float
    ) -> tuple[float, float]:
        """Exact image of the Hoeffding U interval under the quadratic score."""
        phi = np.asarray(alpha, dtype=float) / float(sum(alpha))
        quality = phi[0] + self.zeta * phi[1]
        prior = (1.0 + self.zeta) / 3.0
        low = phi[2]
        difference = prior - quality
        complement = 1.0 - low
        coefficient_2 = difference * low
        coefficient_1 = quality * low + difference * complement
        coefficient_0 = quality * complement
        u_low = max(0.0, uncertainty - self.u_radius)
        u_high = min(1.0, uncertainty + self.u_radius)
        candidates = [u_low, u_high]
        if abs(coefficient_2) > 1e-15:
            stationary = -coefficient_1 / (2.0 * coefficient_2)
            if u_low < stationary < u_high:
                candidates.append(stationary)
        values = [
            coefficient_2 * value * value
            + coefficient_1 * value
            + coefficient_0
            for value in candidates
        ]
        return float(min(values)), float(max(values))

    def _compute(self, alpha: tuple[int, int, int]) -> TVEvaluation:
        if alpha == (1, 1, 1):
            return self._local_cache[alpha]
        mc_tv = self._mc_tv(alpha)
        mc_score = self._score_from_tv(alpha, mc_tv)
        mc_margin = abs(mc_score - self.theta)
        score_low, score_high = self._score_interval(alpha, 1.0 - mc_tv)
        if not score_low <= self.theta <= score_high:
            self._GLOBAL_COUNTS["mc_states"] += 1
            return TVEvaluation(
                mc_tv,
                "mc",
                0,
                0.0,
                True,
                mc_margin,
                score_low,
                score_high,
            )
        tv, order, delta, converged = SlicedDirichletTVQuadrature.evaluate_adaptive(
            alpha, self.quadrature_tolerance, self.quadrature_orders
        )
        self._GLOBAL_COUNTS["quadrature_states"] += 1
        self._GLOBAL_COUNTS["quadrature_converged"] += int(converged)
        self._GLOBAL_COUNTS["quadrature_max_order"] = max(
            self._GLOBAL_COUNTS["quadrature_max_order"], order
        )
        if not converged:
            raise RuntimeError(
                f"Dirichlet-TV quadrature did not meet tolerance for state {alpha}"
            )
        return TVEvaluation(
            tv,
            "quadrature",
            order,
            delta,
            converged,
            mc_margin,
            score_low,
            score_high,
        )

    def evaluation(self, alpha_array: np.ndarray) -> TVEvaluation:
        alpha = tuple(int(value) for value in alpha_array)
        self._GLOBAL_COUNTS["accesses"] += 1
        local = self._local_cache.get(alpha)
        if local is not None:
            self._GLOBAL_COUNTS["local_hits"] += 1
            return local
        cache_key = self._cache_key(alpha)
        shared = self._GLOBAL_CACHE.get(cache_key)
        if shared is not None:
            self._GLOBAL_COUNTS["global_hits"] += 1
            self._local_cache[alpha] = shared
            return shared
        self._GLOBAL_COUNTS["misses"] += 1
        result = self._compute(alpha)
        self._GLOBAL_CACHE[cache_key] = result
        self._local_cache[alpha] = result
        return result

    def tv_distance(self, alpha_array: np.ndarray) -> float:
        return self.evaluation(alpha_array).tv

    def score(self, alpha_array: np.ndarray) -> float:
        alpha = tuple(int(value) for value in alpha_array)
        return self._score_from_tv(alpha, self.tv_distance(np.asarray(alpha, dtype=int)))

    def cached_evaluations(self) -> dict[tuple[int, int, int], TVEvaluation]:
        return dict(self._local_cache)
