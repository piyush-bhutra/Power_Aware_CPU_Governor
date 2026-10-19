# Test plan and results

Last updated October 19, 2026. Every result below comes from a recorded suite run
or a recorded manual check; anything not recorded is marked **pending**.

## Recorded runs (the only sources for the Result column)

| Code | Run | Commit | Date | Recorded outcome |
|---|---|---|---|---|
| **W** | Windows portable suite (Python 3.12.4): all test files except the four Linux-only modules and `test_live_demo.py`, plus six portable `test_live_demo.py` cases | f47e288 | 2026-10-19 | 236 passed + 6 passed, 0 failed |
| **U** | Ubuntu VM full suite (`pytest tests/ -q`) | 8b7280e | 2026-10-19 | 326 passed in 29.84 s, 0 failed (user report) |
| **U2** | Ubuntu VM full suite (code identical to f47e288; later commits were docs only) | 943dba1 | 2026-10-19 | 331 tests. First run: 322 passed, 9 failed, all in `tests/test_safe_launcher.py` with exit code 124 (timeout); the run took 204 s while the VM load average was 3 to 4. Clean re-run of that file: 33 passed in 4.47 s. Those launcher tests are timing-sensitive on a loaded VM (user report) |
| **M5** | Ubuntu VM dashboard: Collect Live Data at 5, 10 and 20 samples, and Cancel | 943dba1 | 2026-10-19 | Collection worked at all three sample counts; Cancel left no leftover worker process; Streamlit logged a harmless "fragment does not exist anymore" warning (user report) |
| **M1** | Ubuntu VM tolerant live collection, 5 samples | 8b7280e or later | 2026-10-19 | One interval discarded (elapsed 2.32 s, outside 0.5-2 s); 5 of 5 samples kept; degraded banner shown; replay revalidated (user report) |
| **M2** | Ubuntu VM `--live --strict`, 5 samples | 8b7280e or later | 2026-10-19 | Passed (user report) |
| **M3** | Ubuntu VM overhead smoke runs (`--smoke`) | before f47e288 | 2026-10-19 | About 0.3 to 0.8 ms CPU per tick; single 5 s runs, quantized (user report) |
| **M4** | Ubuntu VM overhead full plan (`.venv/bin/python -m benchmark.overhead`): 4 intervals x 60 s x 3 repetitions, governor and sleep-only control | f47e288 | 2026-10-19 | 24 runs ok, 0 failed. Net governor CPU per tick (mean): 0.5988 ms at 0.5 s, 0.6168 ms at 1 s, 0.5483 ms at 2 s, 0.5861 ms at 5 s (archived in `evidence/phase1b_overhead/`) |

Results are recorded per suite, not per test: "Pass (W)" means the test is in the
Windows portable selection and that selection passed with zero failures. Tests that
only run on Linux are covered by U. Tests added or changed after 8b7280e (the
Phase 1B.1 overhead tests) have no Linux result yet. "Measured" in this project means
Linux `/proc/stat` counters; frequencies, energy and savings are simulated or modelled
throughout, including in every test.

## Test cases

Test names are in `tests/<file>.py::<test>`. Run one with
`.venv/bin/python -m pytest "tests/<file>.py::<test>" -q`.

