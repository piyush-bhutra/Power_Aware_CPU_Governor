"""Child lifecycle is exercised with fakes, never real monitoring."""
import importlib
import json
import subprocess

import pytest


class Child:
    pid = 987654
    returncode = None

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        if self.returncode is None:
            raise subprocess.TimeoutExpired('fixture', timeout)
        return self.returncode

    def kill(self):
        self.returncode = -9


def module():
    return importlib.import_module('daybreak.collection')


def test_windows_start_never_spawns(monkeypatch, tmp_path):
    m = module()
    monkeypatch.setattr(m.sys, 'platform', 'win32')
    monkeypatch.setattr(m.subprocess, 'Popen', lambda *a, **k: pytest.fail('spawn'))
    with pytest.raises(RuntimeError, match='Linux'):
        m.Collection.start(tmp_path)


def test_start_isolated_exact_command_and_no_second_start(monkeypatch, tmp_path):
    m = module()
    monkeypatch.setattr(m.sys, 'platform', 'linux')
    child = Child()
    calls = []
    def spawn(command, **options):
        calls.append((command, options))
        return child
    monkeypatch.setattr(m.subprocess, 'Popen', spawn)
    monkeypatch.setattr(m.Collection, '_watch', lambda self: None)
    job = m.Collection.start(tmp_path)
    assert calls[0][0][1:3] == ['-m', 'daybreak.worker']
    assert calls[0][1]['start_new_session'] and not calls[0][1].get('shell')
    assert job.poll()['status'] == 'collecting'
    with pytest.raises(RuntimeError, match='active'):
        m.Collection.start(tmp_path, current=job)
    child.returncode = 0
    assert job.poll()['status'] == 'failed'  # missing successful result


@pytest.mark.parametrize('reason', ['cancelled', 'timeout', 'disconnected'])
def test_cancellation_escalates_and_reaps(monkeypatch, tmp_path, reason):
    m = module()
    child = Child()
    signals = []
    monkeypatch.setattr(m.os, 'killpg', lambda pid, sig: signals.append(sig), raising=False)
    job = m.Collection(child, tmp_path)
    job.cancel(reason)
    assert child.returncode == -9
    assert signals
    assert job.poll()['status'] == reason
    job.cancel(reason)  # idempotent


def test_poll_progress_success_and_failure(monkeypatch, tmp_path):
    m = module()
    child = Child()
    job = m.Collection(child, tmp_path)
    path = tmp_path / 'status.json'
    path.write_text(json.dumps({'status': 'collecting', 'count': 3}))
    assert job.poll()['count'] == 3
    path.write_text(json.dumps({'status': 'validated', 'count': 5, 'folder': 'live-fixture'}))
    child.returncode = 0
    assert job.poll()['status'] == 'validated'
    path.write_text(json.dumps({'status': 'failed', 'error': 'invalid raw counters'}))
    child.returncode = 1
    failed = m.Collection(child, tmp_path)
    assert failed.poll()['error'] == 'invalid raw counters'


def test_watchdog_bounds_deadline_and_heartbeat(monkeypatch, tmp_path):
    m = module()
    child = Child()
    job = m.Collection(child, tmp_path)
    calls = []
    monkeypatch.setattr(job, 'cancel', lambda reason: calls.append(reason))
    monkeypatch.setattr(m.time, 'monotonic', lambda: job.started + job.deadline_s + 1)  # 21 s for the tolerant 5-sample default
    job._watch()
    assert calls == ['timeout']
    calls.clear()
    monkeypatch.setattr(m.time, 'monotonic', lambda: job.started + 7)
    job._watch()
    assert calls == ['disconnected']
