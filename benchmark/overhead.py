"""Governor self-overhead measurement. Linux-targeted; explicitly invoked only.

    python -m benchmark.overhead                      # full plan, output in data/overhead-<UTC>
    python -m benchmark.overhead --smoke              # short check, data/overhead-smoke-<UTC>
    python -m benchmark.overhead --duration-s 30 --repetitions 2

Runs the real per-tick pipeline (read /proc/stat -> parse_stat -> compute_signals ->
classify -> Policy.decide -> SimulatedSetter.set, plus the optional cpufreq read
that monitor.reader.sample() performs) for a fixed number of ticks (duration /
interval) with no generated load, and an identical control loop that only sleeps.
Net governor cost = governor minus control, paired per repetition.

Primary metric: CPU ms per tick from time.process_time() (each delta spans one full
loop iteration, sleep included, in both modes). CPU % of one core is DERIVED from it:
mean ms per tick / (interval s * 1000) * 100. Secondary: user+system time from
/proc/self/stat, which is quantized to the 10 ms kernel clock and can read zero or
negative (net) in short runs. Also: voluntary/involuntary context switches and
VmRSS/VmHWM from /proc/self/status; wake-ups/s (voluntary switches per second).

VM timer overshoot is measured, not fatal: each run records its actual elapsed time,
actual/planned ratio and per-tick sleep overshoot. Only a runaway guard (3x the
planned duration) stops a run. A failed run is recorded with its reason, the plan
continues, partial outputs are always written, and the exit code is 1. No retries.

Not measured: CSV logging, terminal/dashboard rendering, electrical power, and any
frequency actuation (the setter is simulated). Nothing else imports this module.
"""
import argparse
import csv
from datetime import datetime, timezone
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

ROOT = Path(__file__).resolve().parents[1]
INTERVALS_S = (0.5, 1.0, 2.0, 5.0)
FULL_PLAN = dict(intervals_s=INTERVALS_S, duration_s=60.0, repetitions=3)
SMOKE_PLAN = dict(intervals_s=(0.5, 1.0), duration_s=5.0, repetitions=1)
GUARD_FACTOR = 3.0
MODES = ('governor', 'control')
# Columns from the first version (Phase 1B) keep their names and meaning; new ones follow.
LEGACY_COLUMNS = ('mode', 'interval_s', 'repetition', 'ticks', 'wall_s', 'cpu_tick_mean_ms',
                  'cpu_tick_median_ms', 'cpu_tick_p95_ms', 'cpu_tick_max_ms', 'proc_cpu_s',
                  'cpu_pct_one_core', 'cpu_s_per_hour', 'voluntary_ctxt_per_s',
                  'involuntary_ctxt_per_s', 'wakeups_per_s', 'rss_kib', 'hwm_kib')
COLUMNS = LEGACY_COLUMNS + ('status', 'failure_reason', 'planned_ticks', 'planned_s', 'actual_elapsed_s',
                            'overshoot_ratio', 'sleep_overshoot_mean_ms', 'sleep_overshoot_p95_ms',
                            'sleep_overshoot_max_ms', 'cpu_pct_one_core_derived', 'cpu_s_per_hour_derived')


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


class RunawayGuard(TimeoutError):
    """A run exceeded GUARD_FACTOR x its planned duration."""


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


def planned_ticks(interval_s, duration_s):
    return max(1, int(round(duration_s / interval_s)))


