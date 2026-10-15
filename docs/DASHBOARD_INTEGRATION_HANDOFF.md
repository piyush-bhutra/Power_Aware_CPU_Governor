# Future dashboard integration handoff

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
