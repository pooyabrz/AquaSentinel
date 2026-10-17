# Milestone 02 — Scientific assumptions and reproducibility

## What is newly functional

EPANET 2.2/ WNTR chemical-transport data feeds the same Bayesian scenario likelihoods, posterior update and five-slot greedy adaptive planner as the stage-one surrogate. Data source depends on WNTR being installed and `stage2_epanet.py` being executed successfully, with output metadata saying `EPANET 2.2 through WNTR`. There is **no surrogate fallback** in the CLI.

## Units

WNTR internal concentration units are kg/m³. EPANET CHEMICAL INP files commonly express mg/L. WNTR Python `wn.add_source(... strength)` accepts SI kg/m³; WNTR `results.node['quality']` is returned in kg/m³. Stage-two function `run_quality_epanet()` converts hypothetical source mg/L -> kg/m³ by dividing by 1000 and results back to mg/L by multiplying by 1000. Stage-two detection threshold is arbitrarily 0.08 mg/L. It is **not a health threshold**.

## Model assumptions

- Network is the 21-node / 30-pipe synthetic demo model, not a calibrated municipal hydraulic model.
- EPANET simulation duration 24h, hydraulic report 30min, quality time step 5min, source strength pattern 30min.
- Source injection is a time-limited SETPOINT injection (idealized). No decay kinetics or realistic source dynamics are calibrated; concentration cannot be interpreted as realistic health risk.
- Five sampling slots at 8, 10, 12, 14, 16 simulation hours, immediate laboratory results (0h turn-around). Real turnaround must be modeled before field adoption.
- Assay sensitivity=0.96, specificity=0.99 (hypothetical); observation independence is assumed conditional on each scenario.
- Training bank: 8 source locations x 3 start times + NO_EVENT = 25 hypotheses. Prior P(NO_EVENT)=0.10, others equally share 0.90. Artificial prior, no prevalence claim.
- Held-out testing: 12 source locations x 3 start times plus a no-event day = 37 cases, none exactly matches training scenarios (but all use the same network and model family).
- Demo hidden scenario at source J08 starts at 6.0h, 7.5h duration, strength 0.95 mg/L, so it is not an exact member of the training bank.
- Binary observation is computed using hypothetical detection threshold, sensitivity, specificity. The simulated benchmark uses an observation random draw keyed by scenario, node, slot, repeat seed to couple assays when policies sample the same point at the same time.
- Static comparator uses fixed prior-optimized greedy scheduling. Random samples five different nodes per day. Adaptive updates the posterior with every assay and re-ranks every next site.
- Stage-one scoring weights are heuristic, do not claim optimized or proven best. Uses demand as a proxy rather than population. Travel penalty uses schematic Euclidean node distance, not road network time.
- False alarms from clean or below-threshold samples do **not** count as true-event detections. No-event scenarios are evaluated separately for false alarms.
- Penalized delay sets detection time to 18h when event not detected within five slots. This is a prespecified modeling convenience; always disclose it alongside detection probability to avoid bias.

## Unverified at build time

WNTR could not be installed in the build environment because network package indexes were unreachable. The actual binary EPANET solver was NOT executed during preparation of this deliverable. 18 ordinary tests passed and one WNTR-dependent test was skipped. `tests/test_stage2.py` uses a strictly named surrogate fixture to validate data plumbing, CSV serialization, posterior and comparison. The first user-side smoke test is required before claiming a confirmed EPANET run.

## Next milestones

1. Run smoke test on Windows with actual WNTR and confirm nonzero source concentration and units.
2. Validate hydraulic flow direction and plausibility with an expert; compare to a recognized EPANET network such as Net3.
3. Incorporate laboratory turnaround and route/travel time into the adaptive scheduling (not just a small Euclidean penalty).
4. Evaluate false alarms, missing observations, robustness to uncertain hydraulic demands, and new-network transfer.
5. Add independent validation, uncertainty intervals and reproducible scientific analysis of benchmarks.
