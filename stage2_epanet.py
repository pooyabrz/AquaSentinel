"""AquaSentinel milestone 02: EPANET 2.2 quality -> Bayesian adaptive planner.

Production path requires EPA WNTR. No surrogate fallback is permitted in CLI.
The tests inject clearly labeled fixture frames to test pipeline behavior offline.
All input/output chemical concentrations in this module are mg/L; WNTR uses kg/m^3.
Only for simulated/tracer research, never regulatory water quality monitoring.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import tempfile
from pathlib import Path

import pandas as pd

from core import (Scenario, SAMPLE_SLOTS_H, THRESHOLD, SENSITIVITY, SPECIFICITY,
                  make_training_bank, make_test_cases, read_inp, rank_sites,
                  bayes_update, p_positive, hash_uniform)
from build_dashboard import build as build_html

ROOT = Path(__file__).resolve().parent
DEFAULT_INP = ROOT / 'data' / 'demo_network.inp'
STAGE2_OUTPUTS = ROOT / 'outputs' / 'epanet_stage2'
SOURCE_STRENGTH_MG_L = 1.0  # an arbitrary simulated tracer, NOT a risk threshold
QUALITY_UNITS = 'mg/L'
DEFAULT_REPS = 5


def validate_quality(q: pd.DataFrame, nodes: list[str], *, label: str) -> pd.DataFrame:
    """Validate that every sampling slot exists, without fabricating any missing time data."""
    if not isinstance(q, pd.DataFrame):
        raise TypeError(f'{label}: quality must be a pandas DataFrame')
    if q.empty or not q.index.is_unique:
        raise ValueError(f'{label}: empty or duplicate timestamps')
    if any(n not in q.columns for n in nodes):
        raise ValueError(f'{label}: missing water-network nodes')
    if not all((slot * 3600) in q.index for slot in SAMPLE_SLOTS_H):
        raise ValueError(f'{label}: required reporting timestamps missing (report step should be 1800 seconds)')
    numeric = q[nodes].astype(float)
    if not numeric.notna().all().all() or not math.isfinite(float(numeric.to_numpy().max())) or not math.isfinite(float(numeric.to_numpy().min())):
        raise ValueError(f'{label}: NaN/inf quality values')
    if float(numeric.to_numpy().min()) < -1e-8:
        raise ValueError(f'{label}: negative quality larger than numerical tolerance')
    return numeric.clip(lower=0)


def run_quality_epanet(
    scenario: Scenario,
    *,
    inp_file: Path = DEFAULT_INP,
    scratch_dir: Path | None = None,
) -> pd.DataFrame:
    """Run one independent EPANET 2.2 hydraulic + water-quality scenario.

    WNTR stores concentrations in kg/m^3. We convert source mg/L -> kg/m^3
    before calling the WNTR API, and resulting quality back to mg/L.
    """
    try:
        import wntr
    except ImportError as exc:
        raise RuntimeError('WNTR not installed: run .\\.venv\\Scripts\\python.exe -m pip install "wntr>=1.3,<2"') from exc
    wn = wntr.network.WaterNetworkModel(str(inp_file))
    if scenario.source is not None and scenario.source not in wn.junction_name_list:
        raise ValueError(f'{scenario.name}: source {scenario.source} is not a junction in network')
    wn.options.time.duration = 24 * 3600
    wn.options.time.hydraulic_timestep = 1800
    wn.options.time.quality_timestep = 300
    wn.options.time.pattern_timestep = 1800
    wn.options.time.report_timestep = 1800
    wn.options.quality.parameter = 'CHEMICAL'
    if scenario.source is not None:
        if scenario.start_h < 0 or scenario.duration_h <= 0 or scenario.start_h + scenario.duration_h > 24:
            raise ValueError('Injection must fit in the 24-hour simulation window')
        if any(abs(v * 2 - round(v * 2)) > 1e-8 for v in (scenario.start_h, scenario.duration_h)):
            raise ValueError('Injection times must align with the 30-minute source pattern')
        pattern = wntr.network.elements.Pattern.binary_pattern(
            'AS_PULSE',
            start_time=int(round(scenario.start_h * 3600)),
            end_time=int(round((scenario.start_h + scenario.duration_h) * 3600)),
            duration=wn.options.time.duration,
            step_size=wn.options.time.pattern_timestep,
        )
        wn.add_pattern('AS_PULSE', pattern)
        # WNTR uses kg/m3: 1 mg/L = 0.001 kg/m3.
        wn.add_source('AS_SOURCE', scenario.source, 'SETPOINT', scenario.strength / 1000.0, 'AS_PULSE')
    if scratch_dir is None:
        with tempfile.TemporaryDirectory(prefix='aquasentinel_epanet_') as dirname:
            results = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(Path(dirname) / 'run'), version=2.2)
    else:
        scratch_dir.mkdir(parents=True, exist_ok=True)
        results = wntr.sim.EpanetSimulator(wn).run_sim(file_prefix=str(scratch_dir / 'run'), version=2.2)
    quality_kg_m3 = results.node['quality']
    return validate_quality(quality_kg_m3 * 1000.0, list(wn.node_name_list), label=scenario.name)


def build_cache(net, scenarios: list[Scenario], frames: dict[str, pd.DataFrame]) -> dict:
    """The exact same (scenario, time, location) likelihood layout as Stage 1."""
    cache = {}
    for s in scenarios:
        if s.name not in frames:
            raise ValueError(f'Missing simulation: {s.name}')
        quality = validate_quality(frames[s.name], net.node_order, label=s.name)
        for slot in SAMPLE_SLOTS_H:
            row = quality.loc[slot * 3600]
            cache[(s.name, slot)] = {n: p_positive(float(row[n])) for n in net.candidates}
    return cache


def quality_at(q: pd.DataFrame, node: str, hour: int) -> float:
    return float(q.loc[hour * 3600, node])


def simulate_from_physical_frames(net, bank, priors, cache, truth, truth_quality,
                                  policy, replicate=2026) -> dict:
    """Identical sampling slots and budget for policies; 0-hour assay lag.

    Detection is a true-positive observation, not any (potentially false) alarm.
    This distinction can only be made because this is a simulated benchmark.
    """
    posterior = priors[:]
    visited = []
    detected = False
    first_hit = None
    detection_h = None
    false_alarms = 0
    for slot in SAMPLE_SLOTS_H:
        if policy == 'random':
            r = random.Random(int(hash_uniform(replicate, truth.name, slot, 'random') * 2**32))
            site = r.choice(sorted(set(net.candidates) - set(visited)))
        elif policy in ('adaptive', 'static'):
            ranked = rank_sites(net, bank, posterior if policy == 'adaptive' else priors,
                                cache, slot, visited, mode=policy)
            site = ranked[0]['node']
        else:
            raise ValueError('Invalid sampling policy')
        visited.append(site)
        concentration = quality_at(truth_quality, site, slot)
        actual_above_detection_threshold = truth.source is not None and concentration >= THRESHOLD
        obs_pos = hash_uniform(replicate, truth.name, slot, site, 'assay') < p_positive(concentration)
        if obs_pos and not actual_above_detection_threshold:
            false_alarms += 1
        if obs_pos and actual_above_detection_threshold and not detected:
            detected, first_hit, detection_h = True, len(visited), float(slot)
        if policy == 'adaptive':
            likelihood = [cache[(s.name, slot)][site] for s in bank]
            posterior = bayes_update(posterior, likelihood, obs_pos)
    return {
        'truth': truth.name, 'has_event': truth.source is not None,
        'policy': policy, 'replicate': replicate, 'detected': detected,
        'detection_hour': detection_h,
        'detection_delay_h': detection_h-truth.start_h if detected else None,
        'first_detection_test': first_hit,
        'penalized_delay_h': (detection_h if detected else 18.0)-truth.start_h if truth.source else None,
        'false_alarms': false_alarms, 'tests_run': len(visited), 'sites': ','.join(visited),
    }


def summarize_benchmark(rows: list[dict]) -> list[dict]:
    result = []
    for policy in ('adaptive', 'static', 'random'):
        r = [item for item in rows if item['policy'] == policy]
        e = [item for item in r if item['has_event']]
        n = [item for item in r if not item['has_event']]
        hits = [item for item in e if item['detected']]
        result.append({
            'policy': policy,
            'event_trials': len(e),
            'detection_rate': sum(item['detected'] for item in e)/len(e) if e else None,
            'mean_penalized_delay_h': sum(item['penalized_delay_h'] for item in e)/len(e) if e else None,
            'mean_tests_to_detection_on_hits': sum(item['first_detection_test'] for item in hits)/len(hits) if hits else None,
            'false_alarms_per_nonevent_day': sum(item['false_alarms'] for item in n)/len(n) if n else None,
            'max_tests_per_day': max(item['tests_run'] for item in r) if r else 0,
        })
    return result


def save_quality_bank(path: Path, scenarios: list[Scenario], frames: dict[str, pd.DataFrame], nodes: list[str]):
    """One row per (scenario,time), columns = nodes; includes every report time."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['scenario', 'time_seconds'] + nodes)
        for scenario in scenarios:
            q = frames[scenario.name]
            for time, row in q[nodes].iterrows():
                writer.writerow([scenario.name, int(time)] + [float(row[n]) for n in nodes])


