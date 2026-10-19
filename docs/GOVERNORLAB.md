# Governorlab terminal demonstration

Governorlab is a finite terminal presentation of the existing governor. Default
replay is read-only. Explicit `--live` collects 5 to 30 background-only Linux
intervals in-process (default 5), then replays simulated decisions. It never starts
generated workloads or physical frequency control. The standard synthetic replay
lasts about 8.25 seconds of display time; its original synthetic time remains 34
one-second ticks.

**Measured vs simulated.** Live mode measures Linux `/proc/stat` counters (CPU
utilization, I/O wait, context switches, runnable/blocked gauges, actual elapsed
interval). Predicted classes come from provisional rules. Candidate and applied
frequencies are simulated decisions on a model ladder; nothing writes to hardware.
No energy or savings figure in Governorlab is measured.

## Current commands (updated October 19, 2026)

Run from the repository root (`/home/vboxuser/Power_Aware_CPU_Governor` on Ubuntu,
`C:\OS Project` on Windows, where `.venv/bin/python` becomes
`.\.venv\Scripts\python.exe`). Live collection needs Linux; everything else works
on Windows. The [user manual](USER_MANUAL.md) has a step-by-step version.

| Command | What it does |
|---|---|
| `.venv/bin/python -m governorlab` | Verified 34-tick synthetic replay (transitions at ticks 13, 23, 29) |
| `.venv/bin/python -m governorlab --recorded-linux` | Five archived Linux observations, counter-only, no decisions |
| `.venv/bin/python -m governorlab --live` | Collect 5 background intervals (tolerant mode), save a session, replay it |
| `.venv/bin/python -m governorlab --live --samples 20` | Same with 20 intervals (allowed 5 to 30) |
| `.venv/bin/python -m governorlab --live --strict` | Abort on the first timing anomaly instead of discarding it |
| `.venv/bin/python -m governorlab --list-sessions` | List saved sessions in `run/`, newest first, with status and manifest |
| `.venv/bin/python -m governorlab --session latest` | Replay the newest saved session after full revalidation |
| `.venv/bin/python -m governorlab --session run/live-<UTC>-<id>` | Replay a specific saved session folder |
| add `--plain --instant` | ASCII output without delays (works without Rich, and when redirected) |
| add `--visual` | Require the colored Rich dashboard; report why if unavailable |
| add `--speed N` | Presentation ticks per second, 2 to 60 (default 4) |

`--samples` and `--strict` apply only to `--live`. `--live`, `--recorded-linux`,
`--session` and `--list-sessions` are mutually exclusive.

### Tolerant collection (default) and `--strict`

Each one-second interval is checked against unchanged validity thresholds: measured
elapsed time 0.5 to 2 s, and CPU-accounting rate 0.5 to 1.5 times
`os.cpu_count() * SC_CLK_TCK`. In the default tolerant mode an interval that fails,
or whose counters went backwards, is **discarded**: it is never given to the
classifier or policy, it is recorded in `raw_events.jsonl` and `metadata.json`
(attempt number, reason, elapsed time, ratio), and sampling continues from that
interval's end snapshot. Collection stops when N valid samples exist, or fails
when attempts reach N + max(3, ceil(N/2)) (8 attempts for 5 samples), or at the
deadline of 2 s per allowed attempt plus 2 s (18 s for 5 samples). A failed
collection keeps its evidence, is never replayed and is never retried automatically.

A session with any discard is marked `timing_quality: degraded`. Its replay prints
`TIMING QUALITY DEGRADED: N intervals discarded because of VM timing anomalies`
with counts per reason, and the final summary lists every discarded attempt.
Limitation: kept samples in a degraded session can be non-adjacent in time, so K=3
persistence may span a real gap.

`--strict` keeps the earlier behaviour: exactly N attempts, and the first timing
anomaly aborts (deadline 2 s x N + 2 s, 12 s for 5 samples).

Recorded VM result (user report, October 19, 2026): one tolerant run discarded one
interval (elapsed 2.32 s), kept 5 of 5 samples and showed the degraded banner; a
strict run also passed; the replay revalidated against the backend.

### Saved sessions (shared with the dashboard)

Every successful live run creates `run/live-<UTC>-<random>/` with `capture.csv`
(raw previous/current counters plus derived rates and resources), `raw_events.jsonl`
(baseline, every attempted interval, every discard), `metadata.json` (counts,
attempts, discards, timing quality, timings, resources, source hashes, decision
summary), `decisions.json` (one frame per kept sample) and `session-sha256.json`
(hash manifest written by `collect_live` itself). The dashboard's **Collect Live
Data** writes exactly the same format under `run/daybreak-*/live-*/`, so both
interfaces list and replay each other's sessions (`presentation/sessions.py`).
Loading a session re-checks the manifest, the raw counters, the sample count
(5 to 30, requested equal to kept), the timing disclosure, and re-runs the classifier
and policy to compare every saved decision. Older sessions without a manifest or
timing fields still load; they are labelled legacy and treated as clean.

