"""Deterministic closed-loop benchmark: MODELLED energy and completion time. Portable.

    python -m benchmark.closed_loop --outdir <new folder>

Nothing here is measured. Frequencies are simulated; time and energy come from the
model below. The point is the feedback the open-loop replay lacks: running CPU work
at a lower frequency takes longer, which raises the utilization the classifier sees
and stretches completion time.

Workload model
- A scenario plan is a list of (profile, units) from benchmark.sensitivity /
  monitor.synthetic. Each unit is one nominal second of that profile at fmax, split
  into CPU work C, I/O wait W and idle (think) time I with the profile's shares,
  jittered by a seeded Gaussian (same jitter model as monitor.synthetic).
- At frequency f a unit takes C * (s + (1 - s) * fmax / f) + W + I seconds, where s is
  the frequency-insensitive fraction of CPU time (memory stalls etc.; default 0, the
  pure 1/f assumption). W and I do not depend on frequency. Within a unit, CPU, I/O and
  idle time are spread evenly.
- One CPU. The policy acts once per 1 s tick: frequency is fixed during a tick and
  set from the decision made on the previous tick's counters. The final tick ends
  when the work ends.
- Each tick produces cumulative /proc/stat-shaped counters (user = CPU time, iowait,
  idle; context switches proportional to work done; runnable/blocked gauges from the
  profile), fed through the existing monitor.reader.compute_signals, then each
  policy's step(sig). Our policies call the existing rule classifier and Policy.
- Energy per tick = power_model.estimate_power_w(f, fmax, util) * tick length,
  with util = the tick's observed CPU busy fraction.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import random
import statistics
import subprocess

from benchmark.baselines import Conservative, Performance, Powersave
from benchmark.sensitivity import SCENARIOS as SENSITIVITY_SCENARIOS, target_khz
from classifier.rules import classify
from hardware_profile import RYZEN_7840HS_LADDER_KHZ as LADDER
from monitor.reader import CPU_FIELDS, compute_signals
from monitor.synthetic import HZ, PROFILES
from policy.governor_policy import Policy
from power_model.estimate import estimate_power_w

ROOT = Path(__file__).resolve().parents[1]
FMAX = LADDER[-1]
TICK_S = 1.0
SEEDS_PER_SCENARIO = 20
INSENSITIVE_FRACTIONS = (0.0, 0.3, 0.6, 0.9)


class FastUpSlowDown:
    """Class targets as in Policy, but raise after 1 tick and lower only after K consecutive ticks."""

    def __init__(self, freqs, k_down=3):
        self.freqs, self.k_down = list(freqs), k_down
        self.current = self.freqs[-1]
        self._reference = Policy(freqs)
        self._pending, self._streak = None, 0

    def step(self, sig):
        cls = classify(sig)
        if cls == self._pending:
            self._streak += 1
        else:
            self._pending, self._streak = cls, 1
        target = self._reference._target_freq(cls)
        if target > self.current or (target < self.current and self._streak >= self.k_down):
            self.current = target
        return self.current


class AdaptiveK:
    """Policy whose K adapts. Exact rule:

    - start at K=3; K stays within [2, 6];
    - a reversal is an applied change back to the frequency that was in force before the
      previous applied change, within 6 ticks of that change: K increases by 1;
    - after 10 consecutive ticks with no applied change: K decreases by 1 (counter restarts).
    """
    K_START, K_MIN, K_MAX, WINDOW, CALM = 3, 2, 6, 6, 10

    def __init__(self, freqs):
        self.policy = Policy(freqs, k=self.K_START)
        self.tick = self.calm = 0
        self.changes = []  # (tick of change, frequency before the change)

    @property
    def current(self):
        return self.policy.current

    def step(self, sig):
        self.tick += 1
        before = self.policy.current
        applied = self.policy.step(sig)
        if applied != before:
            self.calm = 0
            if self.changes and self.tick - self.changes[-1][0] <= self.WINDOW and applied == self.changes[-1][1]:
                self.policy.k = min(self.policy.k + 1, self.K_MAX)
            self.changes.append((self.tick, before))
        else:
            self.calm += 1
            if self.calm >= self.CALM:
                self.policy.k = max(self.policy.k - 1, self.K_MIN)
                self.calm = 0
        return applied


class SchedutilStyle:
    """schedutil-style APPROXIMATION, not the kernel governor.

    next f = 1.25 * util * fmax, rounded up to the ladder (util = the tick's observed busy
    fraction, not the kernel's frequency-invariant PELT signal; no rate limit, no uclamp).
    Optional I/O-wake boost: a tick with I/O wait >= 5 % starts the boost at fmin or
    doubles it (capped at fmax); a tick without halves it (dropped below fmin). The
    applied frequency is max(util request, boost), rounded up to the ladder.
    """
    IOWAIT_PCT = 5.0

    def __init__(self, freqs, io_boost=False):
        self.freqs, self.io_boost = list(freqs), io_boost
        self.current = self.freqs[-1]
        self.boost = 0.0

    def step(self, sig):
        want = 1.25 * sig['util_pct'] / 100.0 * self.freqs[-1]
        if self.io_boost:
            if sig['iowait_pct'] >= self.IOWAIT_PCT:
                self.boost = self.freqs[0] if not self.boost else min(2 * self.boost, self.freqs[-1])
            else:
                self.boost = self.boost / 2 if self.boost / 2 >= self.freqs[0] else 0.0
            want = max(want, self.boost)
        self.current = next((f for f in self.freqs if f >= want), self.freqs[-1])
        return self.current


POLICIES = {
    'performance': lambda: Performance(LADDER),
    'powersave': lambda: Powersave(LADDER),
    'conservative': lambda: Conservative(LADDER),
    'ours_k3': lambda: Policy(LADDER, k=3),
    'ours_k3_rampdown': lambda: Policy(LADDER, k=3, ramp_down_step=1),
    'ours_k1': lambda: Policy(LADDER, k=1),
    'ours_k5': lambda: Policy(LADDER, k=5),
    'fast_up_slow_down': lambda: FastUpSlowDown(LADDER, k_down=3),
    'adaptive_k': lambda: AdaptiveK(LADDER),
    'schedutil_style': lambda: SchedutilStyle(LADDER),
    'schedutil_style_ioboost': lambda: SchedutilStyle(LADDER, io_boost=True),
}

SCENARIOS = {**{name: dict(plan=s['plan'], seed=s['seed'], noise=s['noise'])
                for name, s in SENSITIVITY_SCENARIOS.items()},
             'io_heavy': dict(plan=[('io', 30), ('mixed', 5), ('io', 30)], seed=81, noise=0.1),
             'cpu_heavy': dict(plan=[('cpu', 40), ('mixed', 5), ('cpu', 40)], seed=91, noise=0.1)}
KEY_SCENARIOS = ('archived_seed11', 'cpu_bursts_on_idle_seed51', 'io_heavy', 'cpu_heavy')


def workload(plan, seed, noise):
    """Expand a plan into work units with seeded jitter."""
    rng = random.Random(seed)
    units = []
    for name, count in plan:
        p = PROFILES[name]
        for _ in range(count):
            shares = {k: max(0.0, p[k] * (1 + rng.gauss(0, noise)))
                      for k in ('user', 'system', 'idle', 'iowait', 'softirq')}
            total = sum(shares.values())
            units.append(dict(name=name, cpu=(shares['user'] + shares['system'] + shares['softirq']) / total,
                              io=shares['iowait'] / total, idle=shares['idle'] / total,
                              ctxt=max(0.0, p['ctxt'] * (1 + rng.gauss(0, noise))),
                              run=p['run'], blk=p['blk']))
    return units


def simulate(units, policy, insensitive=0.0):
    """Run one closed-loop simulation. Returns per-tick rows and summary metrics."""
    counters = {f: 0.0 for f in CPU_FIELDS}
    counters.update(ctxt=0.0, procs_running=1, procs_blocked=0)
    prev = dict(counters)
    index, progress, f = 0, 0.0, policy.current
    rows, energy, elapsed_total = [], 0.0, 0.0
    while index < len(units):
        remaining, busy, io, idle, ctxt, by_name = TICK_S, 0.0, 0.0, 0.0, 0.0, Counter()
        while remaining > 1e-12 and index < len(units):
            u = units[index]
            cpu_t = u['cpu'] * (insensitive + (1 - insensitive) * FMAX / f)
            length = cpu_t + u['io'] + u['idle']
            dt = min(remaining, (1 - progress) * length)
            share = dt / length
            busy, io, idle, ctxt = busy + cpu_t * share, io + u['io'] * share, idle + u['idle'] * share, ctxt + u['ctxt'] * share
            by_name[u['name']] += dt
            progress, remaining = progress + share, remaining - dt
            gauges = (u['run'], u['blk'])
            if progress >= 1 - 1e-12:
                index, progress = index + 1, 0.0
        elapsed = TICK_S - remaining
        util = 100.0 * busy / elapsed
        energy += estimate_power_w(f, FMAX, util) * elapsed
        elapsed_total += elapsed
        counters['user'] += busy * HZ
        counters['iowait'] += io * HZ
        counters['idle'] += idle * HZ
        counters['ctxt'] += ctxt
        counters['procs_running'], counters['procs_blocked'] = gauges
        sig = compute_signals(prev, counters, elapsed)
        prev = dict(counters)
        dominant = max(sorted(by_name), key=by_name.get)
        rows.append(dict(f=f, util=util, elapsed=elapsed, truth=dominant, at_target=f == target_khz(dominant)))
        if index < len(units):
            f = policy.step(sig)
    transitions = sum(a['f'] != b['f'] for a, b in zip(rows, rows[1:]))
    return rows, dict(energy_j=energy, completion_s=elapsed_total, edp_js=energy * elapsed_total,
                      transitions=transitions, frac_at_appropriate=sum(r['at_target'] for r in rows) / len(rows),
                      ticks=len(rows))


def run_matrix(scenarios=SCENARIOS, policies=POLICIES, seeds=SEEDS_PER_SCENARIO, fractions=(0.0,)):
    """One row per (scenario, insensitive fraction, policy, seed)."""
    out = []
    for name, scenario in scenarios.items():
        for seed_index in range(seeds):
            seed = scenario['seed'] * 1000 + seed_index
            units = workload(scenario['plan'], seed, scenario['noise'])
            for fraction in fractions:
                for policy_name, factory in policies.items():
                    _, metrics = simulate(units, factory(), fraction)
                    out.append(dict(scenario=name, insensitive_fraction=fraction, policy=policy_name, seed=seed,
                                    **{k: round(v, 6) if isinstance(v, float) else v for k, v in metrics.items()}))
    return out


METRICS = ('energy_j', 'completion_s', 'edp_js', 'transitions', 'frac_at_appropriate')


def aggregate(rows):
    groups = {}
    for row in rows:
        groups.setdefault((row['scenario'], row['insensitive_fraction'], row['policy']), []).append(row)
    out = []
    for (scenario, fraction, policy), members in groups.items():
        entry = dict(scenario=scenario, insensitive_fraction=fraction, policy=policy, runs=len(members))
        for metric in METRICS:
            values = [m[metric] for m in members]
            entry[f'{metric}_mean'] = round(statistics.fmean(values), 6)
            entry[f'{metric}_sd'] = round(statistics.stdev(values), 6) if len(values) > 1 else 0.0
            entry[f'{metric}_min'], entry[f'{metric}_max'] = round(min(values), 6), round(max(values), 6)
        out.append(entry)
    return out


RUN_COLUMNS = ('scenario', 'insensitive_fraction', 'policy', 'seed', 'ticks') + METRICS
SUMMARY_COLUMNS = ('scenario', 'insensitive_fraction', 'policy', 'runs') + tuple(
    f'{m}_{s}' for m in METRICS for s in ('mean', 'sd', 'min', 'max'))


def csv_text(rows, columns):
    return '\n'.join([','.join(columns)] + [','.join(str(r[c]) for c in columns) for r in rows]) + '\n'


def winners(summary, fraction=0.0):
    """Best policy per scenario and metric (lowest energy/time/EDP/transitions, highest fraction)."""
    out = {}
    for scenario in SCENARIOS:
        group = [s for s in summary if s['scenario'] == scenario and s['insensitive_fraction'] == fraction]
        if not group:
            continue
        out[scenario] = {m: (max if m == 'frac_at_appropriate' else min)(group, key=lambda s: s[f'{m}_mean'])['policy']
                         for m in METRICS}
    return out


def rank(summary, scenario, metric, policy, fraction=0.0):
    group = sorted((s for s in summary if s['scenario'] == scenario and s['insensitive_fraction'] == fraction),
                   key=lambda s: s[f'{metric}_mean'], reverse=metric == 'frac_at_appropriate')
    return [s['policy'] for s in group].index(policy) + 1


def summary_text(summary):
    lines = ['# Phase 2a closed-loop benchmark (MODELLED energy and time, SIMULATED frequency)', '',
             'Generated by `python -m benchmark.closed_loop`. Nothing here is measured. Mean ± sample SD over '
             f'{SEEDS_PER_SCENARIO} seeds per scenario. EDP = energy x completion time. See README.md for the model, '
             'assumptions and limits. Results are reported where our policy loses as well as where it wins.', '',
             '## Main results (frequency-insensitive fraction 0, pure 1/f)', '']
    for scenario in SCENARIOS:
        group = [s for s in summary if s['scenario'] == scenario and s['insensitive_fraction'] == 0.0]
        lines += [f'### {scenario}', '',
                  '| policy | energy J | completion s | EDP J·s | transitions | frac at class target |',
                  '|---|---|---|---|---|---|']
        for s in group:
            lines.append(f"| {s['policy']} | {s['energy_j_mean']:.1f} ± {s['energy_j_sd']:.1f} | "
                         f"{s['completion_s_mean']:.2f} ± {s['completion_s_sd']:.2f} | "
                         f"{s['edp_js_mean']:.0f} ± {s['edp_js_sd']:.0f} | {s['transitions_mean']:.1f} | "
                         f"{s['frac_at_appropriate_mean']:.3f} |")
        lines.append('')
    lines += ['## Best policy per metric (lowest mean; highest for frac at class target)', '',
              '| scenario | energy | completion | EDP | transitions | frac at class target | ours_k3 rank (energy / time / EDP of 11) |',
              '|---|---|---|---|---|---|---|']
    for scenario, best in winners(summary).items():
        ranks = ' / '.join(str(rank(summary, scenario, m, 'ours_k3')) for m in ('energy_j', 'completion_s', 'edp_js'))
        lines.append(f"| {scenario} | {best['energy_j']} | {best['completion_s']} | {best['edp_js']} | "
                     f"{best['transitions']} | {best['frac_at_appropriate']} | {ranks} |")
    lines += ['', '## Sensitivity to the frequency-insensitive fraction (key scenarios)', '',
              '| scenario | fraction | policy | energy J | completion s | EDP J·s |', '|---|---|---|---|---|---|']
    for scenario in KEY_SCENARIOS:
        for fraction in INSENSITIVE_FRACTIONS:
            for policy in ('performance', 'powersave', 'ours_k3', 'fast_up_slow_down', 'schedutil_style',
                           'schedutil_style_ioboost'):
                s = next((x for x in summary if x['scenario'] == scenario and x['insensitive_fraction'] == fraction
                          and x['policy'] == policy), None)
                if s:
                    lines.append(f"| {scenario} | {fraction:g} | {policy} | {s['energy_j_mean']:.1f} | "
                                 f"{s['completion_s_mean']:.2f} | {s['edp_js_mean']:.0f} |")
    lines.append('')
    return '\n'.join(lines)


def tables():
    rows = run_matrix()
    sweep = run_matrix({k: SCENARIOS[k] for k in KEY_SCENARIOS}, fractions=INSENSITIVE_FRACTIONS[1:])
    rows += sweep
    return rows, aggregate(rows)


SOURCES = ('benchmark/closed_loop.py', 'benchmark/sensitivity.py', 'benchmark/baselines.py', 'monitor/synthetic.py',
           'monitor/reader.py', 'classifier/rules.py', 'policy/governor_policy.py', 'power_model/estimate.py',
           'hardware_profile.py')


def git(*args):
    try:
        return subprocess.run(['git', *args], capture_output=True, text=True, timeout=10, cwd=ROOT).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 'unavailable'


def plot(summary, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for ax, scenario in zip(axes.flat, KEY_SCENARIOS):
        for s in (x for x in summary if x['scenario'] == scenario and x['insensitive_fraction'] == 0.0):
            ax.errorbar(s['completion_s_mean'], s['energy_j_mean'], xerr=s['completion_s_sd'], yerr=s['energy_j_sd'],
                        fmt='o', ms=4, capsize=2)
            ax.annotate(s['policy'], (s['completion_s_mean'], s['energy_j_mean']), fontsize=6,
                        xytext=(3, 3), textcoords='offset points')
        ax.set(title=scenario, xlabel='MODELLED completion time (s)', ylabel='MODELLED energy (J)')
    fig.suptitle('Closed-loop benchmark: modelled energy vs completion time (simulated frequency; mean ± SD, 20 seeds)')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def generate(outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    rows, summary = tables()
    texts = {'runs.csv': csv_text(rows, RUN_COLUMNS), 'summary.csv': csv_text(summary, SUMMARY_COLUMNS),
             'summary.md': summary_text(summary)}
    for name, text in texts.items():
        (outdir / name).write_bytes(text.encode('utf-8'))
    plot(summary, outdir / 'energy_vs_completion.png')
    produced = sorted(texts) + ['energy_vs_completion.png']
    files = [{'path': n, 'bytes': (outdir / n).stat().st_size,
              'sha256': hashlib.sha256((outdir / n).read_bytes()).hexdigest()} for n in produced]
    provenance = {
        'source_commit': git('rev-parse', 'HEAD'),
        'tracked_working_tree_dirty': bool(git('status', '--porcelain', '--untracked-files=no')),
        'generation_command': 'python -m benchmark.closed_loop --outdir evidence/phase2a_closed_loop',
        'python': platform.python_version(),
        'parameters': {'ladder_khz': list(LADDER), 'tick_s': TICK_S, 'cpus': 1, 'hz': HZ,
                       'seeds_per_scenario': SEEDS_PER_SCENARIO, 'seed_rule': 'scenario seed * 1000 + index (0-19)',
                       'insensitive_fractions': list(INSENSITIVE_FRACTIONS), 'key_scenarios': list(KEY_SCENARIOS),
                       'scenarios': SCENARIOS, 'policies': list(POLICIES),
                       'adaptive_k_rule': {'start': AdaptiveK.K_START, 'min': AdaptiveK.K_MIN, 'max': AdaptiveK.K_MAX,
                                           'reversal_window_ticks': AdaptiveK.WINDOW, 'calm_ticks': AdaptiveK.CALM},
                       'schedutil_style': {'factor': 1.25, 'iowait_boost_threshold_pct': SchedutilStyle.IOWAIT_PCT}},
        'source_hashes': {n: hashlib.sha256((ROOT / n).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                          for n in SOURCES},
        'source_hash_note': 'SHA-256 of LF-normalized source bytes (Git blob content) at source_commit.',
        'model': 'unit time = C*(s + (1-s)*fmax/f) + W + I; P = 21.6 + 32.4*(f/fmax)^3*util/100 W per tick',
        'interpretation_restrictions': [
            'Energy and completion time are modelled, not measured.',
            'Frequency is simulated; the ladder is 3.8-5.1 GHz only.',
            'The 1/f CPU-time assumption is a model choice; see the insensitive-fraction sweep.',
            'schedutil_style is an approximation, not the Linux schedutil governor.',
            'No claim of real energy savings or novelty.'],
        'archived_files': files,
    }
    (outdir / 'PROVENANCE.json').write_bytes((json.dumps(provenance, indent=2) + '\n').encode('utf-8'))
    manifest = [f'{f["sha256"]}  {f["path"]}' for f in files]
    manifest.append(f'{hashlib.sha256((outdir / "PROVENANCE.json").read_bytes()).hexdigest()}  PROVENANCE.json')
    (outdir / 'SHA256SUMS').write_bytes(('\n'.join(manifest) + '\n').encode('utf-8'))
    return rows, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--outdir', required=True, type=Path)
    args = parser.parse_args(argv)
    names = ('runs.csv', 'summary.csv', 'summary.md', 'energy_vs_completion.png', 'PROVENANCE.json', 'SHA256SUMS')
    if any((args.outdir / n).exists() for n in names):
        parser.error('output artifacts already exist; choose a new --outdir')
    print('MODELLED energy and time | SIMULATED frequency | no measurement')
    generate(args.outdir)
    print(f'Closed-loop outputs written to {args.outdir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
