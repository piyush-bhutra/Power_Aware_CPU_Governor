"""Live opt-in lifecycle with recorded fixtures: tests never sample Linux."""
import csv
import io
import json
from pathlib import Path
import signal

import pytest

from governorlab import app
from presentation import adapter


def fixture_rows():
    # Use the current loader to interpret numbers, retaining all raw columns.
    return adapter.load_csv(adapter.LINUX_ARCHIVE / 'validated_trace.csv', 'linux_recorded')


def test_live_adapter_classifies_measured_features_and_uses_stateful_policy(monkeypatch):
    from classifier.rules import classify
    from setter import freq_setter
    rows = fixture_rows()
    seen = []
    def observed(features):
        seen.append(dict(features))
        return classify(features)
    monkeypatch.setattr(adapter, 'classify', observed, raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError('hardware selection/write')
    monkeypatch.setattr(freq_setter, 'open_setter', forbidden)
    monkeypatch.setattr(freq_setter, '_write', forbidden)
    data = adapter.process_live_observations(rows, {'csv_path': 'fixture.csv'})
    assert len(seen) == 5
    required = {'util_pct', 'iowait_pct', 'ctxt_per_s', 'procs_running', 'procs_blocked'}
    assert all(set(features) == required for features in seen)
    assert seen == [{key: row[key] for key in required} for row in rows]
    assert [f.predicted_class for f in data.frames] == [classify(row) for row in rows]
    assert [f.streak for f in data.frames] == [1, 1, 2, 1, 1]
    assert data.frames[0].applied_khz == data.metadata['initial_khz']
    assert all(f.applied_khz == data.metadata['initial_khz'] for f in data.frames)
    assert not any(f.transition for f in data.frames)
    assert data.metadata['frequency_control'] == 'simulated'
    assert rows[0]['freq_khz'] is None


@pytest.mark.parametrize('key,value', [('ctxt_per_s', None), ('procs_blocked', None),
                                      ('util_pct', float('nan'))])
def test_live_adapter_rejects_missing_or_nonfinite_inputs(key, value):
    rows = fixture_rows()
    if value is None:
        del rows[0][key]
    else:
        rows[0][key] = value
    with pytest.raises(ValueError, match='measured feature'):
        adapter.process_live_observations(rows, {'csv_path': 'fixture.csv'})


@pytest.fixture
def collector(monkeypatch):
    from governorlab import live
    initial = {'mem_available_kib': 2_000_000, 'swap_used_kib': 1000}
    monkeypatch.setattr(live, 'resources', lambda: dict(initial))
    monkeypatch.setattr(live, 'expected_jiffies', lambda: 400)
    def sample(interval, count, *, observer):
        assert (interval, count) == (1.0, 8)  # tolerant default: 5 samples, up to 8 attempts
        observer({'event': 'baseline', 'raw': {'fixture': True}})
        for n, row in enumerate(fixture_rows(), 1):
            observer({'event': 'interval', 'attempt': n, 'valid': True})
            yield row
    monkeypatch.setattr(live, 'sample', sample)
    return live


def test_collection_persists_validated_raw_measurements_and_decisions(collector, tmp_path):
    progress = []
    data = collector.collect_live(tmp_path, progress.append)
    assert progress == [0, 1, 2, 3, 4, 5]
    output = Path(data.metadata['csv_path']).parent
    assert len(list(csv.DictReader((output / 'capture.csv').open()))) == 5
    assert len((output / 'raw_events.jsonl').read_text().splitlines()) == 6
    metadata = json.loads((output / 'metadata.json').read_text())
    assert metadata['status'] == 'validated'
    assert metadata['actual_sample_count'] == 5
    assert metadata['observation_source'] == 'linux_proc_stat'
    assert len(metadata['observed_intervals_s']) == 5
    assert metadata['source_sha256']
    assert len(json.loads((output / 'decisions.json').read_text())) == 5
    second = collector.collect_live(tmp_path, lambda n: None)
    assert second.metadata['csv_path'] != data.metadata['csv_path']


@pytest.mark.parametrize('failure', ['partial', 'error', 'interrupt', 'pressure', 'invalid'])
def test_failed_collection_retains_evidence_without_retry(collector, monkeypatch, tmp_path, failure):
    calls = []
    def sample(interval, count, *, observer):
        calls.append(count)
        yield fixture_rows()[0]
        if failure == 'error':
            raise OSError('read failed')
        if failure == 'interrupt':
            raise KeyboardInterrupt
        if failure == 'invalid':
            row = fixture_rows()[1]
            row['elapsed_s'] = 3
            yield row
    monkeypatch.setattr(collector, 'sample', sample)
    if failure == 'pressure':
        reads = iter([{'mem_available_kib': 2_000_000, 'swap_used_kib': 1000},
                      {'mem_available_kib': 1, 'swap_used_kib': 1000}])
        monkeypatch.setattr(collector, 'resources', lambda: next(reads))
    with pytest.raises((ValueError, RuntimeError, OSError, KeyboardInterrupt)):
        collector.collect_live(tmp_path, lambda n: None)
    assert calls == [8]  # one sampler call with the tolerant attempt cap, never a retry
    folders = list(tmp_path.iterdir())
    assert len(folders) == 1
    metadata = json.loads((folders[0] / 'metadata.json').read_text())
    assert metadata['status'] in ('failed', 'interrupted')
    assert metadata['actual_sample_count'] <= 1
    assert metadata['error']
    assert not (folders[0] / 'decisions.json').exists()


def test_deadline_interrupts_and_restores_signal_state():
    from governorlab.live import collection_deadline
    before = signal.getsignal(signal.SIGALRM)
    with pytest.raises(TimeoutError, match='timeout'):
        with collection_deadline(0.01):
            signal.pause()
    assert signal.getsignal(signal.SIGALRM) == before
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_live_cli_is_opt_in_and_rejects_conflicting_sources(monkeypatch):
    from governorlab import live
    def forbidden(*args, **kwargs):
        raise AssertionError('sampling without live opt-in')
    monkeypatch.setattr(live, 'collect_live', forbidden)
    assert app.main(['--plain', '--instant'], io.StringIO()) == 0
    assert app.main(['--recorded-linux', '--plain', '--instant'], io.StringIO()) == 0
    assert app.main(['--live', '--recorded-linux'], io.StringIO()) == 2
    assert app.main(['--live', '--visual'], io.StringIO()) == 2


def test_live_cli_automatically_replays_and_summarizes(collector, monkeypatch, tmp_path):
    original = collector.collect_live
    monkeypatch.setattr(collector, 'collect_live', lambda progress, count=5, strict=False: original(tmp_path, progress))
    output = io.StringIO()
    assert app.main(['--live', '--plain', '--instant'], output) == 0
    text = output.getvalue()
    for expected in ('Collecting Linux samples: 5/5', 'LIVE LINUX OBSERVATION',
                     'SIMULATED GOVERNOR DECISIONS', 'LIVE SESSION COMPLETE',
                     '0 simulated transitions', 'Measured Linux', 'Predicted classes',
                     'unavailable', 'candidate='):
        assert expected in text


def test_live_rich_fits_80x24_and_restores_cursor(collector, monkeypatch, tmp_path):
    from rich.console import Console
    class TerminalStream(io.StringIO):
        encoding = 'utf-8'
        def isatty(self):
            return True
    original = collector.collect_live
    data = original(tmp_path, lambda n: None)
    console = Console(width=80, height=24, file=io.StringIO())
    assert len(console.render_lines(app.rich_frame(data, data.frames, compact=True), console.options)) <= 24
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    monkeypatch.setenv('TERM', 'xterm-256color')
    monkeypatch.setattr(collector, 'collect_live', lambda progress, count=5, strict=False: data)
    output = TerminalStream()
    assert app.main(['--live', '--visual', '--instant'], output) == 0
    assert 'FINAL SUMMARY' in output.getvalue()
    assert '\x1b[?25h' in output.getvalue()


def test_three_consecutive_fixture_classes_apply_at_third_tick():
    rows = fixture_rows()
    for row in rows:
        row['procs_running'] = 1  # explicit unit fixture, never saved as real evidence
    data = adapter.process_live_observations(rows, {'csv_path': 'unit-fixture.csv'})
    assert [f.predicted_class for f in data.frames] == ['idle'] * 5
    assert [f.streak for f in data.frames] == [1, 2, 3, 4, 5]
    assert data.frames[0].candidate_khz < data.frames[0].applied_khz
    assert [f.tick for f in data.frames if f.transition] == [3]
    assert data.frames[2].candidate_khz == data.frames[2].applied_khz


def test_collection_interrupt_reports_preserved_evidence(collector, monkeypatch, tmp_path):
    def interrupted(interval, count, *, observer):
        yield fixture_rows()[0]
        raise KeyboardInterrupt
    monkeypatch.setattr(collector, 'sample', interrupted)
    original = collector.collect_live
    monkeypatch.setattr(collector, 'collect_live', lambda progress, count=5, strict=False: original(tmp_path, progress))
    output = io.StringIO()
    assert app.main(['--live', '--plain'], output) == 130
    assert 'evidence retained at' in output.getvalue()
    assert 'LIVE SESSION COMPLETE' not in output.getvalue()


def test_deadline_preserves_existing_alarm():
    from governorlab.live import collection_deadline
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        with pytest.raises(RuntimeError, match='existing alarm'):
            with collection_deadline():
                pytest.fail('must not enter')
        assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


def test_live_collection_never_spawns_workers_or_selects_hardware(collector, monkeypatch, tmp_path):
    import subprocess
    from setter import freq_setter
    def forbidden(*args, **kwargs):
        raise AssertionError('unexpected worker or hardware operation')
    for name in ('open_setter', 'SysfsSetter', '_write', '_read', 'available_freqs_khz'):
        monkeypatch.setattr(freq_setter, name, forbidden)
    monkeypatch.setattr(subprocess, 'Popen', forbidden)
    assert len(collector.collect_live(tmp_path, lambda n: None).frames) == 5


def test_raw_counter_mismatch_is_rejected_before_policy(collector, monkeypatch, tmp_path):
    def sample(interval, count, *, observer):
        for row in fixture_rows():
            row['util_pct'] += 1
            yield row
    monkeypatch.setattr(collector, 'sample', sample)
    with pytest.raises(ValueError, match='raw counters'):
        collector.collect_live(tmp_path, lambda n: None)
    assert not any(tmp_path.glob('*/decisions.json'))


def test_sampling_iterator_closes_on_pressure_failure(collector, monkeypatch, tmp_path):
    closed = []
    def sample(interval, count, *, observer):
        try:
            yield fixture_rows()[0]
        finally:
            closed.append(True)
    def failed(*args):
        raise RuntimeError('pressure')
    monkeypatch.setattr(collector, 'sample', sample)
    original = collector.check_resources
    calls = []
    def check(current, initial):
        calls.append(True)
        if len(calls) > 1:
            failed()
        original(current, initial)
    monkeypatch.setattr(collector, 'check_resources', check)
    with pytest.raises(RuntimeError, match='pressure'):
        collector.collect_live(tmp_path, lambda n: None)
    assert closed == [True]


def test_live_playback_interrupt_restores_rich_cursor(collector, monkeypatch, tmp_path):
    class TerminalStream(io.StringIO):
        encoding = 'utf-8'
        def isatty(self):
            return True
    data = collector.collect_live(tmp_path, lambda n: None)
    monkeypatch.setattr(collector, 'collect_live', lambda progress, count=5, strict=False: data)
    def interrupted(frames, **kwargs):
        yield frames[0]
        raise KeyboardInterrupt
    monkeypatch.setattr(app, 'playback', interrupted)
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '24')
    monkeypatch.setenv('TERM', 'xterm-256color')
    output = TerminalStream()
    assert app.main(['--live', '--visual'], output) == 130
    assert 'INTERRUPTED' in output.getvalue()
    assert 'LIVE SESSION COMPLETE' not in output.getvalue()
    assert '\x1b[?25h' in output.getvalue()


def test_errno_read_failure_prints_preserved_evidence_path(collector, monkeypatch, tmp_path):
    def failed(interval, count, *, observer):
        yield fixture_rows()[0]
        raise OSError(5, 'read failed', '/proc/stat')
    monkeypatch.setattr(collector, 'sample', failed)
    original = collector.collect_live
    monkeypatch.setattr(collector, 'collect_live', lambda progress, count=5, strict=False: original(tmp_path, progress))
    output = io.StringIO()
    assert app.main(['--live', '--plain'], output) == 1
    assert 'evidence retained at' in output.getvalue()
    assert str(tmp_path) in output.getvalue()