def run_once(probe, mode, interval_s, duration_s):
    """One run of a fixed tick count. Overshoot is recorded; only the runaway guard stops it."""
    if mode not in MODES:
        raise ValueError(f'mode must be one of {MODES}')
    ticks = planned_ticks(interval_s, duration_s)
    planned = ticks * interval_s
    guard = GUARD_FACTOR * planned
    policy, setter = Policy(RYZEN_7840HS_LADDER_KHZ), SimulatedSetter(RYZEN_7840HS_LADDER_KHZ)
    before_cpu = parse_self_stat(probe.self_stat(), probe.ticks_per_s)
    before = parse_self_status(probe.self_status())
    start = probe.clock()
    prev, prev_t = (parse_stat(probe.read_stat()), probe.clock()) if mode == 'governor' else (None, None)
    per_tick, overshoot = [], []
    for _ in range(ticks):
        tick_start = probe.process_time()
        slept_from = probe.clock()
        probe.sleep(interval_s)
        overshoot.append(probe.clock() - slept_from - interval_s)
        if mode == 'governor':
            cur, now = parse_stat(probe.read_stat()), probe.clock()
            probe.read_freq()
            sig = compute_signals(prev, cur, now - prev_t)
            prev, prev_t = cur, now
            if sig is not None:
                setter.set(policy.decide(classify(sig)))
        per_tick.append(probe.process_time() - tick_start)
        if probe.clock() - start > guard:
            raise RunawayGuard(f'{mode} run at {interval_s} s passed the runaway guard '
                               f'({GUARD_FACTOR:g} x {planned:g} s planned = {guard:g} s) after '
                               f'{len(per_tick)} of {ticks} ticks; stopping without retry')
    wall = probe.clock() - start
    after_cpu = parse_self_stat(probe.self_stat(), probe.ticks_per_s)
    after = parse_self_status(probe.self_status())
    proc_cpu = after_cpu - before_cpu
    voluntary = (after['voluntary'] - before['voluntary']) / wall
    ms = [value * 1000 for value in per_tick]
    over_ms = [value * 1000 for value in overshoot]
    mean_ms = statistics.fmean(ms)
    return dict(mode=mode, interval_s=interval_s, status='ok', failure_reason='',
                ticks=ticks, planned_ticks=ticks, planned_s=planned, wall_s=wall, actual_elapsed_s=wall,
                overshoot_ratio=wall / planned, sleep_overshoot_mean_ms=statistics.fmean(over_ms),
                sleep_overshoot_p95_ms=percentile(over_ms, 95), sleep_overshoot_max_ms=max(over_ms),
                cpu_tick_mean_ms=mean_ms, cpu_tick_median_ms=statistics.median(ms),
                cpu_tick_p95_ms=percentile(ms, 95), cpu_tick_max_ms=max(ms),
                cpu_pct_one_core_derived=mean_ms / (interval_s * 1000) * 100,
                cpu_s_per_hour_derived=mean_ms / 1000 / interval_s * 3600,
                proc_cpu_s=proc_cpu, cpu_pct_one_core=100 * proc_cpu / wall, cpu_s_per_hour=3600 * proc_cpu / wall,
                voluntary_ctxt_per_s=voluntary,
                involuntary_ctxt_per_s=(after['involuntary'] - before['involuntary']) / wall,
                wakeups_per_s=voluntary, rss_kib=after['rss_kib'], hwm_kib=after['hwm_kib'])


def plan_budget_s(plan):
    """Worst case if every run hits the runaway guard."""
    return len(MODES) * plan['repetitions'] * sum(
        GUARD_FACTOR * planned_ticks(i, plan['duration_s']) * i for i in plan['intervals_s'])


def plan_nominal_s(plan):
    return len(MODES) * plan['repetitions'] * sum(
        planned_ticks(i, plan['duration_s']) * i for i in plan['intervals_s'])


def run_plan(probe, plan, progress=lambda message: None, on_row=lambda rows: None):
    """Fixed order; governor/control order alternates per repetition to spread drift.

    A failing run becomes a failed row and the plan continues. on_row(rows) lets the
    caller write partial outputs after every run.
    """
    rows = []
    for repetition in range(1, plan['repetitions'] + 1):
        for interval in plan['intervals_s']:
            order = MODES if repetition % 2 else MODES[::-1]
            for mode in order:
                progress(f'repetition {repetition}/{plan["repetitions"]}, {interval} s, {mode}')
                try:
                    row = run_once(probe, mode, interval, plan['duration_s'])
                except Exception as error:  # recorded, never retried; Ctrl+C still stops the plan
                    row = dict(mode=mode, interval_s=interval, status='failed',
                               failure_reason=f'{type(error).__name__}: {error}',
                               planned_ticks=planned_ticks(interval, plan['duration_s']),
                               planned_s=planned_ticks(interval, plan['duration_s']) * interval)
                    progress(f'  FAILED: {row["failure_reason"]}')
                rows.append({**row, 'repetition': repetition})
                on_row(rows)
    return rows


