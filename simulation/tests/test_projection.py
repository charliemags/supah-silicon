"""Projection proposals must still satisfy the unchanged organizer validator."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
HAS_SCIPY = importlib.util.find_spec('scipy') is not None
if HAS_SCIPY:
    import project


@unittest.skipUnless(HAS_SCIPY, 'constraint projection requires the native search image')
class ProjectionTest(unittest.TestCase):
    def test_fixed_target_is_preserved_and_result_passes_exact_router(self):
        source = Path(__file__).resolve().parents[1]/'layouts/supah-v1/submission.json'
        anchor = json.loads(source.read_text())['placements_mm']
        target = [round(v+0.1,3) for v in anchor['G0']]
        candidate = project.project(anchor,target)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate['G0'],target)
        self.assertTrue(project.fast.legal(candidate)[0])

    def test_invalid_seed_cannot_be_projected_and_promoted(self):
        anchor = {die:[1.,1.] for die in project.DIES}
        self.assertIsNone(project.project(anchor,[4.,4.]))


if __name__=='__main__':
    unittest.main()
