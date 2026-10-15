# Review 1 status — October 16, 2026

## Governorlab presentation update — October 15, 2026

The independent terminal MVP is available: `python -m governorlab` (finite 34-tick
synthetic replay), `--recorded-linux` (five separate historical observations),
`--plain --instant` (portable fallback). Candidate/applied simulated levels,
derived K=3 persistence, progressive utilization and verified transitions are shown.
See [demonstration guide](GOVERNORLAB.md) for Windows/Ubuntu commands and faculty notes.
Windows-compatible suite: 72 passing, including 30 new tests. Ubuntu-specific
integration remains pending; no new experiments or web dashboard were implemented.
Prior presentation/status notes below describe earlier milestones. Provisional
thresholds, model assumptions and physical-performance limitations still apply.

Verified October 15, 2026 for the milestone checkpoint. Historical setup documents
record earlier states; this document and the latest PROJECT_STATE update describe
current evidence. This is a progress summary, not the final academic report.

## Project and problem

**Power-Aware CPU Governor** investigates how workload signals can inform Linux
CPU frequency decisions. High frequencies can help CPU-bound work but waste energy
when the processor waits for I/O or has little work. We implement a Python userspace
control loop; this is not a kernel scheduler and does not change scheduling queues.

## Architecture and implemented scope

`/proc/stat` monitor → rate/ratio features → four-class rule classifier → K-tick
hysteresis policy → setter → CSV → modelled power and baseline analysis.

The monitor computes aggregate utilization, iowait, interrupt/context-switch rates
and queue gauges. It preserves raw counters, measures elapsed intervals with a
monotonic clock, avoids duplicate guest accounting, skips resets and flags decreasing
iowait. Rules classify CPU-bound, I/O-bound, idle and mixed signals; thresholds remain
provisional. The default policy requires three matching classifications before
changing frequency. Simulated and self-verifying Linux sysfs setters exist; sysfs
is tested with fake hardware only. Logs distinguish requested and returned frequency.

A cubic power model and deterministic open-loop replay compare our policy with
performance, powersave, ondemand and conservative approximations. The collector and
standalone launchers provide budgets, resource guards, locking, process identities,
monitor readiness, deadlines, cleanup and reports. I/O stress collection is disabled.
The launchers retain interactive RUN confirmation and require separate experiment
approval. ML, schedutil comparison and a frontend are not implemented.

## Experimentally verified

The preserved run `launcher-20261015T144107Z-ulqlq_gi` used source commit
`18b87efa6ffdcc4e7f4ed58936c824876a42d3fc` with a recorded clean working tree.
[Archived evidence](../evidence/review1/background_readiness_20261015/README.md)
contains all 15 original files (33,913 bytes), a provenance manifest and SHA256 sums.
All copies match their shared originals; eight recorded source hashes match Git.
Raw/validated CSVs are identical with five rows and 39 columns; raw-to-derived
recomputation, timestamps, counter continuity, lifecycle and statistics agree.

This background-only run completed with launcher, collector and monitor exits 0,
readiness before release and reported successful cleanup. No generated workers ran.
Mean aggregate utilization was **0.3231%**, mean interval **1.2422 s**, range
**1.0067–1.8549 s**, iowait 0%. The interval spread is a limitation even though the
run passed the existing 0.5–2 s validation bounds. Three idle/two mixed rule outputs
are not classifier ground truth. An earlier five-row background capture is available
in shared `results/real_monitoring_20261015/`; it is separate evidence, not a repeat
of this run. The previous manual CPU attempt failed with zero rows and is unusable
as a CPU dataset. No new collector or real observation ran during this checkpoint.

Fresh bounded automated verification: **115 passed in 8.41 s**, with mocked and
harmless-process lifecycle cases, fake sysfs, synthetic comparison and PNG creation.
Shell syntax and Git whitespace checks pass. Tests do not substitute for loaded VM
validation or prove visual correctness of plots.

## Simulation, modelling and VM limits