NET_METRICS = ('cpu_tick_mean_ms', 'cpu_tick_p95_ms', 'cpu_pct_one_core_derived', 'cpu_s_per_hour_derived',
               'cpu_pct_one_core', 'voluntary_ctxt_per_s', 'involuntary_ctxt_per_s', 'wakeups_per_s', 'rss_kib')


def net_rows(rows):
    """Governor minus control for each (interval, repetition) pair where both runs succeeded."""
    paired = {}
    for row in rows:
        if row.get('status', 'ok') == 'ok':
            paired.setdefault((row['interval_s'], row['repetition']), {})[row['mode']] = row
    return [dict(interval_s=interval, repetition=repetition,
                 **{m: pair['governor'][m] - pair['control'][m] for m in NET_METRICS})
            for (interval, repetition), pair in sorted(paired.items()) if set(pair) == set(MODES)]


def _spread(values, digits):
    if not values:
        return 'n/a'
    return f'{statistics.median(values):.{digits}f} [{min(values):.{digits}f}, {max(values):.{digits}f}]'


def summary_markdown(rows, plan):
    net = net_rows(rows)
    ok = [r for r in rows if r.get('status', 'ok') == 'ok']
    failed = [r for r in rows if r.get('status') == 'failed']
    lines = ['# Governor self-overhead (measured on this Linux host)', '',
             f'Plan: intervals {list(plan["intervals_s"])} s, {plan["duration_s"]:g} s of ticks per run, '
             f'{plan["repetitions"]} repetition(s), governor and sleep-only control. No generated load; '
             'simulated setter (no frequency writes). Net = governor minus control per repetition; '
             'median [min, max] across repetitions.', '',
             f'Runs: {len(ok)} ok, {len(failed)} failed.', '',
             '## Net governor cost (primary: CPU ms per tick)', '',
             '| interval s | net CPU ms/tick (mean) | net p95 ms/tick | net CPU % of one core (derived) | '
             'net CPU-s/hour (derived) | net CPU % from /proc/self/stat (quantized) | net wake-ups/s | pairs |',
             '|---|---|---|---|---|---|---|---|']
    for interval in plan['intervals_s']:
        n = [r for r in net if r['interval_s'] == interval]
        lines.append(f'| {interval:g} | {_spread([r["cpu_tick_mean_ms"] for r in n], 4)} | '
                     f'{_spread([r["cpu_tick_p95_ms"] for r in n], 4)} | '
                     f'{_spread([r["cpu_pct_one_core_derived"] for r in n], 4)} | '
                     f'{_spread([r["cpu_s_per_hour_derived"] for r in n], 3)} | '
                     f'{_spread([r["cpu_pct_one_core"] for r in n], 4)} | '
                     f'{_spread([r["wakeups_per_s"] for r in n], 3)} | {len(n)} |')
    lines += ['', '## Per mode', '',
              '| interval s | mode | CPU ms/tick (mean) | CPU % of one core (derived) | RSS KiB | runs ok |',
              '|---|---|---|---|---|---|']
    for interval in plan['intervals_s']:
        for mode in MODES:
            m = [r for r in ok if r['interval_s'] == interval and r['mode'] == mode]
            lines.append(f'| {interval:g} | {mode} | {_spread([r["cpu_tick_mean_ms"] for r in m], 4)} | '
                         f'{_spread([r["cpu_pct_one_core_derived"] for r in m], 4)} | '
                         f'{_spread([r["rss_kib"] for r in m], 0)} | {len(m)} |')
    lines += ['', '## VM timer overshoot', '',
              '| interval s | mode | actual/planned elapsed | sleep overshoot mean ms | p95 ms | max ms |',
              '|---|---|---|---|---|---|']
    for interval in plan['intervals_s']:
        for mode in MODES:
            m = [r for r in ok if r['interval_s'] == interval and r['mode'] == mode]
            lines.append(f'| {interval:g} | {mode} | {_spread([r["overshoot_ratio"] for r in m], 4)} | '
                         f'{_spread([r["sleep_overshoot_mean_ms"] for r in m], 3)} | '
                         f'{_spread([r["sleep_overshoot_p95_ms"] for r in m], 3)} | '
                         f'{_spread([r["sleep_overshoot_max_ms"] for r in m], 3)} |')
    if failed:
        lines += ['', '## Failed runs (recorded, not retried)', '', '| interval s | mode | repetition | reason |',
                  '|---|---|---|---|']
        lines += [f'| {r["interval_s"]:g} | {r["mode"]} | {r["repetition"]} | {r["failure_reason"]} |' for r in failed]
    lines += ['', 'Primary metric: CPU ms per tick from time.process_time(). CPU % of one core (derived) = '
              'mean ms per tick / (interval s x 1000) x 100, projected at the nominal tick rate. The '
              '/proc/self/stat percentage is secondary: it is quantized to the 10 ms kernel clock and can '
              'read zero or negative in short runs. Wake-ups/s = voluntary context switches per second. '
              'Excludes CSV logging and UI rendering. This is process CPU time, not electrical power.', '']
    return '\n'.join(lines)


