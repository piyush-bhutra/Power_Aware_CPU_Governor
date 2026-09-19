# Power-Aware CPU Governor

A workload-adaptive CPU frequency scaling policy for Linux. Samples `/proc/stat`,
classifies the workload (CPU-bound / I/O-bound / idle / mixed), and sets the core
frequency to match — instead of scaling on aggregate utilisation alone.

BITE303P Operating Systems Lab, VIT Vellore. See [`docs/PRD.md`](docs/PRD.md) for full scope.

## Status

Phase 0 is done: **Outcome B confirmed** (see `docs/vm_feasibility.md`). The dev
VM (VirtualBox, 4 vCPUs, host CPU AMD Ryzen 7 7840HS) exposes no cpufreq
interface on any core, so frequency control is simulated and granularity is
whole-system. `/proc/stat` monitoring is unaffected - it is real inside the VM.
Every power figure is estimated from a modelled frequency, never measured.

| Module | State |
|---|---|
| `governor.py` | control loop + CLI (`--synthetic`, `--interval`, `--ticks`, `--k`, `--csv`); logs both `target_khz` (what landed) and `requested_khz`; runs end-to-end on synthetic signals |
| `monitor/reader.py` | `/proc/stat` parsing + delta/rate computation tested, plus ratio features `iowait_over_util` and `ctxt_over_run` (capped, never inf/nan); `log_csv` creates its parent directory. No run on the VM's live `/proc/stat` is recorded in the repo yet |
| `monitor/synthetic.py` | invented cumulative counters (profiles `cpu`, `io`, `io_burst`, `idle`, `mixed`) pushed through the real delta code; dev/demo only |
| `classifier/rules.py` | 4-class rule classifier, tested; **thresholds are placeholders** (see `docs/thresholds.md`) until tuned on real stress-ng traces |
| `policy/governor_policy.py` | class -> frequency with K-tick hysteresis (default 3) and optional asymmetric ramp-down, tested |
| `setter/freq_setter.py` | with no cpufreq, `open_setter()` returns `SimulatedSetter` on a fallback ladder of 3.8 / 4.23 / 4.67 / 5.1 GHz (Ryzen 7 7840HS base-to-boost, f_max 5.1 GHz), tested. `SysfsSetter` self-verifies every write; tested against fake hardware only - real sysfs writes are impossible on this VM |
| `power_model/estimate.py` | P = P_static + P_dyn(f_max) x (f/f_max)^3 x util; **constants (2.0 W / 13.0 W) are unfitted placeholders**, see `docs/power_model.md` |
| `benchmark/baselines.py` | performance / powersave / ondemand / conservative as comparable policies; no `schedutil` baseline yet |
| `benchmark/compare.py` | runs ours + every baseline over one identical trace |
| `benchmark/summarize.py` | per-run estimated energy (J), mean power, mean frequency, frequency-change count, class distribution |
| `analysis/plots.py` | energy comparison, frequency timeline, class distribution (PNG); tests check only that each file is written. The class-distribution chart is identical across governors on synthetic data by construction - keep it out of the report until it comes from real traces |
| `classifier/ml_model.py` | not started - Review II, needs real traces |

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
.venv/bin/pytest tests/ -v
```

## Run the monitor (Linux only)

```bash
.venv/bin/python -m monitor.reader
```

Reading `/proc/stat` needs no privileges. **Writing frequency does** — the
frequency setter will require root (`sudo`), and the governor must be set to
`userspace` first. Decide and document the launch mechanism before any demo.

## Next step

Record real `stress-ng` traces in the VM (`--cpu`, `--io`, `--hdd`, `--vm`, mixed,
idle) with `governor.py --csv`, then tune the classifier thresholds from them and
justify each one in `docs/thresholds.md`. Monitoring is real under Outcome B, so
this doesn't wait on anything.
