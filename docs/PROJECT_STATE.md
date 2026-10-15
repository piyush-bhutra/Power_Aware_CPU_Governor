# Verified project state

Last inspected: 2026-10-15 11:27:57 UTC. Session `initial-codex-setup-20261015`.
Latest tested checkpoint: main `1ece4a22385c56af0e1c4d139b1ec897f6ca997d`; identical to origin/main after successful
fetch. Setup documents remain uncommitted. This is the authoritative progress snapshot;
PRD's introductory “no code / VM not set up” status is historical and obsolete.

## Objective and architecture
Investigate workload-aware CPU frequency decisions in a Python userspace loop.
Aggregate /proc/stat monitoring → rule classifier → K-tick hysteresis policy →
simulated or sysfs setter → CSV and modelled power → baseline replay and PNG analysis.
Stack: Python 3 virtualenv, pytest, matplotlib Agg, pandas; requirements also include
scikit-learn for future ML. Whole-system signals; no scheduler/queue manipulation.

## Implemented and verified
- Counter parsing, deltas, queue gauges and bounded ratio features; CSV parent creation.
- Four rule classes: CPU-bound, I/O-bound, idle, mixed. Thresholds are provisional.
- Class-frequency mapping, default K=3 hysteresis; optional ramp-down exists with a bug.
- Simulated setter and self-verifying sysfs setter (fake hardware tests only).
- Logging separates requested frequency from setter-confirmed result.
- Cubic power estimate, energy summaries, performance/powersave/ondemand/conservative
  policy approximations and deterministic replay comparison.
- Three PNG plot functions; tests verify PNG presence/signature, not visual correctness.
- Fresh existing suite: **24 passed in 2.51 s**. Synthetic CLI: 20 rows, four classes,
  SimulatedSetter. Baseline demo: five policies, 34 ticks each. Collector bash syntax passes.

## Partial, missing and known issues
Live monitor implementation exists, but no new live sampling run was performed during
setup. Historical cpu/io experiments are documented; vm/mixed profiles remain unverified.
Existing ignored local data needs provenance/integrity review before being used as evidence.
Threshold calibration/classifier accuracy on real labelled data is incomplete.
Counter total includes guest/guest_nice already contained in user/nice (double-count risk).
Negative counter deltas/iowait and counter resets are not robustly handled. Rate computation
uses requested interval rather than measured monotonic elapsed time. Raw snapshots are
not retained in output CSV despite PRD's intended raw-counter logging.
Optional ramp-down stops after its first drop while a class stays stable because the
stable-class early return prevents further convergence. Synthetic CLI ignores --ticks;
its fixed plan yields 20 rows. Input validation is limited for interval/ticks/k/ladders.
Hardware clamping leaves policy state unsynchronized (known tested limitation, dormant
with simulated setter). Real sysfs actuation is unavailable in this guest.
Collector has unsafe load/error/cleanup behavior; see setup report. No schedutil baseline,
ML model/training/evaluation, closed-loop completion-time comparison, repeated validated
trials or final report/presentation artifacts are tracked. Review I report is not tracked.

## Experiment and model limits
No stress or collection performed in setup. CPUFreq is absent; measured kernel statistics
are distinct from simulated frequency decisions and estimated power. Open-loop replay
holds the input trace fixed, so it cannot prove preserved performance or physical savings.
The constants 21.6 W / 32.4 W and 3.8–5.1 GHz ladder are modelling choices documented
in power_model.md, not physical calibration. Host package model vs four guest vCPUs,
base-clock floor, constant leakage and TDP/boost assumptions limit interpretation.
Class-distribution bars are identical for any identical replay, including real trace
replay in this VM; do not infer frequency-dependent workload duration from them.

## Evidence discrepancies and decisions
Current guest Ubuntu 26.04.1 supersedes supplied 25.04 context. lscpu reports KVM,
contradicting historical legacy-paravirt resolution; current timing safety is unresolved.
VM freeze causes remain uncertain. Preserve historical docs rather than rewrite evidence.
Maintain simulated whole-system architecture; do not rush ML before Review 1.
Stable main plus reusable development is proposed; branch/identity/checkpoints await approval.
backup-old-local and remote mock-sysfs-wip contain unique work and are preserved.

## Review readiness and roadmap
Ready: short synthetic pipeline, hysteresis explanation, baseline decisions, unit-test
evidence. Not ready: validated real classification, calibrated thresholds, review report
and screenshots, trustworthy collection safety or performance/energy claims.
Immediate: get development workflow approval; fix collector safety with failure-path
checks; resolve timing discrepancy read-only; then approve a tiny experiment if needed.
Before October 16 prioritize reproducible synthetic demo, honest charts and Review I report.
After review fix monitoring/ramp-down/CLI defects, collect validated traces, tune thresholds,
evaluate classifiers and intervals, design repeated performance/energy methodology, implement
ML comparison, complete report (15+ verified MLA sources) and 15–20 slide presentation.
Verify cited paper claims against primary sources before academic use; setup did no external
literature validation. Reassess hardware access only if it materially serves final scope.
Next priority: make collection safe and observable on an approved development branch.