def build_payload(net, bank, priors, cache, demo: Scenario, demo_quality: pd.DataFrame, engine: str):
    return {
        'engine': engine,
        'assay_threshold': THRESHOLD,
        'nodes': [{'id': n, 'x': net.coordinates[n][0], 'y': net.coordinates[n][1],
                   'demand': net.demand[n]} for n in net.node_order],
        'edges': [list(p) for p in net.directed_edges],
        'slots': list(SAMPLE_SLOTS_H),
        'scenarios': [s.__dict__ for s in bank],
        'priors': priors,
        'likelihood': {str(slot): {n: [cache[(s.name, slot)][n] for s in bank]
                                   for n in net.candidates} for slot in SAMPLE_SLOTS_H},
        'truth_conc': {str(slot): {n: quality_at(demo_quality, n, slot)
                                  for n in net.candidates} for slot in SAMPLE_SLOTS_H},
    }


def write_csv_dicts(path: Path, rows: list[dict]):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def run_pipeline(mode: str, inp: Path, output_dir: Path, replicates: int = DEFAULT_REPS,
                 simulator=run_quality_epanet, engine_label='EPANET 2.2 through WNTR'):
    """Run real physical simulations, then use them in the adaptive Bayesian planner.

    `simulator` is injected only by tests to exercise the pipeline without WNTR.
    """
    if mode not in ('smoke', 'demo', 'benchmark'):
        raise ValueError('Unknown mode')
    if not 1 <= replicates <= 1000:
        raise ValueError('replicates must be 1..1000')
    net = read_inp(inp)  # Stage 2 currently targets the included synthetic DAG INP.
    output_dir.mkdir(parents=True, exist_ok=True)
    demo = Scenario('DEMO_J08_HELDOUT','J08',6.0,7.5,0.95 * SOURCE_STRENGTH_MG_L)
    print('Running simulation for held-out demo source J08... ', flush=True)
    demo_quality = validate_quality(simulator(demo, inp_file=inp), net.node_order, label=demo.name)
    demo_quality.to_csv(output_dir / 'epanet_quality_demo_mg_l.csv', index_label='time_seconds')
    print('  Maximum quality (mg/L):', f'{demo_quality.max().max():.6f}', flush=True)
    if mode == 'smoke':
        if float(demo_quality.max().max()) <= 0:
            raise RuntimeError('Zero signal from simulated source. Inspect hydraulics and injection settings.')
        return {'smoke_quality_file':str(output_dir/'epanet_quality_demo_mg_l.csv')}
    bank, priors = make_training_bank()
    train_frames = {}
    for idx,s in enumerate(bank,1):
        print(f'Training scenario {idx}/{len(bank)}: {s.name}',flush=True)
        train_frames[s.name] = validate_quality(simulator(s, inp_file=inp), net.node_order, label=s.name)
    cache = build_cache(net, bank, train_frames)
    save_quality_bank(output_dir / 'epanet_training_quality_mg_l.csv', bank, train_frames, net.node_order)
    rank = rank_sites(net,bank,priors,cache,SAMPLE_SLOTS_H[0],[])
    write_csv_dicts(output_dir / 'epanet_initial_ranking.csv', rank)
    if float(demo_quality.max().max()) <= 0:
        raise RuntimeError('No signal detected in demo case: refusing to build a misleading dashboard')
    payload = build_payload(net,bank,priors,cache,demo,demo_quality,engine_label)
    dashboard = build_html(output_dir / 'AquaSentinel_EPANET_Dashboard.html', payload=payload)
    metadata = {
        'engine': engine_label,
        'network': str(inp), 'network_type': 'synthetic, not field calibrated',
        'quality_unit': 'mg/L', 'assay_threshold_mg_l': THRESHOLD,
        'source_strength_mg_l': SOURCE_STRENGTH_MG_L,
        'source_method': 'time-patterned SETPOINT injection',
        'source_timing': '30-minute pattern aligned',
        'assay_model': {'sensitivity': SENSITIVITY,'specificity': SPECIFICITY},
        'assay_turnaround_hours': 0,
        'sampling_slots_h': list(SAMPLE_SLOTS_H),
        'total_training_scenarios':len(bank),
        'decision_weights':'Stage1 heuristic; not optimized and no real travel times',
        'caution':'For synthetic research/demo only. Not real contamination risk or validated sampling guidance.'
    }
    (output_dir / 'epanet_run_metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8')
    result = {'dashboard':str(dashboard),'training_scenarios':len(bank),
              'top_five': [r['node'] for r in rank[:5]]}
    if mode == 'benchmark':
        cases = make_test_cases()
        trials = []
        for idx,case in enumerate(cases,1):
            print(f'Held-out test {idx}/{len(cases)}: {case.name}',flush=True)
            case_q = validate_quality(simulator(case,inp_file=inp),net.node_order,label=case.name)
            for replicate in range(replicates):
                for policy in ('adaptive','static','random'):
                    trials.append(simulate_from_physical_frames(net, bank, priors, cache,
                        case,case_q,policy,replicate=2026+replicate))
        summary = summarize_benchmark(trials)
        write_csv_dicts(output_dir / 'epanet_benchmark_trials.csv', trials)
        write_csv_dicts(output_dir / 'epanet_benchmark_summary.csv', summary)
        metadata.update({'test_scenarios':len(cases),'replicates_per_test_scenario':replicates,
                         'miss_penalty_rule':'unobserved event assigned detection time of 18h for penalized-delay metric',
                         'warning':'Training and test scenarios use the same synthetic network; not independent field validation'})
        (output_dir / 'epanet_run_metadata.json').write_text(json.dumps(metadata,indent=2,ensure_ascii=False),encoding='utf-8')
        result['benchmark'] = summary
    return result


def main():
    parser = argparse.ArgumentParser(description='AquaSentinel M02: EPANET 2.2 -> adaptive Bayesian site selection')
    parser.add_argument('--mode', choices=['smoke','demo','benchmark'], default='demo')
    parser.add_argument('--replicates', type=int,default=DEFAULT_REPS)
    parser.add_argument('--input',type=Path,default=DEFAULT_INP)
    parser.add_argument('--output-dir',type=Path,default=STAGE2_OUTPUTS)
    args=parser.parse_args()
    if not args.input.is_file():
        parser.error(f'Network file not found: {args.input}')
    try:
        result = run_pipeline(args.mode,args.input,args.output_dir,args.replicates)
    except (RuntimeError,ValueError,FileNotFoundError) as exc:
        parser.exit(1, f'ERROR: {exc}\n')
    print('\nAquaSentinel milestone 02:', json.dumps(result,indent=2,ensure_ascii=False))
    print('All stage-2 outputs are EPANET-backed only when run with installed WNTR.')

if __name__ == '__main__':
    main()
