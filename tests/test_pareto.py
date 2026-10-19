"""Phase 2b: static baselines, Pareto dominance, I/O-target ablation and evidence integrity."""
from pathlib import Path

import pytest

from benchmark import closed_loop as cl
from benchmark import pareto as p
from hardware_profile import RYZEN_7840HS_LADDER_KHZ as L

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence' / 'phase2b_pareto'
IO_HEAVY = {'io_heavy': cl.SCENARIOS['io_heavy']}


def metrics(policy, scenario='io_heavy', seed=81000, fraction=0.0):
    s = cl.SCENARIOS[scenario]
    return cl.simulate(cl.workload(s['plan'], seed, s['noise']), policy, fraction)


def test_same_inputs_give_identical_results():
    one = cl.run_matrix(IO_HEAVY, policies=p.ALL_POLICIES, seeds=2, fractions=(0.0, 0.6))
    two = cl.run_matrix(IO_HEAVY, policies=p.ALL_POLICIES, seeds=2, fractions=(0.0, 0.6))
    assert one == two


@pytest.mark.parametrize('khz', L)
def test_static_levels_are_constant(khz):
    rows, _ = metrics(p.StaticFrequency(khz))
    assert {r['f'] for r in rows} == {khz}


def test_extreme_static_levels_match_performance_and_powersave():
    assert metrics(p.StaticFrequency(L[-1]))[1] == metrics(cl.POLICIES['performance']())[1]
    assert metrics(p.StaticFrequency(L[0]))[1] == metrics(cl.POLICIES['powersave']())[1]


def pt(name, energy, time):
    return dict(name=name, energy=energy, time=time)


def test_dominance_and_frontier_on_hand_made_points():
    a, b, c_, d = pt('a', 1, 1), pt('b', 2, 2), pt('c', 1, 2), pt('d', 2, 1)
    assert p.dominates(a, b) and p.dominates(a, c_) and p.dominates(a, d)
    assert not p.dominates(c_, d) and not p.dominates(d, c_) and not p.dominates(a, a)
    assert p.frontier([a, b, c_, d]) == ['a']
    assert p.frontier([b, c_, d]) == ['c', 'd']
    twin = pt('twin', 1, 1)
    assert p.frontier([a, twin, b]) == ['a', 'twin']  # equal points do not dominate each other


def test_static_comparison_picks_lowest_energy_no_slower_level():
    statics = [pt('s1', 90, 9), pt('s2', 80, 12), pt('s3', 95, 10)]
    worse = p.static_comparison(pt('x', 100, 10), statics)
    assert worse['best_static'] == 's1' and worse['energy_gap_j'] == 10 and worse['dominated_by_static']
    better = p.static_comparison(pt('y', 85, 9.5), statics)
    assert better['best_static'] == 's1' and better['energy_gap_j'] == -5 and not better['dominated_by_static']
    same = p.static_comparison(pt('z', 90, 9), statics)
    assert same['equal_to_static'] and not same['dominated_by_static']


def test_ablation_default_targets_reproduce_ours_k3():
    assert metrics(p.OursWithTargets(L))[1] == metrics(cl.POLICIES['ours_k3']())[1]


def test_ablation_without_lowering_for_io_and_mixed_behaves_like_performance():
    rows, result = metrics(p.OursWithTargets(L, io=1.0, mixed=1.0))
    assert result == metrics(cl.POLICIES['performance']())[1]
    assert {r['f'] for r in rows} == {L[-1]}


def test_ablation_targets_map_to_the_ladder():
    policy = p.OursWithTargets(L, io=0.0, mixed=1.0)
    assert policy._target_freq('io_bound') == L[0] and policy._target_freq('mixed') == L[-1]
    assert policy._target_freq('idle') == L[0] and policy._target_freq('cpu_bound') == L[-1]
    with pytest.raises(ValueError, match='unknown workload class'):
        policy._target_freq('memory_bound')


def test_lower_io_target_trades_time_for_energy_in_io_heavy():
    full = metrics(p.OursWithTargets(L, io=1.0, mixed=1.0))[1]
    low = metrics(p.OursWithTargets(L, io=0.0, mixed=1.0))[1]
    assert low['energy_j'] < full['energy_j'] and low['completion_s'] > full['completion_s']


def test_committed_evidence_verifies_and_regenerates_identically():
    from presentation.adapter import verify_archive
    expected = {'results.csv', 'frontier.csv', 'ablation.csv', 'summary.md', 'PROVENANCE.json'}
    expected |= {f'pareto_{s}.png' for s in cl.SCENARIOS}
    assert {f.name for f in verify_archive(EVIDENCE)} == expected
    results, front, ablation = p.tables()
    assert (EVIDENCE / 'results.csv').read_bytes() == cl.csv_text(results, cl.SUMMARY_COLUMNS).encode()
    assert (EVIDENCE / 'frontier.csv').read_bytes() == cl.csv_text(front, p.FRONTIER_COLUMNS).encode()
    assert (EVIDENCE / 'ablation.csv').read_bytes() == cl.csv_text(ablation, cl.SUMMARY_COLUMNS).encode()
    assert (EVIDENCE / 'summary.md').read_bytes() == p.summary_text(results, front, ablation).encode()


def test_refuses_existing_outputs(tmp_path):
    (tmp_path / 'results.csv').write_text('x')
    with pytest.raises(SystemExit):
        p.main(['--outdir', str(tmp_path)])
