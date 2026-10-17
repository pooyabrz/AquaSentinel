"""Generate an interactive, self-contained, offline HTML demonstration.
No package installation and no network connection needed to view the dashboard.
"""
from pathlib import Path
import json
from core import read_inp, make_training_bank, build_likelihood_cache, quality_surrogate, Scenario, SAMPLE_SLOTS_H

ROOT = Path(__file__).resolve().parent


def make_payload():
    net = read_inp()
    bank, priors = make_training_bank()
    cache = build_likelihood_cache(net, bank)
    # A hidden scenario drives the reveal button. Synthetic, not a field incident.
    truth = Scenario('DEMO_J08', 'J08', 5.5, 8.0, 1.0)
    c = quality_surrogate(net,truth)
    return {
        'nodes': [{'id':n,'x':net.coordinates[n][0],'y':net.coordinates[n][1],
                   'demand':net.demand[n]} for n in net.node_order],
        'edges':[list(p) for p in net.directed_edges],
        'slots': list(SAMPLE_SLOTS_H),
        'scenarios':[s.__dict__ for s in bank],
        'priors':priors,
        'likelihood':{str(slot):{n:[cache[(s.name,slot)][n] for s in bank] for n in net.candidates} for slot in SAMPLE_SLOTS_H},
        'truth_conc':{str(slot):{n: c[n][int(round(slot/.5))] for n in net.candidates} for slot in SAMPLE_SLOTS_H},
    }


def build(path=ROOT / 'AquaSentinel_Dashboard.html', payload=None):
    template = (ROOT / 'dashboard_template.html').read_text(encoding='utf-8')
    data = json.dumps(payload if payload is not None else make_payload(),ensure_ascii=False,separators=(',',':')).replace('</','<\\/')
    html = template.replace('/*PAYLOAD_GOES_HERE*/',data)
    if payload is not None:
        engine = payload.get('engine', '')
        is_epanet = engine.startswith('EPANET')
        if is_epanet:
            html = html.replace('MILESTONE 01', 'MILESTONE 02')
            html = html.replace('This demo uses a simplified directed-graph transport surrogate, <strong>not EPANET hydraulics</strong>.',
                'This demo uses scenario-specific <strong>EPANET 2.2 water-quality simulation results</strong> generated through WNTR.')
            html = html.replace('a hidden synthetic scenario (idealized', 'a hidden EPANET scenario (idealized')
            html = html.replace('simplified directed-graph transport surrogate', 'EPANET-simulated water-quality transport')
            html = html.replace('AquaSentinel | Offline Prototype', 'AquaSentinel | EPANET-Backed Prototype')
        else:
            html = html.replace('AQUASENTINEL AI · MILESTONE 01', 'AQUASENTINEL AI · TEST FIXTURE ONLY')
            html = html.replace('This demo uses a simplified directed-graph transport surrogate, <strong>not EPANET hydraulics</strong>.',
                'This demo contains an <strong>injected test fixture, NOT an EPANET result</strong>.')
    Path(path).write_text(html,encoding='utf-8')
    return Path(path)

if __name__ == '__main__':
    print('Wrote:', build())
