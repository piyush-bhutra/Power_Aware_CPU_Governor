"""Standalone background preparation: only fixture CSVs and harmless children."""
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from benchmark import safe_cpu_launcher as launcher
from test_safe_launcher import setup


@pytest.fixture
def background(setup):
    root,shared,_=setup
    fixture=root/'fixture.csv'
    fixture.write_text(fixture.read_text().replace('cpu_stressor_1_worker','uncontrolled_background'))
    script=root/'fake_background.py'
    script.write_text('''import sys,pathlib,json,shutil
assert sys.argv[1:3]==['5','64M']
assert sys.argv[4:]==['--profile','background']
run=pathlib.Path(sys.argv[3])/'mock';run.mkdir(parents=True)
events=[{'event':name,'elapsed_s':elapsed} for name,elapsed in
 [('monitor_started',0),('monitor_ready',.1),('sampling_released',.2),
  ('monitor_exited',5.2),('monitor_cleanup_requested',5.2),('cleanup_finished',5.3)]]
lifecycle={'events':events,'monitor_exit':0,'worker_exit':None,'cleanup':'completed'}
(run/'lifecycle.json').write_text(json.dumps(lifecycle))
(run/'manifest.json').write_text(json.dumps({'status':'complete','success':True,
 'processes':{'monitor_exit':0,'worker_exit':None},'lifecycle':lifecycle}))
# Inert fixture identity with no corresponding process; real group cleanup is
# independently covered by harmless-session tests in test_safe_launcher.py.
(run/'processes.json').write_text(json.dumps({'monitor':
 {'pid':99999999,'pgid':99999999,'session':99999999,'start_ticks':1}}))
for name in ['monitor.ready','monitor.start','worker.log']: (run/name).touch()
(run/'monitor.log').write_text('fixture baseline and interval diagnostics')
shutil.copyfile('fixture.csv',run/'trace.csv')
''')
    (root/'collect_real_traces.sh').write_text(f'#!/bin/sh\nexec {sys.executable} "{script}" "$@"\n')
    return root,shared,script


def invoke(root,shared):
    return launcher.run_launcher(root,shared,confirm=lambda _: 'RUN',profile='background')


def test_background_success_exports_handshake_and_no_worker_command(background,monkeypatch):
    root,shared,_=background
    original=launcher.shutil.which
    monkeypatch.setattr(launcher.shutil,'which',lambda name:None if name=='stress-ng' else original(name))
    assert invoke(root,shared)==0
    state=json.loads(next((root/'data').rglob('launcher-metadata.json')).read_text())
    assert state['workload_started'] is False
    assert state['config']['cpu_workers']==state['config']['vm_workers']==state['config']['io_workers']==0
    assert state['config']['supervisor_deadline_s']==11
    assert state['config']['outer_timeout_s']==15
    assert state['handshake_validation']=='passed'
    command=state['command']
    assert '--approved-workload' not in command and command[-1]=='background'
    assert '15s' in command
    target=next((shared/'results').glob('safe_background_*'))
    for name in ('lifecycle.json','monitor.log','manifest.json','trace.csv','monitor.ready','monitor.start'):
        assert list(target.rglob(name))
    assert (target/'BACKGROUND_READINESS_REPORT.md').exists()
    assert 'background' in (shared/'LATEST_REPORT.md').read_text().lower()


@pytest.mark.parametrize('mutation', ['missing_lifecycle','missing_record','worker_present','out_of_order'])
def test_background_rejects_incomplete_or_worker_handshake(background,mutation):
    root,shared,script=background
    extra={
      'missing_lifecycle': "(run/'lifecycle.json').unlink()",
      'missing_record': "(run/'processes.json').unlink(missing_ok=True)",
      'worker_present': "(run/'processes.json').write_text(json.dumps({'worker':{'pid':-1}}))",
      'out_of_order': "lifecycle['events'][1],lifecycle['events'][2]=lifecycle['events'][2],lifecycle['events'][1]; (run/'lifecycle.json').write_text(json.dumps(lifecycle)); manifest=json.loads((run/'manifest.json').read_text()); manifest['lifecycle']=lifecycle; (run/'manifest.json').write_text(json.dumps(manifest))"
    }[mutation]
    script.write_text(script.read_text()+'\n'+extra+'\n')
    assert invoke(root,shared)==1
    assert 'Overall success: True' not in (shared/'LATEST_REPORT.md').read_text()


