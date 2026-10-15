# Daybreak dashboard

Daybreak is a local Streamlit presentation of the verified Governorlab backend and
its archived evidence. Startup and ordinary reruns do not sample. An explicit Linux
action collects five background intervals in an isolated child; no workloads or
physical CPUFreq control are used.

## Install and launch

From `C:\OS Project` in Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe -m streamlit run daybreak/app.py
```

From the friend's Ubuntu repository, after safe Git synchronization:

```bash
cd /home/vboxuser/Power_Aware_CPU_Governor
.venv/bin/python -m pip install -r requirements.txt -r requirements-dashboard.txt
.venv/bin/python -m streamlit run daybreak/app.py
```

Open `http://127.0.0.1:8501` in the same machine's browser. Stop the server with
Ctrl+C. Use a native Linux virtual environment, not a copied Windows environment.
Streamlit 1.66.0 and Plotly 6.9.0 are pinned separately from backend requirements.
Installation needs network access; normal dashboard operation uses local code,
archives and bundled assets. Telemetry is disabled, file watching is disabled and
the default listener is loopback only. There are no remote datasets, fonts or APIs.

## Classroom walkthrough

1. **The Replay:** automatically plays the selected verified session. Use
   Play/Pause/Resume, Restart, previous/next, Reset and 0.5×/1×/2×/4× speed.
   Pause to enable the seek slider; previous/next and Reset also pause for inspection.
   Restart plays from tick 1. The same timeline/inspector/summary serves the synthetic
   34-tick scenario and each validated saved five-observation Linux session.
   The first-transition button selects the first verified event. Three aligned
   lanes show progressive utilization, predicted workload and candidate versus
   applied simulated frequency. At T11 the I/O prediction is waiting; at T13 K=3
   accepts the change. Full-run transitions are T13, T23 and T29. The cursor is
   retained when switching views. Leaving Replay pauses it; returning resumes at
   the current tick (or restarts a completed session). Selection changes restart
   playback with the selected source's actual sample count. At completion, playback
   stops and displays its summary; zero simulated transitions is a valid result.
2. **The Evidence:** inspect five historical Linux observations, their measured
   elapsed intervals, raw-derived features and provenance. Frequency remains
   unavailable; no simulated decisions are inserted into this measured capture.
3. **The Comparison:** inspect performance, powersave, ondemand, conservative and
   ours on identical synthetic inputs. Filter the frequency chart independently;
   the summary table retains all five policies. Energy is an uncalibrated model
   estimate, not electrical measurement or proof of savings at equal performance.
4. **Lab Notes:** read the actual classifier source and provisional thresholds,
   K=3 methodology, model assumptions and VirtualBox limitations.

The cream/violet Daybreak interface follows the approved design. Charts and tables
use source values, not numbers from the design preview. Native Streamlit controls
provide keyboard interaction; Plotly tooltips permit inspection of individual points.

## Source and integrity

`presentation.adapter.load_replay()` reconstructs the existing classifier and
Policy with archived seed 11, K=3 and frequency ladder before exposing candidate,
streak and applied fields. `load_observations()` validates the separate Linux
archive. `daybreak.data.load_comparison()` verifies every archived policy row and
recomputes all stored summaries with the existing backend. Missing or inconsistent
data produces a visible error, never replacement measurements.

Inputs are `evidence/review1/synthetic_policy_comparison_20261015/` and
`evidence/review1/background_readiness_20261015/`. Each view exposes original sample
identity/source commit and limitations. Existing archive verification accepts only
documented CRLF checkout conversion in text; CSV/PNG integrity stays byte-exact.
No evidence or attributes rules are modified by Daybreak.

Synthetic inputs cannot tune thresholds or validate classifier accuracy. Background
observations establish bounded monitoring readiness, not loaded VM stability.
The guest exposes no CPUFreq interface. Physical frequency, electrical energy,
throughput and completion-time preservation are not demonstrated.

## Terminal demonstrations and explicit live collection

Both Ubuntu terminal commands remain available:

```bash
.venv/bin/python -m governorlab --visual
.venv/bin/python -m governorlab --live --visual
```

See [Governorlab guide](GOVERNORLAB.md) for their unchanged boundaries.

On Linux, **Collect Live Data** explicitly starts one single-purpose child per user
session: `python -m daybreak.worker --job <unique ignored run/daybreak-* folder>`.
The child calls the existing `governorlab.live.collect_live()` on its main thread;
its Linux SIGALRM/setitimer 12-second deadline is preserved. The parent imposes a
15-second watchdog and a six-second UI heartbeat lease. Cancel, leaving Replay,
disconnect or server exit interrupts the owned child, escalates if needed and reaps
it. The child starts no descendants. There is no automatic retry. Failed/partial
artifacts remain available for diagnosis and are never substituted or replayed.
Each browser user session can own only one active collection; other users have
independent state. Deploy this local demonstration only on a trusted machine.

