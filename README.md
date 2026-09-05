# Power-Aware CPU Governor

A workload-adaptive CPU frequency scaling policy for Linux. Samples `/proc/stat`,
classifies the workload (CPU-bound / I/O-bound / idle / mixed), and sets the core
frequency to match — instead of scaling on aggregate utilisation alone.

BITE303P Operating Systems Lab, VIT Vellore. See the PRD for full scope.

## Status

Phase 0 not started — **no VM yet**, so nothing that touches `/proc` or `/sys`
has been run for real. What exists is the platform-independent logic, which is
covered by self-checks that run anywhere:

| Module | State |
|---|---|
| `monitor/reader.py` | parsing + delta computation written and tested; file reads untested (needs Linux) |
| `classifier/rules.py` | written; **thresholds are placeholders** until Phase 2 tuning |
| `policy/governor_policy.py` | written and tested (hysteresis, asymmetric ramp-down) |
| `power_model/estimate.py` | written; **constants are placeholders**, see `docs/power_model.md` |
| `setter/`, `benchmark/`, `analysis/` | empty — blocked on Phase 0 outcome A vs B |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

On Windows the venv lives at `.venv/Scripts/` instead.

## Run the self-checks

```bash
.venv/bin/python tests/test_core.py
```

## Run the monitor (Linux only)

```bash
.venv/bin/python -m monitor.reader
```

Reading `/proc/stat` needs no privileges. **Writing frequency does** — the
frequency setter will require root (`sudo`), and the governor must be set to
`userspace` first. Decide and document the launch mechanism before any demo.

## Next step

Stand up the Ubuntu VM and complete `docs/vm_feasibility.md`. Outcome A vs B
decides how `setter/` is built; everything else is unaffected.
