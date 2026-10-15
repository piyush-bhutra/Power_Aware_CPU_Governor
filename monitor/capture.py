"""Bounded Linux counter capture without actuation or generated workloads."""
import argparse
import csv
import json
import math
import os
from pathlib import Path

from monitor.reader import RAW_FIELDS, compute_signals, log_csv, sample

LABEL_COLS = ('workload_label', 'observation_source', 'mem_available_kib', 'swap_used_kib')


def resources():
    values = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value, *_ = line.split()
        values[key.rstrip(':')] = int(value)
    return dict(mem_available_kib=values['MemAvailable'],
                swap_used_kib=values['SwapTotal'] - values['SwapFree'])


def check_resources(current, initial):
    if current['mem_available_kib'] < 512*1024:
        raise RuntimeError('Memory pressure: available memory below 512 MiB')
    if current['swap_used_kib'] - initial['swap_used_kib'] > 128*1024:
        raise RuntimeError('Memory pressure: swap usage increased by more than 128 MiB')


def validate_trace(path, expected_rows, label, expected_jiffies_per_s=None):
    with open(path, newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != expected_rows or not rows:
        raise ValueError(f'CSV row count {len(rows)} != expected {expected_rows}')
    last = None
    for row in rows:
        if row['workload_label'] != label or row['observation_source'] != 'linux_proc_stat':
            raise ValueError('CSV observation label/source mismatch')
        numeric = ('timestamp','util_pct','iowait_pct','irq_pct','ctxt_per_s',
                   'elapsed_s','delta_total_jiffies','procs_running','procs_blocked')
        values = {k: float(row[k]) for k in numeric}
        if not all(math.isfinite(v) and v >= 0 for v in values.values()):
            raise ValueError('Non-finite or negative CSV observation')
        if not .5 <= values['elapsed_s'] <= 2:
            raise ValueError('Sampling elapsed time outside 0.5–2 seconds')
        if any(values[k] > 100 for k in ('util_pct','iowait_pct','irq_pct')):
            raise ValueError('CSV percentage outside [0,100]')
        if last is not None and values['timestamp'] <= last:
            raise ValueError('CSV timestamps do not increase')
        last = values['timestamp']
        snapshots = []
        for side in ('prev','cur'):
            raw = {f:int(row[f'raw_{side}_{f}']) for f in RAW_FIELDS}
            if min(raw.values()) < 0:
                raise ValueError('Negative raw counter')
            raw.update(procs_running=int(row['procs_running']), procs_blocked=int(row['procs_blocked']))
            snapshots.append(raw)
        recomputed = compute_signals(*snapshots, values['elapsed_s'])
        if recomputed is None:
            raise ValueError('Invalid raw counter interval')
        for key in ('util_pct','iowait_pct','irq_pct','ctxt_per_s','delta_total_jiffies'):
            if not math.isclose(values[key], recomputed[key], rel_tol=1e-8, abs_tol=1e-8):
                raise ValueError(f'CSV derived value disagrees with raw counters: {key}')
        if row['iowait_decreased'] != str(recomputed['iowait_decreased']):
            raise ValueError('CSV iowait correction flag disagrees with raw counters')
        if expected_jiffies_per_s:
            ratio = values['delta_total_jiffies'] / values['elapsed_s'] / expected_jiffies_per_s
            if not .5 <= ratio <= 1.5:
                raise ValueError('CPU accounting rate indicates timing/topology anomaly')
    def summary(key):
        vals=[float(r[key]) for r in rows]
        return dict(min=min(vals), mean=sum(vals)/len(vals), max=max(vals))
    return dict(rows=len(rows), workload_label=label, observation_source='linux_proc_stat',
                elapsed_s=summary('elapsed_s'), util_pct=summary('util_pct'),
                iowait_pct=summary('iowait_pct'), ctxt_per_s=summary('ctxt_per_s'),
                iowait_decrease_intervals=sum(r['iowait_decreased']=='True' for r in rows))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--ticks', type=int, default=5)
    parser.add_argument('--label', default='uncontrolled_background')
    args=parser.parse_args()
    if not 1 <= args.ticks <= 30:
        parser.error('--ticks must be 1–30')
    initial=resources()
    check_resources(initial,initial)
    def annotated():
        for sig in sample(1.0,args.ticks):
            current=resources()
            check_resources(current, initial)
            if not .5 <= sig['elapsed_s'] <= 2:
                raise RuntimeError('Sampling timing anomaly; stopping without retry')
            yield {**sig, **current, 'workload_label':args.label,
                   'observation_source':'linux_proc_stat'}
    log_csv(args.output, annotated(), LABEL_COLS, mode='x')
    stats=validate_trace(args.output,args.ticks,args.label,os.cpu_count()*os.sysconf('SC_CLK_TCK'))
    print(json.dumps(stats,indent=2))


if __name__=='__main__':
    main()
