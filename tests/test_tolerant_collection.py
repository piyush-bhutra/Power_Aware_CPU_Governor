"""Phase 1A.1: tolerant live collection with full disclosure. Fake samplers only; nothing reads /proc."""
from contextlib import nullcontext
from dataclasses import asdict
import io
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

import pytest

from presentation import adapter, sessions

ARCHIVE_ROWS = adapter.load_csv(adapter.LINUX_ARCHIVE / 'validated_trace.csv', 'linux_recorded')
MARKER_UTIL = 77.7  # only ever present on rows that must be discarded


def row(n, kind='ok'):
    out = dict(ARCHIVE_ROWS[n % 5])
    out['timestamp'] += 10 * n
    if kind == 'slow':
        out.update(elapsed_s=2.6, util_pct=MARKER_UTIL)
    elif kind == 'fast':
        out.update(elapsed_s=0.3, util_pct=MARKER_UTIL)
    elif kind == 'ratio':
        out.update(delta_total_jiffies=float(out['delta_total_jiffies']) * 3, util_pct=MARKER_UTIL)
    return out


@pytest.fixture
def live(monkeypatch):
    from governorlab import live
    monkeypatch.setattr(live, 'resources', lambda: {'mem_available_kib': 2_000_000, 'swap_used_kib': 1000})
    monkeypatch.setattr(live, 'expected_jiffies', lambda: 400)
    monkeypatch.setattr(live, 'sys', SimpleNamespace(platform='linux'))
    live.deadlines = []
    monkeypatch.setattr(live, 'collection_deadline', lambda seconds: live.deadlines.append(seconds) or nullcontext())
    original = Path.is_file
    monkeypatch.setattr(Path, 'is_file', lambda self: self.as_posix() == '/proc/stat' or original(self))
    return live


def use_plan(live, monkeypatch, plan):
    """plan: one entry per attempt: 'ok', 'slow', 'fast', 'ratio' or 'invalid' (no row yielded)."""
    calls = []
    def sample(interval, count, *, observer):
        calls.append(count)
        observer({'event': 'baseline'})
        for attempt, kind in enumerate(plan[:count], 1):
            observer({'event': 'interval', 'attempt': attempt, 'valid': kind != 'invalid',
                      'elapsed_s': row(attempt, kind)['elapsed_s']})
            if kind != 'invalid':
                yield row(attempt, kind)
    monkeypatch.setattr(live, 'sample', sample)
    return calls


@pytest.mark.parametrize('plan, discarded', [
    (['slow', 'ok', 'ok', 'ok', 'ok', 'ok'], {1: 'elapsed_out_of_range'}),
    (['ok', 'ok', 'ratio', 'ok', 'ok', 'ok'], {3: 'jiffy_ratio_out_of_range'}),
    (['ok', 'invalid', 'ok', 'ok', 'ok', 'ok'], {2: 'invalid_counter_interval'}),
    (['ok', 'ok', 'ok', 'ok', 'fast', 'slow', 'ok'], {5: 'elapsed_out_of_range', 6: 'elapsed_out_of_range'}),
    (['ratio', 'ok', 'slow', 'ok', 'invalid', 'ok', 'ok', 'ok'],
     {1: 'jiffy_ratio_out_of_range', 3: 'elapsed_out_of_range', 5: 'invalid_counter_interval'}),
])
def test_anomalies_are_discarded_recorded_and_count_is_reached(live, monkeypatch, tmp_path, plan, discarded):
    calls = use_plan(live, monkeypatch, plan)
    seen = []
    original = adapter.classify
    monkeypatch.setattr(adapter, 'classify', lambda features: seen.append(features['util_pct']) or original(features))
    data = live.collect_live(tmp_path, count=5)
    folder = Path(data.metadata['csv_path']).parent
    assert calls == [8] and live.deadlines == [18]
    assert len(data.frames) == 5 and len(seen) == 5 and MARKER_UTIL not in seen  # classifier/policy never saw them
    meta = json.loads((folder / 'metadata.json').read_text())
    assert {d['attempt']: d['reason'] for d in meta['discarded_attempts']} == discarded
    assert meta['timing_quality'] == 'degraded' and meta['status'] == 'validated'
    assert meta['attempts_made'] == 5 + len(discarded)
    assert meta['kept_attempt_indices'] == [a for a in range(1, meta['attempts_made'] + 1) if a not in discarded]
    assert all(set(d) == {'attempt', 'reason', 'elapsed_s', 'ratio'} for d in meta['discarded_attempts'])
    events = [json.loads(line) for line in (folder / 'raw_events.jsonl').read_text().splitlines()]
    assert [e['attempt'] for e in events if e['event'] == 'discarded'] == sorted(discarded)
    loaded = sessions.load_session(folder)
    banner = sessions.timing_banner(loaded.metadata)
    assert banner.startswith(f'{len(discarded)} intervals discarded because of VM timing anomalies')


