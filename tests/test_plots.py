"""Each plot writes a real, non-empty PNG from benchmark.compare output.
Deliberately says nothing about pixel content - only that a chart got written.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.plots import (plot_class_distribution, plot_energy_comparison,
                            plot_frequency_timeline)
from benchmark.compare import run_comparison
from benchmark.summarize import summarize
from monitor.synthetic import source as synth

FREQS = [3_800_000, 4_233_333, 4_666_667, 5_100_000]
PLAN = [("cpu", 6), ("io_burst", 6), ("idle", 4), ("mixed", 4)]


def _comparison():
    results = run_comparison(lambda: synth(PLAN, seed=3), FREQS)
    return results, {name: summarize(rows) for name, rows in results.items()}


def _assert_png(path):
    assert path.exists(), path
    assert path.stat().st_size > 0, path
    assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG"


def test_plot_energy_comparison(tmp_path):
    _, summaries = _comparison()
    out = tmp_path / "energy.png"
    plot_energy_comparison(summaries, out)
    _assert_png(out)


def test_plot_frequency_timeline(tmp_path):
    results, _ = _comparison()
    out = tmp_path / "timeline.png"
    plot_frequency_timeline(results, out)
    _assert_png(out)


def test_plot_class_distribution(tmp_path):
    _, summaries = _comparison()
    out = tmp_path / "classes.png"
    plot_class_distribution(summaries, out)
    _assert_png(out)
