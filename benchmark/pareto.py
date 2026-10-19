"""Phase 2b: static-frequency baselines, Pareto frontiers and an I/O-target ablation.

    python -m benchmark.pareto --outdir <new folder>

Reuses the closed-loop model in benchmark/closed_loop.py unchanged: MODELLED energy and
completion time, SIMULATED frequency, nothing measured.

- Static baselines: one constant policy per ladder level (3.8, 4.233, 4.667, 5.1 GHz).
- Pareto: for each scenario and frequency-insensitive fraction, a policy is on the
  energy/completion-time frontier if no other policy or static level has mean energy <=
  and mean time <= with at least one strictly lower. For every dynamic policy we also
  report the best static level whose mean completion time is <= the policy's (lowest
  energy among them) and the energy difference: positive means that fixed frequency uses
  less energy without being slower.
- I/O ablation: our K=3 policy with the I/O-class target fraction set to 1.0, 0.6, 0.3
  (default) or 0.0, crossed with the mixed-class fraction 1.0 or 0.6 (default), on
  io_heavy and cpu_bursts_on_idle_seed51 for every insensitive fraction.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform

from benchmark import closed_loop as cl
from classifier.rules import CPU_BOUND, IDLE, IO_BOUND, MIXED
from policy.governor_policy import TARGET, Policy

ROOT = cl.ROOT
LADDER = cl.LADDER
STATIC_NAMES = {f: f'static_{f / 1e6:.3f}GHz' for f in LADDER}
ABLATION_SCENARIOS = ('io_heavy', 'cpu_bursts_on_idle_seed51')
IO_FRACTIONS = (1.0, 0.6, 0.3, 0.0)
MIXED_FRACTIONS = (1.0, 0.6)


class StaticFrequency:
    """Always the same ladder level."""

    def __init__(self, khz):
        self.current = khz

    def step(self, sig):
        return self.current


class OursWithTargets(Policy):
    """Our K=3 policy with different I/O and mixed class-target fractions (ablation only)."""

    def __init__(self, freqs, io=TARGET[IO_BOUND], mixed=TARGET[MIXED], k=3):
        super().__init__(freqs, k=k)
        self.fractions = {CPU_BOUND: TARGET[CPU_BOUND], IDLE: TARGET[IDLE], IO_BOUND: io, MIXED: mixed}

    def _target_freq(self, cls):
        super()._target_freq(cls)  # keeps the unknown-class check
        return self.freqs[round(self.fractions[cls] * (len(self.freqs) - 1))]


STATIC_POLICIES = {name: (lambda f=f: StaticFrequency(f)) for f, name in STATIC_NAMES.items()}
ALL_POLICIES = {**cl.POLICIES, **STATIC_POLICIES}
DYNAMIC = tuple(cl.POLICIES)
ABLATION_POLICIES = {f'ours_io{io:.1f}_mixed{mixed:.1f}': (lambda io=io, mixed=mixed: OursWithTargets(LADDER, io, mixed))
                     for mixed in MIXED_FRACTIONS for io in IO_FRACTIONS}


def dominates(a, b):
    """a dominates b: energy and time both <= and at least one strictly lower."""
    return (a['energy'] <= b['energy'] and a['time'] <= b['time']
            and (a['energy'] < b['energy'] or a['time'] < b['time']))


def frontier(points):
    """Names of points (dicts with name, energy, time) that no other point dominates."""
    return [p['name'] for p in points if not any(dominates(q, p) for q in points if q is not p)]


def static_comparison(point, statics):
    """Best static level with time <= the point's time (lowest energy), and the energy gap."""
    eligible = [s for s in statics if s['time'] <= point['time']]
    best = min(eligible, key=lambda s: (s['energy'], s['time']))
    gap = point['energy'] - best['energy']
    return dict(best_static=best['name'], energy_gap_j=round(gap, 6),
                energy_gap_pct=round(100 * gap / best['energy'], 6),
                dominated_by_static=any(dominates(s, point) for s in statics),
                equal_to_static=any(s['energy'] == point['energy'] and s['time'] == point['time'] for s in statics))


def frontier_rows(summary):
    rows = []
    for scenario in cl.SCENARIOS:
        for fraction in cl.INSENSITIVE_FRACTIONS:
            group = [s for s in summary if s['scenario'] == scenario and s['insensitive_fraction'] == fraction]
            points = [dict(name=s['policy'], energy=s['energy_j_mean'], time=s['completion_s_mean']) for s in group]
            on = set(frontier(points))
            statics = [p for p in points if p['name'] in STATIC_NAMES.values()]
            for p in points:
                row = dict(scenario=scenario, insensitive_fraction=fraction, policy=p['name'],
                           kind='static' if p['name'] in STATIC_NAMES.values() else 'dynamic',
                           energy_j_mean=p['energy'], completion_s_mean=p['time'], on_frontier=p['name'] in on)
                if row['kind'] == 'dynamic':
                    row.update(static_comparison(p, statics))
                else:
                    row.update(best_static='', energy_gap_j='', energy_gap_pct='', dominated_by_static='',
                               equal_to_static='')
                rows.append(row)
    return rows