def test_background_timeout_preserves_errors_and_never_reports_success(background):
    root,shared,script=background
    script.write_text('import time; time.sleep(10)')
    assert launcher.run_launcher(root,shared,confirm=lambda _: 'RUN',profile='background',timeout_s=.3)==124
    assert 'Overall success: False' in (shared/'LATEST_REPORT.md').read_text()


def test_background_low_ram_prevents_collector(background,monkeypatch):
    root,shared,_=background
    monkeypatch.setattr(launcher,'resources',lambda:dict(mem_available_kib=10,swap_used_kib=0))
    assert invoke(root,shared)==1
    assert not list((root/'data').rglob('manifest.json'))


def test_background_export_failure_keeps_local_report(background,monkeypatch):
    root,shared,_=background
    def fail(*args,**kwargs):
        raise OSError('mock export failed')
    monkeypatch.setattr(launcher.shutil,'copytree',fail)
    assert invoke(root,shared)==1
    report=next((root/'data').rglob('BACKGROUND_READINESS_REPORT.md'))
    assert 'Overall success: False' in report.read_text()


def test_background_collector_releases_ready_monitor_without_worker(tmp_path,monkeypatch):
    from benchmark import collect_traces
    received=[]
    def stop_before_observation(command,worker,directory,timeout_s,**kwargs):
        received.append((command,worker,timeout_s,kwargs))
        raise RuntimeError('mock stop before observation')
    monkeypatch.setattr(collect_traces,'run_processes',stop_before_observation)
    monkeypatch.setattr(sys,'argv',['collector','5','64M',str(tmp_path),'--profile','background'])
    with pytest.raises(RuntimeError,match='mock stop'):
        collect_traces.main()
    command,worker,deadline,options=received[0]
    assert worker is None and deadline==11 and options=={'readiness':True}
    assert command[1:4]==['-u','-m','monitor.capture']
    assert '--ready-file' in command and '--start-file' in command


def test_background_entrypoint_has_fixed_profile_and_refuses_overrides(monkeypatch):
    from benchmark import background_launcher
    received=[]
    monkeypatch.setattr(background_launcher,'run_launcher',lambda *args,**kwargs:received.append(kwargs) or 0)
    monkeypatch.setattr(sys,'argv',['background_launcher'])
    assert background_launcher.main()==0
    assert received==[{'profile':'background'}]
    monkeypatch.setattr(sys,'argv',['background_launcher','--profile','cpu'])
    assert background_launcher.main()==2
    assert len(received)==1


def test_standalone_shell_resolves_root_and_invokes_fixed_background_module(tmp_path):
    import shutil
    import subprocess
    root=tmp_path/'project with spaces'
    (root/'scripts').mkdir(parents=True)
    (root/'.venv/bin').mkdir(parents=True)
    wrapper=root/'scripts/run_background_readiness.sh'
    shutil.copyfile(Path(__file__).resolve().parents[1]/'scripts/run_background_readiness.sh',wrapper)
    interpreter=root/'.venv/bin/python'
    interpreter.write_text('#!/bin/sh\npwd\nprintf "%s\\n" "$@"\n')
    interpreter.chmod(0o755)
    result=subprocess.run(['bash',str(wrapper)],cwd=tmp_path,capture_output=True,text=True,timeout=3)
    assert result.returncode==0
    assert result.stdout.splitlines()==[str(root),'-m','benchmark.background_launcher']