### 1. Monitoring (`/proc/stat` parsing and rates)

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| MON-01 | Counter deltas | Two cumulative snapshots | Utilization, I/O wait, IRQ % and context switches/s from deltas, not totals | `test_core.py::test_deltas` | Pass (W, U) | 2026-10-19 |
| MON-02 | Guest time | Snapshots with guest/guest_nice | Guest time not counted twice | `test_monitor_regressions.py::test_guest_time_is_not_counted_twice` | Pass (W, U) | 2026-10-19 |
| MON-03 | Decreasing iowait | iowait counter goes backwards | Clamped to zero and flagged | `test_monitor_regressions.py::test_decreasing_iowait_is_clamped_and_flagged` | Pass (W, U) | 2026-10-19 |
| MON-04 | Counter reset | Later snapshot smaller | Interval rejected (None), never invalid rates | `test_monitor_regressions.py::test_counter_reset_invalidates_interval` | Pass (W, U) | 2026-10-19 |
| MON-05 | Elapsed time | Non-positive / non-finite interval | ValueError | `test_monitor_regressions.py::test_invalid_elapsed_time_rejected` | Pass (W, U) | 2026-10-19 |
| MON-06 | Monotonic timing | Fake sampler clock | Measured monotonic elapsed used; raw snapshots kept | `test_monitor_regressions.py::test_sample_uses_monotonic_elapsed_and_retains_raw_snapshots` | Pass (W, U) | 2026-10-19 |
| MON-07 | Ratio features | Zero denominators | Capped, never inf/NaN | `test_core.py::test_ratio_features_guard_zero_denominators` | Pass (W, U) | 2026-10-19 |
| MON-08 | Bad counters | Missing, NaN, negative or non-numeric snapshot fields | Clear ValueError naming the field | `test_policy_validation.py::test_compute_signals_rejects_bad_counters` | Pass (W, U) | 2026-10-19 |
| MON-09 | CSV schema | Append to a CSV with a different header | Refused | `test_monitor_regressions.py::test_appending_incompatible_csv_schema_is_refused` | Pass (W, U) | 2026-10-19 |
| MON-10 | Real VM sampling | Live collection on the VM | Valid rows with measured elapsed time | M1 | Pass (M1) | 2026-10-19 |

### 2. Classifier (rule-based)

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| CLS-01 | Four classes | Hand-picked feature dicts | cpu_bound / io_bound / idle / mixed per the rule order | `test_core.py::test_classify` | Pass (W, U) | 2026-10-19 |
| CLS-02 | Synthetic profiles | Noise-0.1 synthetic phases | Class matches the invented label | `test_core.py::test_synthetic_matches_ground_truth` | Pass (W, U) | 2026-10-19 |
| CLS-03 | I/O burst precedence | High-utilization I/O burst | io_bound (I/O rule first); differs from ondemand | `test_baselines.py::test_ours_diverges_from_ondemand_on_an_io_burst` | Pass (W, U) | 2026-10-19 |
| CLS-04 | Input validation | Missing, NaN, negative, non-numeric feature | Clear ValueError | `test_policy_validation.py::test_classify_rejects_bad_features` | Pass (W, U) | 2026-10-19 |
| CLS-05 | Accuracy on labelled real workloads | Bounded stress-ng runs with known labels | Confusion matrix and accuracy | Not implemented | pending | — |

### 3. Policy (hysteresis)

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| POL-01 | K=3 persistence | Class sequence | Frequency changes only after 3 consecutive predictions | `test_core.py::test_hysteresis` | Pass (W, U) | 2026-10-19 |
| POL-02 | Blip suppression | One-tick class change | No frequency change | `test_core.py::test_hysteresis_suppresses_a_blip` | Pass (W, U) | 2026-10-19 |
| POL-03 | Ramp-down | ramp_down_step=1, idle persists | Steps down every tick until the class target | `test_policy_validation.py::test_ramp_down_keeps_stepping_until_target_while_class_persists` | Pass (W, U) | 2026-10-19 |
| POL-04 | Default unchanged | ramp_down_step=None | Jumps straight to target, as before | `test_policy_validation.py::test_default_jump_behaviour_unchanged` | Pass (W, U) | 2026-10-19 |
| POL-05 | Input validation | Empty/unsorted ladder, bad K, bad step, unknown class | Clear ValueError | `test_policy_validation.py` (ladder, k, ramp_step, unknown_class tests) | Pass (W, U) | 2026-10-19 |
| POL-06 | Archived scenario | Seed 11, K=3, 34 ticks | Transitions at ticks 13, 23, 29; matches archived outputs | `test_presentation_adapter.py::test_replay_is_deterministic_and_matches_archived_backend_outputs` | Pass (W, U) | 2026-10-19 |

