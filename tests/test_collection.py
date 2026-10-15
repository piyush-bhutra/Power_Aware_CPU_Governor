"""Collector safeguards tested only with fixtures and harmless short-lived processes."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark.collect_traces import run_processes, parse_args
from monitor.capture import validate_trace


def python(code):
    return [sys.executable, '-c', code]


def test_worker_failure_stops_monitor_and_keeps_error_log(tmp_path):
    marker = tmp_path / 'late'
    monitor = python(f'import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()')
    worker = python('import sys; print("worker failed", file=sys.stderr); sys.exit(7)')
    with pytest.raises(RuntimeError, match='worker'):
        run_processes(monitor, worker, tmp_path, 2)
    assert not marker.exists()
    assert 'worker failed' in (tmp_path / 'worker.log').read_text()


def test_timeout_kills_process_group_descendant(tmp_path):
    pidfile = tmp_path / 'child.pid'
    worker = python('import subprocess,sys,time; from pathlib import Path; '
                    'child=subprocess.Popen([sys.executable,"-c","import time; time.sleep(10)"]); '
                    f'Path({str(pidfile)!r}).write_text(str(child.pid)); time.sleep(10)')
    with pytest.raises(TimeoutError):
        run_processes(python('import time; time.sleep(10)'), worker, tmp_path, .5)
    pid = int(pidfile.read_text())
    stat = Path(f'/proc/{pid}/stat')
    assert not stat.exists() or stat.read_text().split()[2] == 'Z'


def test_monitor_failure_stops_worker(tmp_path):
    with pytest.raises(RuntimeError, match='monitor'):
        run_processes(python('raise SystemExit(4)'), python('import time; time.sleep(10)'), tmp_path, 2)


def test_success_requires_both_exit_codes(tmp_path):
    result = run_processes(python('pass'), None, tmp_path, 1)
    assert result['monitor_exit'] == 0
    assert result['worker_exit'] is None


def test_premature_worker_success_invalidates_workload(tmp_path):
    with pytest.raises(RuntimeError, match='before monitoring'):
        run_processes(python('import time; time.sleep(1)'), python('pass'), tmp_path, 2)


def test_manifest_records_failure_and_preserves_unique_runs(tmp_path, monkeypatch):
    import json
    from benchmark import collect_traces

    def failed(*args):
        raise RuntimeError('mock worker status 7')
    monkeypatch.setattr(collect_traces, 'run_processes', failed)
    monkeypatch.setattr(sys, 'argv', ['collector','5','64M',str(tmp_path),'--approved-workload'])
    for _ in range(2):
        with pytest.raises(RuntimeError, match='status 7'):
            collect_traces.main()
    manifests = list(tmp_path.glob('*/manifest.json'))
    assert len(manifests) == 2
    for manifest in manifests:
        result=json.loads(manifest.read_text())
        assert result['success'] is False and result['status'] == 'failed'
        assert 'status 7' in result['error']
        metadata=json.loads((manifest.parent/'metadata.json').read_text())
        assert metadata['cpu_workers'] == 1


def test_memory_pressure_prevents_process_start(tmp_path, monkeypatch):
    from benchmark import collect_traces
    monkeypatch.setattr(collect_traces, 'resources',
                        lambda:dict(mem_available_kib=100,swap_used_kib=0))
    with pytest.raises(RuntimeError, match='Memory pressure'):
        run_processes(python('raise SystemExit(99)'),None,tmp_path,1)
    assert not (tmp_path/'monitor.log').exists()


def test_worker_cleanup_still_runs_if_monitor_cleanup_raises(tmp_path, monkeypatch):
    from benchmark import collect_traces
    original = collect_traces.stop_group
    cleaned = []
    def cleanup(process):
        original(process)
        cleaned.append(process)
        if len(cleaned) == 1:
            raise RuntimeError('mock monitor cleanup error')
    monkeypatch.setattr(collect_traces, 'stop_group', cleanup)
    with pytest.raises(RuntimeError, match='cleanup error'):
        run_processes(python('pass'),python('import time; time.sleep(.2)'),tmp_path,1)
    assert len(cleaned) == 2


def test_metadata_identifies_uncommitted_sources(tmp_path, monkeypatch):
    import json
    from benchmark import collect_traces
    def failed(*args):
        raise RuntimeError('mock failure')
    monkeypatch.setattr(collect_traces, 'run_processes', failed)
    monkeypatch.setattr(sys, 'argv', ['collector','5','64M',str(tmp_path),'--approved-workload'])
    with pytest.raises(RuntimeError):
        collect_traces.main()
    metadata=json.loads(next(tmp_path.glob('*/metadata.json')).read_text())
    assert isinstance(metadata['working_tree_dirty'],bool)
    assert len(metadata['source_hashes']['monitor/reader.py']) == 64


@pytest.mark.parametrize('args', [['0','64M'], ['31','64M'], ['5','1G'],
                                  ['5','garbage'], ['5','64M','--profile','io'],
                                  ['5','64M']])
def test_unsafe_arguments_rejected(args):
    with pytest.raises(SystemExit):
        parse_args(args)


def test_conservative_arguments_and_explicit_approval():
    args = parse_args(['5','64M','--approved-workload'])
    assert args.duration == 5 and args.memory_bytes == 64*1024*1024
    assert args.profile == 'cpu'


def test_validator_rejects_missing_rows_and_nonfinite_values(tmp_path):
    path = tmp_path / 'trace.csv'
    path.write_text('timestamp,util_pct\n1,nan\n')
    with pytest.raises(ValueError):
        validate_trace(path, 5, 'uncontrolled_background')


def test_validator_checks_label_and_elapsed_and_raw_counters(tmp_path):
    from monitor.reader import CPU_FIELDS, log_csv
    row = dict(timestamp=100, util_pct=50, iowait_pct=0, irq_pct=0,
               ctxt_per_s=10, procs_running=1, procs_blocked=0, elapsed_s=1,
               delta_total_jiffies=100, iowait_decreased=False,
               workload_label='uncontrolled_background', observation_source='linux_proc_stat')
    for f in (*CPU_FIELDS, 'ctxt'):
        row[f'raw_prev_{f}'] = 0
        row[f'raw_cur_{f}'] = {'user':50, 'idle':50, 'ctxt':10}.get(f,0)
    path = tmp_path / 'valid.csv'
    log_csv(path, [row], ('workload_label','observation_source'))
    assert validate_trace(path, 1, 'uncontrolled_background')['rows'] == 1
    with pytest.raises(ValueError):
        validate_trace(path, 1, 'cpu_stressor_1_worker')
    row['elapsed_s'] = 3
    path2=tmp_path/'slow.csv'
    log_csv(path2,[row],('workload_label','observation_source'))
    with pytest.raises(ValueError, match='elapsed'):
        validate_trace(path2, 1, 'uncontrolled_background')
