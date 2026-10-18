# Codex operational workflow

Established 2026-10-15 11:27:57 UTC. Source instruction: `/media/sf_OS_Project_Shared/codex_master_setup.txt`.

## Single-branch workflow and sync protocol

Current Git policy since October 18, 2026. It supersedes every main/development
instruction in the sections below (stop-on-stale branch comparisons, development
checkpoints, the milestone merge policy and READY/DEFER/BLOCKED integration
assessments). Those sections are kept as history.

Consolidation record: development (271c3733b30fb4aca22c172b9b86de42600be737) was
fast-forwarded into main (previously 2753fc397bc97b96421ebb365152c1c0fc66781f),
main was pushed and verified on origin, and development was deleted locally and on
origin after Git confirmed main contained it. Its tip is preserved as annotated tag
pre-consolidation-development. The first safe point is annotated tag
checkpoint-0-daybreak-integrated at the same commit.

Rules for every task on every device:

1. **One branch: main.** Work and commit directly on main. Safe points are annotated
   tags named `checkpoint-N-description`, pushed to origin.
2. **Commits and attribution.** Plain descriptive messages. No AI attribution
   anywhere: no Co-Authored-By trailers, no "Generated with" lines, no mention of
   Claude, Codex or AI in commit messages, tags or PR text. Repository-local identity
   stays piyush-bhutra; never override author or committer.
3. **Start-of-session sync**, every session and every time the device changes:
   - confirm repository root, identity, current branch and a clean working tree;
   - `git fetch origin` without prune; compare local main to origin/main;
   - if the tree is clean and local main is only behind, update with
     `git merge --ff-only origin/main` and nothing else;
   - if the tree is dirty, the branches diverged, or anything is unexpected:
     STOP and report. Never rebase, reset, stash, force-push or resolve conflicts
     silently.
4. **End of task:** clean working tree, main pushed, and the remote hash verified
   with a remote query (`git ls-remote origin refs/heads/main`).
5. **Safety:** no collectors, stress, sudo, installs or hardware writes without
   explicit user approval (see AGENTS.md).
6. **Preservation:** keep `mock-sysfs-wip` (local and origin) and
   `backup-before-cleanup-2026-09-18-tag`. Delete no branch, tag or file without
   explicit approval.

## Environment and paths
Repository: `/home/vboxuser/Power_Aware_CPU_Governor` (verified Git root).
Windows host / VirtualBox guest. Host Ryzen 7 7840HS, 16 GB RAM are user-provided;
guest lscpu confirms Ryzen identity and four vCPUs. Current guest reports Ubuntu
26.04.1 LTS, kernel 7.0.0-31-generic, superseding setup's Ubuntu 25.04 description.
Visible RAM 3.3 GiB, swap 2 GiB; inspection showed 2.1 GiB available and 445 MiB
swap used. Local disk 30 GiB, 16 GiB free. These are snapshots, not stability proof.
Wayland, Nested Paging, Guest Additions and 4096 MB allocation are supplied context,
not all independently verified. Preserve existing Claude configuration.

Shared mount: `/media/sf_OS_Project_Shared/` → Windows
`C:\Users\shubh\OneDrive\Documents\OS_Project_Shared` (user-supplied mapping).
Use it for handoff instead of clipboard. Keep active workloads/data on local disk.
Existing `.venv` is usable; no dependency installation was needed.

## Session startup
1. Read AGENTS.md, PROJECT_STATE.md, recent DEVELOPMENT_LOG.md and latest handoff.
2. Verify root with git rev-parse; inspect status including untracked files/conflicts.
3. List local/remote branches and tracking, default branch, remotes, stashes/worktrees.
4. Inspect author/committer, configuration source, overrides and effective hooks.
5. Look for merge/rebase/cherry-pick markers. Preserve unfinished changes.
6. Fetch (no pruning) when permitted. Compare ahead/behind; do not blindly pull.
7. Identify latest checkpoint and current authorized objective. Ask only if ambiguous.

## Mandatory stop-on-stale rule (historical; superseded by the single-branch sync protocol above)

Before editing in every coding or repository task, inspect Git status, fetch origin
without pruning when network access is available, and independently verify remote
heads. Compare the working branch with its upstream and check both local main and
development against origin/main and origin/development. A clean tree does not prove
freshness; the Windows workspace and friend's Ubuntu VM are both potential writers.

STOP before implementation if the working branch or local development is behind,
any relevant branch is divergent/stale, or local main is behind origin/main. Report
ordinary main advancement separately from conflicts. If remote verification is
unavailable, freshness is unverified: do not edit work requiring current upstream state.
Report checkout path, branch/local/remote hashes, ahead/behind counts, working-tree
state, local-only work and exact safe synchronization options; wait for the user's
separate decision. Do not automatically pull, merge, rebase, reset, stash, cherry-pick
or create commits to resolve stale/divergent state. Preserve historical unique work.