### 4. Simulated actuation

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| ACT-01 | Simulated setter only | Synthetic CLI run | Never probes or writes hardware | `test_cli.py::test_synthetic_never_probes_hardware` | Pass (W, U) | 2026-10-19 |
| ACT-02 | Logged frequency | Clamping fake setter | Log shows the frequency that actually landed | `test_hardware_desync.py::test_run_logs_the_frequency_that_actually_landed` | Pass (W, U) | 2026-10-19 |
| ACT-03 | Clamp resync | Setter clamps below request | Policy state resyncs to the clamp and keeps requesting the target | `test_hardware_desync.py::test_clamped_write_resyncs_policy_current_and_keeps_requesting_target` | Pass (W, U) | 2026-10-19 |
| ACT-04 | Sysfs setter readback | Fake sysfs tree | Reports landed value; detects silent no-op | `test_sysfs_setter.py` | Pass (W, U; fake sysfs tree, no real writes) | 2026-10-19 |
| ACT-05 | Real DVFS on hardware | Native Linux with cpufreq | Frequency actually changes | Not possible on the VM | pending | — |

### 5. Session store (terminal and dashboard)

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| SES-01 | Configurable count | `collect_live(count=5/10/30)` with fake sampler | Count used for sampling, validation and deadline; manifest written | `test_shared_sessions.py::test_collect_live_uses_count_everywhere_and_writes_manifest` | Pass (W, U) | 2026-10-19 |
| SES-02 | Count range | 4, 31, 5.0, True | ValueError before sampling | `test_shared_sessions.py::test_collect_live_rejects_out_of_range_count_before_sampling` | Pass (W, U) | 2026-10-19 |
| SES-03 | Loader checks | Mismatched or out-of-range counts | Rejected | `test_shared_sessions.py::test_load_session_requires_matching_counts_in_range` | Pass (W, U) | 2026-10-19 |
| SES-04 | Tampering | Edited CSV, decisions or manifest; failed status | Rejected | `test_daybreak_sessions.py::test_saved_session_rejects_failed_or_tampered_data` | Pass (W, U) | 2026-10-19 |
| SES-05 | Legacy sessions | Five-sample session without manifest or timing fields | Loads, labelled legacy, treated as clean | `test_tolerant_collection.py::test_legacy_five_sample_session_loads_as_clean` | Pass (W, U) | 2026-10-19 |
| SES-06 | CLI replay | `--session PATH`, `--session latest`, `--list-sessions` | Revalidated replay; newest first listing | `test_shared_sessions.py::test_cli_latest_and_list_sessions` | Pass (W, U) | 2026-10-19 |
| SES-07 | Shared format | Terminal session shown in dashboard and vice versa | Same loader, same result | `test_daybreak_sessions.py::test_same_streamlit_player_switches_saved_and_synthetic` | Pass (W, U) | 2026-10-19 |
| SES-08 | Real VM replay | Replay a session saved on the VM | Revalidates against backend | M1 | Pass (M1) | 2026-10-19 |

### 6. Tolerant collection

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| TOL-01 | Discard and continue | Slow, fast, ratio and invalid intervals at various positions | Discarded, recorded with reason; N kept; classifier never sees them | `test_tolerant_collection.py::test_anomalies_are_discarded_recorded_and_count_is_reached` | Pass (W, U) | 2026-10-19 |
| TOL-02 | Attempt cap | Too many anomalies | Failed, evidence kept, no manifest, no decisions | `test_tolerant_collection.py::test_attempt_cap_fails_and_retains_evidence` | Pass (W, U) | 2026-10-19 |
| TOL-03 | Strict mode | Anomaly with `strict=True` | Aborts on first timing anomaly | `test_tolerant_collection.py::test_strict_aborts_on_first_timing_anomaly` | Pass (W, U) | 2026-10-19 |
| TOL-04 | Rebaseline | Real `sample()` with fake clock, one 2.6 s interval | Next kept interval starts from the discarded one's end snapshot | `test_tolerant_collection.py::test_real_sampler_rebaselines_after_a_discarded_interval` | Pass (W, U) | 2026-10-19 |
| TOL-05 | Disclosure consistency | Edited timing fields | Rejected | `test_tolerant_collection.py::test_inconsistent_disclosure_is_rejected` | Pass (W, U) | 2026-10-19 |
| TOL-06 | Real VM tolerant run | `--live` on the VM | Anomaly discarded, 5 of 5 kept, banner shown | M1 | Pass (M1: one 2.32 s interval discarded) | 2026-10-19 |
| TOL-07 | Real VM strict run | `--live --strict` on the VM | Completes when no anomaly occurs | M2 | Pass (M2) | 2026-10-19 |
| TOL-08 | Real VM attempt cap | Force many anomalies on the VM | Plain-words failure | Not attempted | pending | — |

