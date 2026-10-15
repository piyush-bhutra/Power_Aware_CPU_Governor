# Development log

## 2026-10-15 11:27:57 UTC — Initial Codex infrastructure setup
Objective: inspect and preserve project, establish durable instructions and reporting,
assess Git/VM/collector and plan Review 1 without application changes.
Created AGENTS.md and four workflow/state/review/log documents. Prepared shared directory
structure, initial setup report, latest handoff, session snapshot and supporting logs.
Verified main/origin/main `1ece4a22385c56af0e1c4d139b1ec897f6ca997d` after fetch; default main confirmed remotely.
Two local branches and two remote branches (excluding symbolic origin/HEAD).
Preserved six unique backup-old-local commits and one origin/mock-sysfs-wip WIP commit.
Tests: 24 passed in 2.51 s; synthetic CLI and baseline demo passed; bash syntax passed.
No collector/stress, installs, settings changes, commits, branch creation or pushes.
Findings: absent CPUFreq, provisional thresholds, collector safety gaps, monitor elapsed/
guest-accounting issues, ramp-down defect and ignored synthetic --ticks. Current KVM
report conflicts with historical legacy timing fix; no load validation attempted.
Checkpoint: existing tested main commit above; setup docs uncommitted and exported separately.
Identity Vedant <v***@gmail.com> requires confirmation; development/checkpoint permissions
pending. Next: approve workflow, then harden collector before approving any experiment.

## 2026-10-15 — Git workflow and Review 1 synthetic demonstration
Authorization: prompts/Os_Review1_Document.txt. Configured only repository-local
piyush-bhutra identity; verified effective author/committer. Created development from
main, preserved setup docs, committed/pushed initial checkpoint 1a3d180. Main unchanged.
Minimal CLI fixes: finite tick cap, negative-limit validation, explicit SimulatedSetter
and synthetic/modelled labels. Added seeded evidence driver reusing comparison/plot APIs;
optional plot titles label exported PNGs. No stress, collector, installs or VM changes.
Regression tests failed for both bugs before implementation; full suite 30 passed in
1.76 s. Verified short/full CLI, existing comparison and review evidence generation.
Charts and CSVs are modelled open-loop evidence, not physical energy/performance results.
Final review checkpoint/push hash is in shared handoff/session snapshot.
Next: assemble Review 1 Design & Progress Report and capture presentation screenshots.

## 2026-10-15 — Safe real monitoring and collection preparation
Objective: fix collector hazards and real-counter correctness, then one no-load capture.
Changes: monotonic elapsed rates; corrected guest total; reset handling and flagged
negative iowait; raw snapshot CSV/schema protection; bounded read-only capture/validator;
collector wrapper and Python process-group supervisor with unique outputs, metadata,
resource checks and manifests. I/O loop removed/profile disabled. No stressor executed.
Verification: regression-first accounting tests; harmless worker failure/timeout/cleanup,
manifest and provenance tests; full suite 60 passed in 3.33 s. Synthetic demo and existing
comparison passed. Shell syntax and whitespace checks passed. Pyflakes unavailable;
no installation attempted. Independent review findings on cleanup/provenance fixed and
re-reviewed. One five-row live background trace passed under 12 s external timeout;
intervals 1.001–1.012 s, utilization mean 7.67%, available memory ~2.16 GiB and swap stable.
No repeat. Exact producing source hashes, CSV, statistics and diagnostics exported.
Checkpoint/push: latest hash in shared REAL_MONITORING_MILESTONE.md and SESSION_STATUS.md;
main/historical refs preserved. Next: review report or separately approve one CPU worker
for five sampling intervals under the documented strict budgets; no experiment started.

## 2026-10-15 — Standalone CPU launcher setup (no real stress run)
Implemented scripts/run_safe_cpu_experiment.sh and Python orchestration over the existing
collector. Added shared experiment locking, process identity records, independently
attempted fallback cleanup, strict confirmation, preflight, local logs and standalone
validated export/handoff. Persistent docs include execution/cancellation/recovery steps.
Tests: 80 harmless/fixture/mock cases; shell syntax and diff checks. Regression-first
review fixes cover cleanup exceptions, partial exports and reused identities. A short
mock timeout initially masked a nonzero-exit test; replaced that mock with immediate shell
exit and used production deadline for non-timeout cases. No real stress-ng or launcher
execution against the real collector. No installs/system settings/main changes.
Checkpoint/push: final hash in SAFE_CPU_LAUNCHER_SETUP.md and SESSION_STATUS.md.
Next: wait for user approval and manual execution with Codex closed.
