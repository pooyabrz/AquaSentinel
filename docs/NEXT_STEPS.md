# Engineering plan and acceptance gates

## M1 — Offline feedback loop (included in this ZIP)

**Acceptance criteria**
- [x] Synthetic EPANET-compatible INP generated with 21 nodes and 30 pipes.
- [x] Educational surrogate produces time-dependent artificial tracer values.
- [x] Five candidate assays / fixed day are proposed, with no duplicate locations.
- [x] Posterior probabilities change after positive or negative simulated observations.
- [x] Interactive English dashboard is available offline.
- [x] Fixed prior-greedy, random, and adaptive strategies run on shared held-out scenarios.
- [x] Benchmark CSVs, model limitations and unit tests included.
- [ ] EPANET physical simulation run and verified locally (WNTR unavailable in build environment).

## M2 — EPANET scenario integration (next)

1. Install WNTR locally; run `epanet_engine.py` and verify nonzero concentrations at downstream nodes.
2. Simulate several independent injection source nodes and event start times using WNTR.
3. Replace the surrogate likelihood cache with **measured-from-EPANET** scenario arrays at the same sample locations and slots.
4. Repeat static/random/adaptive comparison fairly with identical test budgets.
5. Add quality regression tests: source injection stop/start, time units, and monotonic timing expectations.
6. Add false-positive, false-negative and diagnostic quality controls.
7. Produce plots comparing surrogate and EPANET (they should not be assumed equal).

**Acceptance:** when the simulator output is supplied, a received negative result changes the next recommendation and the benchmark genuinely uses EPANET output.

## M3 — Operations realism

- Add test turnaround delay, available sampling taps, sampling handling time, and realistic travel routes.
- Optimize site plus visit order, with shift constraints and five-test budget.
- Introduce higher-quality static optimal baseline and confidence intervals.
- Add at least one second water network and out-of-distribution scenarios.

## M4 — Competition deliverables

- English 3–4 minute demo script and screen recording.
- Six to eight slides: problem, opportunity, approach, system diagram, actual experiment, constraints, impact, next steps.
- Version-tagged code, repeatable instructions, and documentation of what is simulated vs validated.
- Signoff by a water professional before discussing practical use.
