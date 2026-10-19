# User manual — Power-Aware CPU Governor

Last updated October 19, 2026 (commit f47e288 plus documentation).

## 1. What this software is

A Python user-space prototype that:

1. reads Linux aggregate CPU counters from `/proc/stat` (**measured**),
2. derives utilization, I/O wait, context-switch rate and runnable/blocked counts,
3. classifies each interval as `cpu_bound`, `io_bound`, `idle` or `mixed` with
   transparent, provisional rules,
4. chooses a target frequency with K=3 hysteresis (a class must persist for three
   consecutive samples before the frequency changes),
5. applies that frequency to a **simulated** setter (no hardware writes), and
6. estimates power and energy with a **modelled** formula (never measured).

It is not a kernel scheduler and does not change task queues. Two interfaces show
it: **Governorlab** (terminal) and **Daybreak** (local web dashboard).

## 2. Installation

You need Python 3.12 and Git. Never copy a virtual environment between Windows and
Ubuntu; create one per machine.

### Windows (replay only)

Windows cannot collect live data (no `/proc/stat`), but every replay, the dashboard,
the synthetic comparison and the sensitivity study work.

```powershell
cd 'C:\OS Project'
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-terminal.txt -r requirements-dashboard.txt
```

On Windows, replace `.venv/bin/python` in the commands below with
`.\.venv\Scripts\python.exe`.

### Ubuntu VM (live collection)

```bash
cd /home/vboxuser/Power_Aware_CPU_Governor
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt -r requirements-terminal.txt -r requirements-dashboard.txt
```

`requirements-terminal.txt` (Rich) is optional: `--plain` output works without it.
`requirements-dashboard.txt` (Streamlit, Plotly) is needed only for Daybreak.

### Keeping the VM checkout up to date

The project uses a single branch, `main`. At the start of every session:

```bash
git status
```
```bash
git fetch origin
```
```bash
git checkout main
```
```bash
git merge --ff-only origin/main
```

If `git status` shows changes, or the merge refuses because histories diverged, stop
and ask; do not reset, stash or force anything.

## 3. Commands

All commands run from the repository root.

### Governorlab (terminal)

| Goal | Command |
|---|---|
| Verified 34-tick synthetic replay | `.venv/bin/python -m governorlab` |
| Same, plain text, no delays | `.venv/bin/python -m governorlab --plain --instant` |
| Require the colored dashboard | `.venv/bin/python -m governorlab --visual` |
| Slower or faster playback (2-60 ticks/s) | `.venv/bin/python -m governorlab --speed 2` |
| Five archived Linux observations | `.venv/bin/python -m governorlab --recorded-linux` |
| Live: collect 5 samples, then replay (Linux) | `.venv/bin/python -m governorlab --live` |
| Live with 10 samples (5 to 30 allowed) | `.venv/bin/python -m governorlab --live --samples 10` |
| Live, abort on first timing anomaly | `.venv/bin/python -m governorlab --live --strict` |
| List saved sessions | `.venv/bin/python -m governorlab --list-sessions` |
| Replay newest saved session | `.venv/bin/python -m governorlab --session latest` |
| Replay a specific session | `.venv/bin/python -m governorlab --session run/live-20261019T101500Z-abc12345` |
| Help | `.venv/bin/python -m governorlab --help` |

Example `--list-sessions` line (format):

```text
/home/vboxuser/Power_Aware_CPU_Governor/run/live-20261019T101500Z-abc12345 | validated | 5/5 samples | manifest
```

Exit codes: 0 success, 1 collection/validation error (evidence kept), 2 bad option
or visual mode unavailable, 130 interrupted with Ctrl+C.

### Daybreak (dashboard)

```bash
.venv/bin/python -m streamlit run daybreak/app.py
```

Open `http://127.0.0.1:8501`. Stop with Ctrl+C in the terminal.

### Other tools

| Goal | Command | Notes |
|---|---|---|
| Synthetic control loop, 3 ticks | `.venv/bin/python governor.py --synthetic --ticks 3` | Invented inputs, simulated frequency |
| Five-policy comparison table | `.venv/bin/python -m benchmark.compare` | Synthetic, modelled energy |
| Regenerate the Review 1 demo export | `.venv/bin/python -m benchmark.review_demo --outdir data/review1-demo-new` | Needs a new folder |
| Sensitivity study (K and interval) | `.venv/bin/python -m benchmark.sensitivity --outdir data/sensitivity-new` | Deterministic; archived copy in `evidence/phase1b_sensitivity/` |
| Overhead smoke check (Linux, ~22 s) | `.venv/bin/python -m benchmark.overhead --smoke` | Output `data/overhead-smoke-<UTC>/` |
| Overhead full plan (Linux, ~26 min on the VM) | `.venv/bin/python -m benchmark.overhead` | Output `data/overhead-<UTC>/` |
| Shorter overhead plan | `.venv/bin/python -m benchmark.overhead --duration-s 30 --repetitions 2` | About 9 min |
| Full test suite (Ubuntu) | `.venv/bin/python -m pytest tests/ -q` | See the test plan |

Do not run `governor.py` without `--synthetic` on an arbitrary machine: it can probe
real cpufreq and samples forever unless `--ticks` is given. Collector and stress
launchers under `scripts/` need separate approval and are not part of normal use.

## 4. Dashboard walkthrough

1. **Start** the server and open the page. The synthetic 34-tick replay starts
   playing automatically. Nothing is collected at startup.
