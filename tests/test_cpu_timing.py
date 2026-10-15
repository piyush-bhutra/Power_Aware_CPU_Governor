"""No workload: simulated process clocks exercise the real supervisor."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark import collect_traces as collector


def simulation(monkeypatch, directory, *, ready=True, monitor_end=5, worker_end=7):
    clock = [0.0]
    launches = []

    class Process:
        def __init__(self, command, **kwargs):
            self.name = command[0]
            self.pid = 100 + len(launches)
            self.start = clock[0]
            self.returncode = None
            launches.append((self.name, self.start))

        def poll(self):
            end = monitor_end if self.name == 'monitor' else worker_end
            if clock[0] - self.start >= end:
                self.returncode = 0
            return self.returncode

    def sleep(seconds):
        clock[0] += seconds
        if ready and clock[0] >= .5:
            (directory/'monitor.ready').touch()

    monkeypatch.setattr(collector.time, 'monotonic', lambda: clock[0])
    monkeypatch.setattr(collector.time, 'sleep', sleep)
    monkeypatch.setattr(collector.subprocess, 'Popen', Process)
    monkeypatch.setattr(collector, 'process_record', lambda pid:
                        dict(pid=pid, pgid=pid, session=pid, start_ticks=1))
    monkeypatch.setattr(collector, 'resources', lambda:
                        dict(mem_available_kib=2000000, swap_used_kib=0))
    def stop(process):
        if process and process.returncode is None:
            process.returncode = -15
    monkeypatch.setattr(collector, 'stop_group', stop)
    return clock, launches


def run(directory):
    return collector.run_processes(['monitor'], ['worker'], directory, 11,
                                   readiness=True)


def test_monitor_readiness_precedes_worker_and_releases_sampling(tmp_path, monkeypatch):
    clock, launches = simulation(monkeypatch, tmp_path)
    result = run(tmp_path)
    assert launches[0] == ('monitor', 0)
    assert launches[1][0] == 'worker' and launches[1][1] >= .5
    assert (tmp_path/'monitor.start').exists()
    assert result['worker_exit'] == result['monitor_exit'] == 0
    events = json.loads((tmp_path/'lifecycle.json').read_text())['events']
    assert [e['event'] for e in events].index('monitor_ready') < [e['event'] for e in events].index('worker_started')


@pytest.mark.parametrize('case,expected', [('startup','startup'),('sampling','sampling'),('workload','workload')])
def test_deadline_phase_and_exit_evidence_survive_failure(tmp_path, monkeypatch, case, expected):
    clock, launches = simulation(monkeypatch, tmp_path, ready=case!='startup',
                                monitor_end=100 if case in ('startup','sampling') else 5,
                                worker_end=100)
    with pytest.raises(TimeoutError, match=expected):
        run(tmp_path)
    evidence = json.loads((tmp_path/'lifecycle.json').read_text())
    assert evidence['deadline_phase'] == expected
    assert evidence['monitor_exit'] in (0, -15)
    assert evidence['cleanup'] == 'completed'
    assert clock[0] <= 11.1
    if case == 'startup':
        assert [name for name, _ in launches] == ['monitor']


def test_failed_supervision_still_attempts_csv_validation(tmp_path, monkeypatch):
    def failed(command, worker, directory, timeout_s, **kwargs):
        (directory/'trace.csv').write_text('timestamp\n')
        raise TimeoutError('sampling deadline exceeded')
    monkeypatch.setattr(collector, 'run_processes', failed)
    monkeypatch.setattr(sys, 'argv', ['collector','5','64M',str(tmp_path),'--approved-workload'])
    with pytest.raises(TimeoutError):
        collector.main()
    manifest = json.loads(next(tmp_path.glob('*/manifest.json')).read_text())
    assert manifest['success'] is False
    assert manifest['sample_validation']['success'] is False
    assert 'row count 0' in manifest['sample_validation']['error']


def test_late_success_does_not_bypass_total_deadline(tmp_path, monkeypatch):
    clock, launches = simulation(monkeypatch, tmp_path, monitor_end=12, worker_end=12)
    original_sleep = collector.time.sleep
    def delayed_poll(seconds):
        original_sleep(13 if (tmp_path/'monitor.start').exists() else seconds)
    monkeypatch.setattr(collector.time, 'sleep', delayed_poll)
    with pytest.raises(TimeoutError):
        run(tmp_path)


def test_skipped_intervals_are_visible_without_csv_rows(monkeypatch):
    from monitor import reader
    snapshot = dict.fromkeys((*reader.CPU_FIELDS, 'ctxt'), 0)
    snapshot.update(procs_running=1, procs_blocked=0)
    monkeypatch.setattr(reader, 'read_stat', lambda: snapshot.copy())
    clocks = iter([10, 11, 12])
    monkeypatch.setattr(reader.time, 'monotonic', lambda: next(clocks))
    monkeypatch.setattr(reader.time, 'sleep', lambda _: None)
    events = []
    assert list(reader.sample(1, 2, observer=events.append)) == []
    assert events[0]['event'] == 'baseline'
    assert [e['valid'] for e in events[1:]] == [False, False]
    assert [e['elapsed_s'] for e in events[1:]] == [1, 1]


def test_capture_waits_for_release_before_baseline(tmp_path, monkeypatch, capsys):
    from monitor import capture
    ready, start = tmp_path/'ready', tmp_path/'start'
    output = tmp_path/'trace.csv'
    monkeypatch.setattr(capture, 'resources', lambda:
                        dict(mem_available_kib=2000000, swap_used_kib=0))
    def release(_):
        assert ready.exists()
        assert output.read_text().startswith('timestamp,')
        start.touch()
    monkeypatch.setattr(capture.time, 'sleep', release)
    def sample(*args, **kwargs):
        assert start.exists()
        yield dict(elapsed_s=1)
    monkeypatch.setattr(capture, 'sample', sample)
    monkeypatch.setattr(capture, 'validate_trace', lambda *args: dict(rows=1))
    monkeypatch.setattr(sys, 'argv', ['capture','--output',str(output),'--ticks','1',
                        '--ready-file',str(ready),'--start-file',str(start)])
    capture.main()
    assert len(output.read_text().splitlines()) == 2
    assert 'monitor ready' in capsys.readouterr().out


def test_interrupt_before_readiness_preserves_cleanup_and_never_starts_worker(tmp_path, monkeypatch):
    clock, launches = simulation(monkeypatch, tmp_path, ready=False)
    monkeypatch.setattr(collector.time, 'sleep', lambda _: (_ for _ in ()).throw(InterruptedError('signal')))
    with pytest.raises(InterruptedError):
        run(tmp_path)
    evidence = json.loads((tmp_path/'lifecycle.json').read_text())
    assert evidence['cleanup'] == 'completed'
    assert evidence['monitor_exit'] == -15
    assert [name for name, _ in launches] == ['monitor']


def test_diagnostic_write_failure_cannot_skip_group_cleanup(tmp_path, monkeypatch):
    simulation(monkeypatch, tmp_path)
    stopped = []
    original_stop = collector.stop_group
    def stop(process):
        if process:
            stopped.append(process.name)
        original_stop(process)
    monkeypatch.setattr(collector, 'stop_group', stop)
    original_replace = collector.os.replace
    def replace(source, target):
        if Path(target).name == 'lifecycle.json':
            raise OSError('mock disk failure')
        original_replace(source, target)
    monkeypatch.setattr(collector.os, 'replace', replace)
    with pytest.raises((RuntimeError, OSError), match='diagnostic|disk'):
        run(tmp_path)
    assert 'monitor' in stopped


def test_valid_samples_do_not_promote_failed_workload_to_success(tmp_path, monkeypatch):
    from monitor.reader import CPU_FIELDS, log_csv
    def failed(command, worker, directory, timeout_s, **kwargs):
        rows=[]
        for tick in range(5):
            row=dict(timestamp=tick+1, util_pct=50, iowait_pct=0, irq_pct=0,
                     ctxt_per_s=10, procs_running=1, procs_blocked=0, elapsed_s=1,
                     delta_total_jiffies=400, iowait_decreased=False,
                     workload_label='cpu_stressor_1_worker', observation_source='linux_proc_stat')
            for field in (*CPU_FIELDS, 'ctxt'):
                step={'user':200, 'idle':200, 'ctxt':10}.get(field,0)
                row['raw_prev_'+field]=tick*step
                row['raw_cur_'+field]=(tick+1)*step
            rows.append(row)
        log_csv(directory/'trace.csv',rows,('workload_label','observation_source'))
        raise TimeoutError('workload deadline exceeded')
    monkeypatch.setattr(collector, 'run_processes', failed)
    monkeypatch.setattr(collector.os, 'cpu_count', lambda:4)
    monkeypatch.setattr(collector.os, 'sysconf', lambda _:100)
    monkeypatch.setattr(sys, 'argv', ['collector','5','64M',str(tmp_path),'--approved-workload'])
    with pytest.raises(TimeoutError):
        collector.main()
    manifest=json.loads(next(tmp_path.glob('*/manifest.json')).read_text())
    assert manifest['sample_validation']['success'] is True
    assert manifest['sample_validation']['statistics']['rows'] == 5
    assert manifest['success'] is False and manifest['status'] == 'failed'