### 7. Dashboard (Daybreak)

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| DAY-01 | Views render | Open all four views | No exception; cursor kept between views | `test_daybreak_app.py::test_all_surfaces_render_and_preserve_replay_cursor` | Pass (W, U) | 2026-10-19 |
| DAY-02 | Player controls | Pause, resume, restart, speed, seek | Correct tick and state | `test_daybreak_playback_ui.py::test_autoplay_pause_resume_restart_speed_and_manual_navigation` | Pass (W, U) | 2026-10-19 |
| DAY-03 | Samples selector | Choose 10, click Collect | Child started with count 10 | `test_shared_sessions.py::test_dashboard_sample_selector_reaches_collection_start` | Pass (W, U) | 2026-10-19 |
| DAY-04 | Degraded banner | Load a degraded session | Banner and discarded table shown; not on synthetic | `test_tolerant_collection.py::test_dashboard_replay_shows_degraded_banner` | Pass (W, U) | 2026-10-19 |
| DAY-05 | Child lifecycle | Fake child: cancel, timeout, disconnect | Escalates and reaps; no retry | `test_daybreak_collection.py::test_cancellation_escalates_and_reaps` | Pass (W, U) | 2026-10-19 |
| DAY-06 | Windows collection | Click on Windows | Disabled, never spawns | `test_daybreak_playback_ui.py::test_windows_collect_disabled_and_never_spawned` | Pass (W, U) | 2026-10-19 |
| DAY-07 | Real VM dashboard collection at 5, 10, 20 | Collect Live Data on a quiet VM | Session collected and replayed | M5 | Pass (M5) | 2026-10-19 |
| DAY-08 | Real child cancel | Cancel during collection on the VM | No leftover worker process | M5 | Pass (M5) | 2026-10-19 |
| DAY-09 | Real child disconnect / server shutdown | Close the browser tab, or stop Streamlit, during collection on the VM | No orphan child, evidence kept | Manual | pending | — |

### 8. Error handling

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| ERR-01 | Failed collection | Partial, error, interrupt, memory pressure, invalid | Evidence kept, status failed, no retry | `test_live_demo.py::test_failed_collection_retains_evidence_without_retry` | Pass (U, Linux-only) | 2026-10-19 |
| ERR-02 | Deadline | Linux SIGALRM deadline | Interrupts and restores signal state | `test_live_demo.py::test_deadline_interrupts_and_restores_signal_state` | Pass (U, Linux-only) | 2026-10-19 |
| ERR-03 | Attempt-cap message | Worker reports cap | Plain words, no raw exception name | `test_tolerant_collection.py::test_dashboard_failure_message_is_plain_words` | Pass (W, U) | 2026-10-19 |
| ERR-04 | Missing evidence | Archive removed | Visible error, nothing invented | `test_daybreak_app.py::test_missing_evidence_is_an_error_without_invented_replacement` | Pass (W, U) | 2026-10-19 |
| ERR-05 | Ctrl+C | Interrupt replay | Partial summary, no completion claim, exit 130 | `test_governorlab.py::test_ctrl_c_reports_partial_replay_without_completion_claim` | Pass (W, U) | 2026-10-19 |
| ERR-06 | Bad CLI options | `--samples` without `--live`, out of range, conflicting sources | Exit 2 before collection | `test_shared_sessions.py::test_cli_rejects_invalid_sample_options_before_collection` | Pass (W, U) | 2026-10-19 |
| ERR-07 | Launcher safeguards | Declined confirmation, low memory, lock held, swapping | Collector never runs | `test_safe_launcher.py` | Pass (U, Linux-only) | 2026-10-19 |