def test_clean_run_stops_at_count(live, monkeypatch, tmp_path):
    use_plan(live, monkeypatch, ['ok'] * 8)
    data = live.collect_live(tmp_path, count=5)
    assert data.metadata['timing_quality'] == 'clean' and data.metadata['attempts_made'] == 5
    assert sessions.timing_banner(data.metadata) is None


def test_attempt_cap_fails_and_retains_evidence(live, monkeypatch, tmp_path):
    use_plan(live, monkeypatch, ['ok', 'slow', 'ok', 'ratio', 'slow', 'ok', 'slow', 'ok', 'ok'])
    with pytest.raises(live.AttemptCapExceeded, match='4 of 5 valid samples after 8 attempts') as caught:
        live.collect_live(tmp_path, count=5)
    folder = Path(caught.value.live_evidence)
    meta = json.loads((folder / 'metadata.json').read_text())
    assert meta['status'] == 'failed' and len(meta['discarded_attempts']) == 4
    assert (folder / 'capture.csv').exists() and (folder / 'raw_events.jsonl').exists()
    assert not (folder / 'decisions.json').exists() and not (folder / 'session-sha256.json').exists()


def test_cap_formula_for_larger_counts(live, monkeypatch, tmp_path):
    calls = use_plan(live, monkeypatch, ['slow'] * 10 + ['ok'] * 20)
    data = live.collect_live(tmp_path, count=20)  # cap 30: ten discards still leave room
    assert calls == [30] and len(data.frames) == 20 and live.deadlines == [62]


def test_strict_aborts_on_first_timing_anomaly(live, monkeypatch, tmp_path):
    calls = use_plan(live, monkeypatch, ['ok', 'slow', 'ok', 'ok', 'ok', 'ok'])
    with pytest.raises(RuntimeError, match='timing anomaly') as caught:
        live.collect_live(tmp_path, count=5, strict=True)
    assert calls == [5] and live.deadlines == [12]
    assert not isinstance(caught.value, live.AttemptCapExceeded)
    meta = json.loads((Path(caught.value.live_evidence) / 'metadata.json').read_text())
    assert meta['status'] == 'failed' and meta['strict'] is True and meta['actual_sample_count'] == 1


def test_strict_clean_run_matches_phase1a(live, monkeypatch, tmp_path):
    use_plan(live, monkeypatch, ['ok'] * 5)
    data = live.collect_live(tmp_path, count=5, strict=True)
    assert len(data.frames) == 5 and data.metadata['collection_timeout_s'] == 12


def test_real_sampler_rebaselines_after_a_discarded_interval(live, monkeypatch, tmp_path):
    """Drive the unchanged monitor.reader.sample() with a fake clock and counters."""
    from monitor import reader
    gaps = iter([1.0, 2.6, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0])
    clock = {'t': 100.0, 'jiffies': 0}
    def sleep(seconds):
        clock['t'] += next(gaps)
    def read_stat():
        busy = clock['jiffies']
        clock['jiffies'] += 400  # matches the 400 jiffies/s fixture rate per elapsed second
        return dict(user=busy // 4, nice=0, system=0, idle=busy - busy // 4, iowait=0, irq=0, softirq=0,
                    steal=0, guest=0, guest_nice=0, ctxt=busy, procs_running=1, procs_blocked=0)
    stat_values = []
    def counted():
        value = read_stat()
        stat_values.append(value)
        return value
    monkeypatch.setattr(reader, 'read_stat', counted)
    monkeypatch.setattr(reader, 'read_freq_khz', lambda cpu=0: None)
    monkeypatch.setattr(reader, 'time', SimpleNamespace(sleep=sleep, monotonic=lambda: clock['t'],
                                                         time=lambda: clock['t']))
    # Attempt 2 lasts 2.6 s: outside 0.5-2 s, so it is discarded (its jiffy ratio would also be < 0.5).
    data = live.collect_live(tmp_path, count=5)
    meta = data.metadata
    assert [d['attempt'] for d in meta['discarded_attempts']] == [2]
    assert meta['kept_attempt_indices'] == [1, 3, 4, 5, 6]
    rows = adapter.load_csv(Path(meta['csv_path']), 'linux_recorded')
    # The interval after the discarded one starts from the discarded interval's end snapshot.
    assert int(rows[1]['raw_prev_user']) == stat_values[2]['user']


