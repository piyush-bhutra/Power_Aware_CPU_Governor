"""Governor self-overhead measurement. Linux-targeted; explicitly invoked only.

    python -m benchmark.overhead --outdir <new folder> [--smoke]

Runs the real per-tick pipeline (read /proc/stat -> parse_stat -> compute_signals ->
classify -> Policy.decide -> SimulatedSetter.set, plus the optional cpufreq read
that monitor.reader.sample() performs) for a bounded time at a fixed interval, with
no generated load, and an identical control loop that only sleeps. Net governor
cost = governor minus control, paired per repetition.

Measured, per run: CPU time per tick from time.process_time() deltas (each delta
spans one full loop iteration, sleep included, in both modes); user+system CPU
from /proc/self/stat; voluntary/involuntary context switches and VmRSS/VmHWM from
/proc/self/status; wake-ups per second (voluntary context switches per second:
each blocking sleep that yields the CPU and is woken counts once).

Not measured: CSV logging, terminal/dashboard rendering, electrical power, and any
frequency actuation (the setter is simulated). Nothing else imports this module.
"""
import argparse
import csv
import math
import os
from pathlib import Path
import statistics
import sys
import time

from classifier.rules import classify
from hardware_profile import RYZEN_7840HS_LADDER_KHZ
from monitor.reader import compute_signals, parse_stat
from policy.governor_policy import Policy
from setter.freq_setter import SimulatedSetter

FULL_PLAN = dict(intervals_s=(0.5, 1.0, 2.0, 5.0), duration_s=60.0, repetitions=3)
SMOKE_PLAN = dict(intervals_s=(0.5, 1.0), duration_s=5.0, repetitions=1)
MODES = ('governor', 'control')
COLUMNS = ('mode', 'interval_s', 'repetition', 'ticks', 'wall_s', 'cpu_tick_mean_ms',
           'cpu_tick_median_ms', 'cpu_tick_p95_ms', 'cpu_tick_max_ms', 'proc_cpu_s',
           'cpu_pct_one_core', 'cpu_s_per_hour', 'voluntary_ctxt_per_s',
           'involuntary_ctxt_per_s', 'wakeups_per_s', 'rss_kib', 'hwm_kib')


class LinuxProbe:
    """The real clock, sleep and /proc readers. Constructing it refuses non-Linux hosts."""

    def __init__(self):
        if sys.platform != 'linux' or not Path('/proc/self/stat').is_file():
            raise RuntimeError(f'benchmark.overhead reads Linux /proc (/proc/stat, /proc/self/stat, '
                               f'/proc/self/status); refusing to run on {sys.platform}. '
                               'Run it on the Ubuntu VM after approval.')
        self.clock = time.monotonic
        self.process_time = time.process_time
        self.sleep = time.sleep
        self.ticks_per_s = os.sysconf('SC_CLK_TCK')

    def read_stat(self):
        return Path('/proc/stat').read_text()

    def read_freq(self):
        from monitor.reader import read_freq_khz
        return read_freq_khz()

    def self_stat(self):
        return Path('/proc/self/stat').read_text()

    def self_status(self):
        return Path('/proc/self/status').read_text()


def parse_self_stat(text, ticks_per_s):
    """user+system CPU seconds of this process from /proc/self/stat."""
    fields = text.rsplit(')', 1)[1].split()  # comm may contain spaces; fields[0] is state
    utime, stime = int(fields[11]), int(fields[12])
    return (utime + stime) / ticks_per_s


def parse_self_status(text):
    keys = {'voluntary_ctxt_switches': 'voluntary', 'nonvoluntary_ctxt_switches': 'involuntary',
            'VmRSS': 'rss_kib', 'VmHWM': 'hwm_kib'}
    out = {}
    for line in text.splitlines():
        name, _, value = line.partition(':')
        if name in keys:
            out[keys[name]] = int(value.split()[0])
    missing = set(keys.values()) - set(out)
    if missing:
        raise ValueError(f'/proc/self/status lacks {sorted(missing)}')
    return out


