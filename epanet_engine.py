"""Single EPANET quality simulation, using the validated stage-2 WNTR adapter.

All output quality columns are in mg/L (hypothetical, non-hazardous tracer).
Does not use the simplified directed-graph transport approximation.
"""
from pathlib import Path
import argparse
from core import Scenario
from stage2_epanet import ROOT, run_quality_epanet


def run_epanet(inp_file=ROOT / 'data' / 'demo_network.inp', source='J08',
               start_h=6.0, duration_h=7.5, strength_mg_l=0.95,
               output=ROOT / 'outputs' / 'epanet_quality_mg_l.csv'):
    q = run_quality_epanet(Scenario('SINGLE_REAL_EPANET',source,start_h,duration_h,strength_mg_l),
                           inp_file=Path(inp_file))
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    q.to_csv(output,index_label='time_seconds')
    print(f'EPANET 2.2 quality saved: {len(q)} rows x {len(q.columns)} nodes, mg/L')
    print(f'Maximum predicted concentration: {q.max().max():.6f} mg/L')
    print(f'File: {output}')
    return q

if __name__=='__main__':
    ap = argparse.ArgumentParser(description='Run a single real EPANET 2.2 tracer simulation')
    ap.add_argument('--input', default=str(ROOT/'data'/'demo_network.inp'))
    ap.add_argument('--source', default='J08')
    ap.add_argument('--output', default=str(ROOT/'outputs'/'epanet_quality_mg_l.csv'))
    ap.add_argument('--start-h',type=float,default=6.0)
    ap.add_argument('--duration-h',type=float,default=7.5)
    ap.add_argument('--strength-mg-l',type=float,default=0.95)
    args=ap.parse_args()
    run_epanet(inp_file=args.input, source=args.source, output=args.output,
               start_h=args.start_h,duration_h=args.duration_h,strength_mg_l=args.strength_mg_l)