On the VirtualBox VM the sleep timer overshoots by about 10 %, so a five-sample run
takes roughly 5.5 to 6 s plus startup; isolated intervals over 2 s are discarded and
disclosed rather than ending the run.

## Historical record (October 15, 2026, five-sample implementation)

The two classroom commands used at Review 1 were:

```bash
.venv/bin/python -m governorlab --visual
.venv/bin/python -m governorlab --live --visual
```

At that time `--live` collected exactly five attempts with a 12-second deadline and
aborted on the first timing anomaly (today's `--strict`). The live flow showed
collection progress, then automatically opened the same Rich dashboard on the fresh
measurements and predicted classes, candidates, applied simulated levels and K=3
persistence. Values and transition counts vary with ordinary VM activity.

Professor explanation: “The first scenario makes hysteresis easy to see. The second
reads actual aggregate Linux CPU counters and derives utilization, I/O wait and
context-switch rates. Our existing provisional classifier predicts a class, and
our existing policy requires three consecutive predictions before applying a
simulated frequency. These are simulated decisions, not physical frequency changes,
energy savings or workload completion-time measurements.”

`monitor.capture --output` itself takes a **file path**, not a directory: the previous
`run/live_check_20261015` is an extensionless CSV and is preserved unchanged.
Collection reuses `monitor.reader.sample()` and the existing capture resource
guards/validator with a SIGALRM deadline and no subprocesses. Missing/nonfinite
classifier features fail explicitly. Read-only CPU frequency may be unavailable in
this VM; no simulated number is substituted in the measured CSV.

`presentation.adapter.process_live_observations()` calls existing `classify()`,
`Policy.decide()` with K=3, and an explicitly constructed `SimulatedSetter` using
the existing model ladder. It preserves candidate versus applied state and reports
zero transitions whenever that is the actual result. The classifier thresholds and
ladder remain provisional modelling choices. Default imports/replay never initiate
live sampling. Explicit visual readiness is checked before collection. Ctrl+C stops
collection/playback and restores terminal state. The deadline requires Linux's main
thread and refuses an existing active interval timer.

Fresh native Ubuntu verification, October 15: **181 tests passed in 22.19 seconds**,
including 22 new live tests, conservative thread limits and a 90-second suite timeout.
Import safety, archived replay and counter-only view remain covered. AST/whitespace
checks passed; all 30 archived evidence files match HEAD. Independent review found
one errno diagnostic-path issue, reproduced with a failing test and corrected; the
reviewer then found no further actionable issues (66 targeted tests passed).

One authorized real 80x24 PTY smoke test completed in **6.14 seconds**, status 0:
`run/live-20261015T184415Z-n0nkxttw/`. Five genuine intervals ranged 1.0004-1.0115 s
(mean 1.0034 s), CPU mean 9.1414%, I/O wait mean 0.05435%, context switches mean
3348.49/s. Predictions: mixed, idle, idle, idle, mixed. One simulated transition at
tick 4: 5.100 -> 3.800 GHz after the third idle prediction. No observed frequency
was available. Available RAM before/after 2,277,536/2,281,980 KiB; swap stayed
502,560 KiB; recent memory-pressure averages stayed zero. Raw events/CSV continuity,
source hashes, independent classifier/policy reproduction, Rich summary, cursor
restoration and process-group exit passed. No stress, frequency writes, installation
or VM changes. This is background readiness, not loaded stability or classifier accuracy.
PTY output verification does not replace the user's physical terminal rehearsal.

Shared handoff: `/media/sf_OS_Project_Shared/reports/GOVERNORLAB_LIVE_DEMO.md`, with
logs and completed live artifacts referenced there. Development checkpoint/push and
exact-target integration assessment are recorded in that report. Main is unchanged;
any integration requires separate approval. Earlier verification entries below are
historical and describe the original replay-only implementation.

## Launch from the repository root

Windows PowerShell, using the existing Windows-created virtual environment:

```powershell
Set-Location 'C:\OS Project'
.\.venv\Scripts\python.exe -m governorlab
```

Ubuntu, after safely synchronizing the VM checkout and using its own Linux environment:

```bash
cd /home/vboxuser/Power_Aware_CPU_Governor
.venv/bin/python -m governorlab
```

Rich is optional. To enable the colored presentation, install only the small terminal
requirements file in each environment separately, when dependency installation is
authorized. It is already installed in the Windows development environment for this task:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-terminal.txt
```

```bash
.venv/bin/python -m pip install -r requirements-terminal.txt
```

Never copy a virtual environment between Windows and Ubuntu. Core replay and plain
output need only Python's standard library and existing project modules; matplotlib,
Streamlit and Plotly are not imported. No network connection is needed to run it.

Useful options, on either platform with that platform's Python executable:

```text
python -m governorlab --speed 2
python -m governorlab --visual
python -m governorlab --plain --instant
python -m governorlab --recorded-linux
python -m governorlab --recorded-linux --plain --instant
python -m governorlab --help
```

`--speed` accepts 2-60 presentation ticks/second; default 4. `--instant` removes
delays. Playback uses monotonic deadlines and has no restart or polling loop.
Ctrl+C restores the terminal and returns 130 with a partial summary, never a
completion claim. Pause/step controls are deliberately omitted for reliability.

Default interactive output uses Rich, with a compact dashboard at normal 80x24
Windows console sizes and the expanded layout when space permits. Limited encodings
use an ASCII graph/box style without disabling the visual dashboard. Missing Rich,
redirected output, genuinely unsupported cursor updates or insufficient dimensions
select plain output with an explicit explanation. Windows console capabilities are
detected by Rich; an inherited POSIX `TERM=dumb`/`unknown` is corrected only in the
Console's private environment copy, never in the process or global environment.
Ubuntu dumb terminals remain unsupported for visual updates.

`--visual` (alias `--rich`) requires interactive Rich rendering and enables dashboard
colors, overriding `NO_COLOR` for that Console only. It returns 2 with a clear reason
if unavailable, without dumping plain replay rows. Default mode honors `NO_COLOR` and
explains monochrome rendering. `--plain` and `--visual` are mutually exclusive.
`--plain` always disables terminal control sequences. The last Rich frame and final
summary remain visible after completion. Plain mode prints every sample and transition.
Renderer exceptions are reported as errors, never silently rerun in plain mode.

For a direct human-visible check in a normal Windows PowerShell window:

```powershell
Set-Location 'C:\OS Project'
.\.venv\Scripts\python.exe -m governorlab --visual
```

Use at least 80 columns and 24 rows. The actual Windows PTY smoke test completed
default and explicit visual playback with cursor redraws; explicit visual emitted
RGB color sequences and restored the cursor. Codex can inspect that output but cannot
observe the user's physical terminal window. Screen appearance is therefore not
claimed as visually verified. The previous static/captured-frame checks do not
substitute for this human-visible check or Ubuntu verification.

## What to explain to faculty (two-minute demonstration)

1. Start Governorlab. Identify **SYNTHETIC REPLAY**, seed 11, K=3, 34 samples.
   The scenario is CPU 10 ticks, I/O burst 10, idle 6, mixed 8, loaded from archive
   metadata. Violet is utilization/candidate; blue is the applied simulated level.
2. At ticks 11 and 12, the predicted class changes to I/O-bound. The candidate is
   4.233333 GHz while the applied simulated level remains 5.1 GHz. Amber persistence
   advances 1/3 then 2/3. At tick 13 the third consecutive sample permits the change.
   High utilization alone does not identify this constructed I/O burst.
3. The progressive graph displays actual archived utilization. At ticks 23 and 29,
   further confirmed simulated transitions move to 3.8 GHz and then 4.666667 GHz.
   There are exactly three applied changes; initial selection is not counted.
4. Read the final distribution: CPU-bound 10, I/O-bound 10, idle 6, mixed 8.
   Explain that classification and hysteresis are real implemented logic running on
   invented inputs; displayed frequencies are simulated, not physical measurements.
5. Run `--recorded-linux`. These are five historical Linux kernel observations,
   not a live view and not idle ground truth. Show utilization, I/O wait, context
   switches and measured elapsed intervals. No candidate, simulated frequency or
   persistence state is assigned to these observations.

Architecture: archived configuration/inputs -> existing synthetic source -> existing
`governor.run`, `Policy`, classifier and explicit `SimulatedSetter` -> consistency
check against archived outputs -> portable frames -> terminal rendering.

## Shared presentation adapter and provenance

`presentation.adapter.load_replay()` returns a `Dataset` with immutable frame/event
records, source metadata and a computed summary. Features/metadata are fresh dictionaries
per load: consumers should treat them as read-only or copy before changing them.
`load_observations()` provides a separate dataset with unavailable decision fields set
to `None`. These APIs contain no Rich rendering and are ready for reuse by Daybreak.

Each frame retains its 1-based tick, original timestamp and CSV path/line identity.
Replay frequency targets are integer kHz; UI rounds only the GHz display. No thresholds
or mappings are copied into the presentation layer. Candidate/pending/streak/stable
state is **derived** by inspecting the actual Policy instance. Optional private fields
that become unavailable are labelled unavailable; changed recorded outputs fail replay.

The default synthetic source is
`evidence/review1/synthetic_policy_comparison_20261015/ours.csv`, produced by
`4055aa2c0700f829b565f01442f392806f0dea73`, seed 11, K=3. All available input features,
classes, requested/applied/pre-tick frequencies and modelled powers are checked against
fresh deterministic backend reconstruction before playback begins. No input dictionary
is shared across replay invocations. Current and historical CSV schemas may carry extra
fields; required fields, duplicate headers, row shape and finite numbers are checked.

The recorded Linux source is
`evidence/review1/background_readiness_20261015/validated_trace.csv`, producing source
`18b87efa6ffdcc4e7f4ed58936c824876a42d3fc`. It is verified through the existing
raw-counter validator with the archived four-vCPU/100-Hz accounting assumption.
The original timestamps and actual elapsed intervals remain unchanged.

All archive SHA256 entries are checked before use. CSV/PNG files must match exact
bytes. Covered `.md`, `.json` and `.log` files may match after CRLF-to-LF normalization
only, accommodating the Windows checkout's existing `core.autocrlf=true`. This does
not authenticate the original experiment independently. No archive/configuration is
rewritten, and no Git executable is needed at runtime.

Scientific limits: rules are provisional; this is an open-loop replay. It establishes
neither physical CPU actuation, measured power/energy savings, workload speedup nor
preserved completion time. The separate background capture establishes short-run
monitoring readiness, not loaded VM stability or classification accuracy.

## Verification and Ubuntu integration checklist

Windows verification uses the existing portable tests plus
`tests/test_presentation_adapter.py` and `tests/test_governorlab.py`. Coverage includes
archive/schema loading, deterministic backend matching, candidate/applied boundaries,
transition counts, unavailable fields, source separation, import safety, fallback,
finite playback and interruption. Test artifacts belong in a new temporary directory;
disable pytest caching and bytecode where workspace cleanliness is required.

Original MVP Windows verification: **72 passed**, including 30 new presentation/UI tests.
The full-suite command was attempted and stops at four pre-existing Windows
collection errors (`No module named fcntl`) in `test_background_launcher.py`,
`test_collection.py`, `test_cpu_timing.py` and `test_safe_launcher.py`. No Linux
result is inferred from this. Windows-compatible command:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/ -q -p no:cacheprovider --ignore=tests/test_background_launcher.py --ignore=tests/test_collection.py --ignore=tests/test_cpu_timing.py --ignore=tests/test_safe_launcher.py
```

In the restricted Codex environment, use a fresh `--basetemp` under a permitted
scratch directory if the default temporary directory cannot create test fixtures.
Both plain modes completed; a progressive Windows PTY smoke run completed all 34
ticks. Rich rendering/startup is additionally exercised with a controlled UTF-8
terminal stream and large/small dimensions. Physical terminal layout and Ctrl+C on
the friend's Ubuntu VM remain unverified. Static checking of the new modules/tests,
dependency consistency and Git whitespace checks passed. The read-only code review
identified a Unicode-path/ASCII-output issue; its failing regression now passes.

Renderer repair verification: **86 Windows-compatible tests passed**, including 14
additional selection/layout/diagnostic/lifecycle cases. Regressions first reproduced
default plain selection at 80x24/25 with `TERM=dumb`, missing fallback explanations,
missing explicit visual flags and renderer-error handling. Rich 14.3.4 was already
installed and compatible; no dependencies were added or upgraded during the repair.
The earlier 30-row expanded frame and raw TERM/Unicode gate caused intentional but
silent fallback. `NO_COLOR` in the tool host separately explained missing color.
Backend consistency, three transition events and archive integrity tests still pass.
Read-only review found no actionable renderer issues. Linux-only tests remain pending.

Before using the friend's Ubuntu VM:

- Inspect status and fetch/query both remote branches. If stale, obtain synchronization
  approval; do not blindly pull or discard local work.
- Use its native Linux virtual environment. Plain mode needs no Rich installation.
- Run the existing full safe unit-test suite and the two new test files. Linux-specific
  collector/launcher tests remain Ubuntu-only because they import `fcntl`.
- Run `python -m governorlab --plain --instant` and the recorded-Linux equivalent.
- Check Rich layout at actual terminal dimensions and Ctrl+C cursor restoration.
- Confirm archive hashes/CSV bytes and the three transition ticks, without running
  collectors, launchers, stress-ng or any frequency writes.

No Ubuntu execution, shared-folder writes or Linux integration is claimed from Windows.
Main integration is deferred until these checks and separate exact-target approval.

## Local recovery handoff

This guide is the local handoff because the friend's shared folder is inaccessible.
The authorized Governorlab task adds only presentation code, targeted tests, optional
terminal requirements and documentation. Existing backend and archived evidence are
unchanged. The exact development checkpoint and remote verification are reported in
the task's final chat handoff; no self-referential commit hash is embedded here.
Next: test/rehearse the terminal demonstration, then separately authorize Daybreak
using the shared adapter. No Daybreak implementation is included in this milestone.