### 9. Evidence and provenance

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| EVD-01 | Archive integrity | Tampered archive file | Rejected | `test_presentation_adapter.py::test_archive_tampering_is_rejected` | Pass (W, U) | 2026-10-19 |
| EVD-02 | Five-policy comparison | Recompute all traces and summaries | All five match the archive | `test_daybreak_data.py::test_comparison_contains_all_five_verified_archived_policies` | Pass (W, U) | 2026-10-19 |
| EVD-03 | Recorded vs simulated separation | Load archived Linux observations | No simulated decision fields | `test_presentation_adapter.py::test_recorded_linux_observations_have_no_synthetic_decision_fields` | Pass (W, U) | 2026-10-19 |
| EVD-04 | Sensitivity archive | Verify hashes and regenerate | Byte-identical CSV and summary | `test_sensitivity.py::test_committed_evidence_verifies_and_regenerates_identically` | Pass (W, U) | 2026-10-19 |

### 10. Benchmarks

| ID | Feature | Input or action | Expected result | How to run | Result | Date |
|---|---|---|---|---|---|---|
| BEN-01 | Baselines | Run all baselines on one trace | Valid frequencies; ours never above performance | `test_baselines.py` | Pass (W, U) | 2026-10-19 |
| BEN-02 | Energy summary | Known rows | Modelled energy matches manual total | `test_baselines.py::test_summarize_computes_energy_and_matches_manual_totals` | Pass (W, U) | 2026-10-19 |
| BEN-03 | K sweep known answers | Burst shorter than K; clean phases | Burst suppressed; lag = K - 1 ticks | `test_sensitivity.py` | Pass (W, U) | 2026-10-19 |
| BEN-04 | Overhead tool logic | Fake clock and /proc, 12 % overshoot, failing run, runaway | Completes with ratio 1.12; failure recorded and plan continues; guard stops runaway | `test_overhead.py` | Pass (W, U2) | 2026-10-19 |
| BEN-05 | Overhead smoke on VM | `--smoke` | Per-tick CPU recorded | M3 | Recorded: about 0.3-0.8 ms CPU per tick (single 5 s runs, quantized) | 2026-10-19 |
| BEN-06 | Overhead full plan on VM | `benchmark.overhead` (4 intervals x 60 s x 3) | Net cost with median and spread; VM timer overshoot table | M4 | Pass (M4): 24/24 runs ok; see the overhead results below | 2026-10-19 |
| BEN-07 | schedutil-style approximation | 1.25 x util x fmax rounded up; optional I/O-wake boost | Rounds up to the ladder; boost starts at fmin and doubles | `test_closed_loop.py::test_schedutil_style_rounds_up_and_boosts_on_io` | Pass (W); an approximation, not the kernel governor | 2026-10-19 |
| BEN-09 | Closed-loop model physics | CPU-only and I/O-only units at fmax and fmin; insensitive fraction | CPU work stretches by fmax/f (or s + (1-s) fmax/f); I/O waits do not; slowing raises observed utilization | `test_closed_loop.py` (physics tests) | Pass (W) | 2026-10-19 |
| BEN-10 | Closed-loop policies | performance, powersave, ours K=1/3/5, ramp-down, fast-up/slow-down, adaptive K | Each behaves as specified on noise-free scenarios | `test_closed_loop.py` (policy tests) | Pass (W) | 2026-10-19 |
| BEN-11 | Closed-loop evidence | Verify hashes; regenerate CSVs and summary | Byte-identical; same seed gives identical results | `test_closed_loop.py::test_committed_evidence_verifies_and_regenerates_identically` | Pass (W) | 2026-10-19 |
| BEN-12 | Static-frequency baselines | One constant policy per ladder level | Applied frequency never changes; 5.1 GHz equals performance and 3.8 GHz equals powersave | `test_pareto.py::test_static_levels_are_constant` and `::test_extreme_static_levels_match_performance_and_powersave` | Pass (W) | 2026-10-19 |
| BEN-13 | Pareto dominance logic | Hand-made energy/time points, including ties | Correct dominance, frontier and best no-slower static level | `test_pareto.py::test_dominance_and_frontier_on_hand_made_points` and `::test_static_comparison_picks_lowest_energy_no_slower_level` | Pass (W) | 2026-10-19 |
| BEN-14 | I/O-target ablation | Our K=3 policy with I/O and mixed target fractions changed | Default targets reproduce ours_k3; I/O and mixed 1.0 behave like performance; lower I/O target trades time for energy | `test_pareto.py` (ablation tests) | Pass (W) | 2026-10-19 |
| BEN-15 | Phase 2b evidence | Verify hashes; regenerate CSVs and summary | Byte-identical | `test_pareto.py::test_committed_evidence_verifies_and_regenerates_identically` | Pass (W) | 2026-10-19 |
| BEN-08 | Measured energy / completion time | Native hardware with energy counters or a meter | — | Not possible on the VM | pending | — |

