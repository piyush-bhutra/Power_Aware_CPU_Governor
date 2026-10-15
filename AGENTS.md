# Power-Aware CPU Governor — persistent agent instructions

Python userspace OS course project: Linux aggregate monitoring → workload
classification → hysteretic frequency policy → setter → CSV → estimated power
and baseline analysis. This is not a kernel scheduler. Review 1: October 16, 2026.

## Start every session
Read [project state](docs/PROJECT_STATE.md), recent [development log](docs/DEVELOPMENT_LOG.md),
and [workflow](docs/CODEX_WORKFLOW.md). README and [PRD](docs/PRD.md) describe
interfaces and intended scope; code and fresh tests determine implemented status.
Inspect root, Git status, branches/tracking, remotes, effective identity, stashes,
worktrees and interrupted operations. Fetch when permitted, inspect differences;
never blindly pull. Resume only the latest authorized task. Preserve Claude files.

## Safety and approvals
Use static checks, existing unit tests, and bounded synthetic demos. No collector,
stress-ng, multi-worker stress, memory exhaustion, aggressive writes, system/kernel/
VM changes, actual frequency changes, sudo or installations without explicit approval.
Controlled experiments need worker/duration/memory/I/O budgets, timeout, monitoring,
error detection and cleanup. Never automatically rerun a failed workload.
No unnecessary guest browsers. Historical timing fixes are not current validation.

## Git and recovery
Stable branch is main; reusable work branch is development. The Review 1 prompt
approved its creation, repository-local identity piyush-bhutra, and development
checkpoints/pushes for the authorized review demonstration task. For future tasks,
apply checkpoint authorization only within its approved scope. Stage explicit
files, run appropriate safe checks, verify pushes. No AI attribution in new commits.
Never force-push, rewrite history, discard work, delete files/branches or merge/push
to stable without explicit approval. Preserve backup-old-local and origin/mock-sysfs-wip.
After a crash inspect status, interrupted operations, stashes, checkpoint and handoff;
compare documents against code. Do not reset/clean or blindly repeat the failed command.

## Complete substantial tasks
Update relevant state/log/review documents without erasing history. Save supporting
logs and reports, then atomically update /media/sf_OS_Project_Shared/LATEST_REPORT.md
and SESSION_STATUS.md; verify readable content. Use reports/, logs/, results/,
prompts/, archive/ there. Preserve old handoffs in archive. Generate experiments locally
before exporting completed artifacts. Do not automatically execute prompt files.
If export is unavailable, save a local recovery handoff and report its location.
Never export secrets. End with task status, latest handoff path, supporting filenames,
Git branch/commit/dirty/push status, merge readiness, and one next action.
Always distinguish measured kernel counters, simulated frequency, modelled energy,
actual hardware control, and workload completion time. Do not invent savings.
See [Review 1 plan](docs/REVIEW1_PLAN.md) and detailed workflow for operational steps.

Real-monitoring milestone: the named prompt authorized collector/monitor fixes, one
five-interval no-generated-load observation, and its development checkpoint/push.
That observation is complete. See [collection workflow](docs/COLLECTION_WORKFLOW.md)
for the repaired collector and separately gated CPU plan; no artificial load is approved.

Safe_CPU_Launcher.txt authorizes standalone launcher implementation/mock tests and its
development checkpoint/push, explicitly not real stress execution. The launcher is for
later user-approved manual use with Codex closed. Do not bypass its RUN confirmation.
