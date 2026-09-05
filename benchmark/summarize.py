"""Aggregate one governor's run into the numbers that actually go in charts.

Per-tick estimated watts is not the benchmark metric - joules over the whole
run is. This is the only place estimate_energy_j gets called.
"""
from collections import Counter

from power_model.estimate import estimate_energy_j


def summarize(rows, interval_s=1.0):
    """rows: the list from governor.run(). Returns one flat dict of metrics."""
    n = len(rows)
    if n == 0:
        return {"ticks": 0}

    total_energy_j = sum(estimate_energy_j(r["est_power_w"], interval_s) for r in rows)
    mean_freq_khz = sum(r["target_khz"] for r in rows) / n
    freq_changes = sum(1 for a, b in zip(rows, rows[1:]) if a["target_khz"] != b["target_khz"])
    class_dist = dict(Counter(r["workload_class"] for r in rows))

    return {
        "ticks": n,
        "total_energy_j": round(total_energy_j, 3),
        "mean_freq_khz": round(mean_freq_khz, 1),
        "mean_power_w": round(total_energy_j / (n * interval_s), 3),
        "freq_change_count": freq_changes,
        "class_distribution": class_dist,
    }


def compare_table(results, interval_s=1.0):
    """results: {governor_name: rows}. Returns {governor_name: summary_dict},
    plus prints a plain-text table - good enough for a quick terminal check;
    analysis/plots.py is the real chart-producing path.
    """
    summaries = {name: summarize(rows, interval_s) for name, rows in results.items()}

    header = f"{'governor':<14}{'ticks':>7}{'energy(J)':>12}{'mean freq':>12}{'changes':>9}"
    print(header)
    print("-" * len(header))
    for name, s in summaries.items():
        print(f"{name:<14}{s['ticks']:>7}{s['total_energy_j']:>12.2f}"
              f"{s['mean_freq_khz']:>12.0f}{s['freq_change_count']:>9}")

    return summaries
