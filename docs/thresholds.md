# Classifier thresholds

**Status: PROVISIONAL. Not yet data-justified.** The values below are the
placeholders currently in `classifier/rules.py`, invented to make the pipeline
runnable end-to-end on synthetic data. None of them are backed by recorded
`stress-ng` runs yet. Do not cite these in the report as tuned values — this
file exists so `rules.py`'s docstring has somewhere real to point, and so
Phase 2 has a template to fill in rather than a blank page.

| Threshold | Current value | Meaning | Why this number (today) |
|---|---|---|---|
| `util_high` | 70.0% | Above this, the core is genuinely computing | Guess — "clearly busy" |
| `util_idle` | 10.0% | Below this with `procs_running` ≤ 1, nothing is happening | Guess — "clearly quiet" |
| `iowait_high` | 20.0% | Above this, a device is the bottleneck | Guess — round number |
| `ctxt_high` | 2000.0/s | Switches/sec typical of short I/O-blocked bursts | Guess — order-of-magnitude only |

## What Phase 2 needs to actually do

1. Run `stress-ng --cpu N`, `--io N`, `--vm N`, and an idle baseline on the real
   VM, each for a few minutes, logging via `monitor.reader.sample()` to CSV.
2. For each recorded signal (`util_pct`, `iowait_pct`, `ctxt_per_s`,
   `procs_blocked`), plot the distribution per known workload type.
3. Pick each threshold at the point that best separates the distributions —
   not a round number chosen by eye. Record the actual data-derived value here,
   replacing the placeholder, with a one-line justification per threshold (e.g.
   "iowait_high=32%: separates io-stress-ng's iowait distribution [28-95%] from
   idle's [0-3%] with zero overlap in N=500 samples").
4. Re-run `tests/test_core.py::test_classify` and `test_synthetic_matches_ground_truth`
   against the new thresholds — the tests use hand-picked signal values, so check
   they still make sense once real thresholds are known; adjust the test fixtures
   if the real data suggests different boundary cases matter more than the
   ones currently covered.
5. Note in the final report which threshold, if any, turned out to matter most
   for classification accuracy — worth knowing before the Review II ML
   classifier comparison, since a feature that barely moves accuracy in the
   rule-based version is a reasonable one to also weight less when interpreting
   the decision tree's feature importances.

## Known gap this file should also eventually cover

The `io` vs `io_burst` distinction added to `monitor/synthetic.py` — a plain
I/O-wait workload (low utilization, high iowait) is the easy case; a bursty
I/O-bound workload with a momentary utilization spike (PRD §2's actual
motivating example) is the case that separates this project's classifier from
`ondemand`. Once real `stress-ng` traces exist, check whether real I/O-bound
processes actually produce signals closer to `io` or to `io_burst` — this
may mean `iowait_high` and `ctxt_high` need different values than a threshold
tuned only against the calmer `io` profile would suggest.
