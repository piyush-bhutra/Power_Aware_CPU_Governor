"""Deterministic sensitivity study: hysteresis K and sampling interval. Synthetic only.

    python -m benchmark.sensitivity --outdir <new folder>

Inputs are invented counters; frequencies are simulated decisions; energy is the
existing power model. Nothing samples Linux, and the archived generators/outputs are
untouched (monitor.synthetic.source is reused unchanged for the K sweep).

K sweep: each scenario is replayed through governor.run with Policy(k=K) and a
SimulatedSetter. "Appropriate" frequency = the policy's own class target for the
scenario's TRUE phase label. Lag = ticks from the first tick of a new sustained phase
(> BURST_MAX ticks) to the first tick whose applied frequency equals that phase's
target; phases that begin with the frequency already at their target need no change
and are not counted. A burst (phase of <= BURST_MAX ticks whose target differs from
the phase before it) is suppressed if the applied frequency does not change at all
during it.

Interval sweep: one 0.1 s-resolution cumulative-counter timeline is sampled every
0.5/1/2/5 s through monitor.reader.compute_signals, so each interval sees the same
workload. Class lag = seconds from a sustained phase change to the end of the first
window classified as the new class. A short CPU burst is missed when no window that
overlaps it is classified cpu_bound. Applied lag (K=3) skips phases whose
frequency was already at target when they began.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import random
import subprocess

from benchmark.summarize import summarize
from classifier.rules import classify
from governor import run
from hardware_profile import RYZEN_7840HS_LADDER_KHZ as LADDER
from monitor.reader import CPU_FIELDS, compute_signals
from monitor.synthetic import HZ, PROFILES, source
from policy.governor_policy import Policy
from setter.freq_setter import SimulatedSetter

ROOT = Path(__file__).resolve().parents[1]
PROFILE_CLASS = {'cpu': 'cpu_bound', 'io': 'io_bound', 'io_burst': 'io_bound',
                 'idle': 'idle', 'mixed': 'mixed'}
K_VALUES = (1, 2, 3, 4, 5, 6, 7, 8, 10)
BURST_MAX = 5
ARCHIVED_PLAN = [('cpu', 10), ('io_burst', 10), ('idle', 6), ('mixed', 8)]


def _bursts(background, burst, lengths, gap):
    plan = [(background, gap)]
    for n in lengths:
        plan += [(burst, n), (background, gap)]
    return plan


SCENARIOS = {
    'archived_seed11': dict(plan=ARCHIVED_PLAN, seed=11, noise=0.1),
    'archived_plan_seed23': dict(plan=ARCHIVED_PLAN, seed=23, noise=0.1),
    'high_noise_seed31': dict(plan=ARCHIVED_PLAN, seed=31, noise=0.3),
    'long_phases_seed41': dict(plan=[('cpu', 20), ('idle', 20), ('io', 20), ('mixed', 20)], seed=41, noise=0.1),
    'cpu_bursts_on_idle_seed51': dict(plan=_bursts('idle', 'cpu', (1, 2, 3, 4, 5), 10), seed=51, noise=0.1),
    'idle_dips_in_cpu_seed53': dict(plan=_bursts('cpu', 'idle', (1, 2, 3, 4, 5), 8), seed=53, noise=0.1),
    'flapping_cpu_idle_seed61': dict(plan=[('cpu', 2), ('idle', 2)] * 10, seed=61, noise=0.1),
}

FINE_DT = 0.1
FINE_NCPU = 4
FINE_SEED = 71
FINE_NOISE = 0.1
INTERVALS = (0.5, 1.0, 2.0, 5.0)
# (profile, seconds). CPU bursts of 0.3-5 s on idle, then sustained phases.
FINE_TIMELINE = [('idle', 10), ('cpu', 0.3), ('idle', 5), ('cpu', 0.5), ('idle', 5), ('cpu', 1),
                 ('idle', 5), ('cpu', 2), ('idle', 5), ('cpu', 3), ('idle', 5), ('cpu', 5),
                 ('idle', 10), ('io', 15), ('mixed', 15), ('idle', 10)]
SUSTAINED_S = 10


def target_khz(profile):
    return Policy(LADDER)._target_freq(PROFILE_CLASS[profile])


def phases(plan):
    """[(profile, first_tick (1-based), length)] for a (name, ticks) plan."""
    out, tick = [], 1
    for name, length in plan:
        out.append((name, tick, length))
        tick += length
    return out


def evaluate(rows, plan):
    """Metrics for one replay. rows: governor.run output in tick order."""
    applied = [row['target_khz'] for row in rows]
    lags, unserved, bursts, suppressed = [], 0, 0, 0
    spans = phases(plan)
    for (prev_name, _, _), (name, start, length) in zip(spans, spans[1:]):
        goal = target_khz(name)
        if goal == target_khz(prev_name):
            continue
        before = applied[start - 2]  # phases after the first start at tick >= 2
        window = applied[start - 1:start - 1 + length]
        if length <= BURST_MAX:
            bursts += 1
            suppressed += all(f == before for f in window)
        elif before == goal:
            continue  # already at target: no change required
        elif goal in window:
            lags.append(window.index(goal))
        else:
            unserved += 1
    truth = [row['expected'] for row in rows]
    return dict(
        transitions=sum(a != b for a, b in zip(applied, applied[1:])),
        sustained_changes=len(lags) + unserved,
        mean_lag_ticks=round(sum(lags) / len(lags), 4) if lags else '',
        max_lag_ticks=max(lags) if lags else '',
        unserved_changes=unserved,
        frac_at_appropriate=round(sum(a == target_khz(t) for a, t in zip(applied, truth)) / len(rows), 4),
        bursts_total=bursts, bursts_suppressed=suppressed,
        classifier_agreement=round(sum(r['workload_class'] == PROFILE_CLASS[r['expected']] for r in rows) / len(rows), 4),
        energy_j=summarize(rows)['total_energy_j'])


def replay(scenario, k):
    setter = SimulatedSetter(LADDER)
    return list(run(source(scenario['plan'], seed=scenario['seed'], noise=scenario['noise']), setter,
                    Policy(LADDER, k=k)))


def k_sweep():
    table, timelines = [], {}
    for name, scenario in SCENARIOS.items():
        for k in K_VALUES:
            rows = replay(scenario, k)
            timelines[(name, k)] = rows
            table.append(dict(scenario=name, seed=scenario['seed'], noise=scenario['noise'],
                              ticks=len(rows), k=k, **evaluate(rows, scenario['plan'])))
    return table, timelines


def fine_snapshots(timeline=FINE_TIMELINE, dt=FINE_DT, ncpu=FINE_NCPU, seed=FINE_SEED, noise=FINE_NOISE):
    """Cumulative /proc/stat-shaped snapshots every dt seconds, plus the true profile per step.

    Same profile shares and jitter model as monitor.synthetic, but float counters at
    fine resolution so short bursts are not lost to integer rounding.
    """
    rng = random.Random(seed)
    counters = {f: 0.0 for f in CPU_FIELDS}
    counters.update(ctxt=0.0, procs_running=1, procs_blocked=0)
    snapshots, truth = [dict(counters)], []
    for name, seconds in timeline:
        p = PROFILES[name]
        for _ in range(round(seconds / dt)):
            shares = {k: max(0.0, p[k] * (1 + rng.gauss(0, noise)))
                      for k in ('user', 'system', 'idle', 'iowait', 'softirq')}
            scale = HZ * ncpu * dt / sum(shares.values())
            for key, value in shares.items():
                counters[key] += value * scale
            counters['ctxt'] += p['ctxt'] * dt * (1 + rng.gauss(0, noise))
            counters['procs_running'], counters['procs_blocked'] = p['run'], p['blk']
            snapshots.append(dict(counters))
            truth.append(name)
    return snapshots, truth


def fine_segments(timeline=FINE_TIMELINE):
    out, t = [], 0.0
    for name, seconds in timeline:
        out.append((name, round(t, 6), round(t + seconds, 6)))
        t += seconds
    return out


def window_signals(snapshots, interval_s, dt=FINE_DT):
    step = round(interval_s / dt)
    sigs = []
    for j in range(step, len(snapshots), step):
        sig = compute_signals(snapshots[j - step], snapshots[j], interval_s)
        sig['window_end_s'] = round(j * dt, 6)
        sigs.append(sig)
    return sigs


def interval_sweep():
    snapshots, _ = fine_snapshots()
    segments = fine_segments()
    table, bursts_table = [], []
    for interval in INTERVALS:
        sigs = window_signals(snapshots, interval)
        ends = [s['window_end_s'] for s in sigs]
        classes = [classify(s) for s in sigs]
        rows = list(run(iter(dict(s, expected='') for s in sigs), SimulatedSetter(LADDER), Policy(LADDER, k=3)))
        applied = [r['target_khz'] for r in rows]
        class_lags, applied_lags, unserved = [], [], 0
        for (prev, _, _), (name, start, stop) in zip(segments, segments[1:]):
            if stop - start < SUSTAINED_S or PROFILE_CLASS[name] == PROFILE_CLASS[prev]:
                continue
            inside = [i for i, end in enumerate(ends) if start < end <= stop]
            hit = [i for i in inside if classes[i] == PROFILE_CLASS[name]]
            served = [i for i in inside if applied[i] == target_khz(name)]
            if hit:
                class_lags.append(ends[hit[0]] - start)
            prior = [i for i, end in enumerate(ends) if end <= start]
            if prior and applied[prior[-1]] == target_khz(name):
                continue  # already at target: no change required
            if served:
                applied_lags.append(ends[served[0]] - start)
            else:
                unserved += 1
        missed = []
        cpu_bursts = [(start, stop) for name, start, stop in segments if name == 'cpu' and stop - start <= BURST_MAX]
        for start, stop in cpu_bursts:
            overlapping = [i for i, end in enumerate(ends) if end - interval < stop and end > start]
            detected = any(classes[i] == 'cpu_bound' for i in overlapping)
            bursts_table.append(dict(interval_s=interval, burst_start_s=start, burst_len_s=round(stop - start, 6),
                                     detected=int(detected)))
            if not detected:
                missed.append(round(stop - start, 6))
        summary = summarize(rows, interval_s=interval)
        table.append(dict(interval_s=interval, windows=len(sigs),
                          mean_class_lag_s=round(sum(class_lags) / len(class_lags), 4) if class_lags else '',
                          max_class_lag_s=round(max(class_lags), 4) if class_lags else '',
                          mean_applied_lag_s_k3=round(sum(applied_lags) / len(applied_lags), 4) if applied_lags else '',
                          unserved_changes_k3=unserved, bursts_total=len(cpu_bursts), bursts_missed=len(missed),
                          missed_burst_lengths_s=';'.join(f'{m:g}' for m in missed),
                          transitions_k3=summary['freq_change_count'], energy_j_k3=summary['total_energy_j']))
    return table, bursts_table


K_COLUMNS = ('scenario', 'seed', 'noise', 'ticks', 'k', 'transitions', 'sustained_changes', 'mean_lag_ticks',
             'max_lag_ticks', 'unserved_changes', 'frac_at_appropriate', 'bursts_total', 'bursts_suppressed',
             'classifier_agreement', 'energy_j')
I_COLUMNS = ('interval_s', 'windows', 'mean_class_lag_s', 'max_class_lag_s', 'mean_applied_lag_s_k3',
             'unserved_changes_k3', 'bursts_total', 'bursts_missed', 'missed_burst_lengths_s',
             'transitions_k3', 'energy_j_k3')
B_COLUMNS = ('interval_s', 'burst_start_s', 'burst_len_s', 'detected')


def csv_text(rows, columns):
    lines = [','.join(columns)]
    lines += [','.join(str(row[c]) for c in columns) for row in rows]
    return '\n'.join(lines) + '\n'


def markdown_table(rows, columns):
    out = ['| ' + ' | '.join(columns) + ' |', '|' + '---|' * len(columns)]
    out += ['| ' + ' | '.join(str(row[c]) for c in columns) + ' |' for row in rows]
    return '\n'.join(out)


def summary_text(k_table, i_table, b_table):
    k_short = ('scenario', 'k', 'transitions', 'mean_lag_ticks', 'unserved_changes', 'frac_at_appropriate',
               'bursts_suppressed', 'bursts_total', 'energy_j')
    return '\n'.join([
        '# Phase 1B sensitivity study (SYNTHETIC inputs, SIMULATED frequency, MODELLED energy)', '',
        'Generated by `python -m benchmark.sensitivity`. See README.md for metric definitions and limits.', '',
        '## K sweep', '', markdown_table(k_table, k_short), '',
        '## Interval sweep (same 0.1 s timeline, K=3 for applied metrics)', '',
        markdown_table(i_table, I_COLUMNS), '',
        '## Short CPU bursts by interval', '', markdown_table(b_table, B_COLUMNS), ''])


def tables():
    k_table, timelines = k_sweep()
    i_table, b_table = interval_sweep()
    return k_table, timelines, i_table, b_table


def git(*args):
    try:
        return subprocess.run(['git', *args], capture_output=True, text=True, timeout=10, cwd=ROOT).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 'unavailable'


SOURCES = ('benchmark/sensitivity.py', 'monitor/synthetic.py', 'monitor/reader.py', 'classifier/rules.py',
           'policy/governor_policy.py', 'governor.py', 'setter/freq_setter.py', 'power_model/estimate.py',
           'hardware_profile.py', 'benchmark/summarize.py', 'analysis/plots.py')


def generate(outdir):
    from analysis.plots import plot_energy_comparison, plot_frequency_timeline
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    k_table, timelines, i_table, b_table = tables()
    texts = {'k_sweep.csv': csv_text(k_table, K_COLUMNS), 'interval_sweep.csv': csv_text(i_table, I_COLUMNS),
             'interval_bursts.csv': csv_text(b_table, B_COLUMNS), 'summary.md': summary_text(k_table, i_table, b_table)}
    for name, text in texts.items():
        (outdir / name).write_bytes(text.encode('utf-8'))
    archived = {f'K={row["k"]}': {'total_energy_j': row['energy_j']} for row in k_table
                if row['scenario'] == 'archived_seed11'}
    plot_energy_comparison(archived, outdir / 'k_energy_archived_seed11.png',
                           title='SYNTHETIC archived scenario: MODELLED energy vs K (simulated frequency)')
    plot_frequency_timeline({f'K={k}': timelines[('cpu_bursts_on_idle_seed51', k)] for k in (1, 3, 5)},
                            outdir / 'k_timeline_cpu_bursts.png',
                            title='SYNTHETIC CPU bursts (1-5 ticks) on idle: SIMULATED frequency by K')
    produced = sorted(texts) + ['k_energy_archived_seed11.png', 'k_timeline_cpu_bursts.png']
    files = [{'path': name, 'bytes': (outdir / name).stat().st_size,
              'sha256': hashlib.sha256((outdir / name).read_bytes()).hexdigest()} for name in produced]
    provenance = {
        'source_commit': git('rev-parse', 'HEAD'),
        'tracked_working_tree_dirty': bool(git('status', '--porcelain', '--untracked-files=no')),
        'untracked_files_note': 'Untracked files are not inspected; generation reads only tracked sources.',
        'generation_command': 'python -m benchmark.sensitivity --outdir evidence/phase1b_sensitivity',
        'python': platform.python_version(),
        'parameters': {'ladder_khz': list(LADDER), 'k_values': list(K_VALUES), 'burst_max_ticks': BURST_MAX,
                       'scenarios': {n: {'plan': s['plan'], 'seed': s['seed'], 'noise': s['noise'],
                                         'interval_s': 1.0, 'ncpu': 1} for n, s in SCENARIOS.items()},
                       'interval_sweep': {'fine_dt_s': FINE_DT, 'ncpu': FINE_NCPU, 'seed': FINE_SEED,
                                          'noise': FINE_NOISE, 'intervals_s': list(INTERVALS),
                                          'timeline_s': FINE_TIMELINE, 'sustained_phase_min_s': SUSTAINED_S,
                                          'k_for_applied_metrics': 3}},
        'source_hashes': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES},
        'model': 'P = 21.6 + 32.4 * (f/5100000)^3 * util/100 W; energy = sum(rounded P * interval)',
        'interpretation_restrictions': [
            'Inputs are invented synthetic counters, not Linux observations.',
            'Frequencies are simulated policy decisions; no hardware actuation.',
            'Energy is the existing model, not measured electrical energy.',
            'Open-loop replay: lower frequency does not stretch work, so completion time is not modelled.'],
        'archived_files': files,
    }
    (outdir / 'PROVENANCE.json').write_bytes((json.dumps(provenance, indent=2) + '\n').encode('utf-8'))
    manifest = [f'{f["sha256"]}  {f["path"]}' for f in files]
    manifest.append(f'{hashlib.sha256((outdir / "PROVENANCE.json").read_bytes()).hexdigest()}  PROVENANCE.json')
    (outdir / 'SHA256SUMS').write_bytes(('\n'.join(manifest) + '\n').encode('utf-8'))
    return k_table, i_table, b_table


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--outdir', required=True, type=Path)
    args = parser.parse_args(argv)
    names = ('k_sweep.csv', 'interval_sweep.csv', 'interval_bursts.csv', 'summary.md', 'PROVENANCE.json',
             'SHA256SUMS', 'k_energy_archived_seed11.png', 'k_timeline_cpu_bursts.png')
    if any((args.outdir / name).exists() for name in names):
        parser.error('output artifacts already exist; choose a new --outdir')
    print('SYNTHETIC inputs | SIMULATED frequency | MODELLED energy')
    generate(args.outdir)
    print(f'Sensitivity outputs written to {args.outdir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
