# Standalone background readiness preparation — October 15, 2026

## Status and exact command

Preparation complete; actual background observation **not executed**. Authorization:
shared prompts/small_task.txt. No stress-ng, artificial CPU/memory/I/O workload,
frequency actuation, installation or VM/system change occurred.

After reviewing and separately approving one background-only observation, close
Codex/unnecessary applications, open an ordinary Ubuntu terminal, and run:

```bash
/home/vboxuser/Power_Aware_CPU_Governor/scripts/run_background_readiness.sh
```

Read the printed limits and type `RUN`; any other answer cancels. Ctrl+C cancels with
cleanup/evidence preservation. The command works from any directory, accepts no safety
overrides, resolves the project root and uses the existing virtualenv. Do not run the
CPU experiment launcher for this background-only check. No execution permission for
the actual observation is inferred from this preparation task.

## Supported method and safeguards

Collector `--profile background` already selects no worker and uses the new
monitor-first ready/start gate. A raw capture command would bypass supervisor
readiness; a plain collector command would omit standalone preflight/export/fallback
cleanup. The new fixed entrypoint reuses the existing standalone launcher with a
background profile, leaving the existing CPU default intact.

Exactly five one-second attempted intervals; monitor startup cap two seconds within
the total eleven-second supervisor budget; fifteen-second GNU timeout with one-second
kill escalation. No artificial workers, no stress-ng dependency, no workload approval
flag, no frequency control. Positional 64M is syntax only and allocates no stressor RAM.
Budgets govern collection rather than confirmation/export time; cleanup may take
additional bounded time. Guest/host pauses can delay in-guest deadlines.

Retained safeguards: shared experiment lock, dependency/project checks, mounted
shared-folder read/write probe, local free disk >=512 MiB, available RAM >=512 MiB,
swap-growth guard <=128 MiB, three 250 ms swap windows (<=32 combined pages in <=1
active window), resource recheck after confirmation and throughout supervision,
monotonic interval/raw accounting validation, owned process groups with TERM/KILL/reap
and independent recorded-group fallback cleanup. No automatic retry or installation.

Successful background status requires monitor exit zero, worker exit absent, complete
successful collector manifest, exact five-row uncontrolled_background CSV validation,
consistent manifest/lifecycle content and ordered monitor_started → monitor_ready →
sampling_released → monitor_exited → cleanup_finished events. The monitor identity,
ready/start files and monitor log must exist. A valid CSV alone cannot establish
successful readiness. Missing process evidence or any worker record rejects success.

## Output and recovery

Local directory: `data/background_readiness/launcher-<UTC>-<random>/`.
Shared directory: `results/safe_background_launcher-<UTC>-<random>/`.
Report: `BACKGROUND_READINESS_REPORT.md`.

The exported tree contains launcher metadata/stdout/stderr, valid-only
validated_trace.csv and collection/<run>/ metadata, manifest, lifecycle.json,
processes.json, monitor.ready/start, monitor.log with baseline/raw interval attempts,
trace.csv, empty worker.log and statistics.json when produced. Partial failures export
all available evidence and error text. SHA256 comparison checks copied files.
Previous handoffs are archived; LATEST_REPORT.md and SESSION_STATUS.md are replaced
atomically. If the mount/export fails, use the local report and export-error.txt;
the shared handoff may be stale. Never infer success merely from a CSV or directory.

## Verification

Initial seven new tests failed against the missing background profile API. Regression
coverage now includes fixed no-worker command/deadlines, missing stress-ng tolerance,
successful fixture export, missing/inconsistent/out-of-order lifecycle, unexpected
worker, missing monitor identity, timeout, low memory, export failure, collector
background readiness wiring, no CLI overrides, and wrapper root resolution with spaces.
New background tests substitute the collector process or supervisor boundary; none
reads a live sample or selects a stressor.
Existing tests cover swap/resource failures, INT/TERM, locking, fallback cleanup,
identity reuse, failed manifests, invalid CSVs and partial exports.

An intermediate string-concatenation syntax error was corrected before tests could
collect. One initial targeted existing CPU cleanup case failed because lscpu exceeded
its three-second metadata timeout before collector startup, yielding 124 rather than
the test's expected 1. The first full suite subsequently passed 114 tests in 38.09 s.
The fixture now mocks environment metadata commands and retains real harmless
collector children, avoiding irrelevant host-tool latency without relaxing production
limits. Full suite after the process-record fix: **115 passed in 13.65 s**. Shell syntax
and git whitespace checks pass. No new live validation or performance claim is made.

Independent review identified a missing-record acceptance gap, reproduced by a failing
test and fixed by requiring monitor identity evidence. Final independent re-review found no remaining integration blockers. Exact
checkpoint/push hashes are in the exported appendix/shared handoff.

## Read-only milestone merge assessment

**READY for implementation integration**, subject to clean verified checkpoint and
explicit user approval of the merge. This recommendation concerns useful implementation
milestones, not the end of a session or completion of the project.

| Accumulated milestone | Evidence / limitation |
|---|---|
| Persistent project/Git workflow | Startup, recovery, scoped approvals, milestone merge policy recorded; pending edits from prior user request preserved. |
| Synthetic review demo | Bounded synthetic mode uses simulated setter; seeded modelled-energy evidence; no physical savings claim. |
| Monitor and collector repair | Corrected counter accounting, measured intervals, raw evidence, conservative resource/deadline/cleanup tests; earlier five-row background capture exists. |
| Standalone CPU launcher | Confirmation, preflight, owned groups and automatic evidence export; first real manual CPU attempt failed and has zero usable rows. |
| Swap preflight | Recorded deltas/rates and conservative transient threshold; engineering threshold, not loaded-VM calibration. |
| Timing diagnostics | Ready/start gate, attempted-interval logs and failure-independent validation; original missing-row cause remains uncertain. |
| Background preparation | Fixed no-worker standalone command with strict readiness/identity/CSV validation; actual observation pending. |

Known optional ramp-down convergence and setter clamping-state limitations predate
this work, are documented and do not affect the fixed raw-only background path.
Threshold calibration, loaded timing, successful CPU datasets, ML, native frequency
control, measured energy and preserved workload completion time remain unverified.
These limitations defer experimental/product claims, not integration of coherent
preparation/diagnostic code. No artificial run should be used as a merge check.

Git began at development 59a2ac3, matching origin/development after fetch. Six milestone
commits accumulated beyond main before this checkpoint; file-level diffs and history
were reviewed. main remains 1ece4a2. backup-old-local has six commits beyond main and
origin/mock-sysfs-wip has one; both refs and their unique historical work are preserved.
Repository-local piyush-bhutra identity/hook remain intact; no AI attribution added.

Proposed safe integration, **only after explicit approval of the checkpoint hash**:

1. Fetch without pruning; verify a clean checkout, approved development/remote hash,
   unchanged main/origin/main, and that main is an ancestor of development.
2. Review the full accumulated file diff/history and the appropriate green safe suite.
3. Switch to main and fast-forward only to the exact approved hash. Stop if fast-forward
   is unavailable or any ref differs from the approved state; do not resolve by rewriting.
4. Push only main:main, verify local/remote main hashes, then return to development
   and verify it remains usable. Record hashes and Git decision in state/log/handoff.

No merge, main push, historical integration, ref deletion, force-push or history rewrite
was performed. The preparation checkpoint/backups are on development only.

One next action: review/approve one manual background-only observation using the
command above, close Codex, then run it once and inspect the exported evidence.
