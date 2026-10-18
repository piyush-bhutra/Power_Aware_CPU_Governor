"""Phase 1A: configurable sample count and the shared saved-session store.

All collection here uses recorded fixture rows; nothing samples /proc or spawns a child.
"""
from contextlib import nullcontext
from dataclasses import replace
import importlib
import io
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace

import pytest

from presentation import adapter, sessions

ARCHIVE_ROWS = adapter.load_csv(adapter.LINUX_ARCHIVE / 'validated_trace.csv', 'linux_recorded')


def fixture_rows(count):
    """count rows built from the archived five, timestamps shifted so they keep increasing."""
    rows = []
    for n in range(count):
        row = dict(ARCHIVE_ROWS[n % 5])
        row['timestamp'] += 100 * (n // 5)
        rows.append(row)
    return rows


@pytest.fixture
def live(monkeypatch):
    """governorlab.live with Linux-only probes replaced by fixtures (portable)."""
    from governorlab import live
    initial = {'mem_available_kib': 2_000_000, 'swap_used_kib': 1000}
    monkeypatch.setattr(live, 'resources', lambda: dict(initial))
    monkeypatch.setattr(live, 'expected_jiffies', lambda: 400)
    monkeypatch.setattr(live, 'sys', SimpleNamespace(platform='linux'))
    deadlines = []
    monkeypatch.setattr(live, 'collection_deadline', lambda seconds: deadlines.append(seconds) or nullcontext())
    original = Path.is_file
    monkeypatch.setattr(Path, 'is_file', lambda self: self.as_posix() == '/proc/stat' or original(self))
    requested = []
    def sample(interval, count, *, observer):
        requested.append(count)
        observer({'event': 'baseline'})
        for n, row in enumerate(fixture_rows(count), 1):
            observer({'event': 'interval', 'attempt': n, 'valid': True, 'elapsed_s': row['elapsed_s']})
            yield row
    monkeypatch.setattr(live, 'sample', sample)
    live.fixture_deadlines, live.fixture_requested = deadlines, requested
    return live


@pytest.mark.parametrize('count', [5, 10, 30])
def test_collect_live_uses_count_everywhere_and_writes_manifest(live, tmp_path, count):
    progress = []
    data = live.collect_live(tmp_path, progress.append, count=count)
    folder = Path(data.metadata['csv_path']).parent
    assert live.fixture_requested == [count]
    assert live.fixture_deadlines == [2 * count + 2]
    assert progress == list(range(count + 1))
    metadata = json.loads((folder / 'metadata.json').read_text())
    assert metadata['requested_attempts'] == metadata['actual_sample_count'] == count
    assert metadata['collection_timeout_s'] == 2 * count + 2
    manifest = json.loads((folder / 'session-sha256.json').read_text())
    assert manifest == sessions.session_hashes(folder)
    loaded = sessions.load_session(folder)
    assert len(loaded.frames) == count
    assert 'capture hashes checked' in loaded.metadata['validation']


@pytest.mark.parametrize('count', [4, 31, 5.0, True])
def test_collect_live_rejects_out_of_range_count_before_sampling(live, tmp_path, count):
    with pytest.raises(ValueError, match='sample count'):
        live.collect_live(tmp_path, count=count)
    assert live.fixture_requested == [] and not list(tmp_path.iterdir())


def test_deadline_and_watchdog_scale_and_keep_five_sample_values():
    assert (sessions.collection_timeout_s(5), sessions.watchdog_s(5)) == (12, 15)
    assert (sessions.collection_timeout_s(20), sessions.watchdog_s(20)) == (42, 45)


def test_daybreak_sessions_is_a_reexport():
    old = importlib.import_module('daybreak.sessions')
    assert old.load_session is sessions.load_session
    assert old.list_sessions is sessions.list_sessions
    assert old.session_hashes is sessions.session_hashes


@pytest.fixture
def ten(live, tmp_path):
    return Path(live.collect_live(tmp_path / 'run', count=10).metadata['csv_path']).parent


@pytest.mark.parametrize('change', [{'requested_attempts': 11}, {'actual_sample_count': 31, 'requested_attempts': 31},
                                    {'actual_sample_count': 4, 'requested_attempts': 4}])
def test_load_session_requires_matching_counts_in_range(ten, change):
    path = ten / 'metadata.json'
    path.write_text(json.dumps({**json.loads(path.read_text()), **change}))
    (ten / 'session-sha256.json').unlink()
    with pytest.raises(ValueError, match='requested_attempts equal to actual_sample_count'):
        sessions.load_session(ten)


def test_list_and_latest_are_newest_first(ten, tmp_path):
    root = ten.parent
    older = root / 'live-20000101T000000Z-old'
    shutil.copytree(ten, older)
    dashboard = root / 'daybreak-job' / 'live-19990101T000000Z-x'
    shutil.copytree(ten, dashboard)
    assert sessions.list_sessions(root) == [ten, older, dashboard]
    assert sessions.resolve_session('latest', root) == ten
    assert sessions.resolve_session(str(older), root) == older
    with pytest.raises(ValueError, match='No saved sessions'):
        sessions.resolve_session('latest', tmp_path / 'empty')


def test_worker_passes_count_and_relies_on_collect_live_manifest(ten, monkeypatch):
    from daybreak import worker
    from governorlab import live as live_module
    data = sessions.load_session(ten)
    data = replace(data, metadata={**data.metadata, 'csv_path': str(ten / 'capture.csv')})
    calls = []
    def collect(root, progress, count=5):
        calls.append(count)
        progress(count)
        return data
    monkeypatch.setattr(live_module, 'collect_live', collect)
    monkeypatch.setattr(worker.signal, 'signal', lambda *args: None)
    assert worker.main(['--job', str(ten.parent), '--count', '10']) == 0
    assert calls == [10]
    status = json.loads((ten.parent / 'status.json').read_text())
    assert status == {'status': 'validated', 'count': 10, 'requested': 10, 'folder': ten.name}


def test_collection_passes_count_to_child_and_scales_watchdog(monkeypatch, tmp_path):
    m = importlib.import_module('daybreak.collection')
    monkeypatch.setattr(m.sys, 'platform', 'linux')
    commands = []
    child = SimpleNamespace(pid=1, poll=lambda: None)
    monkeypatch.setattr(m.subprocess, 'Popen', lambda command, **options: commands.append(command) or child)
    monkeypatch.setattr(m.Collection, '_watch', lambda self: None)
    job = m.Collection.start(tmp_path, count=20)
    assert commands[0][-2:] == ['--count', '20']
    assert job.count == 20 and job.deadline_s == 45
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('spawned'))
    with pytest.raises(ValueError, match='sample count'):
        m.Collection.start(tmp_path, count=7.5)