def test_legacy_five_sample_session_loads_as_clean(tmp_path):
    folder = tmp_path / 'live-legacy'
    folder.mkdir()
    shutil.copyfile(adapter.LINUX_ARCHIVE / 'validated_trace.csv', folder / 'capture.csv')
    metadata = dict(status='validated', actual_sample_count=5, requested_attempts=5,
                    workload_label='uncontrolled_background', observation_source='linux_proc_stat',
                    expected_jiffies_per_s=400, csv_path='/old/capture.csv',
                    frequency_control='simulated', generated_load=False)
    data = adapter.process_live_observations(ARCHIVE_ROWS, metadata)
    (folder / 'metadata.json').write_text(json.dumps(metadata))
    (folder / 'decisions.json').write_text(json.dumps([asdict(f) for f in data.frames]))
    loaded = sessions.load_session(folder)
    assert loaded.metadata['timing_quality'] == 'clean' and loaded.metadata['discarded_attempts'] == []
    assert loaded.metadata['kept_attempt_indices'] == [1, 2, 3, 4, 5]
    assert sessions.timing_banner(loaded.metadata) is None


@pytest.fixture
def degraded(live, monkeypatch, tmp_path):
    use_plan(live, monkeypatch, ['ok', 'slow', 'ok', 'ok', 'ratio', 'ok', 'ok'])
    return Path(live.collect_live(tmp_path / 'run', count=5).metadata['csv_path']).parent


@pytest.mark.parametrize('change', [{'timing_quality': 'degraded', 'discarded_attempts': []},
                                    {'attempts_made': 9}, {'kept_attempt_indices': [1, 3, 4, 6, 6]},
                                    {'timing_quality': 'unknown'}])
def test_inconsistent_disclosure_is_rejected(degraded, change):
    path = degraded / 'metadata.json'
    path.write_text(json.dumps({**json.loads(path.read_text()), **change}))
    (degraded / 'session-sha256.json').unlink()
    with pytest.raises(ValueError, match='timing disclosure'):
        sessions.load_session(degraded)


def run_cli(*argv):
    from governorlab import app
    stream = io.StringIO()
    return app.main(list(argv), stream=stream), stream.getvalue()


def test_terminal_replay_shows_banner_and_reasons(degraded):
    code, out = run_cli('--session', str(degraded), '--plain', '--instant')
    assert code == 0, out
    assert out.count('TIMING QUALITY DEGRADED: 2 intervals discarded because of VM timing anomalies') == 2
    assert 'discarded attempt 2: elapsed_out_of_range' in out
    assert 'discarded attempt 5: jiffy_ratio_out_of_range' in out


def test_terminal_strict_flag(monkeypatch):
    from governorlab import live as live_module
    assert run_cli('--strict')[0] == 2
    assert run_cli('--session', 'latest', '--strict')[0] == 2
    seen = []
    def collect(progress, count, strict):
        seen.append(strict)
        raise RuntimeError('fixture stop')
    monkeypatch.setattr(live_module, 'collect_live', collect)
    assert run_cli('--live', '--strict', '--plain')[0] == 1 and seen == [True]
    assert run_cli('--live', '--plain')[0] == 1 and seen == [True, False]


def test_worker_reports_attempt_cap_reason(monkeypatch, tmp_path):
    from daybreak import worker
    from governorlab import live as live_module
    def collect(root, progress, count=5):
        raise live_module.AttemptCapExceeded('Attempt cap reached: 3 of 5')
    monkeypatch.setattr(live_module, 'collect_live', collect)
    monkeypatch.setattr(worker.signal, 'signal', lambda *args: None)
    assert worker.main(['--job', str(tmp_path)]) == 1
    status = json.loads((tmp_path / 'status.json').read_text())
    assert status['reason'] == 'attempt_cap' and status['status'] == 'failed'


def test_dashboard_failure_message_is_plain_words():
    from daybreak.playback_ui import failure_message
    text = failure_message({'status': 'failed', 'reason': 'attempt_cap', 'error': 'AttemptCapExceeded: x',
                            'evidence': '/run/daybreak-x'})
    assert 'VM timing was unstable' in text and 'Close other applications and retry' in text
    assert 'AttemptCapExceeded' not in text and '/run/daybreak-x' in text
    assert failure_message({'status': 'failed', 'error': 'OSError: boom'}) == 'OSError: boom'


def test_dashboard_replay_shows_degraded_banner(degraded, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import daybreak.playback_ui as ui
    monkeypatch.setattr(ui, 'list_sessions', lambda: [degraded])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'daybreak/app.py'), default_timeout=20).run()
    at.selectbox(key='source_choice').set_value(str(degraded.resolve())).run()
    assert not at.exception
    assert any('2 intervals discarded because of VM timing anomalies' in w.value for w in at.warning)
    at.selectbox(key='source_choice').set_value(ui.SYNTHETIC).run()
    assert not any('discarded' in w.value for w in at.warning)
