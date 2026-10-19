# Daybreak dashboard

## UI refresh on ui-polish (October 19, 2026)

Navigation, session selection, sampling controls and playback controls now live in
the sidebar. The main area switches between a single collection-progress panel
with Cancel and a results view with a plain-language **What happened** summary and
a fixed-height chart. No scrolling script is required. On narrow screens, use the
native sidebar toggle; vertical scrolling can still be necessary.

The results summary describes the full verified session, while the cursor and
status describe the selected sample. **How to read this**, session details, source
tables, provenance and discarded attempts are collapsible. The degraded-timing
warning stays above the chart. Saved sessions show their recorded date/time, sample
count and timing quality; missing metadata is disclosed rather than guessed.
**Download replay table (CSV)** exports the displayed derived features and simulated
decisions, not a replacement for the original raw capture or its manifest.

Only collection progress polls at 0.5-second intervals. Playback redraws the chart
at its selected cadence (0.5× through 4×); static explanation and detail panels are
outside that fragment. A 40-entry presentation cache reuses chart construction for
identical verified data and sample positions. Source selection still runs the
existing loaders and integrity checks. Shared style tokens, native theme colours,
short transitions and reduced-motion support keep the presentation consistent.

Fresh Windows verification: **249 portable tests passed plus 6 portable
live-adapter tests**, including eight new UI checks. Desktop light/dark and
390-pixel browser checks were performed. Actual collection, VM resource usage and
the full Linux suite remain unverified by this refresh. See
[UI refresh report](UI_REFRESH_REPORT.md) for exact commands, screen descriptions,
the redraw diagnosis, limitations and retained stale-code candidates.

This work uses the separate `ui-polish` clone and branch. It does not change the
canonical `main` workflow or authorize integration into `main`.

Daybreak is a local Streamlit presentation of the verified Governorlab backend and
its archived evidence. Startup and ordinary reruns do not sample. An explicit Linux
action collects 5, 10 or 20 background intervals in an isolated child; no workloads
or physical CPUFreq control are used.

**Measured vs simulated.** Saved Linux sessions contain measured `/proc/stat`
counters and derived rates. Predicted classes use provisional rules. Candidate and
applied frequencies are simulated decisions; energy in The Comparison is a model
estimate. Nothing in the dashboard measures power or changes hardware frequency.

## Install and launch