The October 15, 2026 workspace-setup request is a one-time exception: after verifying
the canonical remote, clean tree, no at-risk untracked/ignored work, no unpublished
commits needing preservation, no interrupted operation and fast-forward eligibility,
update local main/development only to their verified corresponding remote heads.
Create a missing local development branch tracking origin/development; finish there.
No history rewriting, branch deletion or main integration is authorized. The request
allows one reviewed, lightweight-checked workflow-policy documentation checkpoint and
normal push to origin/development; synchronization itself authorizes no push. Verify
remote alignment immediately before that push and independently verify its result.
Future stale repositories still require a separate synchronization decision.

Use repository-local identity piyush-bhutra <piyushbhutra1@gmail.com> for new commits;
leave global identity and historical authors unchanged. Follow existing local hooks
and add no AI attribution. Routine verified development checkpoints/pushes require
approved task scope and aligned remote development. Main integration always requires
separate approval of the exact target after accumulated diff/history/tests/limitations
review and a READY / DEFER / BLOCKED recommendation.

Workspace recovery note: this setup executes in Windows PowerShell at C:\OS Project,
not /home/vboxuser/Power_Aware_CPU_Governor. Both documented shared-folder paths are
unavailable here; this workflow note and the chat synchronization report are the local
handoff. The Ubuntu environment/identity/hook observations below are historical and
must be rechecked there. No frontend, backend implementation or experiment is part
of this setup. Governorlab terminal demonstration is the next separately scoped task,
followed by the Daybreak Streamlit/Plotly dashboard with a shared backend data adapter.
Setup checks: 42 Windows-compatible unit/synthetic tests passed; Linux collector/
launcher tests require fcntl and remain Ubuntu checks. All 26 archived SHA256 entries
match stored Git blobs; system core.autocrlf=true converts 14 covered text files to
CRLF locally, so direct working-file hash checks differ for those files only. CSVs
and PNGs retain their recorded bytes. No evidence or line-ending settings were changed.

## Git workflow and permission state (historical; superseded by the single-branch workflow above)
Current stable/default: main. Reusable development created from verified main at
`1ece4a22385c56af0e1c4d139b1ec897f6ca997d` under the explicitly requested Review 1 task.
Initial persistent-documentation checkpoint `1a3d180` was pushed to origin/development.
Keep backup-old-local and origin/mock-sysfs-wip; both have unique historical work.
The branch target does not authorize deletion. Main changes require exact milestone
approval; see the integration record below.
Repository-local identity is confirmed as piyush-bhutra <p***@gmail.com>, overriding
unchanged global Vedant settings. Effective author and committer verified; no environment
identity overrides observed. Existing attribution-blocking commit hook is preserved.
The prompt authorizes coherent development checkpoints and origin/development pushes
for this review task; future unrelated work requires task authorization. Inspect diffs
and secrets, stage explicit files, run safe checks, commit, verify, push only the explicit
development ref and confirm the remote hash. Preserve local checkpoints on push failure.
Never add AI attribution or alter historical attribution.
No merge or push to stable, history rewrite, branch/file deletion, release, public
publication or repository permission change without explicit approval.
Fast-forward only under approved workflow; divergence or conflict-producing
integration requires explanation and approval. Never hide uncommitted work by switching.

## Milestone-based Git synchronization and merge policy (historical; superseded by the single-branch workflow above)

Persistent project policy adopted October 15, 2026 from the user-invoked
`/media/sf_OS_Project_Shared/prompts/GIT_WORKFLOW.txt`. Apply throughout the project;
the earlier task-specific checkpoint permissions above remain scoped to those tasks.

Use origin/development as the backed-up working branch and main as the stable branch.

After meaningful development milestones:

1. Verify the current working tree, commit history, Git identity and remote synchronization.
2. Review all changes between main and development, including file-level diffs and commit history.
3. Ensure appropriate tests have passed and significant functionality is verified.
4. Check whether unresolved defects, experimental limitations or documentation inconsistencies make the changes unsuitable for main.
5. Assess whether the accumulated work forms a coherent, independently useful milestone.
6. Recommend READY, DEFER or BLOCKED for merging, with a brief evidence-based explanation.
7. If READY, propose a safe merge procedure and wait for explicit user approval.
8. Never automatically merge, force-push, rewrite history or delete branches.
9. Preserve historical branches containing unique work.
10. After an approved merge, verify main and origin/main, ensure development remains usable, and record the resulting commit hashes.
11. Keep milestone reports and Git decisions in PROJECT_STATE.md, DEVELOPMENT_LOG.md and the shared-folder handoff.

