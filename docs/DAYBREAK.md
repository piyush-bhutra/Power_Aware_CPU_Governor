# Daybreak dashboard

Daybreak is a local Streamlit presentation of the verified Governorlab backend and
its archived evidence. It does not start sampling, workloads or CPUFreq control.

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

1. **The Replay:** use the slider, previous/next and Reset to inspect all 34 ticks.
   The first-transition button selects the first verified event. Three aligned
   lanes show progressive utilization, predicted workload and candidate versus
   applied simulated frequency. At T11 the I/O prediction is waiting; at T13 K=3
   accepts the change. Full-run transitions are T13, T23 and T29. The cursor is
   retained when switching views. Playback is manual; automatic play is not added.
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

## Terminal demonstrations and optional live integration

Both Ubuntu terminal commands remain available:

```bash
.venv/bin/python -m governorlab --visual
.venv/bin/python -m governorlab --live --visual
```

See [Governorlab guide](GOVERNORLAB.md) for their boundaries. The existing live API
uses Linux SIGALRM/setitimer deadlines and writes capture artifacts. Streamlit
request threads cannot safely own that signal lifecycle, so web live capture is
deferred. It must not be implemented by dropping the timeout or silently spawning
collectors. The offline dashboard has no live dependency.

## Verification and Ubuntu handoff

Windows: 103 portable suite tests and six portable live-adapter tests passed,
including 17 new Daybreak tests. A broader run passed 109 and failed 16 existing
Linux-only live lifecycle tests because Windows lacks /proc and SIGALRM/setitimer.
Four other existing Linux-only modules require fcntl at collection. They remain
Ubuntu checks; no production or test behavior was altered to hide these boundaries.
The real Streamlit server and four views were exercised in a browser at desktop
and 390-pixel widths, including cursor persistence and previous/next/reset. Browser
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

Check all four pages in the VM browser, ticks 1/11/13/23/29/34, policy filtering,
provenance, narrow layout and Ctrl+C server shutdown. Rehearse both terminal commands
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