From `C:\OS Project` in Windows PowerShell (replay only; Windows cannot collect):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dashboard.txt
.\.venv\Scripts\python.exe -m streamlit run daybreak/app.py
```

From the Ubuntu VM repository, after the start-of-session Git sync:

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
See the [user manual](USER_MANUAL.md) for a full walkthrough and troubleshooting.

## Classroom walkthrough

1. **The Replay:** automatically plays the selected verified session. Use
   Play/Pause/Resume, Restart, previous/next, Reset and 0.5×/1×/2×/4× speed.
   Pause to enable the seek slider; previous/next and Reset also pause for inspection.
   Restart plays from tick 1. The same timeline/inspector/summary serves the synthetic
   34-tick scenario and every validated saved Linux session (5 to 30 samples).
   The first-transition button selects the first verified event. Three aligned
   lanes show progressive utilization, predicted workload and candidate versus
   applied simulated frequency. At T11 the I/O prediction is waiting; at T13 K=3
   accepts the change. Full-run transitions are T13, T23 and T29. The cursor is
   retained when switching views. Leaving Replay pauses it; returning resumes at
   the current tick (or restarts a completed session). Selection changes restart
   playback with the selected source's actual sample count. At completion, playback
   stops and displays its summary; zero simulated transitions is a valid result.
   A saved session with discarded intervals shows a yellow banner, "N intervals
   discarded because of VM timing anomalies", and a **Discarded attempts** table.
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

## Live collection and saved sessions (updated October 19, 2026)

On Linux, choose **Samples** (5, 10 or 20), then click **Collect Live Data**. This
starts one single-purpose child per user session:
`python -m daybreak.worker --job <unique ignored run/daybreak-* folder> --count N`.
The child calls the same `governorlab.live.collect_live()` as the terminal, on its
main thread, in tolerant mode:

- Each interval must have a measured elapsed time of 0.5 to 2 s and a CPU-accounting
  rate of 0.5 to 1.5 times the expected rate (thresholds unchanged). A failing
  interval is discarded, never classified, and recorded with its attempt number and
  reason; collection continues from that interval's end snapshot.
- It stops at N valid samples, or fails at N + max(3, ceil(N/2)) attempts, or at the
  inner deadline of 2 s per allowed attempt plus 2 s (18 s for 5 samples, 32 s for
  10, 62 s for 20). The parent watchdog is 3 s longer, and a six-second UI heartbeat
  lease applies.
- If the attempt cap is hit, the dashboard says in plain words that VM timing was
  unstable, suggests closing other applications and retrying, and shows where the
  evidence was kept. There is no automatic retry.

Cancel, leaving Replay, disconnect or server exit interrupts the owned child,
escalates if needed and reaps it. The child starts no descendants. Failed/partial
artifacts remain available for diagnosis and are never substituted or replayed.
Each browser user session can own only one active collection; other users have
independent state. Deploy this local demonstration only on a trusted machine.

**The Samples dropdown applies to the next collection only.** It does not change or
filter a session that is already loaded; a saved session always replays with its own
recorded sample count.

After success the capture loads into the same player and plays all of its samples.
**Session source** lists every saved session: terminal captures `run/live-*` and
dashboard captures `run/daybreak-*/live-*`. Both use one on-disk format and one
loader (`presentation/sessions.py`), so a session collected with
`governorlab --live` can be replayed here and vice versa. Sessions remain labelled
saved observations, not currently live data. Windows disables collection with an
explanation; verified synthetic, saved replay and all other views remain functional.
To replay a Linux capture on Windows, copy its complete folder into `run/live-*`;
do not edit its files or copy a Linux virtual environment.

Saved loading repeats the hash-manifest check (when present), raw-counter validation,
sample-count checks (5 to 30, requested equal to kept), timing-disclosure consistency
and faithful classifier/Policy execution, comparing every saved decision. Legacy
captures without a manifest or timing fields still load; the UI says so and treats
them as clean. Hashes detect changes relative to a capture, not authenticated origin.
No capture's absent frequency measurement is replaced by a simulated frequency.

**Practical advice.** The VM's timer overshoots by about 10 %. Dashboard collection
competes with the browser and Streamlit for the VM's CPU, so it works best on a quiet
VM. The most reliable demonstration route is terminal collection
(`.venv/bin/python -m governorlab --live --samples 10`) followed by dashboard replay
of that session from **Session source**.

The timed Streamlit fragment runs only while playing/collecting. Each callback does
bounded work and advances at most one sample, with no app-side sleep/animation loop.
Slow rendering may stretch presentation time rather than skip observations; speed
is presentation cadence, never a claim about measured sampling intervals. During
playback the clock owns the cursor; pause enables seeking without browser slider
echoes interrupting animation. All chart lanes/inspector/markers use one frame.

## Verification status

- Windows portable suite on commit f47e288: 236 passed, plus 6 portable live-adapter
  tests. These include dashboard tests for the Samples selector (AppTest), the
  degraded banner (AppTest) and the attempt-cap message (unit test).
- Ubuntu VM full suite on commit 8b7280e (October 19, 2026): 326 passed in 29.84 s
  (user report). A run on f47e288 is pending.
- Tolerant collection on the VM (user report): one run discarded one 2.32 s interval,
  kept 5 of 5 samples and showed the degraded banner; strict mode also passed.
- Dashboard collection at 10 and 20 samples on the VM, and cancellation/disconnect/
  server-shutdown checks with a real child: pending.

## Ubuntu checklist

Run the start-of-session sync from [AGENTS.md](../AGENTS.md) (fetch, then
`git merge --ff-only origin/main` only if the tree is clean and main is only behind;
otherwise stop). Then:

```bash
.venv/bin/python -m pip install -r requirements.txt -r requirements-terminal.txt -r requirements-dashboard.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest tests/ -q
.venv/bin/python -m streamlit run daybreak/app.py
```

Check all four pages, ticks 1/11/13/23/29/34, automatic completion, pause/resume,
paused seek, Restart, speed, policy filtering and narrow layout. Collect one session
at each sample setting on a quiet VM: verify progress, one child, the actual row
count, source labels, automatic replay, any degraded banner and an honest transition
count. Replay a terminal-collected session from Session source. Check cancellation,
browser disconnect and server shutdown: no orphan child or retry, partial artifacts
retained, no failed capture replay. Use no generated load, sudo or hardware changes.

## Historical verification (October 16, 2026, five-sample dashboard)

Unified-player Windows verification at that time: **127 portable suite tests plus
six portable live-adapter tests passed (133 total)**, including 24 new upgrade tests
and the 17 original dashboard cases. Saved-source switching from synthetic tick 34 to
a five-sample capture also passed. The real Streamlit server and four views were
exercised in a browser at desktop and 390-pixel widths, including 1×/4× automatic
completion, pause/resume, cursor persistence and previous/next/reset. Browser checks
reported no external HTTP assets and no console errors. Windows restricted execution
blocked asyncio's loopback socketpair initialization; the bounded server/AppTest
checks succeeded with local socket access. No application event-loop workaround was
added. At that time collection was exactly five attempts with a 12-second child
deadline and a 15-second watchdog; the dashboard lived on the former development
branch, which was fast-forwarded into main on October 18, 2026
(tag checkpoint-0-daybreak-integrated).
