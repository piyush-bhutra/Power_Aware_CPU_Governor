"""Module 7 - Analysis charts over benchmark.compare / benchmark.summarize output.

Every power/energy axis says "estimated" - nothing here is measured (PRD S4).
"""
import matplotlib

matplotlib.use("Agg")  # file output only - no display in a VM or under pytest
import matplotlib.pyplot as plt
import pandas as pd


def _save(ax, output_path):
    if ax.get_legend():  # outside the axes, so it never covers a line or bar
        ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0))
    ax.figure.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(ax.figure)


def plot_energy_comparison(summaries, output_path):
    """Bar chart of total_energy_j per governor. summaries: {name: summarize() dict}."""
    energy = pd.Series({name: s["total_energy_j"] for name, s in summaries.items()})
    ax = energy.plot.bar(rot=0, figsize=(7, 4))
    ax.set(title="Total energy per governor (ESTIMATED)",
           xlabel="governor", ylabel="estimated energy (J)")
    _save(ax, output_path)


def plot_frequency_timeline(results, output_path):
    """target_khz over tick index, one line per governor. results: {name: run() rows}."""
    # Series, not lists, so governors with different run lengths still align by tick.
    freqs = pd.DataFrame({name: pd.Series([r["target_khz"] for r in rows])
                          for name, rows in results.items()})
    # steps-post: frequency holds for the whole tick, it doesn't ramp between ticks
    ax = freqs.plot(drawstyle="steps-post", figsize=(9, 4))
    ax.set(title="Target frequency over time",
           xlabel="tick", ylabel="target frequency (kHz)")
    _save(ax, output_path)


def plot_class_distribution(summaries, output_path):
    """Stacked bar of workload_class counts per governor.

    On a synthetic replay every governor sees an identical trace, and
    classify() reads only the signals, never the chosen frequency - so the
    bars are identical by construction. Only meaningful on real stress-ng
    runs, where a lower frequency stretches CPU-bound work over more ticks.

    Do not include this chart in the report until it's generated from
    real stress-ng traces - identical bars on synthetic data could be
    misread as "the governors behave identically," which isn't a real
    finding here.
    """
    dist = pd.DataFrame.from_dict(
        {name: s["class_distribution"] for name, s in summaries.items()},
        orient="index").fillna(0)
    ax = dist.plot.bar(stacked=True, rot=0, figsize=(7, 4))
    ax.set(title="Workload classification per governor",
           xlabel="governor", ylabel="ticks")
    _save(ax, output_path)
