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
| `governor.py` | control loop, runs end-to-end on synthetic signals today |
| `monitor/reader.py` | parsing + deltas tested; the `/proc` and `/sys` reads themselves are untested (need Linux) |
| `monitor/synthetic.py` | invented signals for dev/demo without a VM |
| `classifier/rules.py` | written; **thresholds are placeholders** until Phase 2 tuning on real stress-ng traces |
| `policy/governor_policy.py` | hysteresis + asymmetric ramp-down, tested |
| `setter/freq_setter.py` | simulated path tested; sysfs path is **write-untested** until Phase 0 |
| `power_model/estimate.py` | written; **constants are placeholders**, see `docs/power_model.md` |
| `benchmark/`, `analysis/`, `classifier/ml_model.py` | empty - need real runs and real data |

## See it work without a VM

```bash
.venv/bin/python governor.py --synthetic
```

Prints one line per tick: classification, signals, chosen frequency, estimated
power. The synthetic plan walks cpu -> io -> idle -> mixed -> cpu, so the 3-tick
hysteresis lag is visible at each transition. Add `--csv data/run.csv` to log it.

**The synthetic numbers are invented.** They are for wiring and demos only -
never for tuning thresholds or training the Review II classifier. Both of those
need real stress-ng traces.

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