def tables():
    results = cl.aggregate(cl.run_matrix(policies=ALL_POLICIES, fractions=cl.INSENSITIVE_FRACTIONS))
    ablation = cl.aggregate(cl.run_matrix({k: cl.SCENARIOS[k] for k in ABLATION_SCENARIOS}, policies=ABLATION_POLICIES,
                                          fractions=cl.INSENSITIVE_FRACTIONS))
    return results, frontier_rows(results), ablation


FRONTIER_COLUMNS = ('scenario', 'insensitive_fraction', 'policy', 'kind', 'energy_j_mean', 'completion_s_mean',
                    'on_frontier', 'dominated_by_static', 'equal_to_static', 'best_static', 'energy_gap_j',
                    'energy_gap_pct')


def short(name):
    return name.replace('static_', '').replace('schedutil_style', 'sched')


def summary_text(results, front, ablation):
    lines = ['# Phase 2b Pareto and I/O ablation (MODELLED energy and time, SIMULATED frequency)', '',
             'Generated by `python -m benchmark.pareto`. Nothing here is measured. Means over 20 seeds. '
             'See README.md for the model, assumptions and limits.', '',
             '## Energy/completion-time frontier (policies not dominated on mean energy and mean time)', '',
             '| scenario | s = 0 | s = 0.3 | s = 0.6 | s = 0.9 |', '|---|---|---|---|---|']
    for scenario in cl.SCENARIOS:
        cells = []
        for fraction in cl.INSENSITIVE_FRACTIONS:
            on = sorted((r for r in front if r['scenario'] == scenario and r['insensitive_fraction'] == fraction
                         and r['on_frontier']), key=lambda r: r['completion_s_mean'])
            cells.append(', '.join(short(r['policy']) for r in on))
        lines.append(f'| {scenario} | ' + ' | '.join(cells) + ' |')
    lines += ['', '## Dynamic policies against fixed frequencies', '',
              'Each cell: energy difference (J, %) versus the lowest-energy static level whose completion time is '
              '<= the policy\'s, and that level. Positive = the fixed frequency uses less energy and is no slower. '
              'D = dominated by a static level; = = identical to a static level; F = on the frontier.', '']
    for scenario in cl.SCENARIOS:
        lines += [f'### {scenario}', '', '| policy | s = 0 | s = 0.3 | s = 0.6 | s = 0.9 |', '|---|---|---|---|---|']
        for policy in DYNAMIC:
            cells = []
            for fraction in cl.INSENSITIVE_FRACTIONS:
                r = next(x for x in front if x['scenario'] == scenario and x['insensitive_fraction'] == fraction
                         and x['policy'] == policy)
                flag = '=' if r['equal_to_static'] else ('D' if r['dominated_by_static'] else ('F' if r['on_frontier'] else ''))
                cells.append(f"{r['energy_gap_j']:+.1f} J ({r['energy_gap_pct']:+.2f}%) vs {short(r['best_static'])} {flag}".rstrip())
            lines.append(f'| {policy} | ' + ' | '.join(cells) + ' |')
        lines.append('')
    lines += ['## I/O-target ablation (our K=3 policy; default io 0.3, mixed 0.6)', '',
              'Energy (J), completion time (s) and EDP (J·s), mean over 20 seeds. Lower io fraction = lower frequency '
              'during I/O-classified phases.', '']
    for scenario in ABLATION_SCENARIOS:
        lines += [f'### {scenario}', '', '| variant | s | energy J | completion s | EDP J·s |', '|---|---|---|---|---|']
        for fraction in cl.INSENSITIVE_FRACTIONS:
            for policy in ABLATION_POLICIES:
                a = next(x for x in ablation if x['scenario'] == scenario and x['insensitive_fraction'] == fraction
                         and x['policy'] == policy)
                lines.append(f"| {policy} | {fraction:g} | {a['energy_j_mean']:.1f} ± {a['energy_j_sd']:.1f} | "
                             f"{a['completion_s_mean']:.2f} ± {a['completion_s_sd']:.2f} | {a['edp_js_mean']:.0f} |")
        lines.append('')
    return '\n'.join(lines)


