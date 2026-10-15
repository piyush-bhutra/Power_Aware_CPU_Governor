# Dashboard integration handoff

## Daybreak implemented — October 16, 2026

Windows main/development were safely synchronized to the approved integrated
Governorlab checkpoint `2753fc397bc97b96421ebb365152c1c0fc66781f`. The local dashboard
now lives in `daybreak/app.py`, with read-only verification/table helpers in
`daybreak/data.py`, Plotly views in `daybreak/charts.py` and local `theme.css`.
Four views use the shared adapter and existing backend, retaining sample identity
and measured/synthetic/model boundaries. `load_comparison()` additionally verifies
every archived five-policy row and recomputes summaries. Web live is deferred due
to the terminal collector's Linux signal lifecycle; no automatic collector exists.

See [DAYBREAK.md](DAYBREAK.md) for launch, verification and Ubuntu deployment checks.
The sections below retain the earlier planning context; their future-work and old
main-checkpoint statements are historical. New dashboard work goes to development
only, without merging main.

## Shared adapter available — Governorlab update, October 15, 2026

`presentation.adapter.load_replay()` and `load_observations()` now return portable
Dataset/Frame/Transition objects with original CSV sample identity, source metadata
and separate synthetic/recorded modes. Candidate/persistence fields use the existing
backend and are exposed only after archive/output consistency checks; Linux decision
fields stay unavailable. Features and metadata are fresh dictionaries: treat as
read-only or copy. No Rich, plotting, live collector, subprocess or hardware selector
is called by the adapter. Cache only read-only results; create fresh policy state
through the adapter for each reconstructed replay. Private Policy introspection is
isolated in `policy_snapshot`; backend drift fails verification rather than inventing
state. See GOVERNORLAB.md for schemas, integrity rules and limitations. Daybreak
implementation remains separately authorized future work; existing APIs are unchanged.

Planning boundaries only; no final UI design, frontend code or installations.
Start implementation after the separate frontend brainstorming resolves the design.
The stable backend baseline is main `207e7326369506c4e9021cc8f397c50c06fb3794`.

## Display-ready evidence

| Repository location | Display use | Required interpretation |
|---|---|---|
| `evidence/review1/background_readiness_20261015/validated_trace.csv` | Five measured aggregate kernel observations; elapsed intervals and raw deltas | Historical uncontrolled background capture; not live, not idle ground truth |
| Background archive `collection/20261015T144114Z-la72apwi/statistics.json`, `lifecycle.json`, `manifest.json` | Statistics, readiness ordering, exits and reported cleanup | One successful no-generated-load run; no loaded timing guarantee |
| `evidence/review1/synthetic_policy_comparison_20261015/*.csv` | Five 34-tick policy replays | Synthetic signals; simulated frequency; 15-column historical schema |
| Synthetic archive `summaries.json` and two labelled PNGs | Modelled energy table/chart and simulated frequency timeline | Model estimates and Python baseline approximations; no measured savings |
| Both archives' `metadata.json` / `PROVENANCE.json` / README / SHA256SUMS | Source checkpoint, parameters, integrity and limitations | Source commit differs from archive commit; synthetic timing is not UTC |

The background launcher metadata is named `launcher-metadata.json`; collection
metadata is under its collection subdirectory. Synthetic `freq_khz` is simulated
pre-tick setter state; background `freq_khz` is blank. Never fill that blank with a
simulated frequency while labelling it measured. The original synthetic CSVs have
15 columns, the archived background CSV has 39, and current generated governor CSVs
have 40. Detect schemas and reject incompatible append/interpretation. Preserve files.

## Reusable modules and APIs to inspect

- `monitor.reader.parse_stat(text)` / `compute_signals(prev, cur, interval_s)` are
  pure parsing/rate helpers. `sample(interval_s=1.0, count=None, observer=None)` is
  live/blocking and can be unbounded without count; inspect it before UI integration.
- `classifier.rules.classify(sig)` provides provisional four-class rules; expose
  thresholds honestly and do not call outputs validated labels.
- `policy.governor_policy.Policy(...).step(sig)` maintains hysteresis state; inspect
  pending/streak/stable-class behavior and known optional ramp-down defect.
- `governor.run(source, setter, policy)` yields annotated rows; use an explicit
  `SimulatedSetter` for replay. It can mutate input dictionaries via frequency fallback;
  use fresh copies/factories and inspect before introducing caching/session state.
- `monitor.synthetic.source(plan, interval_s=1.0, seed=...)` creates invented signals.
  Inspect its actual signature and deterministic seed use before wiring controls.
- `benchmark.compare.run_comparison(source_factory, available_khz, k=3,
  ramp_down_step=None)` expects a fresh iterator per policy; it uses simulated setters.
- `benchmark.summarize.summarize(rows, interval_s=1.0)` integrates using a supplied
  constant interval, not each row's measured elapsed time; do not apply blindly to
  measured timing data. `compare_table` also prints a terminal table.
- `power_model.estimate.estimate_power_w` / `estimate_energy_j` implement the assumed
  model; label every derived figure modelled, document constants and fixed-trace limits.
- `analysis.plots` renders static Agg PNGs. Reuse verified data for any future Plotly
  view; do not imply an interactive chart introduces new measurements.
- `benchmark.review_demo` is the finite seeded CLI generator, not a UI API.
  `monitor.capture.validate_trace` validates real raw-counter traces, not old synthetic
  CSVs. Inspect validation assumptions rather than forcing one schema into another.

Before implementing, check input contracts, mutable policy/setter state, deterministic
replay, finite limits, row timing, schema detection and cache behavior. Retain existing
backend APIs until an actual design requirement and focused verification justify changes.

## Operations that must not run automatically

No stress-ng, collectors/standalone launchers, auto-retries, infinite live sampling,
physical frequency setters, sudo, package installation, VM/system configuration,
bulk writes or overwriting archived evidence on page load/refresh. Do not call
`open_setter()` to choose hardware implicitly for replay. Do not trigger CLI entrypoints
as import side effects. Any future live monitoring needs explicit finite bounds and a
clear historical-versus-live label; workload/hardware permissions are separate.