## Overhead results (M4, measured process CPU time on the Ubuntu VM)

Net = governor minus a sleep-only control, paired per repetition. CPU % of one core is
derived as mean ms per tick / (interval s x 1000) x 100 at the nominal tick rate.

| Interval | Net CPU ms per tick (mean) | Net CPU % of one core (derived) | Net CPU-s per hour (derived) |
|---|---|---|---|
| 0.5 s | 0.5988 | 0.1198 | 4.312 |
| 1 s | 0.6168 | 0.0617 | 2.221 |
| 2 s | 0.5483 | 0.0274 | 0.987 |
| 5 s | 0.5861 | 0.0117 | 0.422 |

Governor resident memory: median about 17,700 KiB (17.3 MiB), the same as the control.
Net wake-ups per second: medians between -0.180 and 0.001, i.e. no measurable difference.

VM timer overshoot in the same run: the 0.5 s governor runs took a median 1.57 times
their planned time (range 1.05 to 1.72); the other medians were 1.0014 to 1.0845, with
single runs up to 1.38 (0.5 s control) and 1.35 (1 s governor); single sleeps overshot by
up to 3.21 s; the 5 s runs were about 1.001 (12 ticks each). Because ticks
ran slower than planned, the derived percentages are upper bounds.

Caveats: this is process CPU time, not electrical power; it was measured inside a VM;
it excludes CSV logging and the terminal/dashboard UI. The output files, provenance,
hashes and full per-tick tables are archived in
[`evidence/phase1b_overhead/`](../evidence/phase1b_overhead/README.md) and checked by
`tests/test_overhead_evidence.py`.

## Still pending

- Disconnect and server-shutdown handling with a real dashboard child (DAY-09).
- A real attempt-cap failure on the VM (TOL-08).
- Classifier accuracy on labelled workloads (CLS-05).
- Measured energy, completion time and real DVFS (BEN-08, ACT-05).

Known issue: `tests/test_safe_launcher.py` can time out (exit code 124) when the VM is
loaded (U2: 9 failures at load average 3 to 4, all passing on a clean re-run). Run the full
suite on a quiet VM, or re-run that file on its own before treating a failure as real.

## How to reproduce

From the repository root.

Windows portable suite:

```powershell
.\.venv\Scripts\python.exe -B -m pytest tests/ -q -p no:cacheprovider --ignore=tests/test_background_launcher.py --ignore=tests/test_collection.py --ignore=tests/test_cpu_timing.py --ignore=tests/test_safe_launcher.py --ignore=tests/test_live_demo.py
.\.venv\Scripts\python.exe -B -m pytest tests/test_live_demo.py -q -p no:cacheprovider -k "live_adapter or live_cli_is_opt_in or three_consecutive_fixture"
```

Ubuntu full suite (after the start-of-session Git sync):

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/mpl timeout 240s .venv/bin/python -B -m pytest tests/ -q -p no:cacheprovider
```

Manual VM checks (background only, no generated load):

```bash
.venv/bin/python -m governorlab --live --samples 5 --plain
.venv/bin/python -m governorlab --live --samples 5 --strict --plain
.venv/bin/python -m governorlab --session latest --plain --instant
.venv/bin/python -m benchmark.overhead --smoke
```

Linux-only test modules (need `fcntl`, `/proc` or SIGALRM): `test_background_launcher.py`,
`test_collection.py`, `test_cpu_timing.py`, `test_safe_launcher.py`, and 16 of the 22
cases in `test_live_demo.py`.
