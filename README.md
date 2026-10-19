# Power-Aware CPU Governor

A user-space prototype of a workload-adaptive CPU frequency policy for Linux. It
samples `/proc/stat`, classifies the workload (CPU-bound / I/O-bound / idle / mixed)
with transparent rules, and chooses a target frequency with K-tick hysteresis instead
of scaling on aggregate utilisation alone.

**What is measured and what is simulated.** Linux kernel counters from `/proc/stat`
are measured (on the Ubuntu VM). Frequencies are **simulated** decisions on a model
ladder: the development VM has no cpufreq interface, so nothing writes to hardware.
Power, energy and any "savings" are **modelled** estimates, never measured.

BITE303P Operating Systems Lab, VIT Vellore. See [`docs/PRD.md`](docs/PRD.md) for the
original scope (proposal-era; some status lines there are historical).

## Documentation

| Document | Use it for |
|---|---|
| [User manual](docs/USER_MANUAL.md) | Installation, every command, dashboard walkthrough, troubleshooting |
| [Problem statement](docs/PROBLEM_STATEMENT.md) | Problem, objectives, scope, measured vs simulated, related work and positioning |
| [Test plan and results](docs/TEST_PLAN_AND_RESULTS.md) | Test cases by feature, recorded results, how to reproduce |
| [Viva Q&A](docs/VIVA_QA.md) | Likely examiner questions with honest answers |
| [Review II checklist](docs/REVIEW2_CHECKLIST.md) | Each lab deliverable mapped to its status and file |
| [Governorlab](docs/GOVERNORLAB.md) / [Daybreak](docs/DAYBREAK.md) | Terminal and dashboard details |
| [Project state](docs/PROJECT_STATE.md) / [Development log](docs/DEVELOPMENT_LOG.md) | Dated record of what was built and verified |

## Daybreak web dashboard

From the repository root, install `requirements-dashboard.txt`, then run
`.\.venv\Scripts\python.exe -m streamlit run daybreak/app.py` on Windows or
`.venv/bin/python -m streamlit run daybreak/app.py` on Ubuntu. Open
`http://127.0.0.1:8501`. Four views cover automatic/manual 34-tick replay,
archived Linux observations, five-policy comparison and lab methodology.
One shared player supports pause/resume, restart, paused seek, previous/next and
speed for synthetic and saved Linux sessions. An explicit Linux-only Collect Live
Data action captures 5, 10 or 20 bounded background intervals (the **Samples**
dropdown; it applies to the next collection, not to a loaded session) in an isolated
child, then replays them in that same player. Collection is tolerant: intervals with
VM timing anomalies are discarded, disclosed in a banner and never classified.
Terminal and dashboard sessions share one format in `run/`, so either can replay the
other's captures. Startup and ordinary reruns never collect.
Candidate/applied simulated frequencies and K=3 state use the existing backend;
measured observations and uncalibrated model estimates remain clearly separated.
See [Daybreak installation, demonstration and Ubuntu checklist](docs/DAYBREAK.md).

## Governorlab terminal demonstration

Run `.venv/bin/python -m governorlab` on Ubuntu or
`.\.venv\Scripts\python.exe -m governorlab` in Windows PowerShell from the repository
root. Finite 34-tick synthetic replay shows actual backend classification, candidate
versus applied simulated frequency, K=3 persistence, progressive CPU history and
verified transitions. `--recorded-linux` displays the five archived Linux observations
separately. Default replay performs no live monitoring, workload or hardware control.
For fresh background-only Linux observations followed automatically by simulated
K=3 governor decisions, run `.venv/bin/python -m governorlab --live` (5 samples by
default; `--samples N` for 5 to 30). Collection is tolerant: an interval outside
0.5-2 s or with an implausible CPU-accounting rate is discarded and disclosed, and
the run continues up to N + max(3, ceil(N/2)) attempts; `--strict` aborts on the
first anomaly instead. Each run saves a session in `run/live-*/`;
`--list-sessions` lists saved sessions and `--session latest` (or a folder path)
replays one after full revalidation. No generated workload or physical frequency writes.

Rich is optional (`requirements-terminal.txt`); `--plain --instant` works without it.
Default interactive mode uses a compact Rich dashboard at 80x24. `--visual` (alias
`--rich`) explicitly requires the colored dashboard and reports why unavailable;
redirected/unsupported output explains its plain fallback.
See [startup and professor demonstration guide](docs/GOVERNORLAB.md) for provenance,
limitations, Windows/Ubuntu instructions and the Linux integration checklist.

## Status

Phase 0 is done: **Outcome B confirmed** (see `docs/vm_feasibility.md`). The dev
VM (VirtualBox, 4 vCPUs, host CPU AMD Ryzen 7 7840HS) exposes no cpufreq
interface on any core, so frequency control is simulated and granularity is
whole-system. `/proc/stat` monitoring is unaffected - it is real inside the VM.
Every power figure is estimated from a modelled frequency, never measured.

