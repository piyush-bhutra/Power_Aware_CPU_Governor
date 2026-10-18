"""Known-answer checks for benchmark.sensitivity (synthetic, deterministic, portable)."""
import json
from pathlib import Path

import pytest

from benchmark import sensitivity as s
from presentation.adapter import SYNTHETIC_ARCHIVE

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence' / 'phase1b_sensitivity'


def clean(plan, k, seed=0):
    scenario = dict(plan=plan, seed=seed, noise=0.0)
    return s.evaluate(s.replay(scenario, k), plan)


def test_archived_scenario_at_k3_matches_archive():
    rows = s.replay(s.SCENARIOS['archived_seed11'], 3)
    changes = [i for i, (a, b) in enumerate(zip(rows, rows[1:]), 2) if a['target_khz'] != b['target_khz']]
    assert changes == [13, 23, 29]
    archived = json.loads((SYNTHETIC_ARCHIVE / 'summaries.json').read_text())['ours']
    metrics = s.evaluate(rows, s.ARCHIVED_PLAN)
    assert metrics['energy_j'] == archived['total_energy_j']
    assert metrics['transitions'] == archived['freq_change_count'] == 3
    assert metrics['mean_lag_ticks'] == 2.0  # K - 1 ticks after each true change


@pytest.mark.parametrize('k', [2, 3, 5])
def test_burst_shorter_than_k_is_suppressed_and_longer_reacts(k):
    short = [('idle', 10), ('cpu', k - 1), ('idle', 10)]
    long = [('idle', 10), ('cpu', k), ('idle', 10)]
    assert clean(short, k)['bursts_suppressed'] == 1
    assert clean(long, k)['bursts_suppressed'] == 0


@pytest.mark.parametrize('k', [1, 2, 4, 6])
def test_lag_is_k_minus_one_on_clean_phases(k):
    metrics = clean([('cpu', 10), ('idle', 10), ('mixed', 10)], k)
    assert metrics['mean_lag_ticks'] == k - 1 and metrics['unserved_changes'] == 0
    assert metrics['frac_at_appropriate'] == pytest.approx((30 - 2 * (k - 1) - 0) / 30, abs=1e-4)


def test_phase_already_at_target_needs_no_change():
    # Starts at max, so the first CPU phase and a CPU phase after a suppressed idle dip need no change.
    metrics = clean([('cpu', 8), ('idle', 2), ('cpu', 8)], 3)
    assert metrics['bursts_suppressed'] == 1 and metrics['sustained_changes'] == 0
    assert metrics['transitions'] == 0


def test_flapping_is_fully_suppressed_from_k3():
    table, _ = s.k_sweep()
    flapping = {row['k']: row for row in table if row['scenario'] == 'flapping_cpu_idle_seed61'}
    assert flapping[1]['transitions'] == 19
    assert all(flapping[k]['transitions'] == 0 for k in s.K_VALUES if k >= 3)


def test_k_sweep_covers_every_scenario_and_k():
    table, _ = s.k_sweep()
    assert len(table) == len(s.SCENARIOS) * len(s.K_VALUES)
    assert all(0 <= row['frac_at_appropriate'] <= 1 for row in table)


def test_fine_timeline_windows_see_the_same_workload():
    snapshots, truth = s.fine_snapshots()
    total_s = sum(seconds for _, seconds in s.FINE_TIMELINE)
    assert len(truth) == round(total_s / s.FINE_DT)
    for interval in s.INTERVALS:
        sigs = s.window_signals(snapshots, interval)
        assert len(sigs) == int(len(truth) // round(interval / s.FINE_DT))
        assert all(sig['elapsed_s'] == interval for sig in sigs)
    # Busy jiffies over the first 10 s are identical whichever window size reads them.
    one = s.window_signals(snapshots[:101], 1.0)
    five = s.window_signals(snapshots[:101], 5.0)
    busy = lambda sigs: sum(x['util_pct'] / 100 * x['delta_total_jiffies'] for x in sigs)
    assert busy(one) == pytest.approx(busy(five))


def test_longer_intervals_miss_more_bursts_and_lag_more():
    table, bursts = s.interval_sweep()
    missed = [row['bursts_missed'] for row in table]
    assert missed == sorted(missed)
    lags = [row['mean_class_lag_s'] for row in table]
    assert lags == sorted(lags)
    detected = {(b['interval_s'], b['burst_len_s']): b['detected'] for b in bursts}
    assert detected[(0.5, 0.3)] == 0 and detected[(0.5, 5.0)] == 1 and detected[(5.0, 5.0)] == 0


def test_archived_generator_untouched():
    provenance = json.loads((SYNTHETIC_ARCHIVE / 'PROVENANCE.json').read_text())
    import hashlib
    current = hashlib.sha256((ROOT / 'monitor/synthetic.py').read_bytes().replace(b'\r\n', b'\n')).hexdigest()
    assert current == provenance['source_hashes']['monitor/synthetic.py']


def test_refuses_existing_outputs(tmp_path):
    (tmp_path / 'k_sweep.csv').write_text('x')
    with pytest.raises(SystemExit):
        s.main(['--outdir', str(tmp_path)])
