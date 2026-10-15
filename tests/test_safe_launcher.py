"""Standalone launcher contracts using a fake collector; never executes stress-ng."""
import csv
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from benchmark import safe_cpu_launcher as launcher
from monitor.reader import CPU_FIELDS, RAW_COLS, SIGNALS


@pytest.fixture
def setup(tmp_path, monkeypatch):
    root=tmp_path/'project'; shared=tmp_path/'shared'
    shared.mkdir(); (root/'.venv/bin').mkdir(parents=True)
    (root/'.venv/bin/python').symlink_to(sys.executable)
    for name in ('benchmark/collect_traces.py','monitor/capture.py','monitor/reader.py'):
        path=root/name; path.parent.mkdir(exist_ok=True); path.touch()
    monkeypatch.setattr(launcher.os.path,'ismount',lambda p:Path(p)==shared)
    monkeypatch.setattr(launcher,'resources',lambda:dict(mem_available_kib=2*1024*1024,swap_used_kib=0))
    monkeypatch.setattr(launcher,'swap_activity',lambda:(0,0))
    monkeypatch.setattr(launcher.time,'sleep',lambda _:None)
    which=launcher.shutil.which
    monkeypatch.setattr(launcher.shutil,'which',lambda name:'/mock/stress-ng' if name=='stress-ng' else which(name))
    # This fixture tests launcher behavior, not the VM's uname/lscpu/git latency.
    # Keep the fake collector a real harmless subprocess, but isolate metadata I/O.
    import subprocess
    original_run=launcher.subprocess.run
    def metadata_run(command,**kwargs):
        if command[0] in ('uname','lscpu','git'):
            stdout='' if command==['git','status','--porcelain'] else 'fixture metadata\n'
            return subprocess.CompletedProcess(command,0,stdout,'')
        return original_run(command,**kwargs)
    monkeypatch.setattr(launcher.subprocess,'run',metadata_run)
    # Independently constructed valid Linux-shaped observations, not live data.
    columns=['timestamp',*SIGNALS,*RAW_COLS,'workload_label','observation_source']
    rows=[]
    for i in range(5):
        row=dict(timestamp=100+i,util_pct=25,iowait_pct=0,irq_pct=0,ctxt_per_s=100,
                 elapsed_s=1,delta_total_jiffies=400,iowait_decreased=False,
                 procs_running=1,procs_blocked=0,workload_label='cpu_stressor_1_worker',
                 observation_source='linux_proc_stat')
        for side,offset in [('prev',i),('cur',i+1)]:
            for f in (*CPU_FIELDS,'ctxt'):
                row[f'raw_{side}_{f}']={'user':100*offset,'idle':300*offset,'ctxt':100*offset}.get(f,0)
        rows.append(row)
    fixture=root/'fixture.csv'
    with fixture.open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    def collector(mode='success'):
        if mode=='nonzero':
            (root/'collect_real_traces.sh').write_text('#!/bin/sh\nexit 7\n')
            return
        code='''import sys,pathlib,json,shutil,time
out=pathlib.Path(sys.argv[3]);run=out/'mock';run.mkdir(parents=True)
mode=MODE
if mode=='timeout': time.sleep(10)
if mode=='nonzero': raise SystemExit(7)
if mode!='missing_manifest':
 (run/'manifest.json').write_text(json.dumps({'status':'failed' if mode=='failed_manifest' else 'complete','success':mode!='failed_manifest','processes':{'monitor_exit':0,'worker_exit':0}}))
if mode!='missing_csv': shutil.copyfile('fixture.csv',run/'trace.csv')
if mode=='invalid_csv': (run/'trace.csv').write_text('broken')
'''.replace('MODE',repr(mode))
        script=root/'fake_collector.py';script.write_text(code)
        (root/'collect_real_traces.sh').write_text(f'#!/bin/sh\nexec {sys.executable} "{script}" "$@"\n')
    collector()
    return root,shared,collector


def test_successful_mock_exports_handoff_and_preserves_previous(setup):
    root,shared,_=setup
    (shared/'LATEST_REPORT.md').write_text('previous report')
    assert launcher.run_launcher(root,shared,confirm=lambda _: 'RUN')==0
    assert 'Validation: passed' in (shared/'LATEST_REPORT.md').read_text()
    assert next((shared/'archive').rglob('LATEST_REPORT.md')).read_text()=='previous report'
    assert len(list((shared/'results').glob('*/validated_trace.csv')))==1
    assert launcher.run_launcher(root,shared,confirm=lambda _: 'RUN')==0
    assert len(list((shared/'results').glob('*/validated_trace.csv')))==2


@pytest.mark.parametrize('mode,code',[('nonzero',7),('timeout',124),('missing_csv',1),
                                    ('invalid_csv',1),('missing_manifest',1),('failed_manifest',1)])