Progress shows actual completed intervals (five attempts; invalid attempts are not
replaced). After success the capture loads into the same player and automatically
plays all five samples. **Session source** separately lists saved terminal
`run/live-*` and dashboard `run/daybreak-*/live-*` captures. These remain labelled
saved observations, not currently live data. Windows disables collection with an
explanation; verified synthetic, saved replay and all other views remain functional.
To replay a Linux capture on Windows, copy its complete folder into `run/live-*`;
do not edit its files or copy a Linux virtual environment.

Saved loading repeats raw-counter validation, original five-row/source checks and
faithful classifier/Policy execution, comparing every saved decision. New dashboard
captures also hash CSV, metadata, decisions and raw events. Legacy terminal captures
have no hash manifest: the UI says so and revalidates counters and decisions. Hashes
detect changes relative to a capture, not authenticated origin. Original source paths
are preserved in metadata while current sample identities point at the copied CSV.
No capture's absent frequency measurement is replaced by a simulated frequency.

The timed Streamlit fragment runs only while playing/collecting. Each callback does
bounded work and advances at most one sample, with no app-side sleep/animation loop.
Slow rendering may stretch presentation time rather than skip observations; speed
is presentation cadence, never a claim about measured sampling intervals. During
playback the clock owns the cursor; pause enables seeking without browser slider
echoes interrupting animation. All chart lanes/inspector/markers use one frame.

## Verification and Ubuntu handoff

Unified-player Windows verification: **127 portable suite tests plus six portable
live-adapter tests passed (133 total)**, including 24 new upgrade tests and the
17 original dashboard cases. Saved-source switching from synthetic tick34 to a
five-sample capture also passed. Existing 16 Linux-only live lifecycle
tests cannot execute on Windows because it lacks /proc and SIGALRM/setitimer.
Four other existing Linux-only modules require fcntl at collection. They remain
Ubuntu checks; no production or test behavior was altered to hide these boundaries.
The real Streamlit server and four views were exercised in a browser at desktop
and 390-pixel widths, including 1×/4× automatic completion, pause/resume, cursor
persistence and previous/next/reset. Browser
checks reported no external HTTP assets and no console errors. This does not verify
Ubuntu deployment or a human classroom rehearsal.

Windows restricted execution blocked asyncio's loopback socketpair initialization;
the bounded server/AppTest checks succeeded with local socket access. No application
event-loop workaround was added.

On Ubuntu, first inspect cleanliness, branches, stashes/worktrees and incomplete
operations; fetch without pruning and independently query remote main/development.
If dirty, stale/diverged or unpublished work exists, stop and report it. Do not
reset, stash, discard, rebase or overwrite refs. Otherwise fast-forward development
to its independently verified remote head, then:

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-terminal.txt -r requirements-dashboard.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m streamlit run daybreak/app.py
```

Check all four pages in the VM browser, ticks 1/11/13/23/29/34, automatic completion,
pause/resume, paused seek, Restart, speed, policy filtering and narrow layout.
Explicitly collect one five-interval background session: verify progress, one child,
five actual rows, source labels, automatic replay and an honest transition count.
Replay the saved capture independently; verify leaving/returning retains source/speed.
Check cancellation, child timeout/failure and browser disconnect/server shutdown:
no orphan child or retry, partial artifacts retained, no failed capture replay.
Perform these Linux lifecycle checks under normal VM resource conditions, with no
generated load, sudo or hardware changes. Rehearse both terminal commands
only under their documented Linux safety conditions; web startup must not collect
anything. No main merge is authorized by this dashboard milestone.

## Milestone and recovery handoff

**DEFER main integration** pending Ubuntu full-suite, dashboard visual/startup and
shutdown verification, followed by separate approval of the exact development head.
The Daybreak change is additive and main is its ancestor, so it is fast-forward
eligible while refs retain that relationship. No known dashboard defect blocks
Ubuntu validation. Historical branches and unique commits are preserved.

All 26 archive manifest entries were independently checked against Git blobs; 14
working text files differ only by documented Windows checkout conversion. CSV/PNG
bytes and evidence Git content are unchanged. Static analysis, dependency checks
and whitespace checks pass. The owned preview server was stopped after browser QA.

This guide is the Windows local recovery handoff: neither the friend's shared
mount nor its Windows mapping is available here. Supporting verification is recorded
in PROJECT_STATE.md, DEVELOPMENT_LOG.md and REVIEW1_STATUS.md. Identify the checkpoint
with `git log -1 development`; independently query remote refs before synchronization.
No force-push or history rewrite is part of this work.
