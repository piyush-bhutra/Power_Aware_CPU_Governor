"""Conservative, explicitly approved collection; never changes CPU frequency."""
import argparse
from contextlib import contextmanager
import fcntl
from datetime import datetime, timezone
import json
import hashlib
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

from monitor.capture import check_resources, resources, validate_trace


@contextmanager
def experiment_lock(root):
    """One project experiment; launcher may pass its already-held lock to collector."""
    path=Path(root)/'data/.experiment.lock'
    path.parent.mkdir(parents=True,exist_ok=True)
    inherited=os.environ.get('POWER_GOVERNOR_EXPERIMENT_LOCK_FD')
    if inherited:
        fd=os.dup(int(inherited))
        if (os.fstat(fd).st_dev,os.fstat(fd).st_ino)!=(path.stat().st_dev,path.stat().st_ino):
            os.close(fd)
            raise RuntimeError('Invalid inherited experiment lock')
    else:
        fd=os.open(path,os.O_RDWR|os.O_CREAT,0o600)
    try:
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError('Another project experiment is already running') from error
        yield fd
    finally:
        os.close(fd)  # keep parent lock held when collector inherited the same description


def process_record(pid):
    fields=Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()
    return dict(pid=pid,pgid=int(fields[2]),session=int(fields[3]),start_ticks=int(fields[19]))


def cleanup_recorded_groups(directory):
    """Fallback after supervisor interruption; identify owned sessions before signalling."""
    def members(record):
        found=[]
        for path in Path('/proc').glob('[0-9]*/stat'):
            try:
                if path.stat().st_uid!=os.getuid():
                    continue
                fields=path.read_text().rsplit(')',1)[1].split()
                if (int(fields[2])==record['pgid'] and int(fields[3])==record['session']
                        and int(fields[19])>=record['start_ticks'] and fields[0] not in ('Z','X')):
                    found.append(int(path.parent.name))
            except (OSError,ValueError,IndexError):
                continue
        return found
    clean=True
    for path in Path(directory).rglob('processes.json'):
        records=json.loads(path.read_text())
        for record in records.values():
            if record['pgid']!=record['pid'] or record['session']!=record['pid'] or record['pgid']==os.getpgrp():
                raise RuntimeError('Unsafe recorded process group; refusing cleanup')
            try:
                leader=process_record(record['pid'])
            except FileNotFoundError:
                leader=None
            if leader is not None and leader['start_ticks']!=record['start_ticks']:
                raise RuntimeError('Recorded leader identity has changed; refusing cleanup')
            for sig,delay in ((signal.SIGTERM,.2),(signal.SIGKILL,.2)):
                if not members(record):
                    break
                try:
                    os.killpg(record['pgid'],sig)
                except ProcessLookupError:
                    break
                time.sleep(delay)
            clean=not members(record) and clean
    return clean


