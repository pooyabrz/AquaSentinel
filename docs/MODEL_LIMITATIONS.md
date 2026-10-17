# Model limitations and evaluation boundaries

## What has actually been executed

- An **educational, fixed-flow, directed-graph time-lag and attenuation** contamination surrogate. Nodes sum their parent concentrations with equal inflow weights. This is not a mass-conserving calibrated water-quality simulation.
- A separate Bayesian binary-test update, using assumed sensitivity and specificity.
- A greedy next-node selection policy with weights chosen for illustration, not calibrated on utility priorities.
- A synthetic comparison with fixed prior-based and random-node policies over the same five preassigned sampling times.
- Seven Python standard-library unit tests and a browser interaction smoke test in the build environment.

## What has not been executed or established

- WNTR/EPANET simulator, hydraulic pressure/flow estimates, real pipe travel times, real contamination or concentration limits, GIS road routing, population/equity impact, field sampling or laboratory turnaround, independent network generalization, operational integration, and expert validation.
- Static comparison method is a **myopic optimized heuristic**, not a guaranteed global optimum.
- Adaptive planner ranking and benchmark use the surrogate, not the EPANET results produced by `epanet_engine.py`.
- Probability of a positive test refers to the specified simulation assumptions; it is not a calibrated probability of unsafe drinking water.

## Benchmark definitions

- **Detection rate:** proportion of synthetic event trials with a *true-positive* measurement by simulation hour 16.
- **Detected-only delay:** hours from the event's assumed start to the first assay event on an actually contaminated node. False-positive results are not counted as true detection.
- **Penalized delay:** same delay when detected; otherwise a prespecified censored penalty of hour 18 minus start hour. This is a *benchmark score*, not a fully developed survival analysis.
- **Tests to detection:** number of assays consumed before the first true-positive result, conditional on a detected event. All simulation runs still use all five allowed slots to expose the replanning behavior.
- **False alarms on no event:** average number of positive assays when no injected event exists. A false alarm can also occur during a pollution event if the tested site is uncontaminated.
- **Travel penalty:** distance in schematic layout coordinates, not kilometers or road-network travel times. No actual routing constraint is enforced in this milestone.

The aggregate benchmark assumes no latency between sampling and results; future milestones will add realistic lab turnaround and sampling time.

## Safer deployment assumptions

A genuinely useful operational decision-support system would require independently checked hydraulic calibration, assay performance characterization, accessible sampling taps, proper sampling protocols, field data validation, protected operational network data, human approval, and conformance to applicable water-quality rules. The prototype is for learning, research and competition presentation only.
