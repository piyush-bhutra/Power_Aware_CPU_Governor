# Safe Linux monitoring and controlled collection

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
