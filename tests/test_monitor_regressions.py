"""Real counter accounting and elapsed-time regression cases; no live sampling."""
import csv
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from monitor import reader


def snap(**values):
    return {**dict.fromkeys(reader.CPU_FIELDS, 0), 'ctxt': 0,
            'procs_running': 1, 'procs_blocked': 0, **values}


def test_guest_time_is_not_counted_twice():
    result = reader.compute_signals(snap(), snap(user=40, nice=10, idle=50,
                                               guest=20, guest_nice=5), 1)
    assert result['util_pct'] == 50


def test_decreasing_iowait_is_clamped_and_flagged():
    result = reader.compute_signals(snap(iowait=10), snap(user=50, idle=50, iowait=5), 1)
    assert result['util_pct'] == 50
    assert result['iowait_pct'] == 0
    assert result['iowait_decreased'] is True


@pytest.mark.parametrize('field', ['user', 'idle', 'steal', 'ctxt'])
def test_counter_reset_invalidates_interval(field):
    previous = snap(**{field: 100})
    current = snap(**{'user': 60, 'idle': 40, field: 90})
    assert reader.compute_signals(previous, current, 1) is None


@pytest.mark.parametrize('interval', [0, -1, math.nan, math.inf])
def test_invalid_elapsed_time_rejected(interval):
    with pytest.raises(ValueError):
        reader.compute_signals(snap(), snap(user=100), interval)


def test_sample_uses_monotonic_elapsed_and_retains_raw_snapshots(monkeypatch, tmp_path):
    snapshots = iter([snap(user=100, idle=100, ctxt=1000),
                      snap(user=150, idle=150, ctxt=1200)])
    clocks = iter([10.0, 12.0])
    monkeypatch.setattr(reader, 'read_stat', lambda: next(snapshots))
    monkeypatch.setattr(reader.time, 'monotonic', lambda: next(clocks))
    monkeypatch.setattr(reader.time, 'sleep', lambda _: None)
    monkeypatch.setattr(reader, 'read_freq_khz', lambda: None)
    rows = list(reader.sample(1, 1))
    assert rows[0]['ctxt_per_s'] == 100
    assert rows[0]['elapsed_s'] == 2
    assert rows[0]['delta_total_jiffies'] == 100
    path = tmp_path / 'monitor.csv'
    reader.log_csv(path, rows)
    with path.open() as stream:
        row = next(csv.DictReader(stream))
    assert row['raw_prev_ctxt'] == '1000'
    assert row['raw_cur_ctxt'] == '1200'
    assert row['raw_cur_user'] == '150'


def test_appending_incompatible_csv_schema_is_refused(tmp_path):
    path = tmp_path / 'old.csv'
    path.write_text('timestamp,util_pct\n1,50\n')
    with pytest.raises(ValueError, match='header'):
        reader.log_csv(path, [{'timestamp': 2, 'util_pct': 60}])
    assert path.read_text() == 'timestamp,util_pct\n1,50\n'
