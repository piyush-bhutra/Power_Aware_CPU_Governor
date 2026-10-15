# Safe Linux monitoring and controlled collection

Latest October 15 update: the first manual CPU attempt failed with zero CSV rows.
The timing investigation added readiness gating and failure diagnostics; no retry
was run. See the final section below and CPU_TIMING_DIAGNOSTIC.md. Earlier milestone
statements below describe their historical authorization and validation scope.

Milestone authorization: shared `prompts/Real_Monitoring_Milestone.txt`, October 15,
2026. Only one background-only five-interval observation was authorized and executed.
No artificial workload or actual collector invocation has been executed in this milestone.

## Counter semantics and CSV compatibility
`monitor.reader.sample()` now measures each snapshot interval with a monotonic clock.
Percentages use deltas from user/nice/system/idle/iowait/irq/softirq/steal; guest and
guest_nice remain in raw evidence but are not added to the total a second time.
The utilization convention still includes steal as non-idle time, preserving callers;
it must not be interpreted as application execution time alone in a contended VM.
Negative deltas outside iowait, or decreasing context-switch totals, invalidate that
interval and rebaseline. The fixed sample count counts attempted intervals, not valid
rows; validation fails if a trace is short. A decreasing iowait delta is clamped to zero
and flagged; it is an estimate with disclosed correction, not repaired kernel evidence.
Invalid or nonpositive elapsed time is rejected.

CSV adds elapsed_s, delta_total_jiffies, iowait_decreased and raw_prev_/raw_cur_ columns
for ten CPU counters and ctxt. Synthetic rows retain derived features but have blank
raw columns, because they are not measured Linux snapshots. Live capture also adds
workload_label, observation_source, available memory and swap used. Older CSVs remain
untouched; appending across header/schema versions is refused. New callers can request
exclusive creation with log_csv(..., mode='x'); default compatible append is retained.