def percentile(values, q):
    """Nearest-rank percentile (q in 0..100) of a non-empty list."""
    ordered = sorted(values)
    return ordered[max(0, math.ceil(q / 100 * len(ordered)) - 1)]


def run_once(probe, mode, interval_s, duration_s):
    """One bounded run. Raises TimeoutError if wall time overruns the hard limit."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES}')
    ticks = max(1, int(round(duration_s / interval_s)))
    hard_limit = duration_s + max(5.0, 2 * interval_s)
    policy, setter = Policy(RYZEN_7840HS_LADDER_KHZ), SimulatedSetter(RYZEN_7840HS_LADDER_KHZ)
    before_cpu = parse_self_stat(probe.self_stat(), probe.ticks_per_s)
    before = parse_self_status(probe.self_status())
    start = probe.clock()
    prev, prev_t = (parse_stat(probe.read_stat()), probe.clock()) if mode == 'governor' else (None, None)
    per_tick = []
    for _ in range(ticks):
        tick_start = probe.process_time()
        probe.sleep(interval_s)
        if mode == 'governor':
            cur, now = parse_stat(probe.read_stat()), probe.clock()
            probe.read_freq()
            sig = compute_signals(prev, cur, now - prev_t)
            prev, prev_t = cur, now
            if sig is not None:
                setter.set(policy.decide(classify(sig)))
        per_tick.append(probe.process_time() - tick_start)
        if probe.clock() - start > hard_limit:
            raise TimeoutError(f'{mode} run at {interval_s} s exceeded its {hard_limit:.1f} s hard limit; '
                               'stopping without retry')
    wall = probe.clock() - start
    after_cpu = parse_self_stat(probe.self_stat(), probe.ticks_per_s)
    after = parse_self_status(probe.self_status())
    proc_cpu = after_cpu - before_cpu
    voluntary = (after['voluntary'] - before['voluntary']) / wall
    ms = [value * 1000 for value in per_tick]
    return dict(mode=mode, interval_s=interval_s, ticks=ticks, wall_s=wall,
                cpu_tick_mean_ms=statistics.fmean(ms), cpu_tick_median_ms=statistics.median(ms),
                cpu_tick_p95_ms=percentile(ms, 95), cpu_tick_max_ms=max(ms), proc_cpu_s=proc_cpu,
                cpu_pct_one_core=100 * proc_cpu / wall, cpu_s_per_hour=3600 * proc_cpu / wall,
                voluntary_ctxt_per_s=voluntary,
                involuntary_ctxt_per_s=(after['involuntary'] - before['involuntary']) / wall,
                wakeups_per_s=voluntary, rss_kib=after['rss_kib'], hwm_kib=after['hwm_kib'])


def plan_budget_s(plan):
    per_run = [plan['duration_s'] + max(5.0, 2 * i) for i in plan['intervals_s']]
    return len(MODES) * plan['repetitions'] * sum(per_run)


def run_plan(probe, plan, progress=lambda message: None):
    """Fixed order; governor/control order alternates per repetition to spread drift."""
    rows = []
    for repetition in range(1, plan['repetitions'] + 1):
        for interval in plan['intervals_s']:
            order = MODES if repetition % 2 else MODES[::-1]
            for mode in order:
                progress(f'repetition {repetition}/{plan["repetitions"]}, {interval} s, {mode}')
                rows.append({**run_once(probe, mode, interval, plan['duration_s']), 'repetition': repetition})
    return rows


NET_METRICS = ('cpu_tick_mean_ms', 'cpu_tick_p95_ms', 'cpu_pct_one_core', 'cpu_s_per_hour',
               'voluntary_ctxt_per_s', 'involuntary_ctxt_per_s', 'wakeups_per_s', 'rss_kib')


def net_rows(rows):
    """Governor minus control for each (interval, repetition) pair."""
    paired = {}
    for row in rows:
        paired.setdefault((row['interval_s'], row['repetition']), {})[row['mode']] = row
    out = []
    for (interval, repetition), pair in sorted(paired.items()):
        if set(pair) != set(MODES):
            raise ValueError(f'unpaired run at {interval} s repetition {repetition}')
        out.append(dict(interval_s=interval, repetition=repetition,
                        **{m: pair['governor'][m] - pair['control'][m] for m in NET_METRICS}))
    return out


def summary_markdown(rows, plan):
    net = net_rows(rows)
    lines = ['# Governor self-overhead (measured on this Linux host)', '',
             f'Plan: intervals {list(plan["intervals_s"])} s, {plan["duration_s"]:g} s per run, '
             f'{plan["repetitions"]} repetition(s), governor and sleep-only control. '
             'No generated load; simulated setter (no frequency writes). '
             'Net = governor minus control per repetition; median [min, max] across repetitions.', '',
             '| interval s | net CPU % of one core | net CPU-s/hour | net CPU ms/tick (mean) | '
             'net p95 ms/tick | net wake-ups/s | governor CPU % | control CPU % | governor RSS KiB |',
             '|---|---|---|---|---|---|---|---|---|']

    def spread(values, digits):
        return (f'{statistics.median(values):.{digits}f} '
                f'[{min(values):.{digits}f}, {max(values):.{digits}f}]')
    for interval in plan['intervals_s']:
        n = [r for r in net if r['interval_s'] == interval]
        g = [r for r in rows if r['interval_s'] == interval and r['mode'] == 'governor']
        c = [r for r in rows if r['interval_s'] == interval and r['mode'] == 'control']
        lines.append(f'| {interval:g} | {spread([r["cpu_pct_one_core"] for r in n], 4)} | '
                     f'{spread([r["cpu_s_per_hour"] for r in n], 2)} | '
                     f'{spread([r["cpu_tick_mean_ms"] for r in n], 3)} | '
                     f'{spread([r["cpu_tick_p95_ms"] for r in n], 3)} | '
                     f'{spread([r["wakeups_per_s"] for r in n], 3)} | '
                     f'{spread([r["cpu_pct_one_core"] for r in g], 4)} | '
                     f'{spread([r["cpu_pct_one_core"] for r in c], 4)} | '
                     f'{spread([r["rss_kib"] for r in g], 0)} |')
    lines += ['', 'CPU % and CPU-s/hour come from /proc/self/stat user+system time (USER_HZ '
              'resolution); per-tick ms from time.process_time(). Wake-ups/s = voluntary context '
              'switches per second. Excludes CSV logging and UI rendering. This is process CPU '
              'time, not electrical power.', '']
    return '\n'.join(lines)


def write_outputs(outdir, rows, plan):
    outdir = Path(outdir)
    with (outdir / 'overhead_runs.csv').open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, COLUMNS, lineterminator='\n')
        writer.writeheader()
        writer.writerows({k: row[k] for k in COLUMNS} for row in rows)
    with (outdir / 'overhead_net.csv').open('x', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, ('interval_s', 'repetition', *NET_METRICS), lineterminator='\n')
        writer.writeheader()
        writer.writerows(net_rows(rows))
    (outdir / 'overhead_summary.md').write_text(summary_markdown(rows, plan), encoding='utf-8')


def main(argv=None, probe_factory=LinuxProbe, stream=None):
    stream = stream or sys.stdout
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--outdir', required=True, type=Path, help='new or empty output folder')
    parser.add_argument('--smoke', action='store_true',
                        help='short check: 0.5 and 1 s intervals, 5 s each, one repetition')
    args = parser.parse_args(argv)
    plan = SMOKE_PLAN if args.smoke else FULL_PLAN
    if args.outdir.exists() and any(args.outdir.iterdir()):
        parser.error(f'{args.outdir} is not empty; choose a new --outdir')
    try:
        probe = probe_factory()
    except RuntimeError as error:
        print(error, file=stream)
        return 2
    print(f'Overhead plan: {plan}; hard budget {plan_budget_s(plan):.0f} s; no generated load.', file=stream)
    args.outdir.mkdir(parents=True, exist_ok=True)
    rows = run_plan(probe, plan, progress=lambda message: print(message, file=stream, flush=True))
    write_outputs(args.outdir, rows, plan)
    print(f'Wrote overhead_runs.csv, overhead_net.csv, overhead_summary.md to {args.outdir}', file=stream)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
