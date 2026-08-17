from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from run_rq4 import make_stability_reports, stability_trial
from src.rq4_core import Parameters, angular_scores, bounded_truth_discovery


class RQ4InvariantTests(unittest.TestCase):
    def setUp(self):
        self.p = Parameters()

    def test_exact_report_at_current_mean_is_finite(self):
        reports, truth = make_stability_reports(0, 1e-3, "full-rank")
        self.assertTrue(np.array_equal(reports.mean(axis=0), truth))
        result = bounded_truth_discovery(reports, self.p.epsilon, self.p.epsilon_w, self.p.max_iterations, True)
        self.assertTrue(result.finite)
        self.assertLessEqual(result.max_raw_weight, math.log(2.0) + 1e-12)
        self.assertLessEqual(result.normalization_error, 1e-12)

    def test_identical_reports_return_common_truth(self):
        reports = np.ones((27, 9)) * 3.25
        result = bounded_truth_discovery(reports, self.p.epsilon, self.p.epsilon_w, self.p.max_iterations, True)
        np.testing.assert_array_equal(result.truth, reports[0])
        self.assertEqual(result.iterations, 0)

    def test_rank_one_declares_angular_fallback(self):
        reports, _ = make_stability_reports(1, 1e-3, "rank-1")
        ids = np.arange(1, 28)
        _, available, diagnostic = angular_scores(reports, ids, set(int(x) for x in ids), 1, 1, 20, 1e-12, "rabod", True)
        self.assertFalse(available)
        self.assertTrue(diagnostic.fallback)

    def test_protected_stability_trial_succeeds(self):
        for geometry in ("full-rank", "rank-1"):
            for tau in (1e-3, 1e-12, 1e-150, 0.0):
                reports, truth = make_stability_reports(2, tau, geometry)
                result = stability_trial(self.p, reports, truth, geometry, True)
                self.assertTrue(result["success"], (geometry, tau, result))


if __name__ == "__main__":
    unittest.main()
