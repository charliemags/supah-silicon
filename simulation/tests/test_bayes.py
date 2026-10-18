"""Checks for the Bayesian search model. No HotSpot needed."""
from pathlib import Path
import sys
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import bayes
import fast
from verify_submission import parse_submission

LAYOUT = Path(__file__).resolve().parents[1] / "layouts/bayes-v1/submission.json"


class BayesTest(unittest.TestCase):
    def test_gp_reproduces_observed_points(self):
        rng = np.random.default_rng(0)
        x = rng.uniform(-1, 1, (12, 4))
        y = (x ** 2).sum(1)
        mean, sd = bayes.GP().fit(x, y).predict(x)
        self.assertLess(np.abs(mean - y).max(), 0.05)
        self.assertTrue((sd < 0.1).all())

    def test_uncertainty_grows_away_from_data(self):
        x = np.zeros((3, 2)) + np.array([[0, 0], [0.1, 0], [0, 0.1]])
        gp = bayes.GP().fit(x, np.array([1.0, 1.1, 0.9]))
        _, near = gp.predict(np.array([[0.05, 0.05]]))
        _, far = gp.predict(np.array([[5.0, 5.0]]))
        self.assertGreater(far[0], near[0])

    def test_expected_improvement_prefers_lower_mean_and_more_uncertainty(self):
        ei = bayes.expected_improvement(np.array([0.9, 1.1, 1.1]), np.array([0.01, 0.01, 0.5]), 1.0)
        self.assertGreater(ei[0], ei[1])
        self.assertGreater(ei[2], ei[1])

    def test_saved_layout_satisfies_frozen_rules(self):
        layout, paths = parse_submission(LAYOUT, fast.SPEC)
        passed, reason, _ = fast.legal(layout, paths)
        self.assertTrue(passed, reason)


if __name__ == "__main__":
    unittest.main()