def test_failure_paths_do_not_report_success(setup,mode,code):
    root,shared,collector=setup;collector(mode)
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN',timeout_s=.3 if mode=='timeout' else 15)==code
    assert 'Validation: passed' not in (shared/'LATEST_REPORT.md').read_text()


def test_confirmation_declined_never_runs_collector(setup):
    root,shared,_=setup
    assert launcher.run_launcher(root,shared,confirm=lambda _:'no')==1
    assert not list((root/'data').rglob('manifest.json'))


def test_missing_dependency_prevents_workload(setup,monkeypatch):
    root,shared,_=setup
    original=launcher.shutil.which
    monkeypatch.setattr(launcher.shutil,'which',lambda name:None if name=='stress-ng' else original(name))
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    assert 'stress-ng' in (shared/'LATEST_REPORT.md').read_text()


def test_memory_preflight_failure_prevents_workload(setup,monkeypatch):
    root,shared,_=setup
    monkeypatch.setattr(launcher,'resources',lambda:dict(mem_available_kib=10,swap_used_kib=0))
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    assert not list((root/'data').rglob('manifest.json'))


def test_export_failure_preserves_local_report(setup,monkeypatch):
    root,shared,_=setup
    def failed(*args,**kwargs):raise OSError('mock export failed')
    monkeypatch.setattr(launcher.shutil,'copytree',failed)
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    assert list((root/'data').rglob('CPU_EXPERIMENT_REPORT.md'))
    assert 'Overall success: False' in next((root/'data').rglob('CPU_EXPERIMENT_REPORT.md')).read_text()


def test_existing_experiment_lock_refuses_launcher(setup):
    root,shared,_=setup
    from benchmark.collect_traces import experiment_lock
    with experiment_lock(root):
        assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1


@pytest.mark.parametrize('signal_name,exit_code',[('SIGINT',130),('SIGTERM',143)])
def test_interrupt_stops_harmless_collector_and_exports_report(setup,monkeypatch,signal_name,exit_code):
    import os
    import signal
    import threading
    root,shared,collector=setup;collector('timeout')
    original=launcher.subprocess.Popen
    children=[]
    timers=[]
    def launch(*args,**kwargs):
        process=original(*args,**kwargs)
        if kwargs.get('start_new_session'):
            children.append(process)
            timer=threading.Timer(.3,lambda:os.kill(os.getpid(),getattr(signal,signal_name)))
            timers.append(timer);timer.start()
        return process
    monkeypatch.setattr(launcher.subprocess,'Popen',launch)
    try:
        assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==exit_code
    finally:
        for timer in timers:timer.join(timeout=1)
    assert children and all(p.poll() is not None for p in children)
    assert 'Interrupted by signal' in (shared/'LATEST_REPORT.md').read_text()


def test_active_swapping_prevents_workload(setup,monkeypatch):
    root,shared,_=setup
    values=iter([(0,0),(0,1),(0,2),(0,3)])
    monkeypatch.setattr(launcher,'swap_activity',lambda:next(values))
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    assert not list((root/'data').rglob('manifest.json'))


def test_inherited_lock_does_not_release_launcher_lock(setup):
    import os
    import subprocess
    from benchmark.collect_traces import experiment_lock
    root,_,_=setup
    with experiment_lock(root) as fd:
        command=[sys.executable,'-c',
                 'from pathlib import Path; import sys; from benchmark.collect_traces import experiment_lock; '
                 'ctx=experiment_lock(Path(sys.argv[1])); ctx.__enter__(); ctx.__exit__(None,None,None)',str(root)]
        result=subprocess.run(command,cwd=Path(__file__).resolve().parents[1],
                              env=dict(os.environ,POWER_GOVERNOR_EXPERIMENT_LOCK_FD=str(fd)),
                              pass_fds=(fd,),capture_output=True,text=True,timeout=5)
        assert result.returncode==0,result.stderr
        with pytest.raises(RuntimeError,match='already running'):
            with experiment_lock(root):
                pass


def test_fallback_cleanup_stops_recorded_harmless_session(tmp_path):
    import subprocess
    from benchmark.collect_traces import process_record,cleanup_recorded_groups,stop_group
    process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'],start_new_session=True)
    try:
        (tmp_path/'processes.json').write_text(json.dumps({'worker':process_record(process.pid)}))
        assert cleanup_recorded_groups(tmp_path)
        assert process.wait(timeout=2) != 0
    finally:
        stop_group(process)


def test_recorded_cleanup_runs_even_if_launcher_child_stop_raises(setup,monkeypatch):
    root,shared,_=setup;called=[]
    def failed(*args):raise RuntimeError('mock stop race')
    monkeypatch.setattr(launcher,'stop_launcher_child',failed)
    monkeypatch.setattr(launcher,'cleanup_recorded_groups',lambda p:called.append(p) or True)
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    assert called


