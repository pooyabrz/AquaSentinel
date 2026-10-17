"""AquaSentinel educational sampler and reproducible benchmark.

IMPORTANT: Uses a deliberately simplified directed-graph time-delay transport
surrogate, NOT a validated hydraulic or EPANET water-quality simulation.
See docs/MODEL_LIMITATIONS.md. No clinical or public-health decisions.

All code in this file uses only the Python standard library.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict, deque
from pathlib import Path
import hashlib
import math
import random

ROOT = Path(__file__).resolve().parent
TIMESTEP_H = 0.5
HORIZON_H = 24
SAMPLE_SLOTS_H = (8, 10, 12, 14, 16)
THRESHOLD = 0.08    # synthetic tracer units, NOT a health threshold
SENSITIVITY = 0.96
SPECIFICITY = 0.99


@dataclass(frozen=True)
class Scenario:
    name: str
    source: str | None
    start_h: float
    duration_h: float
    strength: float


@dataclass
class Network:
    coordinates: dict
    demand: dict
    directed_edges: list
    lengths_m: dict
    node_order: list
    candidates: list


def read_inp(path: Path | str = ROOT / 'data' / 'demo_network.inp') -> Network:
    """Read only the tiny supported INP subset. Edge order defines surrogate flow.

    This parser is intentionally NOT a general EPANET parser; WNTR handles
    general EPANET INP files in the optional adapter.
    """
    section = None
    coordinates, demand, edges, lengths = {}, {}, [], {}
    seen = set()
    for raw in Path(path).read_text(encoding='utf-8').splitlines():
        line = raw.split(';', 1)[0].strip()
        if not line:
            continue
        if line.startswith('['):
            section = line.upper()
            continue
        p = line.split()
        if section == '[JUNCTIONS]':
            demand[p[0]] = float(p[2]); seen.add(p[0])
        elif section == '[RESERVOIRS]':
            demand[p[0]] = 0.0; seen.add(p[0])
        elif section == '[PIPES]':
            u, v = p[1:3]
            edges.append((u, v))
            lengths[(u, v)] = float(p[3])
        elif section == '[COORDINATES]':
            coordinates[p[0]] = (float(p[1]), float(p[2]))
    if not edges or 'R0' not in seen or seen != set(coordinates):
        raise ValueError('INP demo needs a reservoir R0, pipes, and coordinates for each node')
    indeg = {node: 0 for node in seen}
    outgoing = defaultdict(list)
    for u, v in edges:
        if u not in seen or v not in seen:
            raise ValueError('Pipe references an unknown node')
        indeg[v] += 1
        outgoing[u].append(v)
    q = deque(sorted(n for n, k in indeg.items() if k == 0))
    order = []
    while q:
        node = q.popleft()
        order.append(node)
        for nxt in outgoing[node]:
            indeg[nxt] -= 1
            if indeg[nxt] == 0:
                q.append(nxt)
    if len(order) != len(seen):
        raise ValueError('Surrogate expects a directed acyclic graph. Use WNTR for general networks.')
    return Network(coordinates, demand, edges, lengths, order, sorted(n for n in seen if n != 'R0'))


def quality_surrogate(network: Network, s: Scenario, velocity_m_s: float = .22) -> dict[str, list[float]]:
    """Illustrative transport: lagged equal-inflow mixing and first-order decay.

    Not mass-balance accurate; no hydraulic solver or directional-flow estimate.
    Each pipe has a fixed hypothetical velocity and upstream-to-downstream
    direction defined by file order. Use epanet_engine.py for physical simulation.
    """
    n_steps = int(HORIZON_H / TIMESTEP_H) + 1
    incoming = defaultdict(list)
    for u, v in network.directed_edges:
        lag = max(1, int(round(network.lengths_m[(u, v)] / (velocity_m_s * 3600 * TIMESTEP_H))))
        attenuation = math.exp(-0.075 * lag * TIMESTEP_H)
        incoming[v].append((u, lag, attenuation))
    c = {n: [0.0] * n_steps for n in network.node_order}
    for idx in range(n_steps):
        t = idx * TIMESTEP_H
        for node in network.node_order:
            ins = incoming[node]
            if ins:
                c[node][idx] = sum(c[u][idx-lag] * attenuation for u,lag,attenuation in ins if idx >= lag) / len(ins)
            if s.source == node and s.start_h <= t < (s.start_h+s.duration_h):
                c[node][idx] = max(c[node][idx], s.strength)
    return c


def concentration_at(series: dict[str, list[float]], node: str, hour: float) -> float:
    idx = max(0, min(len(series[node])-1, int(round(hour/TIMESTEP_H))))
    return float(series[node][idx])


def make_training_bank() -> tuple[list[Scenario], list[float]]:
    # Eight possible sources, three possible injection times, plus no-event.
    sources = ('J01','J02','J04','J05','J08','J11','J14','J16')
    scenarios = [Scenario('NO_EVENT', None, 0, 0, 0)]
    for node in sources:
        for start in (2.5, 5.5, 8.5):
            scenarios.append(Scenario(f'{node}_t{start:g}',node,start,8.0,1.0))
    priors = [.10] + [.90/(len(scenarios)-1)] * (len(scenarios)-1)
    return scenarios, priors


def make_test_cases() -> list[Scenario]:
    # Exact (source,time) combinations are withheld from the training bank.
    # Note: some sources occur in training, so this is not a fully new-network test.
    sources = ('J01','J02','J04','J05','J08','J11','J14','J16', 'J03','J06','J09','J12')
    test = [Scenario('TEST_NONE', None, 0, 0, 0)]
    for node in sources:
        for start in (3.0, 6.0, 9.0):
            test.append(Scenario(f'TEST_{node}_{start:g}',node,start,7.5,.95))
    return test


def p_positive(concentration: float) -> float:
    """Simple imperfect binary measurement model (illustrative)."""
    return SENSITIVITY if concentration >= THRESHOLD else 1.0-SPECIFICITY


def entropy_binary(p: float) -> float:
    if p <= 0 or p >= 1:
        return 0.0
    return -p*math.log2(p) - (1-p)*math.log2(1-p)


def bayes_update(posterior: list[float], likelihood: list[float], positive: bool) -> list[float]:
    w = [prior * (p if positive else 1-p) for prior,p in zip(posterior, likelihood)]
    z = sum(w)
    if z <= 1e-15:
        return posterior[:]
    return [v/z for v in w]


def build_likelihood_cache(net: Network, scenarios: list[Scenario]) -> dict:
    caches = {}
    for s in scenarios:
        q = quality_surrogate(net, s)
        for slot in SAMPLE_SLOTS_H:
            caches[(s.name,slot)] = {node: p_positive(concentration_at(q,node,slot)) for node in net.candidates}
    return caches


def information_gain(posterior: list[float], likelihood: list[float]) -> float:
    p_pos = sum(a*b for a,b in zip(posterior, likelihood))
    return max(0.0, entropy_binary(p_pos)-sum(pi*entropy_binary(p) for pi,p in zip(posterior,likelihood)))


def distance_proxy(net: Network, a: str, b: str) -> float:
    x1,y1 = net.coordinates[a]; x2,y2 = net.coordinates[b]
    return math.hypot(x2-x1,y2-y1)


def rank_sites(net: Network, scenarios: list[Scenario], posterior: list[float], cache: dict,
               slot: int, visited: list[str], *, mode='adaptive') -> list[dict]:
    """Score unconstrained next sites; five slots are a fixed demonstration budget.

    Weights are design choices, not scientifically optimized quantities.
    Distance is a schematic-coordinate proxy, NOT a real travel-time estimate.
    """
    maximum_demand = max(net.demand[n] for n in net.candidates) or 1
    origin = visited[-1] if visited else 'R0'
    max_distance = max(distance_proxy(net, origin, site) for site in net.candidates) or 1
    output = []
    for n in net.candidates:
        if n in visited:
            continue
        likelihood = [cache[(s.name, slot)][n] for s in scenarios]
        pred = sum(p*x for p,x in zip(posterior, likelihood))
        gain = information_gain(posterior,likelihood)
        demand = net.demand[n] / maximum_demand
        dist = distance_proxy(net,origin,n) / max_distance
        if mode == 'static':
            # A deliberately non-adaptive but prior-optimized fixed schedule.
            score = 0.75*pred + 0.20*gain + 0.05*demand
        else:
            score = 0.67*pred + 0.26*gain + 0.10*demand - 0.03*dist
        output.append({'node':n,'score':score,'p_positive':pred,
                       'information_gain_bits':gain,'demand_proxy':demand,'distance_proxy':dist})
    return sorted(output,key=lambda d: (-d['score'],d['node']))


def hash_uniform(*parts) -> float:
    payload = '|'.join(map(str,parts)).encode('utf-8')
    return (int.from_bytes(hashlib.sha256(payload).digest()[:8],'big') + .5)/2**64


def simulate_run(net: Network, bank: list[Scenario], priors: list[float], cache: dict,
                 truth: Scenario, policy: str, seed: int = 2026) -> dict:
    truth_series = quality_surrogate(net, truth)
    posterior = priors[:]
    visited = []
    detected = False
    detection_hour = None
    first_detection_test = None
    false_alarms = 0
    num_tests = 0
    for slot in SAMPLE_SLOTS_H:
        if policy == 'random':
            rng = random.Random(int(hash_uniform(seed,truth.name,slot,'random')*2**32))
            site = rng.choice(sorted(set(net.candidates)-set(visited)))
        elif policy in ('adaptive','static'):
            top = rank_sites(net,bank,posterior if policy=='adaptive' else priors,cache,
                             slot,visited,mode=policy)
            site = top[0]['node']
        else:
            raise ValueError(f'Invalid policy: {policy}')
        visited.append(site)
        num_tests += 1
        concentration = concentration_at(truth_series,site,slot)
        is_real_positive = truth.source is not None and concentration >= THRESHOLD
        obs_pos = hash_uniform(seed,truth.name,slot,site,'assay') < p_positive(concentration)
        if obs_pos and not is_real_positive:
            false_alarms += 1
        if obs_pos and is_real_positive and not detected:
            detected, detection_hour, first_detection_test = True, float(slot), num_tests
        if policy == 'adaptive':
            likelihood = [cache[(s.name,slot)][site] for s in bank]
            posterior = bayes_update(posterior,likelihood,obs_pos)
    return {'truth':truth.name,'has_event':truth.source is not None,'policy':policy,
            'replicate':seed,'detected':detected,'detection_hour':detection_hour,
            'detection_delay_h':detection_hour-truth.start_h if detected else None,
            'first_detection_test':first_detection_test,
            'penalized_delay_h':(detection_hour if detected else 18.0)-truth.start_h if truth.source else None,
            'false_alarms':false_alarms,'tests_run':num_tests,
            'sites':','.join(visited)}


def benchmark(net: Network, n_reps: int = 5) -> tuple[list[dict], list[dict]]:
    bank, priors = make_training_bank()
    cache = build_likelihood_cache(net,bank)
    rows = []
    for trial in make_test_cases():
        for rep in range(n_reps):
            for policy in ('adaptive','static','random'):
                rows.append(simulate_run(net,bank,priors,cache,trial,policy,seed=2026+rep))
    summaries = []
    for policy in ('adaptive','static','random'):
        relevant = [r for r in rows if r['policy']==policy]
        events = [r for r in relevant if r['has_event']]
        nonevents = [r for r in relevant if not r['has_event']]
        hits = [r for r in events if r['detected']]
        summaries.append({
            'policy':policy,
            'event_trials':len(events),
            'detection_rate':sum(r['detected'] for r in events)/len(events),
            'mean_penalized_delay_h':sum(r['penalized_delay_h'] for r in events)/len(events),
            'mean_delay_detected_only_h':sum(r['detection_delay_h'] for r in hits)/len(hits) if hits else None,
            'mean_tests_to_detection_detected_only':sum(r['first_detection_test'] for r in hits)/len(hits) if hits else None,
            'mean_false_alarms_on_nonevent':sum(r['false_alarms'] for r in nonevents)/len(nonevents),
            'max_tests_per_day':max(r['tests_run'] for r in relevant),
        })
    return rows,summaries