2. **The Replay view.** Three aligned lanes show utilization, predicted class and
   candidate versus applied simulated frequency. Use Play/Pause, Restart, ← / →,
   Reset and the speed selector (0.5× to 4×). Pause to use the tick slider. Press
   **Explore the first transition** to jump to tick 13; ticks 11 and 12 show the
   I/O class waiting (1/3, 2/3), tick 13 applies it. Transitions are at 13, 23 and 29.
3. **Session source.** Pick the synthetic scenario or any saved Linux session
   (terminal `run/live-*` or dashboard `run/daybreak-*/live-*`). The player restarts
   with that session's real sample count.
4. **Samples and Collect Live Data** (Linux only). Choose 5, 10 or 20, then click
   Collect Live Data. A progress bar shows kept samples; **Cancel collection** stops
   it. On success the new session loads and plays. The Samples dropdown only affects
   the next collection; it does not change a session already loaded.
5. **Degraded sessions.** If any interval was discarded, a yellow banner reads
   "N intervals discarded because of VM timing anomalies ..." and a **Discarded
   attempts** table lists each attempt, reason, elapsed time and ratio.
6. **The Evidence** shows the five archived Linux observations (measured, no
   decisions). **The Comparison** shows five policies on one synthetic trace with
   modelled energy. **Lab Notes** shows the classifier source, thresholds and limits.

## 5. Sessions

A session is one folder under `run/` (ignored by Git):

| File | Content |
|---|---|
| `capture.csv` | Measured raw counters (previous and current) and derived rates for each kept sample |
| `raw_events.jsonl` | Baseline, every attempted interval, every discarded attempt |
| `metadata.json` | Status, requested and kept counts, attempts made, discarded attempts, `timing_quality`, timings, resources, source hashes, decision summary |
| `decisions.json` | Predicted class, candidate and applied simulated frequency, persistence state per kept sample |
| `session-sha256.json` | Hash manifest of the four files above |

Terminal and dashboard write the same format and use the same loader, so either can
replay the other's sessions. Loading re-checks hashes, raw counters, counts and the
timing disclosure, and recomputes every decision; any mismatch is an error, never a
silent fix. To replay a Linux session on Windows, copy the whole folder into `run/`
and do not edit it. Failed sessions keep their files for diagnosis but cannot be
replayed.

## 6. Troubleshooting

| Symptom | Cause | What to do |
|---|---|---|
| "Live observation requires Linux /proc/stat" | Running `--live` on Windows | Use replay, or run on the Ubuntu VM |
| "Sampling timing anomaly; stopping without retry" | `--strict` run hit an interval outside 0.5-2 s | Run without `--strict` (tolerant mode), or close other applications and retry |
| Yellow banner / "TIMING QUALITY DEGRADED: N intervals discarded ..." | The VM paused or overran some intervals; they were discarded and recorded | The session is valid but its kept samples may not be adjacent in time; say so when presenting it |
| "Attempt cap reached ..." (terminal) or "VM timing was unstable ..." (dashboard) | Too many intervals were discarded (more than max(3, ceil(N/2))) | Close the browser and other applications, wait a moment, retry once manually. Evidence is kept in `run/` |
| Dashboard collection fails but terminal works | The browser and Streamlit compete for the VM's CPU; the VM timer overshoots by about 10 % | Use a quiet VM, or collect in the terminal (`--live --samples 10`) and replay that session in the dashboard |
| "Saved session integrity mismatch" / "disagree with the existing backend" | A session file was edited, or the backend changed since capture | Keep the original folder; do not edit session files |
| "Visual mode unavailable: ..." | Terminal too small, output redirected, or Rich missing | Enlarge to at least 80x24, run in a real terminal, or use `--plain` |
| `git: 'switch' is not a git command` | Old Git on the VM | Use `git checkout main` and `git merge --ff-only origin/main` |
| Overhead tool reports failed runs | A run hit the 3x runaway guard or raised an error | The other runs still finish; read `overhead_summary.md` "Failed runs"; exit code is 1 |

## 7. Limitations

- **Frequency is simulated.** The VirtualBox VM exposes no cpufreq interface. The
  four-step ladder (3.8 to 5.1 GHz) is a model of the Ryzen 7 7840HS base-to-boost
  range, not the hardware's real P-states.
- **Energy is modelled** with P = 21.6 + 32.4·(f/5.1 GHz)³·util/100 W, fitted to the
  published TDP range. No electrical power has been measured, so no savings are claimed.
- **Thresholds are provisional** (`docs/thresholds.md`); they were not tuned on
  labelled workloads, so classifier accuracy is unknown.
- **The classifier is rule-based**, not machine learning.
- **Replay is open loop**: running work at a lower simulated frequency does not make
  it take longer, so completion time is not modelled.
- **Baselines** (performance, powersave, ondemand, conservative) are Python
  approximations; there is no schedutil baseline.
- **VM timing** overshoots by about 10 %; tolerant collection discards anomalous
  intervals, so a degraded session's kept samples can be non-adjacent in time.
- **Governor overhead** was measured once on the VM (4 intervals x 60 s x 3
  repetitions, 24/24 runs ok): net 0.5988, 0.6168, 0.5483 and 0.5861 ms CPU per tick at
  0.5, 1, 2 and 5 s intervals, i.e. 0.1198 % to 0.0117 % of one core (derived, an upper
  bound because the VM's ticks ran late). This is process CPU time inside a VM, not
  power, and excludes logging and the UI. The run is archived in
  [`evidence/phase1b_overhead/`](../evidence/phase1b_overhead/README.md).
- **Aggregate counters only**: no per-core, per-process or PMU (IPC/stall) signals.
