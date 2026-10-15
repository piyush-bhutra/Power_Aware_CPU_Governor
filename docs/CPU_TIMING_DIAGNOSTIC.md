# CPU timing diagnostic — October 15, 2026

## Outcome and scope

The first manual CPU attempt failed and produced no usable dataset. Two reproducible
supervision defects are corrected: worker startup preceded monitor readiness, and
failure discarded lifecycle/exit evidence and bypassed sample validation. These are
verified code defects, **not a proven explanation for the original missing samples**.
No real collector, live capture, stress-ng or artificial workload was run during this
investigation. No hardware-frequency, kernel, VM, package or system changes occurred.

Authorization: shared `prompts/CPU_Timing_Diagnostics.txt`, explicitly invoked by the
user. Changes and checkpoint/push are restricted to development. Main and historical
branches are preserved. The user requested autonomous completion of this prompt.

## Original evidence and timeline

Run: `data/controlled_cpu/launcher-20261015T134651Z-69tl2qzm/`.
Collector artifacts are beneath `collection/20261015T134713Z-79zl25jm/`.
All four collector metadata source hashes match committed sources at `81dd446`.
The original files were read, hashed and retained without modification.

| UTC | Verified event / evidence |
|---|---|
| 13:46:51.888 | Launcher start recorded in launcher-metadata.json. |
| Before collector | Three requested 250 ms swap windows actually lasted 0.546233, 0.639973 and 0.254342 s; no swap counter movement. Confirmation/preflight also occur in this phase; the whole launcher-to-collector gap is not Python startup time. |
| 13:47:13.074556 | Collector metadata start timestamp; original total supervisor limit 11 s. |
| Approximately 13:47:13.075–.078 | Source launches worker PID/PGID/session 32758 first, monitor 32759 second. processes.json has both at start_ticks 1086352; this does not give sub-tick ordering. File metadata corroborates near-simultaneous startup. |
| 13:47:13.126458 | trace.csv filesystem birth time: monitor reached output creation roughly 52 ms after collector metadata timestamp. |
| 13:47:24.211615 | trace.csv last modification, size 556 bytes, header only, zero observations. The header was buffered by the old logger until flush/close; this time is not a sampling timestamp. |
| 13:47:24.214615 | worker.log last modification. stress-ng reports one int64 CPU worker, requested timeout 7 s, successful completion in 11.08 s, 41,337 bogo operations, user 10.69 s, system 0.38 s. These are worker-reported quantities, not independently calibrated host timings. |
| 13:47:24.418633 | Collector failure manifest: external collector deadline exceeded; no process exit statuses or samples validated. Approximately 11.344 s from metadata start includes launch, polling and cleanup. |
| 13:47:24.664544 | Launcher end, exit 1, validation not performed. Fallback cleanup records no remaining running processes in recorded groups. |

The source raises the timeout before returning process results, then attempts TERM,
KILL and bounded reap for both groups. The launcher independently checks recorded
groups. This verifies the cleanup path and reported final absence of running groups;
it does not recover which group was still running when the timeout fired. There is
no original lifecycle log, ready signal, interval log or captured monitor return code.
The worker's successful log message alone does not prove the parent observed exit 0.

## Findings and uncertainty

1. **No validated observations.** trace.csv has only its header. Existing per-row
   flush means accepted/written rows should have been visible. Missing rows cannot
   be explained simply by buffered stdout. Invalid/reset/zero-total intervals are
   silently skipped by the old sampler; no evidence proves whether that happened.
2. **Monitor state is unresolved.** Empty monitor.log is expected while old capture
   is sampling, because it prints statistics only after validation. It does not
   prove a crash, stall or healthy sampling. Supervisor cleanup can terminate a
   live monitor, but original exit codes are absent. Do not assert a specific signal.
3. **Import delay is not supported as the dominant cause.** The original CSV birth
   time places execution past imports/output setup about 52 ms after metadata
   start. One bounded, import-only `python -X importtime -c 'import monitor.capture'`
   measured cumulative monitor.capture imports at 13,378 microseconds. This excludes
   interpreter startup and does not reproduce loaded scheduling; it is no substitute
   for the original missing readiness timeline. No pandas/numpy imports are needed
   by this capture module.
4. **Timing concern is real; clock distortion is unproved.** Two requested 250 ms
   waits exceeded twice their requested time, and worker-reported elapsed time was
   1.58 times its requested seven-second timeout. These demonstrate deadline/sleep
   overruns in recorded guest observations. Host contention, guest descheduling,
   stressor timeout responsiveness and VM clock behaviour remain hypotheses. There
   is no independent host clock or usable raw-jiffy trace to isolate them. KVM versus
   historical legacy-paravirtualization disagreement remains unresolved.
5. **Memory exhaustion is unsupported.** Collector available memory changed from
   2,339,372 to 2,335,976 KiB; swap used stayed 424,224 KiB. Launcher swap went from
   424,232 to 424,224 KiB. These snapshots do not exclude a transient between polls,
   but provide no evidence of material swap growth or exhausted memory.