def test_collection_watchdog_times_out_at_scaled_deadline(monkeypatch, tmp_path):
    m = importlib.import_module('daybreak.collection')
    child = SimpleNamespace(pid=1, returncode=None)
    child.poll = lambda: child.returncode
    def wait(timeout):
        if child.returncode is None:
            raise subprocess.TimeoutExpired('fixture', timeout)
        return child.returncode
    child.wait = wait
    child.kill = lambda: setattr(child, 'returncode', -9)
    monkeypatch.setattr(m.os, 'killpg', lambda pid, sig: None, raising=False)
    job = m.Collection(child, tmp_path, count=10)
    job.started -= 24.0
    job.heartbeat = m.time.monotonic() + 100
    monkeypatch.setattr(m.time, 'sleep', lambda s: setattr(job, 'started', job.started - 1.5))
    job._watch()
    assert job.result['status'] == 'timeout'


def test_dashboard_sample_selector_reaches_collection_start(ten, monkeypatch):
    from streamlit.testing.v1 import AppTest
    import daybreak.playback_ui as ui
    calls = []
    def start(**kwargs):
        calls.append(kwargs['count'])
        raise RuntimeError('fixture: no child')
    monkeypatch.setattr(ui.Collection, 'start', start)
    monkeypatch.setattr(ui, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setattr(ui, 'list_sessions', lambda: [ten])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'daybreak/app.py'), default_timeout=20).run()
    assert list(at.selectbox(key='collect_count').options) == ['5', '10', '20']
    at.selectbox(key='collect_count').set_value(10).run()
    at.button(key='collect').click().run()
    assert calls == [10]
    assert not at.exception