def test_partial_handoff_failure_cannot_leave_shared_success(setup,monkeypatch):
    root,shared,_=setup
    original=launcher.atomic_text
    def failed(path,content):
        if Path(path)==shared/'SESSION_STATUS.md':raise OSError('mock handoff failure')
        return original(path,content)
    monkeypatch.setattr(launcher,'atomic_text',failed)
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    latest=shared/'LATEST_REPORT.md'
    assert not latest.exists() or 'Overall success: True' not in latest.read_text()
    for report in (shared/'results').glob('*/CPU_EXPERIMENT_REPORT.md'):
        assert 'Overall success: True' not in report.read_text()


def test_fallback_refuses_reused_leader_identity(tmp_path):
    import subprocess
    from benchmark.collect_traces import process_record,cleanup_recorded_groups,stop_group
    process=subprocess.Popen([sys.executable,'-c','import time; time.sleep(10)'],start_new_session=True)
    try:
        record=process_record(process.pid);record['start_ticks']-=1
        (tmp_path/'processes.json').write_text(json.dumps({'worker':record}))
        with pytest.raises(RuntimeError,match='identity'):
            cleanup_recorded_groups(tmp_path)
        assert process.poll() is None
    finally:
        stop_group(process)


@pytest.mark.parametrize('counters,expected_code',[
    ([(100,200),(118,200),(118,200),(118,200)],0),
    ([(100,200),(132,200),(132,200),(132,200)],0),
    ([(100,200),(133,200),(133,200),(133,200)],1),
    ([(100,200),(101,200),(102,200),(102,200)],1),
    ([(100,200),(100,201),(100,202),(100,203)],1),
    ([(100,200),(99,200),(99,200),(99,200)],1),
    ([(100,200),(100,200),(100,200),(101,200)],0),
    ([(100,200),(116,216),(116,216),(116,216)],0),
    ([(100,200),(116,217),(116,217),(116,217)],1),
    ([(100,200),(101,200),(101,200),(101,201)],1),
])
def test_swap_windows_reject_sustained_or_large_activity(setup,monkeypatch,counters,expected_code):
    root,shared,_=setup
    values=iter(counters)
    monkeypatch.setattr(launcher,'swap_activity',lambda:next(values))
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==expected_code
    state=json.loads(next((root/'data').rglob('launcher-metadata.json')).read_text())
    diagnostic=state['swap_preflight']
    assert diagnostic['samples'][0]['pswpin']==100
    assert diagnostic['samples'][0]['pswpout']==200
    assert diagnostic['max_total_pages']==32
    assert diagnostic['max_active_windows']==1
    assert diagnostic['passed']==(expected_code==0)
    if expected_code:
        assert state['collector_started'] is False
        assert 'swap_preflight' in (shared/'LATEST_REPORT.md').read_text()


def test_swap_diagnostics_report_units_deltas_and_resources(setup,monkeypatch):
    root,shared,_=setup
    values=iter([(100,200),(118,200),(118,200),(118,200)])
    times=iter([10,10.25,10.5,10.75])
    monkeypatch.setattr(launcher,'swap_activity',lambda:next(values))
    monkeypatch.setattr(launcher.time,'monotonic',lambda:next(times))
    monkeypatch.setattr(launcher.os,'sysconf',lambda _:4096)
    diagnostics={}
    launcher.preflight(root,shared,diagnostics)
    result=diagnostics['swap_preflight']
    assert result['elapsed_s']==.75
    assert result['total_pages']==18
    assert result['total_kib']==72
    assert result['active_windows']==1
    assert result['windows'][0]['delta_pswpin_pages']==18
    assert result['windows'][0]['delta_pswpout_pages']==0
    assert result['windows'][0]['swap_kib_per_s']==288
    assert result['samples'][0]['resources']['mem_available_kib']==2097152


@pytest.mark.parametrize('current',[
    dict(mem_available_kib=512*1024-1,swap_used_kib=0),
    dict(mem_available_kib=2*1024*1024,swap_used_kib=128*1024+1),
])
def test_memory_pressure_during_swap_windows_preserves_failure_evidence(setup,monkeypatch,current):
    root,shared,_=setup
    observations=iter([dict(mem_available_kib=2*1024*1024,swap_used_kib=0),current,current])
    monkeypatch.setattr(launcher,'resources',lambda:next(observations))
    assert launcher.run_launcher(root,shared,confirm=lambda _:'RUN')==1
    state=json.loads(next((root/'data').rglob('launcher-metadata.json')).read_text())
    assert state['collector_started'] is False
    assert state['swap_preflight']['passed'] is False
    assert state['swap_preflight']['samples'][-1]['resources']==current
