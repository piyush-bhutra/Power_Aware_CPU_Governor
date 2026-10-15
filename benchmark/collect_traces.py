"""Conservative, explicitly approved collection; never changes CPU frequency."""
import argparse
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


def run_processes(monitor_command, worker_command, directory, timeout_s):
    """Watch new process groups; always tear both down on failure or timeout."""
    monitor=worker=None
    started=time.monotonic()
    initial=resources()
    check_resources(initial,initial)
    with (directory/'monitor.log').open('x') as monitor_log, (directory/'worker.log').open('x') as worker_log:
        try:
            if worker_command:
                worker=subprocess.Popen(worker_command,stdout=worker_log,stderr=subprocess.STDOUT,
                                        start_new_session=True)
            monitor=subprocess.Popen(monitor_command,stdout=monitor_log,stderr=subprocess.STDOUT,
                                     start_new_session=True)
            while True:
                check_resources(resources(),initial)
                monitor_code=monitor.poll()
                worker_code=worker.poll() if worker else None
                if worker and worker_code is not None and worker_code != 0:
                    raise RuntimeError(f'worker exited with status {worker_code}; see worker.log')
                if monitor_code is not None and monitor_code != 0:
                    raise RuntimeError(f'monitor exited with status {monitor_code}; see monitor.log')
                if worker and worker_code==0 and monitor_code is None:
                    raise RuntimeError('worker ended before monitoring completed; invalid workload trace')
                if monitor_code==0 and (worker is None or worker_code==0):
                    return dict(monitor_exit=monitor_code,worker_exit=worker_code,
                                elapsed_s=time.monotonic()-started)
                if time.monotonic()-started > timeout_s:
                    raise TimeoutError('external collector deadline exceeded')
                time.sleep(.05)
        finally:
            try:
                stop_group(monitor)
            finally:
                stop_group(worker)


def main():
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
    command=[sys.executable,'-m','monitor.capture','--ticks',str(args.duration),
             '--label',label,'--output',str(directory/'trace.csv')]
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
        manifest['processes']=run_processes(command,worker,directory,args.duration+6)
        stats=validate_trace(directory/'trace.csv',args.duration,label,
                             os.cpu_count()*os.sysconf('SC_CLK_TCK'))
        (directory/'statistics.json').write_text(json.dumps(stats,indent=2)+'\n')
        manifest.update(status='complete',success=True)
    except BaseException as error:
        manifest.update(status='failed',error=f'{type(error).__name__}: {error}')
        raise
    finally:
        for sig,handler in previous.items():
            signal.signal(sig,handler)
        manifest['final_resources']=resources()
        manifest['end_utc']=datetime.now(timezone.utc).isoformat()
        save_manifest()
        print(f'Run preserved in {directory}; status={manifest["status"]}')


if __name__=='__main__':
    main()
