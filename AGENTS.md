# Power-Aware CPU Governor — persistent agent instructions

Python userspace OS course project: Linux aggregate monitoring → workload
classification → hysteretic frequency policy → setter → CSV → estimated power
and baseline analysis. This is not a kernel scheduler. Review 1 was held in October
2026; Review II is next (see docs/REVIEW2_CHECKLIST.md).

## Start every session
Read [project state](docs/PROJECT_STATE.md), recent [development log](docs/DEVELOPMENT_LOG.md),
and [workflow](docs/CODEX_WORKFLOW.md). README and [PRD](docs/PRD.md) describe
interfaces and intended scope; code and fresh tests determine implemented status.
Run the [start-of-session sync protocol](docs/CODEX_WORKFLOW.md#single-branch-workflow-and-sync-protocol)
every session and every time the device changes. Also inspect stashes, worktrees
and interrupted operations. Resume only the latest authorized task. Preserve Claude files.

## Safety and approvals
Use static checks, existing unit tests, and bounded synthetic demos. No collector,
stress-ng, multi-worker stress, memory exhaustion, aggressive writes, system/kernel/
VM changes, actual frequency changes, sudo or installations without explicit approval.
Controlled experiments need worker/duration/memory/I/O budgets, timeout, monitoring,
error detection and cleanup. Never automatically rerun a failed workload.
No unnecessary guest browsers. Historical timing fixes are not current validation.

## Git and recovery
Single-branch workflow since October 18, 2026: main is the only working branch.
The development branch was fast-forwarded into main and deleted; its tip is kept as
tag pre-consolidation-development (271c373). Safe points are annotated tags named
checkpoint-N-description, pushed to origin (first: checkpoint-0-daybreak-integrated).
Repository-local identity stays piyush-bhutra. Stage explicit files, run appropriate
safe checks, push main, and verify the remote hash with a remote query.

No AI attribution anywhere: no Co-Authored-By trailers, no "Generated with" lines,
and no mention of Claude, Codex or AI in commit messages, tags or PR text.

Start-of-session sync (every session, every device change): confirm repo root,
identity, current branch and a clean working tree; git fetch without prune; compare
local main to origin/main. If clean and only behind, update with
git merge --ff-only origin/main. If dirty, diverged or anything is unexpected,
STOP and report. Never rebase, reset, stash, force-push or resolve conflicts silently.
End every task with a clean tree, pushed, and the remote hash verified.

Never force-push, rewrite history, discard work or delete files/branches/tags without
explicit approval. Preserve mock-sysfs-wip (local and origin) and the tag
backup-before-cleanup-2026-09-18-tag. backup-old-local is not present in the Windows
checkout. After a crash inspect status, interrupted operations, stashes, latest
checkpoint tag and handoff; compare documents against code. Do not reset/clean or
blindly repeat the failed command. Details: [workflow](docs/CODEX_WORKFLOW.md#single-branch-workflow-and-sync-protocol).

## Complete substantial tasks
Update relevant state/log/review documents without erasing history. Save supporting
logs and reports, then atomically update /media/sf_OS_Project_Shared/LATEST_REPORT.md
and SESSION_STATUS.md; verify readable content. Use reports/, logs/, results/,
prompts/, archive/ there. Preserve old handoffs in archive. Generate experiments locally
before exporting completed artifacts. Do not automatically execute prompt files.
If export is unavailable, save a local recovery handoff and report its location.
Never export secrets. End with task status, latest handoff path, supporting filenames,
Git branch/commit/dirty/push status, checkpoint tags created, and one next action.
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