def plot(front, scenario, path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    names = list(ALL_POLICIES)
    colours = plt.get_cmap('tab20').colors
    fig, axes = plt.subplots(2, 2, figsize=(12, 8.5))
    for ax, fraction in zip(axes.flat, cl.INSENSITIVE_FRACTIONS):
        group = [r for r in front if r['scenario'] == scenario and r['insensitive_fraction'] == fraction]
        for r in group:
            i = names.index(r['policy'])
            marker = 's' if r['kind'] == 'static' else ('*' if r['policy'].startswith(('ours', 'fast', 'adaptive')) else 'o')
            ax.scatter(r['completion_s_mean'], r['energy_j_mean'], color=colours[i % 20], marker=marker,
                       s=60 if marker == '*' else 30, edgecolors='black' if r['on_frontier'] else 'none',
                       linewidths=0.8, label=r['policy'], zorder=3)
        on = sorted((r for r in group if r['on_frontier']), key=lambda r: r['completion_s_mean'])
        ax.plot([r['completion_s_mean'] for r in on], [r['energy_j_mean'] for r in on], color='grey', lw=1, zorder=1)
        ax.set(title=f'insensitive fraction s = {fraction:g}', xlabel='MODELLED completion time (s)',
               ylabel='MODELLED energy (J)')
    handles, labels = axes.flat[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='center right', fontsize=8, title='policy (outlined = on frontier)')
    fig.suptitle(f'{scenario}: modelled energy vs completion time, mean of 20 seeds (simulated frequency; grey = frontier)')
    fig.tight_layout(rect=(0, 0, 0.8, 0.96))
    fig.savefig(path, dpi=130)
    plt.close(fig)


SOURCES = ('benchmark/pareto.py', 'benchmark/closed_loop.py', 'benchmark/sensitivity.py', 'benchmark/baselines.py',
           'monitor/synthetic.py', 'monitor/reader.py', 'classifier/rules.py', 'policy/governor_policy.py',
           'power_model/estimate.py', 'hardware_profile.py')


def generate(outdir):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    results, front, ablation = tables()
    texts = {'results.csv': cl.csv_text(results, cl.SUMMARY_COLUMNS),
             'frontier.csv': cl.csv_text(front, FRONTIER_COLUMNS),
             'ablation.csv': cl.csv_text(ablation, cl.SUMMARY_COLUMNS),
             'summary.md': summary_text(results, front, ablation)}
    for name, text in texts.items():
        (outdir / name).write_bytes(text.encode('utf-8'))
    pngs = []
    for scenario in cl.SCENARIOS:
        pngs.append(f'pareto_{scenario}.png')
        plot(front, scenario, outdir / pngs[-1])
    produced = sorted(texts) + pngs
    files = [{'path': n, 'bytes': (outdir / n).stat().st_size,
              'sha256': hashlib.sha256((outdir / n).read_bytes()).hexdigest()} for n in produced]
    provenance = {
        'source_commit': cl.git('rev-parse', 'HEAD'),
        'tracked_working_tree_dirty': bool(cl.git('status', '--porcelain', '--untracked-files=no')),
        'generation_command': 'python -m benchmark.pareto --outdir evidence/phase2b_pareto',
        'python': platform.python_version(),
        'parameters': {'ladder_khz': list(LADDER), 'static_levels': list(STATIC_NAMES.values()),
                       'dynamic_policies': list(DYNAMIC), 'scenarios': list(cl.SCENARIOS),
                       'insensitive_fractions': list(cl.INSENSITIVE_FRACTIONS),
                       'seeds_per_scenario': cl.SEEDS_PER_SCENARIO, 'seed_rule': 'scenario seed * 1000 + index (0-19)',
                       'ablation': {'scenarios': list(ABLATION_SCENARIOS), 'io_fractions': list(IO_FRACTIONS),
                                    'mixed_fractions': list(MIXED_FRACTIONS), 'k': 3},
                       'dominance': 'a dominates b if mean energy <= and mean time <= with at least one strictly lower'},
        'source_hashes': {n: hashlib.sha256((ROOT / n).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                          for n in SOURCES},
        'source_hash_note': 'SHA-256 of LF-normalized source bytes (Git blob content) at source_commit.',
        'interpretation_restrictions': [
            'Energy and completion time are modelled, not measured.',
            'Frequency is simulated; the ladder is 3.8-5.1 GHz only.',
            'Pareto comparisons use means over 20 seeds; spreads are in results.csv.',
            'schedutil_style is an approximation, not the Linux schedutil governor.',
            'No claim of real energy savings or novelty.'],
        'archived_files': files,
    }
    (outdir / 'PROVENANCE.json').write_bytes((json.dumps(provenance, indent=2) + '\n').encode('utf-8'))
    manifest = [f'{f["sha256"]}  {f["path"]}' for f in files]
    manifest.append(f'{hashlib.sha256((outdir / "PROVENANCE.json").read_bytes()).hexdigest()}  PROVENANCE.json')
    (outdir / 'SHA256SUMS').write_bytes(('\n'.join(manifest) + '\n').encode('utf-8'))
    return results, front, ablation


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--outdir', required=True, type=Path)
    args = parser.parse_args(argv)
    names = ('results.csv', 'frontier.csv', 'ablation.csv', 'summary.md', 'PROVENANCE.json', 'SHA256SUMS')
    if any((args.outdir / n).exists() for n in names):
        parser.error('output artifacts already exist; choose a new --outdir')
    print('MODELLED energy and time | SIMULATED frequency | no measurement')
    generate(args.outdir)
    print(f'Pareto outputs written to {args.outdir}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
