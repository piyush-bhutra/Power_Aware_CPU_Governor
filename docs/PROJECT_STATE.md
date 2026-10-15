# Verified project state

Last inspected: October 15, 2026. Latest milestone: safe real Linux monitoring.
See the chronological updates below; initial setup observations are historical.
Latest tested checkpoint: main `1ece4a22385c56af0e1c4d139b1ec897f6ca997d`; identical to origin/main after successful
fetch. Setup documents were checkpointed as `1a3d180` and pushed to origin/development. This is the authoritative progress snapshot;
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
Five-interval live background monitoring is now validated; no generated workload was
run. Historical cpu/io experiments are documented; vm/mixed profiles remain unverified.
Existing ignored local data needs provenance/integrity review before being used as evidence.
Threshold calibration/classifier accuracy on real labelled data is incomplete.
Monitoring now excludes duplicate guest time, uses monotonic measured intervals, skips
reset intervals, flags/clamps decreasing iowait and captures previous/current raw counters.
New CSV headers are version-incompatible with old traces; cross-schema append is refused.
Optional ramp-down stops after its first drop while a class stays stable because the
stable-class early return prevents further convergence. Synthetic CLI now caps its finite 20-row plan with --ticks, rejects negative limits,
and constructs SimulatedSetter directly without hardware probing. Input validation is limited for interval/ticks/k/ladders.
Hardware clamping leaves policy state unsynchronized (known tested limitation, dormant
with simulated setter). Real sysfs actuation is unavailable in this guest.
Collector safeguards are implemented and harmless-process tests pass; artificial workload
operation remains unvalidated and requires separate approval. I/O profile is disabled. No schedutil baseline,
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
Stable main plus reusable development is established; repository-local piyush-bhutra
identity and development checkpoints/pushes are authorized for the Review 1 demo task.
backup-old-local and remote mock-sysfs-wip contain unique work and are preserved.

## Review readiness and roadmap
Ready: short synthetic pipeline, hysteresis explanation, baseline decisions, unit-test
evidence. Not ready: validated real classification, calibrated thresholds, review report
and screenshots, collection under stress or performance/energy claims.
Immediate: prepare review report using synthetic and background-monitor evidence; resolve
or explicitly accept timing discrepancy before separately approving a tiny CPU experiment.
Before October 16 prioritize reproducible synthetic demo, honest charts and Review I report.
After review fix monitoring/ramp-down/CLI defects, collect validated traces, tune thresholds,
evaluate classifiers and intervals, design repeated performance/energy methodology, implement
ML comparison, complete report (15+ verified MLA sources) and 15–20 slide presentation.
Verify cited paper claims against primary sources before academic use; setup did no external
literature validation. Reassess hardware access only if it materially serves final scope.
## Review 1 demonstration update — October 15, 2026
Current work branch: development. Main remains at the tested hash above.
Fresh suite: 30 passed in 1.76 s, including six CLI/evidence cases. Failing regression
tests first reproduced ignored limits and hardware selection in synthetic mode.
`benchmark.review_demo` exports 34 seeded rows per policy, summaries/provenance and
two labelled PNGs. Existing default demo still runs 20 synthetic rows. Review evidence
does not validate physical frequency, energy, workload speed or real thresholds.
Latest demonstration checkpoint/push hash is recorded in shared SESSION_STATUS.md
and the Review 1 handoff (avoids a self-referential commit hash in committed documents).
Next priority: assemble Review 1 Design & Progress Report using this evidence pack;
collector hardening remains required before any separately approved real experiment.

## Real monitoring milestone — October 15, 2026
Authorization: shared prompts/Real_Monitoring_Milestone.txt includes development commit/push.
60 automated tests passed in 3.33 s; no real collector invocation or artificial load.
Single live capture: five valid Linux observations, labelled uncontrolled_background.
Elapsed interval 1.001–1.012 s; mean utilization 7.67% (4.29–13.51%), iowait 0%.
Available RAM before/after 2,262,312/2,266,264 KiB; swap unchanged at 423,072 KiB.
No pressure or gross timing anomaly detected in this short no-load run. This does not
resolve historical freeze risk or prove timing stability under stress. Source SHA256s
identify the observed pre-commit files; latest checkpoint/push is in shared handoff.
Collector now uses single conservative profiles, 1 cpu worker, <=128 MiB vm request,
1–30 intervals, worker and supervisor deadlines, groups with TERM/KILL/reap, resource
checks, unique run directories, logs/metadata and atomic success/failure manifests.
CSV validation checks row counts, labels, finite values, elapsed bounds, raw accounting
and gross aggregate jiffy rate. Raw-only observation never selects a frequency setter.
I/O is disabled rather than replaced by an unreviewed disk workload. See
[collection workflow](COLLECTION_WORKFLOW.md) for semantics, compatibility and pending plan.
Review findings about cleanup exceptions/provenance were reproduced and fixed.
Optional static lint was unavailable (pyflakes module absent); no package installed.
Next: Review 1 report, or separately approve the documented one-worker CPU experiment.

## Standalone CPU launcher setup — October 15, 2026
Authorized by Safe_CPU_Launcher.txt for implementation and harmless tests only.
Added executable scripts/run_safe_cpu_experiment.sh and benchmark.safe_cpu_launcher;
reuses collector CLI/supervisor/validator. Adds interactive RUN confirmation, environment/
resource/shared-mount preflight, lock shared with direct collector, source provenance,
outer timeout, fallback recorded-group cleanup and standalone local/shared handoff.
Collector now records process groups and participates in the launcher-inherited lock.
80 lightweight tests cover mocked success, dependencies/resources, failures/timeouts,
INT/TERM cleanup, manifest/CSV validation, exports, locks and identity reuse. No real
CPU, memory or I/O workload ran. Existing Linux/synthetic behavior remains covered.
Review findings on cleanup exceptions/partial exports/identity reuse were fixed.
Launcher is ready for user-approved manual execution with Codex closed, subject to
its fresh preflight and interactive confirmation. Stress-ng effectiveness and loaded
VM timing remain unvalidated. Checkpoint/push hash is recorded in shared setup handoff.
Next: user reviews limits, closes Codex, and manually launches only if approved.
