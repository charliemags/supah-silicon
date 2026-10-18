"""Regression checks for the participant workflow, using the real rule checker."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import fast
import optimize
from export_system_profile import export, PROXIES
from verify_submission import parse_submission

P2 = Path(__file__).resolve().parents[1] / "layouts/p2/submission.json"


class WorkflowTest(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads(P2.read_text())["placements_mm"]

    def test_existing_design_satisfies_frozen_rules(self):
        passed, reason, route = fast.legal(self.layout)
        self.assertTrue(passed, reason)
        self.assertEqual(len(route["routes"]), 8)

    def test_explicit_routes_round_trip_through_submission_validator(self):
        _, _, routing = fast.legal(self.layout)
        paths = {k: v["path_grid"] for k, v in routing["routes"].items()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "submission.json"
            optimize.write_json(path, {"placements_mm": self.layout, "wire_routes_grid": paths})
            layout, recovered = parse_submission(path, fast.SPEC)
            self.assertTrue(fast.legal(layout, recovered)[0])
            self.assertEqual(paths, recovered)

    def test_invalid_explicit_route_is_not_silently_replaced(self):
        with patch.object(fast.subprocess, "run", side_effect=AssertionError("solver must not run")):
            result = fast.estimate(self.layout, paths={"P0": [[0, 0]]})
        self.assertFalse(result["passed"])

    def test_hbm_regression_cannot_hide_behind_gpu_improvement(self):
        reference = {"gpu": 105, "hbm": 100}
        self.assertGreater(optimize.score({"gpu": 95, "hbm": 110}, reference), 1)
        self.assertLess(optimize.score({"gpu": 100, "hbm": 95}, reference), 1)

    def test_invalid_mesh_or_workload_fails_before_solver(self):
        with self.assertRaises(ValueError):
            fast.estimate(self.layout, grid=48)
        with self.assertRaises(ValueError):
            fast.estimate(self.layout, workloads=["supah_measured"])
        with self.assertRaises(ValueError):
            fast.estimate(self.layout, workloads=[])
        with self.assertRaises(ValueError):
            fast.estimate(self.layout, workloads=["memory_stream", "memory_stream"])

    def test_system_export_does_not_invent_energy_per_task(self):
        report = {"passed": True, "grid": 128, "hotspot_sha256": "fixture", "score": 0.98,
                  "provenance": {"verification": "fixture"},
                  "workloads": {name: {"total_w": 350, "gpu_peak_c": 100, "hbm_peak_c": 90}
                                for name in PROXIES}}
        profile = export(report)
        self.assertTrue(all(case["joules_per_task"] is None for case in profile["workloads"].values()))
        del report["workloads"]["memory_stream"]
        with self.assertRaises(ValueError):
            export(report)


if __name__ == "__main__":
    unittest.main()
