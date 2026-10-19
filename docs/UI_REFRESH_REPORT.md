# Daybreak UI refresh

Date: October 19, 2026. Checkout: `C:\OS Project UI`. Branch: `ui-polish`.
Starting commit: `4eb1865`. Implementation checkpoint: `2371250`.
The final documentation/polish commit is identified by the branch head and
`git log --oneline 4eb1865..ui-polish`; its hash is reported in the task handoff.

## Scope and preservation

UI-only work, using the existing Streamlit 1.66.0 / Plotly 6.9.0 environment.
No dependencies installed or changed. No collector or generated workload ran.
No collection, worker, session validation, classifier, governor or policy logic was
edited. `main` was never checked out or committed to. No tracked file was deleted;
`data/`, `run/`, evidence and the protected documentation were left unchanged.
No tags were created. No history rewriting or stash operations were used.

## Before and after

| Before | After |
|---|---|
| Source controls, playback controls, hero, policy card and pipeline preceded results | Controls in a sidebar; summary and results start the main area |
| Collection showed progress in two places alongside the old replay | One polling progress view, with a visible Cancel button; success returns to results |
| Whole replay presentation regenerated four times each second | Only the chart/status fragment updates at the chosen playback cadence |
| Explanations, growing transition lists and final JSON changed layout during playback | Static full-session summary; secondary information in expanders outside the timed fragment |
| Folder names in the source picker | Recorded date/time, sample count and timing quality; unavailable fields disclosed |
| Hard-coded light surfaces and chart text | Shared tokens and inherited theme colours; translucent surfaces and theme-aware Plotly text |
| Internal class names prominent | CPU busy, Waiting for I/O, Mostly idle and Mixed activity in summaries and tooltips |

The summary is explicitly full-session information, not a claim that playback has
already reached every sample. Simulated frequency remains distinguished from
measured Linux counters. Synthetic inputs are explicitly labelled **not measured**.
Comparison energy remains an uncalibrated model. Zero transitions is valid and
does not imply savings or improved performance. The timing-degraded banner remains
visible above results; discarded attempts remain available in their own expander.

## Cause of the jitter

The old 250 ms fragment called `replay_view()` on every callback. That rebuilt the
hero, cards, chart, transition list, provenance and tables even when the player had
not advanced (four renders per sample at 1×, eight at 0.5×). Collection polling was
also rendered in both `controls()` and the fragment. The new regression test saw
**three progress bars** before the fix: two collection bars and the old replay bar.
This directly reproduced the duplicated UI, rather than relying on a timing guess.

The chart also introduced a new transition trace/legend entry at its first event;
the growing event list and final summary changed document height. The refreshed
view keeps one chart with fixed axes and 420 px height, a stable trace structure,
and a plain legend outside the plot. Static details no longer redraw with each
sample. Chart construction is cached with `max_entries=40`; the complete validated
dataset and sample number are cache keys, so changed source content cannot reuse
the wrong chart. No cache bypasses source validation.

Browser measurement confirmed equal chart bounding boxes at samples 13 and 14.
This is evidence for stable geometry, not a frame-time benchmark or proof of zero
flicker on every browser. Collection redraws only its progress fragment every
0.5 seconds; completed collection and playback completion each still require a
normal app rerun to synchronize controls.

## Screen descriptions and browser checks

- **Replay, desktop:** left sidebar contains navigation, source, Samples, collection
  and playback controls. The main area shows honesty badges, What happened, a short
  legend, status and a fixed-height three-lane chart. At 1440 × 1000 the chart is
  visible without scrolling. Details and CSV export follow in compact sections.
- **Collection:** heading and measured-counter disclosure at the top, Cancel,
  one progress bar and a brief explanation. No old replay chart is rendered while
  collecting. This was verified with AppTest fake jobs only.
- **Errors/cancellation:** clear error above the previous verified results; no
  invented samples or automatic retry. Existing missing-source and tamper tests
  continue to pass. Launch failure, cancellation and successful source switching
  are covered with AppTest.
- **Evidence:** measured badge, archived-observation metrics, a chart and collapsible
  measured source table. Provenance and limitations remain available.
- **Comparison:** simulated/modelled badges, energy and frequency charts, policy
  filtering and the complete summary table. Empty selection retains its instruction.
- **Lab Notes:** methodology, source thresholds and limitations; the displayed
  tolerant-collection deadline explanation now matches the existing attempt budget.
- **Dark theme:** verified using server-only theme overrides; repository defaults
  were not changed. Initial browser inspection exposed unsupported CSS theme variable
  assumptions; the final styles inherit native text colour and use translucent
  surfaces, avoiding white cards with unreadable light text.