Accounting references checked during the milestone:
[Linux /proc documentation](https://docs.kernel.org/filesystems/proc.html) documents
the aggregate counters and decreasing iowait;
[Linux proc_stat manual](https://www.man7.org/linux/man-pages/man5/proc_stat.5.html)
documents guest time's inclusion in user time. These sources do not validate VM timing.

## No-load observation
The completed run used `timeout --signal=TERM --kill-after=1s 12s .venv/bin/python -m
monitor.capture --ticks 5 --label uncontrolled_background --output <new-local-path>`.
Do not rerun merely to reproduce the milestone: future live runs need authorized scope.
Capture never opens a setter, changes CPU frequency or creates load. It reads /proc/stat,
optional current frequency and /proc/meminfo. One-second sleeps are checked against actual
0.5–2 s elapsed bounds. It rejects low memory (<512 MiB available), swap growth >128 MiB,
wrong row count, invalid/nonfinite observations, inconsistent raw-derived values, labels,
nonincreasing timestamps and gross jiffy-rate anomalies (0.5–1.5 times ncpu*USER_HZ).
Those loose timing guards catch gross anomalies, not subtle bias or host-clock drift.

Completed evidence: five valid uncontrolled/background rows; utilization 4.29–13.51%,
mean 7.67%; elapsed 1.001–1.012 s; no iowait decrease, swap growth or pressure detected.
This does not establish idle ground truth, classifier calibration or safety under stress.
Live metadata records source hashes because observation preceded the milestone commit.

## Repaired collector contract — not yet run with stress
`collect_real_traces.sh` retains positional `<duration_s> <vm_bytes> [outdir]` and
delegates process supervision to `benchmark.collect_traces`. Python is used for bounded
waits, process groups and structured metadata, alongside the existing Python monitor.
One explicit profile per run replaces the automatic full sweep. Default profile cpu
uses one `int64` CPU worker. vm uses one `flip` worker with a positive memory request
at most 128 MiB. mixed uses one cpu and one vm worker; it still needs separate approval.
background/legacy idle means no stressor and is labelled uncontrolled_background.
Requested profile labels describe the stressors, never classifier ground truth.
Artificial profiles require `--approved-workload`; the flag records an operator assertion,
not a substitute for explicit user approval. I/O is deliberately disabled: there is no
dd loop or approved replacement, and no disk-intensive profile can be selected.

Duration must be 1–30 one-second intervals. Worker timeout is duration+2 seconds and
supervisor deadline is duration+6, including bounded waits and resource polling every
50 ms. Logs retain stdout/stderr. Failed/nonzero or premature workers, failed monitor,
resource pressure and deadline expiry fail the run. INT/TERM raise through cleanup;
each process group receives TERM then KILL after 0.1 s, followed by a bounded reap.
Cleanup attempts both groups even if the first attempt raises. Host pause/SIGKILL can
still prevent the guest supervisor from executing; no in-guest timeout proves host safety.

Unique timestamp/random directories preserve previous files. metadata.json records
source commit/dirty state/hashes, commands, budgets, labels and initial resources.
manifest.json starts running/unsuccessful; failure keeps error and partial data/logs;
only successful exit codes and validated CSV can produce success=true with statistics.
Manifest updates use atomic replacement. Collection refuses the known shared mount,
requires at least 512 MiB disk free, and leaves completed export to a separate action.
The vm memory option bounds the stressor request, not whole-process RSS or system memory.
No package installs, automatic retries, frequency writes or privileged configuration.
Tests use fixture counters, mocked orchestration, and sleeping/exiting Python children;
they validate failure paths, not real stress-ng compatibility or workload effectiveness.

## Proposed first controlled CPU experiment — requires separate approval
Use exactly one int64 CPU worker, five monitoring intervals and worker timeout seven
seconds, with no vm/io worker, no large input allocations and no intentional disk I/O.
Retain only the small local CSV/metadata/log files. Budget: request no vm memory, monitor
available RAM and swap, abort below 512 MiB available or on >128 MiB swap growth.
Supervisor deadline 11 s, proposed outer timeout 15 s with one-second kill escalation;
monitor errors, accounting/timing anomalies and nonzero exit fail without retry.
TERM/KILL process-group cleanup and preserved failure manifests are required. If the
outer timeout fires, inspect for remaining groups rather than blindly rerun. Resolve or
explicitly accept the current KVM-versus-legacy discrepancy before approving the plan.

Pending-approval command (not executed):

```bash
timeout --signal=TERM --kill-after=1s 15s ./collect_real_traces.sh 5 64M data/controlled_cpu --profile cpu --approved-workload
```

Expect about 25% aggregate CPU utilization from one fully busy worker on four vCPUs
plus background activity, not the rule's 70% CPU-bound threshold. Do not increase
workers simply to obtain a desired label. Verify worker success and counter response
first; calibration requires independent workload evidence and multiple approved trials.

## Standalone launcher — manual execution with Codex closed
Safe_CPU_Launcher.txt authorizes implementation/mock testing, not a real stress run.
The executable scripts/run_safe_cpu_experiment.sh locates the project root and launches
benchmark.safe_cpu_launcher with the existing virtualenv. No extra dependency is needed.
It runs independently of Codex and accepts no command-line safety overrides.

After user approval, save your work, close Codex and unnecessary guest applications
(especially browsers), and use an ordinary Ubuntu terminal from the repository root:

```bash
./scripts/run_safe_cpu_experiment.sh
```

Codex should be closed to reduce memory use, scheduling interference and measurement
noise. The launcher checks the virtualenv/files, stress-ng/timeout/bash/git availability,
the mounted shared folder with write/read probe, disk >=512 MiB, RAM >=512 MiB, current
resource state and three 250 ms swap-activity windows. Preflight accepts at most 32
pages total (swap-in plus swap-out), confined to one window; activity in two or more
windows, a larger burst, or decreasing counters rejects the attempt. At 4 KiB per
page the burst cap is 128 KiB. This conservative engineering allowance addresses an
observed isolated 18-page swap-in; it is not a validated safety threshold under load.
Samples, measured elapsed times, page size, deltas, rates, thresholds and resources
are preserved in launcher metadata/report even on rejection. RAM below 512 MiB or
swap occupancy growth above 128 MiB still aborts. Historical swap allocation alone
is not treated as current thrashing. It records kernel/CPU information and warns that
KVM/legacy timing disagreement is unresolved. Type exactly RUN only if you accept the
printed limits and VM timing uncertainty; every other answer cancels before the collector.
A noninteractive/piped answer is refused. Resources are checked again after confirmation.

Exactly one int64 CPU worker is requested; five one-second samples, seven-second worker
timeout, eleven-second supervisor deadline, fifteen-second GNU timeout (one-second kill
escalation). No vm/io worker or hardware-frequency write. The 64M positional argument
satisfies existing collector syntax; CPU profile does not launch a memory stressor.
Both launcher and direct collector acquire the same advisory experiment lock under data/;
the launcher passes its lock descriptor to its collector, keeping ownership through export.
Preflight also checks existing collector processes. No experiment retries automatically.

To cancel: press Ctrl+C once. SIGINT/SIGTERM request child shutdown, allow the existing
supervisor to clean up, then independently check recorded owned sessions for survivors.
Collector records process identities atomically; fallback refuses a changed live leader
identity before signalling. Cleanup and export still run after cancellation. Do not kill
processes by broad names. Guest timers cannot recover a frozen host/VirtualBox; SIGKILL,
power loss or failure before a process identity is recorded can prevent complete cleanup.

Local run: data/controlled_cpu/launcher-<UTC>-<random>/, with collector artifacts beneath
collection/<run>/. Includes raw trace.csv, exclusive validated_trace.csv on validation
success, worker/monitor logs, manifests, source hashes, launcher stdout/stderr and metadata,
resources/statistics/class counts and CPU_EXPERIMENT_REPORT.md. Metadata is checkpointed
before collection starts. Only actual worker process records indicate startup; collector
startup alone does not prove a stressor ran. Missing/failed manifests and bad CSVs fail.

Completed evidence is copied without overwriting to the shared results/safe_cpu_launcher-.../
folder; SHA256 verification precedes atomic handoff updates. Prior LATEST_REPORT and
SESSION_STATUS copies are archived. The detailed report is CPU_EXPERIMENT_REPORT.md
inside that unique results directory. On Windows, open:
`C:\Users\shubh\OneDrive\Documents\OS_Project_Shared\LATEST_REPORT.md`.
If export fails, local report records failure, partial shared reports are corrected when
possible, and export-error.txt points to the problem. A disconnected/full shared folder
may leave the previous handoff; use the printed local recovery path. Never assume a
CSV or exported directory alone proves success: read success manifest, exit codes and
validation. Exit statuses preserve collector failures, 124 for timeout, 130/143 for
interrupts, and 1 for preflight/validation/export failures.

One busy worker on four vCPUs often suggests ~25% aggregate utilization; the provisional
70% threshold need not label this cpu_bound. Report observed values and stressor success,
not desired labels, measured energy savings or physical frequency changes.
If the VM becomes unresponsive, do not launch another run. Allow recovery, inspect host
VM activity, and use manual restart only if necessary. After recovery, inspect local
metadata/manifests/process records and handoff before deciding what happened; do not
reset Git, delete evidence, change VM settings or blindly repeat the experiment.

## Timing diagnostic correction — no real experiment executed
Monitor launches first with unbuffered output, flushes its exclusive CSV header,
checks resources and signals readiness. Supervisor waits <=2 s inside the existing
duration+6 total budget, starts the worker, then releases sampling. Capture takes
its baseline after release and has its own <=2 s release wait. Readiness proves
capture setup, not stressor initialization or uninterrupted guest scheduling.
Five-interval CPU limits remain seven-second worker / eleven-second supervisor /
fifteen-second outer guard. No startup extension, weaker resource/timing check or
automatic retry was added. Late success cannot bypass the total deadline.

lifecycle.json atomically records launch/readiness/release, observed exits, deadline
phase and cleanup events with UTC/monotonic timing. monitor.log flushes baseline and
all attempted intervals, including invalid/skipped raw-counter intervals. Diagnostic
storage errors cannot skip cleanup. Manifest sample_validation is attempted after
failed supervision too; sample validity and workload success remain separate. Even
valid rows cannot make a failed workload a successful controlled dataset.

Original manual run launcher-20261015T134651Z-69tl2qzm is failed evidence: worker
reported 11.08 s for requested 7 s, collector exceeded deadline, zero rows, stable
swap occupancy and ample available RAM. No specific original monitor failure is
proved. Current code has 104 passing safe tests; real readiness/loaded VM timing
remain unvalidated. Next proposed separately approved action is one background-only
five-interval readiness observation with no worker and existing 11/15 s limits.

## Standalone background readiness preparation

`prompts/small_task.txt` authorizes launcher preparation, mock/harmless tests,
documentation and development checkpoint/push. It explicitly prohibits performing
the actual observation during preparation. No real observation has been run here.

After separate approval, close Codex/unnecessary guest applications and run exactly:

```bash
/home/vboxuser/Power_Aware_CPU_Governor/scripts/run_background_readiness.sh
```

The wrapper resolves the project root and uses the existing virtualenv. It accepts
no overrides and runs `benchmark.background_launcher`, which fixes the shared
launcher to the collector's `background` profile. Review the limits and type `RUN`
in an interactive terminal; piped confirmation is rejected and Ctrl+C cancels.
The collector command is equivalent to the following, but use the wrapper so
preflight, fallback cleanup, validation and export are included:

```text
timeout --signal=TERM --kill-after=1s 15s bash collect_real_traces.sh 5 64M <unique-local-output>/collection --profile background
```

Five one-second attempted intervals, <=2 s monitor readiness within an eleven-second
supervisor deadline, fifteen-second outer timeout plus one-second kill escalation.
No stressor is created, no `--approved-workload` is passed, and stress-ng is not a
dependency for this background path. The 64M positional argument satisfies collector
syntax and allocates no workload memory. No setter/frequency write is selected.

Shared experiment lock, disk >=512 MiB, RAM >=512 MiB, swap growth <=128 MiB,
three-window swap preflight, resource recheck after confirmation, monitor timing/raw
accounting checks, TERM/KILL/reap and recorded-session fallback cleanup are reused.
Success requires a complete manifest, monitor exit zero, no worker, exact five-row
uncontrolled_background CSV validation, and a consistent lifecycle with ordered
monitor_started → monitor_ready → sampling_released → monitor_exited → cleanup_finished.
The monitor identity record and ready/start files must exist. Missing evidence fails.
No failed run retries automatically. Guest/host pauses can still delay guest deadlines.

Local evidence: `data/background_readiness/launcher-<UTC>-<random>/`, including
`BACKGROUND_READINESS_REPORT.md`, launcher metadata/stdout/stderr, validated_trace.csv
only after validation, and `collection/<run>/` containing lifecycle.json, processes.json,
monitor.ready/start, monitor.log (baseline and every attempted raw interval), worker.log
(empty without a worker), manifest.json, trace.csv, metadata.json and statistics.json
when produced. Failure preserves available evidence and errors without a success claim.

Automatic shared export: `results/safe_background_launcher-<UTC>-<random>/`, SHA256
verified copy, archived previous handoffs, and atomic LATEST_REPORT.md/SESSION_STATUS.md.
If export fails, local report/export-error.txt remains authoritative and the old shared
handoff may remain. This background report never implies a successful CPU workload,
idle ground truth, measured energy or physical frequency control. Review exported
evidence before separately approving any further observation or workload.
