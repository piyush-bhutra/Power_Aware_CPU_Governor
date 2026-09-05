"""Tests the project's actual central claim (PRD S17): our governor behaves
differently from ondemand, and specifically better on the case PRD S2 opens
with - an I/O-bound burst that spikes utilization.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark.baselines import Performance, Powersave, Ondemand, Conservative, BASELINES
from benchmark.compare import run_comparison
from benchmark.summarize import summarize
from monitor.synthetic import source as synth

FREQS = [1_000_000, 1_800_000, 2_600_000, 3_400_000]


def _settled(rows, k=3):
    """Drop the first k rows of a segment - the hysteresis lag from whatever
    came before it hasn't cleared yet, so comparing during it is unfair to
    ours (baselines have no lag; that's not the claim being tested here).
    """
    return rows[k:]


def test_ours_matches_performance_on_genuinely_cpu_bound_work():
    # No reason to differ here - clock speed IS the bottleneck, so both should
    # sit at max. If ours were LOWER here, that would be a real performance
    # regression, not a power saving.
    plan = [("cpu", 8)]
    results = run_comparison(lambda: synth(plan, seed=1), FREQS)
    for row in _settled(results["ours"]):
        assert row["target_khz"] == FREQS[-1]
        assert row["target_khz"] == results["performance"][0]["target_khz"]


def test_ours_diverges_from_ondemand_on_an_io_burst():
    # The actual motivating case from PRD S2: an I/O-bound process shows a
    # momentary utilization SPIKE when data arrives, even though it's
    # fundamentally blocked on a device. ondemand only sees the spike (>80%
    # utilization -> max). Ours also sees procs_blocked>0 and a high
    # context-switch rate, correctly stays classified io_bound, and targets
    # a lower frequency. This is the plain "io" profile's high-util sibling -
    # see monitor/synthetic.py's io_burst comment for why "io" alone doesn't
    # exercise this case.
    plan = [("cpu", 6), ("io_burst", 8)]
    results = run_comparison(lambda: synth(plan, seed=11), FREQS)

    ours_burst = _settled(results["ours"][6:])
    ondemand_burst = _settled(results["ondemand"][6:])

    assert all(r["util_pct"] > 80 for r in ours_burst), "test setup: burst must actually spike"
    assert all(r["workload_class"] == "io_bound" for r in ours_burst)
    assert all(o["target_khz"] < d["target_khz"]
               for o, d in zip(ours_burst, ondemand_burst)), (
        "ours should undercut ondemand once the burst's high utilization would "
        "otherwise trigger ondemand's up_threshold"
    )


def test_ours_never_exceeds_performance():
    # Sanity bound: whatever ours does, it should never draw MORE frequency
    # than the always-max baseline - that would indicate a policy bug, not a
    # design tradeoff.
    plan = [("cpu", 6), ("io_burst", 6), ("idle", 6), ("mixed", 6)]
    results = run_comparison(lambda: synth(plan, seed=5), FREQS)
    for o, p in zip(results["ours"], results["performance"]):
        assert o["target_khz"] <= p["target_khz"]


def test_all_baselines_run_and_produce_valid_frequencies():
    # Coverage sanity check, not a behavioural claim: every baseline in the
    # registry runs to completion and only ever picks frequencies from the
    # ladder it was given.
    plan = [("cpu", 4), ("io", 4), ("idle", 4), ("mixed", 4), ("io_burst", 4)]
    results = run_comparison(lambda: synth(plan, seed=3), FREQS)
    assert set(results) == set(BASELINES) | {"ours"}
    for name, rows in results.items():
        assert len(rows) == 20, name
        assert all(r["target_khz"] in FREQS for r in rows), name


def test_summarize_computes_energy_and_matches_manual_totals():
    plan = [("cpu", 5), ("io", 5)]
    results = run_comparison(lambda: synth(plan, seed=2), FREQS)
    rows = results["performance"]  # constant power draw - easiest to hand-check
    s = summarize(rows, interval_s=1.0)
    assert s["ticks"] == 10
    manual_total = sum(r["est_power_w"] * 1.0 for r in rows)
    assert abs(s["total_energy_j"] - manual_total) < 1e-6
    assert s["freq_change_count"] == 0  # performance never changes frequency


def test_summarize_counts_frequency_changes():
    plan = [("cpu", 6), ("io_burst", 8)]
    results = run_comparison(lambda: synth(plan, seed=11), FREQS)
    s = summarize(results["ours"])
    assert s["freq_change_count"] >= 1  # it does drop once the burst settles
    assert s["class_distribution"].get("cpu_bound", 0) > 0
    assert s["class_distribution"].get("io_bound", 0) > 0


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