- **Narrow screen:** at 390 × 844, page scroll width and client width were both 390 px.
  The native sidebar collapses. Vertical scrolling remains necessary for the full
  chart/details on small screens. No custom scrolling script was introduced.
- **Motion/accessibility:** native labelled controls and focus outlines; reduced-motion
  emulation returned `0s` button transitions. Normal transitions use one 120 ms token;
  Plotly transitions are disabled. A full screen-reader audit was not performed.

All four views rendered in the Windows browser without app exceptions. Browser
console check reported zero errors or warnings. Screenshots were inspected during
verification; this report supplies descriptions instead of retaining generated
screenshots in the repository. No real Linux capture, disconnect, child shutdown,
4 GB VM memory/performance benchmark, or full Linux test run was performed.
The CSV download is a **presentation table** of derived features and simulated
decisions; it is not a raw-session archive export.

## Tests

Used the existing interpreter `C:/OS Project/.venv/Scripts/python.exe` from this
checkout, with bytecode and pytest caching disabled. The portable selection is
documented in `docs/TEST_PLAN_AND_RESULTS.md` (AGENTS.md itself has no explicit
Windows test command).

```powershell
& 'C:/OS Project/.venv/Scripts/python.exe' -B -m pytest tests/ -q -p no:cacheprovider --ignore=tests/test_background_launcher.py --ignore=tests/test_collection.py --ignore=tests/test_cpu_timing.py --ignore=tests/test_safe_launcher.py --ignore=tests/test_live_demo.py
# 249 passed in 18.43 s

& 'C:/OS Project/.venv/Scripts/python.exe' -B -m pytest tests/test_live_demo.py -q -p no:cacheprovider -k 'live_adapter or live_cli_is_opt_in or three_consecutive_fixture'
# 6 passed, 16 deselected in 0.13 s
```

**255 passing tests total in the final selections; zero failures.** The eight new
checks cover sidebar/results layout, one collection panel with no replay, known
transition wording, friendly labels, missing label metadata, zero transitions,
cancellation returning to verified results, and chart-cache reuse/invalidation.
Existing degraded-banner, discarded-session integrity, sample selector and shared
player tests remain in the passing suite. Initial red tests demonstrated the old
layout/duplicate progress; an additional zero-transition fixture initially omitted
required `csv_path` metadata and was corrected before the final run.

## Files changed

- `daybreak/app.py`: state-driven main view, separated static details and timed
  rendering, cached chart, summary, badges, CSV presentation export.
- `daybreak/playback_ui.py`: sidebar controls, friendly picker labels, loading/empty
  text, single progress rendering; backend calls and result validation retained.
- `daybreak/charts.py`: shared colours, readable class labels, stable traces,
  fixed-height/theme-aware figures, disabled plot transitions.
- `daybreak/theme.css`: shared spacing/type tokens, compact cards/buttons, inherited
  theme surfaces, focus and reduced-motion styles.
- `daybreak/design.py`: shared chart/style tokens.
- `daybreak/ui_text.py`: pure presentation helpers for summaries and picker labels.
- `tests/test_daybreak_refresh.py`: eight UI/presentation regressions.
- `docs/DAYBREAK.md`: current UI workflow and verification note.
- `docs/UI_REFRESH_REPORT.md`: this report and local recovery handoff.

## Stale-file review and cleanup

**No entire tracked file was established to be unused. No tracked file was deleted.**
Reference searches covered the repository for `state_card`, `navigate`, `move_tick`,
`daybreak.sessions` and `daybreak.player`, and the old hero/state CSS class names.

| Retained candidate | Evidence / disposition |
|---|---|
| `daybreak/app.py` functions `state_card` and `navigate` | No remaining callers after layout refresh; retained as unused helpers, not grounds to delete the active app file |
| `daybreak/data.py` helper `move_tick` | No current UI caller, but explicitly exercised by `tests/test_daybreak_data.py`; retained |
| `daybreak/sessions.py` | Compatibility re-export used by playback controls and several tests; not stale |
| `daybreak/player.py` | Used by playback controls and player tests; not stale |

Only generated scratch scripts, temporary preview screenshots and browser snapshot
output created during this task were eligible for removal. No files under tests,
docs or evidence were removed. The shared VM export location is unavailable in this
Windows clone; this report is the local handoff.

Next action: review `ui-polish` and, when explicitly authorized, rehearse collection
and cancellation on the Ubuntu VM. This task does not authorize merging into main.
