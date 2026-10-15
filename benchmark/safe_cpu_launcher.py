"""Standalone CPU experiment handoff; interactive, single attempt, no dependency installs."""
from collections import Counter
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from benchmark.collect_traces import cleanup_recorded_groups, experiment_lock
from classifier.rules import classify
from monitor.capture import check_resources, resources, validate_trace


def swap_activity():
    values=dict(line.split() for line in Path('/proc/vmstat').read_text().splitlines())
    return int(values['pswpin']),int(values['pswpout'])


def atomic_text(path,content):
    path=Path(path)
    fd,temp=tempfile.mkstemp(prefix='.'+path.name+'.',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(content);stream.flush();os.fsync(stream.fileno())
        os.replace(temp,path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def preflight(root,shared,diagnostics=None,*,profile='cpu'):
    for name in ('.venv/bin/python','collect_real_traces.sh','benchmark/collect_traces.py',
                 'monitor/capture.py','monitor/reader.py'):
        if not (root/name).is_file():
            raise RuntimeError(f'Missing required project file: {name}')
    if not os.access(root/'.venv/bin/python',os.X_OK):
        raise RuntimeError('Python environment is not executable')
    for name in (('stress-ng',) if profile=='cpu' else ()) + ('timeout','bash','git'):
        if not shutil.which(name):
            raise RuntimeError(f'Missing dependency: {name}; no packages installed')
    if not os.path.ismount(shared):
        raise RuntimeError('Shared folder is not mounted; no workload started')
    fd,probe=tempfile.mkstemp(prefix='.cpu-preflight-',dir=shared)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write('write/read probe\n')
        if Path(probe).read_text()!='write/read probe\n':
            raise RuntimeError('Shared folder readback failed')
    finally:
        Path(probe).unlink(missing_ok=True)
    if shutil.disk_usage(root).free < 512*1024*1024:
        raise RuntimeError('Free local disk space below 512 MiB')
    if diagnostics is None:
        diagnostics={}
    activity=dict(requested_window_s=.25,window_count=3,max_total_pages=32,
                  max_active_windows=1,page_size_bytes=os.sysconf('SC_PAGE_SIZE'),
                  min_available_kib=512*1024,max_swap_growth_kib=128*1024,
                  samples=[],windows=[],passed=False)
    diagnostics['swap_preflight']=activity
    first=resources()
    diagnostics['resources_before']=first
    check_resources(first,first)
    previous=swap_activity();start=time.monotonic();previous_time=start
    activity['samples'].append(dict(pswpin=previous[0],pswpout=previous[1],
                                    elapsed_s=0,resources=first))
    for _ in range(activity['window_count']):
        time.sleep(activity['requested_window_s'])
        current=swap_activity();now=time.monotonic();second=resources()
        elapsed=now-previous_time
        delta_in=current[0]-previous[0];delta_out=current[1]-previous[1]
        kib=(delta_in+delta_out)*activity['page_size_bytes']/1024
        activity['samples'].append(dict(pswpin=current[0],pswpout=current[1],
                                        elapsed_s=now-start,resources=second))
        activity['windows'].append(dict(elapsed_s=elapsed,delta_pswpin_pages=delta_in,
                                        delta_pswpout_pages=delta_out,
                                        swap_kib_per_s=kib/elapsed if elapsed>0 else None))
        check_resources(second,first)
        if delta_in<0 or delta_out<0 or elapsed<=0:
            raise RuntimeError('Invalid swap counter/timing observation; see swap_preflight diagnostics')
        previous=current;previous_time=now
    activity['elapsed_s']=now-start
    activity['total_pages']=sum(w['delta_pswpin_pages']+w['delta_pswpout_pages']
                                for w in activity['windows'])
    activity['total_kib']=activity['total_pages']*activity['page_size_bytes']/1024
    activity['active_windows']=sum(w['delta_pswpin_pages']+w['delta_pswpout_pages']>0
                                   for w in activity['windows'])
    if (activity['total_pages']>activity['max_total_pages']
            or activity['active_windows']>activity['max_active_windows']):
        raise RuntimeError(f'Swap preflight rejected: {activity["total_pages"]} pages '
                           f'({activity["total_kib"]:g} KiB), {activity["active_windows"]}/3 active windows; '
                           'limits <=32 pages and <=1 active window; close applications and inspect before retrying manually')
    activity['passed']=True
    for path in Path('/proc').glob('[0-9]*/cmdline'):
        try:
            if int(path.parent.name)==os.getpid() or path.stat().st_uid!=os.getuid():
                continue
            args=path.read_bytes().split(b'\0')
            if any(a==b'benchmark.collect_traces' or a.endswith(b'/collect_real_traces.sh') for a in args):
                raise RuntimeError('An existing collector process is running')
        except (OSError,ValueError):
            continue
    return second


def stop_launcher_child(process):
    if process is None:
        return
    if process.poll() is None:
        try:
            os.killpg(process.pid,signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=2)


def export_run(run,shared,report,*,profile='cpu'):
    report_name='CPU_EXPERIMENT_REPORT.md' if profile=='cpu' else 'BACKGROUND_READINESS_REPORT.md'
    target=shared/'results'/(f'safe_{profile}_'+run.name)
    target.parent.mkdir(exist_ok=True)
    shutil.copytree(run,target)  # refuses an existing destination
    for source in run.rglob('*'):
        if source.is_file():
            copied=target/source.relative_to(run)
            if hashlib.sha256(source.read_bytes()).digest()!=hashlib.sha256(copied.read_bytes()).digest():
                raise RuntimeError('Export hash verification failed')
    for name,content in [('SESSION_STATUS.md',
            f'# Standalone {profile} observation\nReport: results/{target.name}/{report_name}\n'
            'Read LATEST_REPORT.md for outcome, errors, checkpoint and next action.\n'),('LATEST_REPORT.md',report)]:
        path=shared/name
        if path.exists():
            archive=shared/'archive'/run.name
            archive.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,archive/name)
        atomic_text(path,content)
    return target


def validate_background_handshake(directory,manifest):
    """A valid CSV alone cannot establish the new readiness mechanism worked."""
    lifecycle=json.loads((directory/'lifecycle.json').read_text())
    if lifecycle!=manifest.get('lifecycle'):
        raise RuntimeError('Background lifecycle and manifest disagree')
    names=[event['event'] for event in lifecycle['events']]
    required=('monitor_started','monitor_ready','sampling_released','monitor_exited','cleanup_finished')
    if any(names.count(name)!=1 for name in required):
        raise RuntimeError('Missing or ambiguous background readiness lifecycle events')
    positions=[names.index(name) for name in required]
    if positions!=sorted(positions):
        raise RuntimeError('Background readiness lifecycle order is invalid')
    if (lifecycle.get('monitor_exit')!=0 or lifecycle.get('worker_exit') is not None
            or lifecycle.get('cleanup')!='completed' or 'worker_started' in names):
        raise RuntimeError('Background lifecycle exits/cleanup failed or worker started')
    records=json.loads((directory/'processes.json').read_text())
    if set(records)!={'monitor'}:
        raise RuntimeError('Background observation requires only a recorded monitor, no worker')
    for name in ('monitor.ready','monitor.start','monitor.log'):
        if not (directory/name).is_file():
            raise RuntimeError(f'Missing background readiness evidence: {name}')


def run_launcher(root,shared,confirm=None,timeout_s=15,*,profile='cpu'):
    if profile not in ('cpu','background'):
        raise ValueError('Only cpu and background launcher profiles are supported')
    cpu=profile=='cpu'
    report_name='CPU_EXPERIMENT_REPORT.md' if cpu else 'BACKGROUND_READINESS_REPORT.md'
    label='cpu_stressor_1_worker' if cpu else 'uncontrolled_background'
    root=Path(root).resolve();shared=Path(shared).resolve()
    parent=root/('data/controlled_cpu' if cpu else 'data/background_readiness')
    parent.mkdir(parents=True,exist_ok=True)
    run=Path(tempfile.mkdtemp(prefix='launcher-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=parent))
    (run/'launcher-stdout.log').touch(exist_ok=False)
    (run/'launcher-stderr.log').touch(exist_ok=False)
    state=dict(start_utc=datetime.now(timezone.utc).isoformat(),workload_started=False,
               collector_started=False,validation='not performed',cleanup='not needed',errors=[],
               config=dict(profile=profile,cpu_workers=1 if cpu else 0,method='int64' if cpu else None,sampling_intervals=5,interval_s=1,
                           worker_timeout_s=7 if cpu else None,supervisor_deadline_s=11,outer_timeout_s=timeout_s,
                           vm_workers=0,io_workers=0,frequency_control='none'),statistics=None)
    process=None;code=1;handlers={};lock=None
    def cancelled(signum,frame):
        raise InterruptedError(signum)
    try:
        lock=experiment_lock(root);fd=lock.__enter__()
        handlers={sig:signal.signal(sig,cancelled) for sig in (signal.SIGINT,signal.SIGTERM)}
        state['resources_before']=preflight(root,shared,state,profile=profile)
        for cmd,name in ((['uname','-a'],'kernel'),(['lscpu'],'cpu'),(['git','rev-parse','HEAD'],'commit'),
                         (['git','status','--porcelain'],'git_changes')):
            result=subprocess.run(cmd,cwd=root,text=True,capture_output=True,timeout=3)
            state[name]=result.stdout.strip()
        state['source_hashes']={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                               for name in ('benchmark/collect_traces.py','monitor/capture.py','monitor/reader.py',
                                            'benchmark/safe_cpu_launcher.py','scripts/run_safe_cpu_experiment.sh',
                                            'scripts/run_background_readiness.sh','benchmark/background_launcher.py',
                                            'collect_real_traces.sh') if (p:=root/name).is_file()}
        prompt=('Close Codex and unnecessary applications first. This starts ONE int64 CPU worker, '
                '5 samples, 7s worker / 11s supervisor / 15s outer deadline. '
                'KVM/legacy timing discrepancy remains unresolved; guest timers cannot protect a frozen host. '
                'Type RUN to confirm this exact experiment (anything else cancels): ')
        if not cpu:
            prompt=('Close Codex and unnecessary applications first. This records FIVE background-only '
                    'intervals with ZERO CPU/memory/I/O workers and no frequency control. '
                    '11s supervisor / 15s outer deadline; existing preflight and cleanup remain. '
                    'Type RUN to confirm this observation (anything else cancels): ')
        if confirm is None:
            if not sys.stdin.isatty():
                raise RuntimeError('Interactive terminal required; piped confirmation is refused')
            confirm=input
        if confirm(prompt)!='RUN':
            raise RuntimeError('Experiment cancelled before starting collector')
        # Recheck resources after the user may have spent time reading the prompt.
        check_resources(resources(),state['resources_before'])
        command=['timeout','--signal=TERM','--kill-after=1s',f'{timeout_s}s','bash',
                 str(root/'collect_real_traces.sh'),'5','64M',str(run/'collection'),
                 '--profile',profile]
        if cpu:
            command.append('--approved-workload')
        state['command']=command
        atomic_text(run/'launcher-metadata.json',json.dumps(state,indent=2)+'\n')
        env=dict(os.environ,POWER_GOVERNOR_EXPERIMENT_LOCK_FD=str(fd),
                 OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1')
        with (run/'launcher-stdout.log').open('a') as stdout, (run/'launcher-stderr.log').open('a') as stderr:
            process=subprocess.Popen(command,cwd=root,env=env,pass_fds=(fd,),stdout=stdout,stderr=stderr,
                                     start_new_session=True)
            state['collector_started']=True
            state['launcher_child_pid']=process.pid
            atomic_text(run/'launcher-metadata.json',json.dumps(state,indent=2)+'\n')
            code=process.wait(timeout=timeout_s+4)
        state['collector_exit']=code
        if code:
            raise RuntimeError(f'Collector/outer timeout returned {code}; no automatic retry')
        manifests=list((run/'collection').glob('*/manifest.json'))
        if len(manifests)!=1:
            raise RuntimeError('Missing or ambiguous collector manifest')
        directory=manifests[0].parent
        manifest=json.loads(manifests[0].read_text())
        state['manifest']=manifest
        if (manifest.get('status')!='complete' or manifest.get('success') is not True
                or manifest.get('processes',{}).get('worker_exit')!=(0 if cpu else None)
                or manifest.get('processes',{}).get('monitor_exit')!=0):
            raise RuntimeError('Collector success/exit manifest failed validation')
        if not cpu:
            validate_background_handshake(directory,manifest)
            state['handshake_validation']='passed'
        stats=validate_trace(directory/'trace.csv',5,label,
                             os.cpu_count()*os.sysconf('SC_CLK_TCK'))
        with (directory/'trace.csv').open() as stream:
            rows=list(csv.DictReader(stream))
        state['classifier_counts']=dict(Counter(classify({k:float(r[k]) for k in
            ('util_pct','iowait_pct','ctxt_per_s','procs_running','procs_blocked')}) for r in rows))
        shutil.copy2(directory/'trace.csv',run/'validated_trace.csv')
        state.update(validation='passed',statistics=stats)
    except InterruptedError as error:
        code=128+int(error.args[0]);state['errors'].append(f'Interrupted by signal {error.args[0]}')
    except subprocess.TimeoutExpired:
        code=124;state['errors'].append('Launcher wait deadline exceeded; no retry')
    except Exception as error:
        code=code or 1;state['errors'].append(f'{type(error).__name__}: {error}')
    finally:
        # Finish cleanup/reporting even if the terminal sends another interrupt.
        for sig in handlers:
            signal.signal(sig,signal.SIG_IGN)
        try:
            stop_launcher_child(process)
        except Exception as error:
            code=code or 1
            state['errors'].append(f'Launcher child stop: {error}')
        try:
            clean=cleanup_recorded_groups(run/'collection')
            state['cleanup']='verified no recorded running processes' if clean else 'failed: running processes remain'
            if not clean:
                code=code or 1
            state['resources_after']=resources()
            if 'resources_before' in state:
                check_resources(state['resources_after'],state['resources_before'])
            state['workload_started']=any('worker' in json.loads(p.read_text())
                                            for p in (run/'collection').rglob('processes.json'))
        except Exception as error:
            state['cleanup']='unverified';code=code or 1
            state['errors'].append(f'Cleanup/resource check: {error}')
        state['exit_code']=code;state['end_utc']=datetime.now(timezone.utc).isoformat()
        state['success']=code==0 and state['validation']=='passed'
        with (run/'launcher-stdout.log').open('a') as stream:
            stream.write(f'Launcher pre-export exit={code}; local evidence: {run}\n')
        with (run/'launcher-stderr.log').open('a') as stream:
            stream.write('\n'.join(state['errors'])+'\n')
        report=(('# CPU experiment report\n\n' if cpu else '# Background readiness report\n\n')+
                f'Date: {state["start_utc"]}\n\nValidation: {state["validation"]}\n'
                f'Overall success: {state["success"]}; exit code: {code}\n'
                f'Commit: {state.get("commit","unavailable")}; dirty state: {bool(state.get("git_changes"))}\n'
                f'Collector started: {state["collector_started"]}; worker startup recorded: {state["workload_started"]}\n'
                f'Cleanup: {state["cleanup"]}\n\n'
                f'Local evidence: {run}\nShared evidence: results/safe_{profile}_{run.name}/\n\n'
                'Configuration, resources before/after, manifest, statistics, class counts and errors:\n\n'
                '```json\n'+json.dumps(state,indent=2)+'\n```\n\n'
                'Interpretation: actual Linux counters; no frequency writes or measured energy. '+
                ('A successful worker exit plus validated observations supports completion, not classifier ground truth. '
                 'One busy worker may yield roughly 25% aggregate utilization on four vCPUs; below 70% is not failure. '
                 if cpu else 'Background-only observations are uncontrolled kernel counters, not idle ground truth or a CPU workload dataset. ')+
                'Guest timers cannot recover an unresponsive VM/host. No retry occurred.\n\n'
                'Next action: review manifest, worker logs and CSV; obtain approval before any further experiment.\n')
        atomic_text(run/report_name,report)
        atomic_text(run/'launcher-metadata.json',json.dumps(state,indent=2)+'\n')
        try:
            if not os.path.ismount(shared):
                raise RuntimeError('Shared mount unavailable; local handoff preserved')
            target=export_run(run,shared,report,profile=profile)
            print(f'Report exported: {target}/{report_name}')
        except Exception as error:
            code=code or 1
            state.update(exit_code=code,success=False,export='failed')
            state['errors'].append(f'Export: {error}')
            report=report.replace('Overall success: True; exit code: 0',
                                  f'Overall success: False; exit code: {code}')
            report+=f'\nExport failed: {error}. Local evidence preserved; shared handoff may be stale.\n'
            before_json,after_json=report.split('```json\n',1)
            _,tail=after_json.split('\n```',1)
            report=before_json+'```json\n'+json.dumps(state,indent=2)+'\n```'+tail
            atomic_text(run/report_name,report)
            atomic_text(run/'launcher-metadata.json',json.dumps(state,indent=2)+'\n')
            atomic_text(run/'export-error.txt',f'{type(error).__name__}: {error}\n')
            # Correct any partial export once; leave local evidence if the mount is failing.
            try:
                target=shared/'results'/(f'safe_{profile}_'+run.name)
                if target.is_dir():
                    atomic_text(target/report_name,report)
                    atomic_text(target/'launcher-metadata.json',json.dumps(state,indent=2)+'\n')
                latest=shared/'LATEST_REPORT.md'
                if latest.exists() and str(run) in latest.read_text():
                    atomic_text(latest,report)
            except Exception:
                pass
            print(f'Export failed: {error}. Local report: {run}/{report_name}',file=sys.stderr)
        if lock is not None:
            lock.__exit__(None,None,None)
        for sig,handler in handlers.items():
            signal.signal(sig,handler)
        print(f'Launcher exit={code}; local evidence: {run}')
    return code


def main():
    if len(sys.argv)!=1:
        print('No command-line overrides are accepted; run interactively without arguments.',file=sys.stderr)
        return 2
    return run_launcher(Path(__file__).resolve().parents[1],Path('/media/sf_OS_Project_Shared'))


if __name__=='__main__':
    raise SystemExit(main())