def write_outputs(outdir, rows, plan):
    outdir = Path(outdir)
    with (outdir / 'overhead_runs.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, COLUMNS, lineterminator='\n', restval='')
        writer.writeheader()
        writer.writerows({k: row.get(k, '') for k in COLUMNS} for row in rows)
    with (outdir / 'overhead_net.csv').open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, ('interval_s', 'repetition', *NET_METRICS), lineterminator='\n')
        writer.writeheader()
        writer.writerows(net_rows(rows))
    (outdir / 'overhead_summary.md').write_text(summary_markdown(rows, plan), encoding='utf-8')


def read_runs(path):
    """Read overhead_runs.csv from either version; numbers become floats, absent new columns stay absent."""
    text_fields = {'mode', 'status', 'failure_reason'}
    out = []
    with Path(path).open(newline='', encoding='utf-8') as handle:
        for raw in csv.DictReader(handle):
            row = {k: (v if k in text_fields or v == '' else float(v)) for k, v in raw.items()}
            row.setdefault('status', 'ok')
            out.append(row)
    return out


def default_outdir(smoke, now=None):
    stamp = (now or datetime.now(timezone.utc)).strftime('%Y%m%dT%H%M%SZ')
    return ROOT / 'data' / f'overhead-{"smoke-" if smoke else ""}{stamp}'


def main(argv=None, probe_factory=LinuxProbe, stream=None, now=None):
    stream = stream or sys.stdout
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--outdir', type=Path, help='new or empty folder (default data/overhead-<UTC time>)')
    parser.add_argument('--smoke', action='store_true',
                        help='short check: 0.5 and 1 s intervals, 5 s each, one repetition')
    parser.add_argument('--duration-s', type=float, help='seconds of ticks per run, 1-300 (default 60, smoke 5)')
    parser.add_argument('--repetitions', type=int, help='repetitions, 1-5 (default 3, smoke 1)')
    args = parser.parse_args(argv)
    plan = dict(SMOKE_PLAN if args.smoke else FULL_PLAN)
    if args.duration_s is not None:
        if not math.isfinite(args.duration_s) or not 1 <= args.duration_s <= 300:
            parser.error('--duration-s must be between 1 and 300')
        plan['duration_s'] = args.duration_s
    if args.repetitions is not None:
        if not 1 <= args.repetitions <= 5:
            parser.error('--repetitions must be between 1 and 5')
        plan['repetitions'] = args.repetitions
    outdir = args.outdir or default_outdir(args.smoke, now)
    if outdir.exists() and any(outdir.iterdir()):
        parser.error(f'{outdir} is not empty; choose a new --outdir')
    try:
        probe = probe_factory()
    except RuntimeError as error:
        print(error, file=stream)
        return 2
    print(f'Overhead plan: {plan}; nominal {plan_nominal_s(plan):.0f} s, runaway guard worst case '
          f'{plan_budget_s(plan):.0f} s; no generated load. Output: {outdir}', file=stream, flush=True)
    outdir.mkdir(parents=True, exist_ok=True)
    rows = run_plan(probe, plan, progress=lambda message: print(message, file=stream, flush=True),
                    on_row=lambda partial: write_outputs(outdir, partial, plan))
    failed = sum(r['status'] == 'failed' for r in rows)
    print(f'Wrote overhead_runs.csv, overhead_net.csv, overhead_summary.md to {outdir} '
          f'({len(rows) - failed} runs ok, {failed} failed)', file=stream)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