def parse_args(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('duration', type=int, help='1–30 one-second sampling intervals')
    parser.add_argument('vm_bytes', help='positive memory budget, at most 128M')
    parser.add_argument('outdir', nargs='?', default='data/real_traces')
    parser.add_argument('--profile', choices=('cpu','vm','mixed','background','idle'), default='cpu')
    parser.add_argument('--approved-workload', action='store_true',
                        help='use only after explicit approval of this experiment plan')
    args=parser.parse_args(argv)
    match=re.fullmatch(r'([1-9][0-9]*)([KMGkmg]?)',args.vm_bytes)
    if not match or not 1 <= args.duration <= 30:
        parser.error('duration must be 1–30 and vm_bytes a positive byte count or K/M/G value')
    args.memory_bytes=int(match[1])*1024**('KMG'.index(match[2].upper())+1 if match[2] else 0)
    if args.memory_bytes > 128*1024*1024:
        parser.error('memory budget exceeds conservative 128 MiB limit')
    if args.profile=='idle':
        args.profile='background'
    if args.profile!='background' and not args.approved_workload:
        parser.error('artificial workloads require separate approval and --approved-workload')
    return args


def stop_group(process):
    if process is None:
        return
    # Descendants can remain even if the leader has exited.
    for sig in (signal.SIGTERM,signal.SIGKILL):
        try:
            os.killpg(process.pid,sig)
        except ProcessLookupError:
            break
        if sig==signal.SIGTERM:
            time.sleep(.1)
    process.wait(timeout=2)


def run_processes(monitor_command, worker_command, directory, timeout_s, *, readiness=False):
    """Watch owned groups within one total budget; readiness never extends it."""
    monitor=worker=None
    started=time.monotonic()
    initial=resources()
    check_resources(initial,initial)
    records={}
    evidence=dict(events=[], monitor_exit=None, worker_exit=None, cleanup='pending')
    diagnostic_errors=[]
    def event(name, **details):
        evidence['events'].append(dict(event=name, elapsed_s=time.monotonic()-started,
                                      utc=datetime.now(timezone.utc).isoformat(), **details))
        save_evidence()
    def save_evidence():
        try:
            temp=directory/'.lifecycle.tmp'
            temp.write_text(json.dumps(evidence,indent=2)+'\n')
            os.replace(temp,directory/'lifecycle.json')
        except OSError as error:
            # Diagnostic storage must never prevent either group's cleanup.
            diagnostic_errors.append(str(error))
    def record(name,process):
        records[name]=process_record(process.pid)
        temp=directory/'.processes.tmp'
        temp.write_text(json.dumps(records,indent=2)+'\n')
        os.replace(temp,directory/'processes.json')
        event(name+'_started',pid=process.pid)
    def deadline(phase):
        evidence['deadline_phase']=phase
        event('deadline_exceeded',phase=phase)
        raise TimeoutError(f'{phase} deadline exceeded within external collector budget')
    with (directory/'monitor.log').open('x') as monitor_log, (directory/'worker.log').open('x') as worker_log:
        try:
            monitor=subprocess.Popen(monitor_command,stdout=monitor_log,stderr=subprocess.STDOUT,
                                     start_new_session=True)
            record('monitor',monitor)
            if readiness:
                while True:
                    check_resources(resources(),initial)
                    code=monitor.poll()
                    if code is not None:
                        raise RuntimeError(f'monitor exited before readiness with status {code}; see monitor.log')
                    elapsed=time.monotonic()-started
                    if elapsed >= min(2,timeout_s):
                        deadline('startup')
                    if (directory/'monitor.ready').exists():
                        event('monitor_ready')
                        break
                    time.sleep(.05)
            if worker_command:
                if time.monotonic()-started >= (min(2,timeout_s) if readiness else timeout_s):
                    deadline('startup')
                worker=subprocess.Popen(worker_command,stdout=worker_log,stderr=subprocess.STDOUT,
                                        start_new_session=True)
                record('worker',worker)
            if readiness:
                if time.monotonic()-started >= timeout_s:
                    deadline('startup')
                # Baseline is taken only after worker launch, so pre-load startup
                # does not consume one of the requested observation intervals.
                (directory/'monitor.start').touch(exist_ok=False)
                event('sampling_released')
            while True:
                check_resources(resources(),initial)
                monitor_code=monitor.poll()
                worker_code=worker.poll() if worker else None
                for name,code in (('monitor',monitor_code),('worker',worker_code)):
                    if code is not None and evidence[name+'_exit'] is None:
                        evidence[name+'_exit']=code
                        event(name+'_exited',exit_code=code)
                if worker and worker_code is not None and worker_code != 0:
                    raise RuntimeError(f'worker exited with status {worker_code}; see worker.log')
                if monitor_code is not None and monitor_code != 0:
                    raise RuntimeError(f'monitor exited with status {monitor_code}; see monitor.log')
                if worker and worker_code==0 and monitor_code is None:
                    raise RuntimeError('worker ended before monitoring completed; invalid workload trace')
                # Deadline precedes success: a late poll must not accept overruns.
                if time.monotonic()-started >= timeout_s:
                    deadline('sampling' if monitor_code is None else 'workload')
                if monitor_code==0 and (worker is None or worker_code==0):
                    return dict(monitor_exit=monitor_code,worker_exit=worker_code,
                                elapsed_s=time.monotonic()-started)
                time.sleep(.05)
        except BaseException as error:
            event('failure',error=f'{type(error).__name__}: {error}')
            raise
        finally:
            cleanup_errors=[]
            for name,process in (('monitor',monitor),('worker',worker)):
                try:
                    if process is not None:
                        event(name+'_cleanup_requested',exit_before_cleanup=process.poll())
                    stop_group(process)
                except BaseException as error:
                    cleanup_errors.append(error)
                    event(name+'_cleanup_failed',error=f'{type(error).__name__}: {error}')
                finally:
                    if process is not None:
                        evidence[name+'_exit']=process.returncode
            evidence['cleanup']='failed' if cleanup_errors else 'completed'
            event('cleanup_finished')
            if cleanup_errors:
                raise cleanup_errors[0]
            if diagnostic_errors and sys.exc_info()[0] is None:
                raise RuntimeError(f'Lifecycle diagnostic storage failed: {diagnostic_errors[0]}')


def collect():
    args=parse_args()
    parent=Path(args.outdir).resolve()
    shared=Path('/media/sf_OS_Project_Shared')
    if parent==shared or shared in parent.parents:
        raise ValueError('Collect locally first; shared-folder collection is refused')
    parent.mkdir(parents=True,exist_ok=True)
    if shutil.disk_usage(parent).free < 512*1024*1024:
        raise RuntimeError('Disk free space below 512 MiB')
    directory=Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-'),dir=parent))
    label=dict(cpu='cpu_stressor_1_worker', vm='memory_stressor_1_worker',
               mixed='cpu_memory_stressors_1_each', background='uncontrolled_background')[args.profile]
    worker=None
    if args.profile!='background':
        worker=['stress-ng','--timeout',f'{args.duration+2}s','--verify','--metrics-brief']
        if args.profile in ('cpu','mixed'):
            worker+=['--cpu','1','--cpu-method','int64']
        if args.profile in ('vm','mixed'):
            worker+=['--vm','1','--vm-bytes',str(args.memory_bytes),'--vm-method','flip']
    command=[sys.executable,'-u','-m','monitor.capture','--ticks',str(args.duration),
             '--label',label,'--output',str(directory/'trace.csv'),
             '--ready-file',str(directory/'monitor.ready'),'--start-file',str(directory/'monitor.start')]
    revision=subprocess.run(['git','rev-parse','HEAD'],capture_output=True,text=True,timeout=5)
    dirty=subprocess.run(['git','status','--porcelain'],capture_output=True,text=True,timeout=5)
    root=Path(__file__).resolve().parents[1]
    source_hashes={name:hashlib.sha256((root/name).read_bytes()).hexdigest()
                   for name in ('monitor/reader.py','monitor/capture.py',
                                'benchmark/collect_traces.py','collect_real_traces.sh')}
    metadata=dict(start_utc=datetime.now(timezone.utc).isoformat(),commit=revision.stdout.strip(),
                  working_tree_dirty=bool(dirty.stdout.strip()),source_hashes=source_hashes,
                  profile=args.profile,workload_label=label,monitor_command=command,worker_command=worker,
                  max_memory_bytes=args.memory_bytes,cpu_workers=1 if args.profile in ('cpu','mixed') else 0,
                  interval_s=1,duration_intervals=args.duration,external_timeout_s=args.duration+6,
                  startup_timeout_s=2,worker_timeout_s=args.duration+2,
                  frequency_control='none',initial_resources=resources(),
                  limitations='Aggregate counters; requested stressor labels are not classifier ground truth.')
    (directory/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    manifest=dict(status='running',success=False,workload_label=label)
    def save_manifest():
        temp=directory/'.manifest.tmp'
        temp.write_text(json.dumps(manifest,indent=2)+'\n')
        os.replace(temp,directory/'manifest.json')
    save_manifest()
    def interrupted(signum,frame):
        raise InterruptedError(f'collector interrupted by signal {signum}')
    previous={sig:signal.signal(sig,interrupted) for sig in (signal.SIGINT,signal.SIGTERM)}
    try:
        manifest['processes']=run_processes(command,worker,directory,args.duration+6,readiness=True)
        stats=validate_trace(directory/'trace.csv',args.duration,label,
                             os.cpu_count()*os.sysconf('SC_CLK_TCK'))
        manifest['sample_validation']=dict(success=True,statistics=stats)
        (directory/'statistics.json').write_text(json.dumps(stats,indent=2)+'\n')
        manifest.update(status='complete',success=True)
    except BaseException as error:
        manifest.update(status='failed',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        for sig,handler in previous.items():
            signal.signal(sig,handler)
        if 'sample_validation' not in manifest:
            try:
                stats=validate_trace(directory/'trace.csv',args.duration,label,
                                     os.cpu_count()*os.sysconf('SC_CLK_TCK'))
                manifest['sample_validation']=dict(success=True,statistics=stats)
            except Exception as error:
                manifest['sample_validation']=dict(success=False,error=f'{type(error).__name__}: {error}')
        lifecycle=directory/'lifecycle.json'
        if lifecycle.exists():
            manifest['lifecycle']=json.loads(lifecycle.read_text())
        manifest['final_resources']=resources()
        manifest['end_utc']=datetime.now(timezone.utc).isoformat()
        save_manifest()
        print(f'Run preserved in {directory}; status={manifest["status"]}')


def main():
    with experiment_lock(Path(__file__).resolve().parents[1]):
        collect()


if __name__=='__main__':
    main()