The four-vCPU VirtualBox guest reports AMD Ryzen 7 7840HS and KVM hypervisor vendor.
Current CPUFreq policy interfaces are absent; frequency control is simulated. Kernel
counters are measured guest observations. Synthetic counters are invented inputs.
Power/energy values are model outputs using an assumed ladder and uncalibrated
constants (see [power model](power_model.md)), not electrical measurements.

Open-loop replay holds input signals fixed. It cannot establish performance preservation,
workload completion-time differences or physical energy savings. Current KVM reporting
conflicts with historical legacy-paravirtualization timing notes; this short background
success does not resolve previous loaded-run timing distortion or freeze risk.

Known code limitations: optional ramp-down stops after its first drop under a stable
class; hardware clamping does not resynchronize policy state; CLI validation remains
limited. These are pre-existing, documented limitations, outside the default simulated
K=3 demonstration. CSV schema changed; old/new traces must not be appended together.

## Presentation path and existing inventory

Use the terminal to show three synthetic ticks, then the finite 20-row transition
sequence and K=3 lag. Explain module flow and show existing labelled PNGs, followed
by the archived background CSV/lifecycle to establish measured monitoring separately.
No guest browser or new frontend is needed. From the repository root:

```bash
timeout 10s .venv/bin/python governor.py --synthetic --ticks 3
timeout 10s .venv/bin/python governor.py --synthetic
timeout 10s .venv/bin/python -m benchmark.compare
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 60s .venv/bin/python -m pytest tests/ -q
# Optional synthetic chart regeneration; choose a new, unused local directory:
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 30s .venv/bin/python -m benchmark.review_demo --outdir data/review1-presentation-new
```

Existing shared `results/review1_verified_20261015/` has five 34-row policy CSVs
(`ours`, `performance`, `powersave`, `ondemand`, `conservative`), `summaries.json`,
`metadata.json`, `synthetic_modelled_energy.png` and `synthetic_simulated_frequency.png`.
Its metadata records clean producing commit `4055aa2c0700f829b565f01442f392806f0dea73`,
seed 11, K=3 and one-second nominal intervals. These nine original outputs are now archived in
[synthetic evidence](../evidence/review1/synthetic_policy_comparison_20261015/README.md).
Their original values and PNG bytes reproduce; original shared files remain untouched.
`benchmark.review_demo` reproduces this synthetic scenario; `benchmark.compare`
prints the default five-policy model table. `analysis/plots.py` also implements class
distribution bars, which are identical for identical input replay and provide no
comparative evidence. Visualization is static PNG only; no web UI/dashboard exists.
The short synthetic CLI and comparison commands were rechecked during this checkpoint;
no existing result was overwritten. Older scripts/experimental data are not the safe
presentation path. Live monitor/collector commands are not required for Review 1.

## Remaining milestones and integration

Prepare the Design & Progress Report, architecture figure and presentation using
these existing artifacts; screenshots/slides and the final formatted academic report
are still incomplete. Then fix optional policy/validation limitations, obtain separately
approved bounded labelled traces, calibrate thresholds, evaluate classifier accuracy,
add ML comparison and design repeated completion-time/energy measurements.
Hardware control is an optional later milestone requiring suitable hardware and approval.

The approved monitoring/synthetic/evidence milestone was fast-forwarded to main and
verified on GitHub at `207e7326369506c4e9021cc8f397c50c06fb3794`. Fresh integration tests
passed 115 cases before integration (7.91 s) and on main (8.35 s). The subsequent
synthetic archive and roadmap stay on development; no later main merge is authorized.
[Roadmap](DEVELOPMENT_ROADMAP.md) prioritizes the OS Course Project v1.0 demonstration
separately from research. Frontend brainstorming is pending; preferred Streamlit and
optional Plotly remain unimplemented/uninstalled. Use the existing terminal/PNG path
until design is finalized. Loaded stress validation and physical savings remain deferred.
See [dashboard handoff](DASHBOARD_INTEGRATION_HANDOFF.md) for evidence/APIs and safety
boundaries. Exact archive checkpoint, review and push verification are in the shared
STABLE_MILESTONE_INTEGRATION.md report.
