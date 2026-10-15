# Codex operational workflow

Established 2026-10-15 11:27:57 UTC. Source instruction: `/media/sf_OS_Project_Shared/codex_master_setup.txt`.

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

## Git workflow and permission state
Current stable/default: main. Reusable development created from verified main at
`1ece4a22385c56af0e1c4d139b1ec897f6ca997d` under the explicitly requested Review 1 task.
Initial persistent-documentation checkpoint `1a3d180` was pushed to origin/development.
Keep backup-old-local and origin/mock-sysfs-wip; both have unique historical work.
The branch target does not authorize deletion. Main must remain unchanged.
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
