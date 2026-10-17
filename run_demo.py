"""Rebuild the interactive demo and a fully reproducible illustrative benchmark.

Requires Python >= 3.10. No third-party packages required.
"""
from pathlib import Path
import argparse
import csv
import json
from core import (read_inp, benchmark, make_training_bank, build_likelihood_cache,
                  rank_sites, make_test_cases, quality_surrogate,
                  Scenario, TIMESTEP_H, HORIZON_H)
from build_dashboard import build as build_dashboard
from create_network import make_inp

ROOT = Path(__file__).resolve().parent


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        return
    with path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)


def main(reps: int):
    make_inp()
    net = read_inp()
    bank, priors = make_training_bank()
    cache = build_likelihood_cache(net,bank)
    scores = rank_sites(net,bank,priors,cache,8,[])
    write_csv(ROOT/'outputs'/'initial_ranking.csv',scores)
    truth = Scenario('DEMO_J08','J08',5.5,8.0,1.0)
    quality = quality_surrogate(net,truth)
    write_csv(ROOT/'outputs'/'surrogate_quality_timeseries.csv',[
        {'time_h':k*TIMESTEP_H, 'node':node, 'synthetic_concentration':value}
        for node,values in quality.items() for k,value in enumerate(values)
    ])
    rows,summary=benchmark(net,n_reps=reps)
    write_csv(ROOT/'outputs'/'benchmark_trials.csv',rows)
    write_csv(ROOT/'outputs'/'benchmark_summary.csv',summary)
    path=build_dashboard()
    (ROOT/'outputs'/'metadata.json').write_text(json.dumps({
        'simulation_engine':'EDUCATIONAL SURROGATE - NOT EPANET',
        'network_nodes':len(net.node_order),
        'network_pipes':len(net.directed_edges),
        'candidate_sample_sites':len(net.candidates),
        'training_scenarios':len(bank),
        'held_out_test_cases':len(make_test_cases()),
        'sampling_slots_h':[8,10,12,14,16],
        'assay_threshold_arbitrary_units':0.08,
        'replications_per_case':reps,
        'assumed_sensitivity':.96,
        'assumed_specificity':.99,
        'assay_turnaround_lag':'zero (simplifying assumption)',
        'travel_cost':'schematic Euclidean distance penalty only',
        'model_limitations':'See docs/MODEL_LIMITATIONS.md',
    },indent=2),encoding='utf-8')
    print('\nAquaSentinel MILESTONE 01 — Offline educational surrogate')
    print(f'Network: {len(net.node_order)} nodes, {len(net.directed_edges)} pipes, {len(net.candidates)} candidate sampling nodes')
    print('Top five candidate nodes at first slot:',', '.join(s['node'] for s in scores[:5]))
    print('Benchmark columns: policy | event detection rate | penalized detection delay (h) | tests before detection on hits')
    for row in summary:
        print(f"  {row['policy']:9} {row['detection_rate']:.3f} {row['mean_penalized_delay_h']:.2f}h "
              f"{row['mean_tests_to_detection_detected_only']:.2f} tests")
    print(f'Open locally in a browser: {path}')
    print('NOTE: These are synthetic surrogate-only results; not EPANET or real-world performance.')


if __name__ == '__main__':
    ap=argparse.ArgumentParser(description='Build the AquaSentinel offline stage 1 demo')
    ap.add_argument('--reps',type=int,default=5,help='Replications per held-out case (default: 5)')
    args=ap.parse_args()
    if not 1 <= args.reps <= 1000:
        ap.error('--reps must be between 1 and 1000')
    main(args.reps)
