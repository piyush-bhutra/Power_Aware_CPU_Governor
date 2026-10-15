# Review 1 preparation — October 16, 2026

## Goal and scope
Demonstrate credible architecture and working OS-project progress. Do not assign a
completion percentage without a requirements mapping. Announce ML as Review II work.
Show measured Linux signals separately from synthetic inputs, simulated actuation and
estimated/modelled energy; never claim workload speed preservation from replay.

## Three priorities
1. Prepare a bounded reproducible demo and evidence pack (1–2 hours): existing tests,
   synthetic four-class transitions, K=3 hysteresis, io_burst vs ondemand explanation,
   frequency timeline and explicitly estimated energy chart. Capture terminal screenshots.
2. Address collection safety before any real workload (2–4 hours including checks):
   validate budgets, bounded single-worker profile, retained stderr/exit codes, external
   timeout, process-group cleanup, unique output paths and CSV integrity. Then inspect
   current KVM-vs-legacy discrepancy; do not alter VM settings. Experiment approval is separate.
3. Assemble Design & Progress Report (2–3 hours): architecture, module responsibilities,
   flowchart, algorithms, verified progress/test evidence, limitations/challenges, remaining
   plan and references. If time is short, deliver honest synthetic evidence first.
Estimates are approximate and exclude unexpected VM or tooling problems.

## Safe demo commands and expected outputs
Run from repository root using existing virtualenv; no installations or stress required.

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 60s .venv/bin/python -m pytest tests/ -q
.venv/bin/python governor.py --synthetic
.venv/bin/python -m benchmark.compare
```

Review demo validation verified 30 passing tests, 20 synthetic rows with SimulatedSetter and four classes,
and five comparison rows with 34 ticks each. --ticks now caps the finite 20-row synthetic plan; zero emits no rows, and
negative values are rejected before hardware selection. Synthetic mode never probes hardware. Comparison's default plain io scenario does not necessarily
beat ondemand; explain decisions rather than promise an advantage. Existing io_burst
regression test demonstrates the motivating difference after hysteresis settles.
Reproducible chart/evidence command (use a new directory for every run):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 30s .venv/bin/python -m benchmark.review_demo --outdir data/review1-demo-new
```

This driver uses seed 11, interval 1 s, K=3 and cpu→io_burst→idle→mixed (34 rows).
It writes five policy CSVs, summaries.json, metadata.json,
synthetic_modelled_energy.png and synthetic_simulated_frequency.png, with explicit
labels on each chart. Metadata records commit and dirty state at generation.
It refuses to append to or overwrite existing evidence artifacts.
Label charts synthetic and energy estimated. Do not present
identical classification bars as comparative evidence.

Optional later read-only live demo: `.venv/bin/python -m monitor.reader` (five one-second
samples, no generated stress). Not executed during setup; confirm safe execution and
capture before claiming live validation. Never run the collector as a review shortcut.

## Evidence checklist and explanation points
Capture test summary, four-class synthetic output, hysteresis lag at transitions,
architecture/flowchart, frequency timeline, labelled modelled-energy table/chart,
read-only missing-CPUFreq evidence and Git checkpoint. Save provenance (command, seed,
interval, commit, synthetic/real designation). No screenshots were captured in setup.
Explain cumulative counters vs deltas, instantaneous queue gauges, I/O-first rules,
provisional thresholds, tradeoff of hysteresis lag, setter abstraction, estimated
power assumptions, whole-system VM granularity and open-loop benchmark limitations.
Use PRD report format: Times New Roman, headings 16/14/12 pt, body 12 pt, 1.5 spacing,
justified text, bottom-centre pages, captions below figures and above tables.

## Risks, fixes and deferred work
Immediate risk: unstable VM and unsafe collector; real calibrated evidence may not
fit remaining time. No repeated stress runs or settings changes without approval.
Correctness fixes: measured elapsed-time accounting, guest counter handling, gradual
ramp-down convergence and CLI validation. Fix only with targeted authorization and tests;
optional ramp-down is not enabled in the current default demo.
Real labelled trace calibration remains missing; show it as future work if unavailable.
Final project: repeated validated trials, classifier accuracy/ML comparison, sampling
interval study, credible completion-time methodology, final report and presentation.
Native hardware frequency control and a dashboard are optional, not Review 1 blockers.

## Real monitoring evidence now available
The safe monitoring milestone adds five genuine Linux counter observations labelled
uncontrolled_background, raw snapshots, measured intervals and resource diagnostics.
60 tests passed; collector safeguards are tested with harmless processes. Show this
separately from the synthetic/simulated energy charts. No workload-class ground truth,
physical actuation, measured energy or stress validation is claimed. Use the exported
REAL_MONITORING_MILESTONE.md and CSV in the progress report. Collector I/O remains
intentionally disabled. The first CPU experiment plan still needs explicit approval;
see COLLECTION_WORKFLOW.md, including the ~25% aggregate utilization expectation.