| Module | State |
|---|---|
| `governor.py` | control loop + CLI (`--synthetic`, `--interval`, `--ticks`, `--k`, `--csv`); logs both `target_khz` (what landed) and `requested_khz`; runs end-to-end on synthetic signals |
| `monitor/reader.py` | `/proc/stat` parsing + delta/rate computation tested, plus ratio features `iowait_over_util` and `ctxt_over_run` (capped, never inf/nan); missing/NaN/negative counters rejected with clear errors; `log_csv` creates its parent directory |
| `governorlab/live.py`, `presentation/sessions.py` | Live collection (5-30 samples, tolerant or `--strict`) and the shared saved-session store used by terminal and dashboard |
| `benchmark/overhead.py` | Governor self-overhead tool (Linux only; CPU ms per tick, wake-ups, memory, VM timer overshoot). Full run on the VM (October 19, 2026): 24/24 runs ok, net 0.55-0.62 ms CPU per tick, 0.0117-0.1198 % of one core derived (upper bound), RSS about 17,700 KiB (17.3 MiB); measured CPU time inside a VM, not power; archived in [`evidence/phase1b_overhead/`](evidence/phase1b_overhead/README.md) |
| `benchmark/sensitivity.py` | Deterministic synthetic K and sampling-interval study; results in `evidence/phase1b_sensitivity/` |
| `benchmark/closed_loop.py` | Deterministic closed-loop benchmark: lower frequency stretches CPU work; MODELLED energy, completion time and EDP for 11 policies (including a schedutil-style approximation) on 9 scenarios x 20 seeds; results in [`evidence/phase2a_closed_loop/`](evidence/phase2a_closed_loop/README.md). Under the pure 1/f assumption our policy wins no energy, time or EDP comparison |
| `benchmark/pareto.py` | Fixed-frequency baselines (one per ladder level), energy/completion-time Pareto frontiers for every scenario and frequency-insensitive fraction, and an I/O-target ablation of our policy; results in [`evidence/phase2b_pareto/`](evidence/phase2b_pareto/README.md). All four fixed levels are always on the frontier; a fixed 4.67 or 4.23 GHz dominates our K=3 policy in 9 of 36 scenario/fraction cells (modelled) |
| `monitor/synthetic.py` | invented cumulative counters (profiles `cpu`, `io`, `io_burst`, `idle`, `mixed`) pushed through the real delta code; dev/demo only |
| `classifier/rules.py` | 4-class rule classifier, tested; **thresholds are placeholders** (see `docs/thresholds.md`) until tuned on real stress-ng traces |
| `policy/governor_policy.py` | class -> frequency with K-tick hysteresis (default 3), optional asymmetric ramp-down that keeps stepping until the target, resync to a clamped setter result, input validation; tested |
| `setter/freq_setter.py` | with no cpufreq, `open_setter()` returns `SimulatedSetter` on the fallback ladder `RYZEN_7840HS_LADDER_KHZ` from `hardware_profile.py` (Ryzen 7 7840HS base-to-boost; its top step is f_max), tested. `SysfsSetter` self-verifies every write; tested against fake hardware only - real sysfs writes are impossible on this VM |
| `power_model/estimate.py` | P = P_static + P_dyn(f_max) x (f/f_max)^3 x util; constants fitted (two-point) to AMD's published Ryzen 7 7840HS figures, see `docs/power_model.md` |
| `benchmark/baselines.py` | performance / powersave / ondemand / conservative as comparable policies; a schedutil-style approximation (not the kernel governor) lives in `benchmark/closed_loop.py` |
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

Read [safe collection workflow](docs/COLLECTION_WORKFLOW.md) before any experiment.
The collector now runs one bounded profile, preserves metadata/manifests and refuses
artificial loads without explicit experiment approval. I/O collection is disabled.
Five real background-only Linux samples are verified; real threshold calibration is
still pending. No generated workload is authorized by these documentation examples.

## Review 1 synthetic evidence

Synthetic mode always uses simulated frequency control and makes no hardware writes.
`--ticks N` caps the finite 20-row demonstration (zero is allowed; negative is rejected).
Inputs are invented; power and energy are modelled, never measured.

```bash
.venv/bin/python governor.py --synthetic --ticks 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 30s .venv/bin/python -m benchmark.review_demo --outdir data/review1-demo-new
```

Choose a new output directory. The review driver exports five 34-row policy CSVs,
summary/provenance JSON and labelled energy/frequency PNGs using seed 11 and K=3.
This is an open-loop comparison of policy approximations, not evidence of measured
physical energy savings or preserved workload completion time. See docs/REVIEW1_PLAN.md.
Original Review 1 charts/CSVs are preserved in
[the synthetic archive](evidence/review1/synthetic_policy_comparison_20261015/README.md);
see [current roadmap](docs/DEVELOPMENT_ROADMAP.md) and
[dashboard handoff](docs/DASHBOARD_INTEGRATION_HANDOFF.md).

## Standalone one-worker CPU experiment
After reviewing and approving the limits in [collection workflow](docs/COLLECTION_WORKFLOW.md),
close Codex/unnecessary applications and run `./scripts/run_safe_cpu_experiment.sh`
from the repository root in an ordinary Ubuntu terminal. Fresh preflight and typing
`RUN` are required. Ctrl+C cancels with cleanup. No real workload was executed as part
of launcher setup. Reports are generated without Codex in the Windows shared folder;
failures preserve local evidence and never trigger an automatic retry.

The first manual CPU attempt failed with zero samples. See
[CPU timing diagnostic](docs/CPU_TIMING_DIAGNOSTIC.md) for verified evidence and
remaining uncertainty. Monitor-first readiness and failure diagnostics are tested;
another real observation or workload requires separate approval.

## Standalone background readiness check

One manual background-only observation succeeded on October 15, 2026. Its five-row
evidence is preserved in [the archive](evidence/review1/background_readiness_20261015/README.md);
see [Review 1 status](docs/REVIEW1_STATUS.md). Any further observation needs separate
approval. For an approved future observation, close Codex and run from any terminal:

```bash
/home/vboxuser/Power_Aware_CPU_Governor/scripts/run_background_readiness.sh
```

Type `RUN` after reviewing the printed limits. The fixed command uses five intervals,
zero artificial workers, an eleven-second supervisor and fifteen-second outer timeout.
It retains resource/lock/cleanup/CSV checks and exports readiness, lifecycle, raw interval
diagnostics and the report to the shared folder. No command-line overrides are accepted.
See [collection workflow](docs/COLLECTION_WORKFLOW.md#standalone-background-readiness-preparation).
