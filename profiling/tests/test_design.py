import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from design import derive, DEFAULT_RATES, REQUIRED


def fixture():
    return {'schema_version': 1, 'profiler_sha256': 'fixture', 'host': {'cpu_model': 'fixture'},
            'muni': {'commit': 'fixture'}, 'measurement_kind': 'test',
            'unmeasured': {'wall_energy_j': None},
            'stages': [{'name': name, 'units_per_iteration': 100,
                        'summary': {'cpu_s': {'median': 0.1}, 'wall_s': {'median': 0.2}}}
                       for name in sorted(REQUIRED)]}


class DesignTest(unittest.TestCase):
    def test_uses_per_operation_cpu_service_not_batch_wall_time(self):
        rates = {key: 0 for key in DEFAULT_RATES}
        rates['queries_s'] = 10
        design = derive(fixture(), rates, utilization=.5)
        self.assertAlmostEqual(design['scenario']['host_cpu_seconds_per_second'], .01)
        self.assertAlmostEqual(design['scenario']['reference_host_core_equivalents_at_target_utilization'], .02)

    def test_does_not_invent_hardware_or_power_requirements(self):
        design = derive(fixture())
        self.assertIsNone(design['architecture']['cpu_tile']['core_count'])
        self.assertIsNone(design['architecture']['packaging']['package_power_w'])
        self.assertIsNone(design['architecture']['memory']['required_dram_bandwidth_bytes_s'])
        self.assertIsNone(design['architecture']['inference_tile']['tops'])

    def test_rejects_incomplete_and_duplicate_stages(self):
        data = fixture()
        data['stages'].pop()
        with self.assertRaises(ValueError):
            derive(data)
        data = fixture()
        data['stages'].append(copy.deepcopy(data['stages'][0]))
        with self.assertRaises(ValueError):
            derive(data)

    def test_rejects_nonfinite_or_nonpositive_measurements(self):
        for bad in (float('nan'), float('inf'), 0, -1):
            data = fixture()
            data['stages'][0]['summary']['cpu_s']['median'] = bad
            with self.assertRaises(ValueError):
                derive(data)

    def test_rejects_invalid_scenario_rates(self):
        for bad in (float('nan'), float('inf'), -1):
            rates = DEFAULT_RATES.copy()
            rates['queries_s'] = bad
            with self.assertRaises(ValueError):
                derive(fixture(), rates)
        with self.assertRaises(ValueError):
            derive(fixture(), utilization=1)

    def test_amdahl_bound_keeps_other_stages(self):
        design = derive(fixture())
        self.assertAlmostEqual(design['software_findings']['service_requests']['ideal_decode_only_acceleration_upper_bound'], 1.5)


if __name__ == '__main__':
    unittest.main()
