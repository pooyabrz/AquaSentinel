# AquaSentinel

An educational prototype for adaptive water-quality sampling under a five-test
daily budget. The project combines a Bayesian sampling planner, a synthetic
network, an offline dashboard, and an optional WNTR/EPANET simulation pipeline.

> **Research/demo use only.** The included network and scenarios are synthetic.
> Stage 1 uses an educational graph surrogate, not EPANET hydraulics. Stage 2
> can use EPANET through WNTR but still relies on uncalibrated assumptions.
> This project is not suitable for drinking-water safety or operational
> decisions. See [Model limitations](docs/MODEL_LIMITATIONS.md) and
> [Stage 2 scientific notes](docs/STAGE2_SCIENTIFIC_NOTES.md).

## Quick start

Stage 1 requires Python 3.10 or newer and uses only the standard library:

```bash
python run_demo.py
python -m unittest discover -s tests -v
```

Open `AquaSentinel_Dashboard.html` in a browser for the interactive offline
demo. Running `run_demo.py` regenerates the dashboard and illustrative outputs
under `outputs/`.

## Optional EPANET pipeline (Stage 2)

Use a supported 64-bit Python version (3.10–3.13), install WNTR, then run:

```bash
python -m pip install -r requirements_stage2.txt
python stage2_epanet.py --mode smoke
python stage2_epanet.py --mode demo
```

To run the benchmark:

```bash
python stage2_epanet.py --mode benchmark --replicates 10
```

Stage 2 outputs are written to `outputs/epanet_stage2/`. The actual EPANET
solver must run successfully in your environment before treating any output as
EPANET-generated. See [Stage 2 scientific notes](docs/STAGE2_SCIENTIFIC_NOTES.md)
for assumptions and verification requirements.

## Project layout

- `core.py` — surrogate model, Bayesian updates, site ranking, and benchmarks.
- `run_demo.py` — regenerates the Stage 1 dashboard and outputs.
- `stage2_epanet.py` — optional EPANET-backed scenario and benchmark pipeline.
- `epanet_engine.py` — optional WNTR/EPANET adapter.
- `data/demo_network.inp` — synthetic EPANET-compatible network.
- `tests/` — automated tests; the real-EPANET test is optional when WNTR is
  unavailable.
- `docs/` — scientific assumptions, limitations, and next steps.

Generated outputs, local environment files, caches, temporary EPANET files,
and the supplemental Persian-language Markdown guides are excluded by
`.gitignore`. Outputs can be regenerated with the commands above.

## License

No license file is currently included. Until the project owner adds one, reuse
permissions have not been granted.