Do not recommend merging merely because a session is ending. Do not indefinitely
postpone integration when a coherent, fully verified milestone is ready.

Prefer small, understandable, recoverable integrations over large accumulated merges.

Continue making and remotely backing up authorized development checkpoints between
merge assessments. This policy does not itself authorize a merge or expand experiment
permissions.

## Safe validation and VM history
Level 1 static/read-only inspection and level 2 short unit/synthetic checks are allowed.
Use bounded commands and limit numerical library threads where useful:
`OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 60s .venv/bin/python -m pytest tests/ -q`.
Do not run the collector, stress-ng, unbounded loops, memory/disk exhaustion, prolonged
benchmarks, sudo, frequency writes, package installs or system/kernel/VM changes
without explicit approval. No automatic retry of a failed workload; avoid guest browsers.

Past freezes, swapping, workload failures, SIGILL and timing distortion are reported.
September docs record method-specific SIGILL workarounds and a legacy-paravirt timing
fix. Today lscpu reports KVM, contradicting those notes; do not treat the fix as currently
verified. Root cause of current freeze risk is undetermined. Memory pressure, worker
saturation, disk loop, hypervisor timing and script defects remain candidates.
Read-only checks found no CPUFreq interfaces; use simulated control. Native Linux with
exposed CPUFreq may support physical actuation later; that is optional engineering,
not a Review 1 prerequisite, and must be assessed before any privileged write.

Level 3 experiments need explicit approval of worker count, maximum duration, memory
budget, disk limits, output, timeout/kill escalation, cleanup, error validation and
monitoring. Level 4 heavy benchmarking also needs explicit approval and is discouraged.

## Reports, export and completion
Directories: reports (investigations), logs (bounded relevant outputs), results (validated
completed CSV/plots), prompts (read only explicitly requested files), archive (history).
LATEST_REPORT.md includes timestamp/session/branch/hash/status, work, changed files,
checks/results/errors, verified findings, problems, commit/push, Review 1 readiness,
next task, decisions and supporting filenames. SESSION_STATUS.md is a compact recovery
snapshot including active task, last tests/checkpoint, outstanding changes and next safe action.
Write a temporary file on the destination filesystem and replace atomically. Archive
existing handoffs before replacement; preserve all other contents. Export no secrets or
unnecessary personal information; mask email. Verify files by rereading them and matching
hashes against local originals. If mount/permissions fail, retain local recovery files,
report the fallback path, and retry only when access is available. Sandbox escalation
is required for shared-folder writes in this environment.
At completion update only relevant docs and log, inspect final diff/status, verify
outputs, record checkpoint/push status and merge readiness. Tell user to upload
`/media/sf_OS_Project_Shared/LATEST_REPORT.md` plus referenced supporting report.

## Crash recovery
Read SESSION_STATUS.md and latest report; inspect Git status/branches/recent commits,
stashes/worktrees and interrupted-operation markers. Compare changed files against
project state and last checkpoint. Preserve partial work and diagnostics. Determine
what failed before suggesting safe recovery; never reset/clean/discard or rerun stress.
Local commits protect reproducibility, remote pushes protect VM disk loss, and handoffs
protect context. Initial setup was subsequently checkpointed and pushed under the Review 1 authorization.

## Real monitoring milestone authorization and workflow
The October 15 Real_Monitoring_Milestone prompt authorizes collection/monitor repairs,
one no-generated-load capture of at most five one-second intervals, and development
checkpoint/push for that task. That observation completed once; it does not authorize
artificial CPU/memory/I/O/mixed experiments. Read COLLECTION_WORKFLOW.md before using
the repaired collector. Failed traces remain failed; do not auto-retry, relabel background
as idle ground truth, or combine schema versions by appending to old CSVs. Snapshot
resource availability, validate raw/derived data, and export only after validation.


## Stable integration authorization record — October 15, 2026
The user-invoked Stable_Milestone_Integration.txt authorized exactly
207e7326369506c4e9021cc8f397c50c06fb3794 to main after guarded checks; this succeeded
and origin/main was independently verified. Original main
1ece4a22385c56af0e1c4d139b1ec897f6ca997d and historical branches remain recoverable.
This prompt also authorizes the subsequent selective synthetic evidence/roadmap
checkpoint and normal origin/development backup, not its integration into main.
Keep evidence and related documents in one coherent checkpoint to avoid needless
divergence. Assess that accumulated diff independently; a READY assessment alone
never authorizes main. Future frontend work starts after stable baseline/design
completion and task authorization; no frontend install/implementation in this task.
See DEVELOPMENT_ROADMAP.md and DASHBOARD_INTEGRATION_HANDOFF.md for scope/boundaries.
