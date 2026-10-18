"""Numerical and data-integrity checks for the thermal surrogate."""
import sys
from pathlib import Path
import unittest

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import surrogate


class SurrogateTest(unittest.TestCase):
    def test_smooth_temperature_prediction_on_held_out_positions(self):
        x = np.linspace(-2, 2, 17)[:, None]
        y = 100 + 0.5*x[:, 0]**2
        model = surrogate.GaussianProcess().fit(x, y)
        test = np.array([[-1.1], [0.1], [1.1]])
        mean, std = model.predict(test)
        np.testing.assert_allclose(mean, 100+0.5*test[:, 0]**2, atol=0.08)
        self.assertTrue(np.all(std >= 0))
        self.assertTrue(np.isfinite(model.loo_rmse_c))
        _, far_std = model.predict(np.array([[10.0]]))
        self.assertGreater(far_std[0], max(std))

    def test_training_excludes_wrong_mesh_missing_workload_and_custom_routes(self):
        layout = {d: [i, 0] for i, d in enumerate(surrogate.DIES)}
        valid = {"passed": True, "grid": 64, "submission": {"placements_mm": layout},
                 "peaks": {"memory_stream": {"G0": 110, "H0": 94, "H1": 95}}}
        records = [valid, valid, {**valid, "grid": 16}, {**valid, "passed": False},
                   {**valid, "peaks": {}},
                   {**valid, "submission": {"placements_mm": layout, "wire_routes_grid": {"P0": [[1, 1]]}}}]
        x, y = surrogate.observations(records, "memory_stream", "H")
        self.assertEqual(len(x), 1)
        self.assertEqual(y, [95])

    def test_candidate_prefilter_respects_die_clearance(self):
        layout = surrogate.fast.SPEC["example_layouts_mm"]["ring_compact"]
        self.assertTrue(surrogate.cheap_legal(surrogate.vector(layout)))
        layout = {d: [1, 1] for d in surrogate.DIES}
        self.assertFalse(surrogate.cheap_legal(surrogate.vector(layout)))

    def test_additive_model_combines_independent_die_contributions(self):
        rng = np.random.default_rng(4)
        x = rng.uniform(-1, 1, (80, 4))
        y = 100 + x[:, 0] + 0.5*x[:, 2]
        model = surrogate.GaussianProcess(additive=True).fit(x, y)
        test = rng.uniform(-0.8, 0.8, (12, 4))
        mean, std = model.predict(test)
        np.testing.assert_allclose(mean, 100+test[:, 0]+0.5*test[:, 2], atol=0.08)
        self.assertTrue(np.all(np.isfinite(std)))

    def test_per_die_predictions_preserve_distinct_temperatures(self):
        x = np.linspace(-2, 2, 17)[:, None]
        y = np.column_stack([100+x[:, 0], 90-0.5*x[:, 0]])
        model = surrogate.GaussianProcess().fit(x, y)
        test = np.array([[-1.1], [0.1], [1.1]])
        mean, std = model.predict(test)
        expected = np.column_stack([100+test[:, 0], 90-0.5*test[:, 0]])
        np.testing.assert_allclose(mean, expected, atol=0.08)
        self.assertEqual(std.shape, expected.shape)
        self.assertTrue(np.all(std >= 0))


if __name__ == "__main__":
    unittest.main()