6. **Nominal budgets were ordered but startup was unaccounted for.** Five one-second
   attempts, seven-second worker timeout, eleven-second supervisor deadline and
   fifteen-second outer deadline nominally leave margins. Worker-first launch lets
   monitor startup consume workload coverage, and guest scheduling can exhaust
   those margins. Increasing every timeout would conceal this defect and expose the
   VM to longer load; no timeout or resource guard was relaxed.

## Corrections

- Collector launches Python with `-u` and starts the monitor first. Capture checks
  resources and opens/flushed its exclusive CSV header, then signals monitor.ready.
  Supervisor requires readiness within two seconds of supervision start, inside
  the unchanged total budget. No worker launches on absent/failed readiness.
- After readiness, supervisor launches/records the worker and creates monitor.start.
  Capture waits at most two seconds for release, then takes its sampling baseline.
  Baseline follows process launch, not verified stressor initialization: readiness
  does not prove full stressor activity or classifier ground truth.
- Atomic lifecycle.json records UTC and monotonic elapsed events for launch, ready,
  release, observed exits, failure/deadline and cleanup; it retains statuses before
  and after cleanup. Startup, sampling and workload-wait deadline phases differ.
  Exit observation timestamps are polling times, not exact kernel exit times.
- Capture flushes diagnostic output. Optional sampler observer records baseline and
  every attempted interval with raw snapshots, elapsed time and validity, including
  skipped intervals. CSV header and every written row are explicitly flushed.
- Total deadline is checked before accepting success, preventing a delayed final
  poll from accepting an overrun. Existing worker timeout is unchanged. Sampling
  and workload phase labels identify what remains unfinished at the total deadline;
  they do not add separate extended budgets.
- Supervisor failures still attempt independent CSV validation after cleanup and
  retain success/error/statistics in manifest.sample_validation. Valid samples do
  not change failed workload status into success or qualify it as a CPU dataset.
- Diagnostic storage failure cannot skip cleanup of either process group. A test
  caught this intermediate regression and the corrected writer defers storage
  failure until after cleanup on otherwise successful runs. Original active
  failures remain authoritative. Persistent storage/guest failure can still prevent
  durable evidence; the outer launcher fallback remains necessary.

The two-second readiness cap uses the existing four-second nominal difference
between worker and supervisor budgets; it does not increase total runtime. It is a
fail-closed engineering limit, not a calibrated VM guarantee. Cleanup/reap can take
additional bounded time; GNU outer timeout remains the independent guard. Guest/host
pause or SIGKILL can defeat timely execution of in-guest cleanup.

## Verification and review

Existing baseline: 93 passed in 10.84 s. Initial new regressions: five expected
failures (missing readiness interface/failure-time validation). Additional tests
failed for silent skipped intervals and buffered header, then passed after changes.
A diagnostic-write failure test reproduced skipped cleanup, then passed after fix.
Final suite output and duration are in logs/full-tests.log (104 passing tests).
Independent reviewer ran the prior 103-test suite: 103 passed in 8.19 s, and found
no remaining code/safety issues after cleanup correction. The final added test
confirms valid samples cannot promote a failed worker/supervisor run to success.
Shell syntax and git whitespace checks pass. No installation or optional lint tool
was needed. Tests use simulated clocks/processes, fixture counters and existing
harmless short-lived child processes, never stress-ng or real counter sampling.

## Milestone merge readiness and next experiment

**READY for implementation integration**, after checkpoint/push verification. Reviewed
accumulated main-to-development milestones: persistent workflow, bounded synthetic
demo with simulated setter, raw-counter/accounting repairs, conservative collector,
standalone launcher, swap preflight and timing corrections. Existing synthetic and
five-row background evidence remain usable with their original limits. Known optional
ramp-down/clamping issues predate this scope; no new claim relies on those features.
This is an implementation readiness recommendation, not permission to merge main.

**DEFER experimental readiness and any claim of a validated CPU dataset.** Another
loaded experiment is not justified as the immediate next step while no-load behaviour
of the new handshake/diagnostics has not been observed. Do not automatically rerun
the failed workload. No fresh workload approval is implied by this investigation.

One specific next action: separately approve one background-only five-interval
collector observation through the new readiness path, with no worker, unchanged
eleven-second supervisor/fifteen-second outer limits, existing RAM/swap/timing guards,
and preserved lifecycle/raw diagnostic logs. This was not executed. If it passes,
review it before considering a separately approved one-int64-worker retry. Any later
CPU retry should retain five intervals, seven-second worker, eleven-second supervisor,
fifteen-second outer timeout, no vm/io worker, no frequency control and RUN confirmation.
Do not increase workers, intervals or deadlines to obtain a desired classifier label.

Measured Linux counters, simulated frequency, modelled energy and worker-reported
completion time are distinct. This failed trace supports no classification accuracy,
performance preservation, measured energy savings or actual hardware control claim.

Checkpoint and verified push hash are recorded in the exported report appendix and
LATEST_REPORT.md/SESSION_STATUS.md to avoid a self-referential tracked commit hash.
Supporting files: evidence-summary.json, baseline-tests.log, regression-red.log,
additional-red.log, io-red.log, targeted-tests.log, full-tests.log, import-time.log,
review.txt and original-failed-run/ (original logs, CSV, process and resource metadata).