def test_old_five_sample_session_without_manifest_still_loads(tmp_path):
    folder = tmp_path / 'live-legacy'
    folder.mkdir()
    shutil.copyfile(adapter.LINUX_ARCHIVE / 'validated_trace.csv', folder / 'capture.csv')
    metadata = dict(status='validated', actual_sample_count=5, requested_attempts=5,
                    workload_label='uncontrolled_background', observation_source='linux_proc_stat',
                    expected_jiffies_per_s=400, csv_path='/old/capture.csv',
                    frequency_control='simulated', generated_load=False)
    data = adapter.process_live_observations(ARCHIVE_ROWS, metadata)
    from dataclasses import asdict
    (folder / 'metadata.json').write_text(json.dumps(metadata))
    (folder / 'decisions.json').write_text(json.dumps([asdict(f) for f in data.frames]))
    loaded = sessions.load_session(folder)
    assert len(loaded.frames) == 5 and 'no hash manifest' in loaded.metadata['validation']


# Governorlab CLI

def run_cli(*argv):
    from governorlab import app
    stream = io.StringIO()
    return app.main(list(argv), stream=stream), stream.getvalue()


def test_cli_replays_saved_session_with_revalidation(ten):
    code, out = run_cli('--session', str(ten), '--plain', '--instant')
    assert code == 0, out
    assert 'SAVED LINUX OBSERVATIONS' in out and 'SAVED SESSION REPLAY COMPLETE | 10/10 samples' in out
    assert 'capture hashes checked' in out


def test_cli_rejects_tampered_session(ten):
    path = ten / 'decisions.json'
    path.write_text(path.read_text().replace('"applied_khz": 5100000', '"applied_khz": 1', 1))
    code, out = run_cli('--session', str(ten), '--plain', '--instant')
    assert code == 1 and 'integrity mismatch' in out


def test_cli_latest_and_list_sessions(ten, monkeypatch):
    from governorlab import app
    monkeypatch.setattr(app, 'resolve_session', lambda choice: sessions.resolve_session(choice, ten.parent))
    monkeypatch.setattr(app, 'list_sessions', lambda: sessions.list_sessions(ten.parent))
    code, out = run_cli('--session', 'latest', '--plain', '--instant')
    assert code == 0 and '10/10 samples' in out
    code, out = run_cli('--list-sessions')
    assert code == 0 and ten.name in out and 'validated | 10/10 samples | manifest' in out
    monkeypatch.setattr(app, 'list_sessions', lambda: [])
    assert 'No saved sessions' in run_cli('--list-sessions')[1]


@pytest.mark.parametrize('argv', [['--samples', '10'], ['--live', '--samples', '4'],
                                  ['--live', '--samples', '31'], ['--session', 'latest', '--live']])
def test_cli_rejects_invalid_sample_options_before_collection(argv, monkeypatch):
    from governorlab import live as live_module
    monkeypatch.setattr(live_module, 'collect_live', lambda *a, **k: pytest.fail('collected'))
    assert run_cli(*argv)[0] == 2


def test_cli_live_forwards_samples(ten, monkeypatch):
    from governorlab import live as live_module
    seen = []
    def collect(progress, count):
        seen.append(count)
        progress(count)
        return sessions.load_session(ten)
    monkeypatch.setattr(live_module, 'collect_live', collect)
    code, out = run_cli('--live', '--samples', '10', '--plain', '--instant')
    assert code == 0 and seen == [10] and 'Collecting Linux samples: 10/10' in out


def test_failed_collection_writes_no_manifest(live, tmp_path, monkeypatch):
    def broken(interval, count, *, observer):
        yield from fixture_rows(2)
        raise RuntimeError('fixture sampling failure')
    monkeypatch.setattr(live, 'sample', broken)
    with pytest.raises(RuntimeError, match='fixture sampling failure'):
        live.collect_live(tmp_path, count=10)
    (folder,) = tmp_path.iterdir()
    assert json.loads((folder / 'metadata.json').read_text())['status'] == 'failed'
    assert not (folder / 'session-sha256.json').exists()
