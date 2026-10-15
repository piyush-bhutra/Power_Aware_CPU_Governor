"""Saved sessions are test fixtures, never presented as experimental results."""
from dataclasses import asdict
import importlib
import json
import shutil

import pytest

from presentation.adapter import LINUX_ARCHIVE, load_csv, process_live_observations


@pytest.fixture
def saved(tmp_path):
    folder = tmp_path / 'live-fixture'
    folder.mkdir()
    shutil.copyfile(LINUX_ARCHIVE / 'validated_trace.csv', folder / 'capture.csv')
    metadata = dict(status='validated', actual_sample_count=5, requested_attempts=5,
                    workload_label='uncontrolled_background', observation_source='linux_proc_stat',
                    expected_jiffies_per_s=400, csv_path='/original/Linux/capture.csv',
                    frequency_control='simulated', generated_load=False, started_utc='fixture')
    data = process_live_observations(load_csv(folder / 'capture.csv', 'linux_recorded'), metadata)
    (folder / 'metadata.json').write_text(json.dumps(metadata))
    (folder / 'decisions.json').write_text(json.dumps([asdict(f) for f in data.frames]))
    return folder


def test_saved_replay_revalidates_and_preserves_actual_count(saved):
    sessions = importlib.import_module('daybreak.sessions')
    data = sessions.load_session(saved)
    assert len(data.frames) == 5 and 'SAVED' in data.mode
    assert data.summary['transitions'] == 0
    assert data.frames[0].candidate_khz is not None
    assert data.frames[0].source_kind == 'linux_live'
    assert data.metadata['original_csv_path'] == '/original/Linux/capture.csv'
    assert sessions.list_sessions(saved.parent) == [saved]


@pytest.mark.parametrize('damage', ['failed', 'raw', 'decision', 'manifest'])
def test_saved_session_rejects_failed_or_tampered_data(saved, damage):
    sessions = importlib.import_module('daybreak.sessions')
    if damage == 'failed':
        path = saved / 'metadata.json'
        obj = json.loads(path.read_text())
        obj['status'] = 'failed'
        path.write_text(json.dumps(obj))
    elif damage == 'raw':
        path = saved / 'capture.csv'
        path.write_text(path.read_text().replace('uncontrolled_background', 'invented'))
    elif damage == 'decision':
        path = saved / 'decisions.json'
        obj = json.loads(path.read_text())
        obj[0]['applied_khz'] = 1
        path.write_text(json.dumps(obj))
    else:
        (saved / 'session-sha256.json').write_text(json.dumps({'capture.csv': 'bad'}))
    with pytest.raises(ValueError):
        sessions.load_session(saved)


def test_same_streamlit_player_switches_saved_and_synthetic(saved, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from pathlib import Path
    import daybreak.playback_ui as ui
    monkeypatch.setattr(ui, 'list_sessions', lambda: [saved])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'daybreak/app.py'), default_timeout=20).run()
    at.button(key='pause').click().run()
    at.slider(key='tick_control').set_value(34).run()
    at.selectbox(key='source_choice').set_value(str(saved.resolve())).run()
    assert not at.exception
    assert at.session_state['player'].total == 5
    assert at.session_state['player'].playing
    assert at.slider(key='tick_control').max == 5
    assert at.slider(key='tick_control').value == 1
    at.selectbox(key='speed').set_value(4.0).run()
    at.radio(key='view').set_value('The Evidence').run()
    at.radio(key='view').set_value('The Replay').run()
    assert at.selectbox(key='source_choice').value == str(saved.resolve())
    assert at.selectbox(key='speed').value == 4.0
    assert at.session_state['player'].total == 5
    at.button(key='pause').click().run()
    at.slider(key='tick_control').set_value(5).run()
    assert at.session_state['player'].complete
    assert at.session_state['dataset'].summary['transitions'] == 0
    at.button(key='previous').click().run()
    assert at.session_state['player'].tick == 4
    at.selectbox(key='source_choice').set_value(ui.SYNTHETIC).run()
    assert at.session_state['player'].total == 34
    assert at.session_state['player'].tick == 1
    assert not at.exception


def test_child_worker_calls_existing_pipeline_once_and_preserves_hashes(saved, monkeypatch):
    from daybreak import worker
    from governorlab import live
    data = process_live_observations(load_csv(saved / 'capture.csv', 'linux_recorded'),
                                     json.loads((saved / 'metadata.json').read_text()))
    from dataclasses import replace
    data = replace(data, metadata={**data.metadata, 'csv_path': str(saved / 'capture.csv')})
    (saved / 'raw_events.jsonl').write_text('')
    calls = []
    def collect(root, progress):
        calls.append(root)
        progress(0)
        progress(5)
        return data
    monkeypatch.setattr(live, 'collect_live', collect)
    monkeypatch.setattr(worker.signal, 'signal', lambda *args: None)
    assert worker.main(['--job', str(saved.parent)]) == 0
    assert calls == [saved.parent]
    status = json.loads((saved.parent / 'status.json').read_text())
    assert status['count'] == 5 and status['status'] == 'validated'
    assert importlib.import_module('daybreak.sessions').load_session(saved).summary['ticks'] == 5


def test_worker_failure_is_retained_without_retry(tmp_path, monkeypatch):
    from daybreak import worker
    from governorlab import live
    calls = []
    def fail(root, progress):
        calls.append(root)
        raise RuntimeError('fixture invalid counters')
    monkeypatch.setattr(live, 'collect_live', fail)
    monkeypatch.setattr(worker.signal, 'signal', lambda *args: None)
    assert worker.main(['--job', str(tmp_path)]) == 1
    assert len(calls) == 1
    status = json.loads((tmp_path / 'status.json').read_text())
    assert status['status'] == 'failed' and 'invalid counters' in status['error']


def test_successful_collection_enters_same_player_once(saved, monkeypatch):
    from pathlib import Path
    from types import SimpleNamespace
    from streamlit.testing.v1 import AppTest
    import daybreak.playback_ui as ui
    class Job:
        folder = saved.parent
        active = True
        def poll(self):
            return {'status': 'collecting', 'count': 2} if self.active else {'status': 'validated', 'count': 5, 'folder': saved.name}
        def cancel(self):
            self.active = False
    job = Job()
    calls = []
    def start(**kwargs):
        calls.append(True)
        return job
    monkeypatch.setattr(ui.Collection, 'start', start)
    monkeypatch.setattr(ui, 'sys', SimpleNamespace(platform='linux'))
    monkeypatch.setattr(ui, 'list_sessions', lambda: [saved])
    at = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'daybreak/app.py'), default_timeout=20).run()
    at.button(key='collect').click().run()
    assert at.button(key='collect').disabled
    assert not at.session_state['player'].playing
    job.active = False
    at.run()
    assert at.session_state['player'].total == 5
    assert at.session_state['player'].playing
    assert at.selectbox(key='source_choice').value == str(saved.resolve())
    at.button(key='pause').click().run()
    at.run()
    assert not at.session_state['player'].playing
    assert len(calls) == 1
    assert not at.exception
