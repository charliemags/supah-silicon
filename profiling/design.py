"""Derive an auditable architecture hypothesis and host-capacity scenario from a Muni profile.

No conversion from Ruby timings to custom-chip watts, area, TOPS or DRAM traffic.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path

REQUIRED = {f'{domain}.{operation}' for domain in ('service_requests', 'building_permits')
            for operation in ('json_decode', 'normalize', 'insert_individual', 'insert_bulk')}
REQUIRED |= {'records.indexed_query', 'inference.empirical_311', 'digest.context_and_rank',
             'digest.select_cards', 'inference.request_prepare'}
DEFAULT_RATES = {'service_request_rows_s': 100, 'permit_rows_s': 100,
                 'queries_s': 10, 'empirical_predictions_s': 10, 'digest_requests_s': 0.1}


def stages_from(report):
    if report.get('schema_version') != 1 or not report.get('profiler_sha256'):
        raise ValueError('Expected a version 1 measured profile with profiler hash')
    rows = report.get('stages', [])
    stages = {s['name']: s for s in rows}
    if len(stages) != len(rows) or REQUIRED - stages.keys():
        raise ValueError('Missing or duplicate measured stages')
    for stage in stages.values():
        if not isinstance(stage['units_per_iteration'], (float, int)) or not math.isfinite(stage['units_per_iteration']) or stage['units_per_iteration'] <= 0:
            raise ValueError('Positive finite work-unit count required')
        for metric in ('cpu_s', 'wall_s'):
            value = stage['summary'][metric]['median']
            if not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Positive finite measured durations required')
    return stages


def derive(report, rates=None, utilization=0.6):
    stages = stages_from(report)
    rates = DEFAULT_RATES.copy() if rates is None else rates.copy()
    if set(rates) != set(DEFAULT_RATES) or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0 for v in rates.values()):
        raise ValueError('Provide all five nonnegative finite scenario rates')
    if not math.isfinite(utilization) or not 0 < utilization < 1:
        raise ValueError('Target utilization must be between zero and one')

    def per_unit(name, metric):
        s = stages[name]
        return s['summary'][metric]['median'] / s['units_per_iteration']

    ingestion = {}
    operations = {}
    for domain, rate_name in (('service_requests', 'service_request_rows_s'), ('building_permits', 'permit_rows_s')):
        individual = sum(per_unit(f'{domain}.{op}', 'wall_s') for op in ('json_decode', 'normalize', 'insert_individual'))
        bulk = sum(per_unit(f'{domain}.{op}', 'wall_s') for op in ('json_decode', 'normalize', 'insert_bulk'))
        decode_fraction = per_unit(f'{domain}.json_decode', 'wall_s') / bulk
        normalize_fraction = per_unit(f'{domain}.normalize', 'wall_s') / bulk
        ingestion[domain] = {
            'individual_insert_vs_bulk_insert_speedup': per_unit(f'{domain}.insert_individual', 'wall_s') / per_unit(f'{domain}.insert_bulk', 'wall_s'),
            'estimated_pipeline_speedup_using_existing_bulk_api': individual / bulk,
            'pipeline_basis': 'Sum of isolated stage medians, not an end-to-end measured speedup',
            'bulk_pipeline_wall_s_per_row': bulk,
            'decode_time_fraction': decode_fraction,
            'normalization_time_fraction': normalize_fraction,
            'ideal_decode_only_acceleration_upper_bound': 1 / (1 - decode_fraction),
            'ideal_normalize_only_acceleration_upper_bound': 1 / (1 - normalize_fraction),
            'amdahl_assumption': 'Only this stage becomes infinitely fast; all other stage times and workload stay fixed',
        }
        operations[rate_name] = sum(per_unit(f'{domain}.{op}', 'cpu_s') for op in ('json_decode', 'normalize', 'insert_bulk'))
    operations.update(queries_s=per_unit('records.indexed_query', 'cpu_s'),
                      empirical_predictions_s=per_unit('inference.empirical_311', 'cpu_s'),
                      digest_requests_s=sum(per_unit(name, 'cpu_s') for name in ('digest.context_and_rank', 'digest.select_cards', 'inference.request_prepare')))
    contributions = {name: rate * operations[name] for name, rate in rates.items()}
    demand = sum(contributions.values())
    return {
        'schema_version': 1,
        'name': 'Supah Edge v0 — workload-derived architecture hypothesis',
        'status': 'Reference-host capacity scenario and architecture requirements; not RTL or a fabricated chip',
        'reference_host': report['host'], 'muni_commit': report['muni']['commit'],
        'source_profiler_sha256': report['profiler_sha256'],
        'measured_scope': report['measurement_kind'],
        'software_findings': ingestion,
        'scenario': {
            'rates_are_assumptions': True, 'rates': rates, 'target_utilization': utilization,
            'host_cpu_seconds_per_unit': operations, 'host_cpu_seconds_per_second_by_activity': contributions,
            'host_cpu_seconds_per_second': demand,
            'reference_host_core_equivalents_at_target_utilization': demand / utilization,
            'integer_reference_host_cpu_budget_lower_bound': math.ceil(demand / utilization),
            'limitations': ['Service-demand estimate only; excludes queues, synchronization, cold caches and contention',
                            'Same host, same Ruby runtime and same dataset sizes; not a prediction for an ARM or RISC-V custom core',
                            'Excludes generative inference, full analytics refresh, network fetch, other server work and production redundancy',
                            'SQLite writer serialization and Ruby process/thread behavior require a separate concurrency benchmark']},
        'architecture': {
            'cpu_tile': {'decision': 'Start with programmable 64-bit CPU cores and shared cache for Ruby, SQLite, ranking and empirical prediction',
                         'core_count': None, 'evidence': 'These measured operations execute through the CPU software path; CPU time alone cannot distinguish ALU from memory stalls'},
            'memory': {'decision': 'Begin evaluation on a shared-memory SoC; measure working set and cache misses before fixing SRAM or external-memory bandwidth',
                       'capacity_bytes': None, 'required_dram_bandwidth_bytes_s': None,
                       'hbm': 'Not justified by this small replay; local LLM weights and KV-cache requirements remain unmeasured'},
            'io': {'decision': 'Keep durable records in external storage; retain standard storage/network DMA and normal OS support',
                   'bandwidth_bytes_s': None},
            'inference_tile': {'decision': 'Reserve an optional programmable inference-accelerator interface; select NPU/GPU only after profiling a chosen local model',
                               'tops': None, 'precision': None, 'weights_bytes': None, 'kv_cache_bytes': None},
            'custom_kernel_gate': {'decision': 'Prototype candidate kernels in software/FPGA before creating dedicated RTL',
                                   'first_candidates': ['Record normalization/tokenization', 'Batched columnar filtering or context assembly'],
                                   'required_evidence': ['CPU/cache/DRAM counters', 'End-to-end speedup at unchanged outputs', 'Measured energy per task', 'Synthesis area/timing and interface overhead']},
            'packaging': {'decision': 'Evaluate a CPU/memory/I-O SoC with an optional accelerator; 2.5D is a later bandwidth/capacity decision',
                          'process_node': None, 'die_area_mm2': None, 'package_power_w': None}},
        'simulation_bridge': {
            'track_1': 'Use the explicit rates and reference-host service demand as a workload-sizing input; add measured system power and concurrency',
            'track_2': 'Retain the verified four-GPU/four-HBM challenge layout unchanged. These CPU timings cannot be converted into its synthetic power maps',
            'next_thermal_input': 'Calibrated per-component power traces plus a physically defined custom architecture outside the frozen challenge'},
        'unmeasured': report['unmeasured'],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--rates', type=Path, help='JSON object with all five scenario rates')
    parser.add_argument('--utilization', type=float, default=0.6)
    args = parser.parse_args()
    raw = args.profile.read_bytes()
    rates = json.loads(args.rates.read_text()) if args.rates else None
    design = derive(json.loads(raw), rates, args.utilization)
    design['profile_sha256'] = hashlib.sha256(raw).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(design, indent=2, allow_nan=False) + '\n')
    print(args.output)


if __name__ == '__main__':
    main()
