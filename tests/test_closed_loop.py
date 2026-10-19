"""Phase 2a closed-loop benchmark: determinism, model physics, policy behaviour, evidence."""
from pathlib import Path

import pytest

from benchmark import closed_loop as c
from hardware_profile import RYZEN_7840HS_LADDER_KHZ as L

EVIDENCE = Path(__file__).resolve().parents[1] / 'evidence' / 'phase2a_closed_loop'
FMIN, FMAX = L[0], L[-1]


def unit(cpu, io=0.0, idle=0.0, name='cpu', run=2, blk=0, ctxt=200.0):
    return dict(name=name, cpu=cpu, io=io, idle=idle, ctxt=ctxt, run=run, blk=blk)


def applied(rows):
    return [r['f'] for r in rows]


# Determinism

def test_same_seed_gives_identical_results():
    one = c.run_matrix({'archived_seed11': c.SCENARIOS['archived_seed11']}, seeds=3)
    two = c.run_matrix({'archived_seed11': c.SCENARIOS['archived_seed11']}, seeds=3)
    assert one == two
    assert c.workload(c.SCENARIOS['io_heavy']['plan'], 5, 0.1) == c.workload(c.SCENARIOS['io_heavy']['plan'], 5, 0.1)
    assert c.workload(c.SCENARIOS['io_heavy']['plan'], 5, 0.1) != c.workload(c.SCENARIOS['io_heavy']['plan'], 6, 0.1)


# Model physics

def test_lower_frequency_stretches_cpu_work_but_not_io_wait():
    cpu_only = [unit(1.0)] * 10
    io_only = [unit(0.0, io=1.0, name='io', run=1, blk=1)] * 10
    fast = c.simulate(cpu_only, c.POLICIES['performance']())[1]['completion_s']
    slow = c.simulate(cpu_only, c.POLICIES['powersave']())[1]['completion_s']
    assert fast == pytest.approx(10.0)
    assert slow == pytest.approx(10.0 * FMAX / FMIN)
    for name in ('performance', 'powersave'):
        assert c.simulate(io_only, c.POLICIES[name]())[1]['completion_s'] == pytest.approx(10.0)


def test_insensitive_fraction_limits_the_slowdown():
    cpu_only = [unit(1.0)] * 10
    half = c.simulate(cpu_only, c.POLICIES['powersave'](), insensitive=0.5)[1]['completion_s']
    assert half == pytest.approx(10.0 * (0.5 + 0.5 * FMAX / FMIN))
    assert c.simulate(cpu_only, c.POLICIES['powersave'](), insensitive=1.0)[1]['completion_s'] == pytest.approx(10.0)


def test_slowing_down_raises_observed_utilization():
    mixed = [unit(0.5, io=0.0, idle=0.5, name='mixed')] * 6
    fast_rows = c.simulate(mixed, c.POLICIES['performance']())[0]
    slow_rows = c.simulate(mixed, c.POLICIES['powersave']())[0]
    assert fast_rows[0]['util'] == pytest.approx(50.0)
    assert slow_rows[0]['util'] > fast_rows[0]['util']


def test_energy_uses_the_existing_power_model():
    rows, metrics = c.simulate([unit(1.0)] * 3, c.POLICIES['performance']())
    assert metrics['energy_j'] == pytest.approx(3 * (21.6 + 32.4))
    assert metrics['edp_js'] == pytest.approx(metrics['energy_j'] * metrics['completion_s'])


# Policy behaviour on simple scenarios (noise 0)

def plan_units(plan):
    return c.workload(plan, 0, 0.0)


def test_performance_and_powersave_are_constant():
    units = plan_units([('cpu', 5), ('idle', 5)])
    assert set(applied(c.simulate(units, c.POLICIES['performance']())[0])) == {FMAX}
    assert set(applied(c.simulate(units, c.POLICIES['powersave']())[0])) == {FMIN}


@pytest.mark.parametrize('name, k', [('ours_k1', 1), ('ours_k3', 3), ('ours_k5', 5)])
def test_ours_lowers_after_k_idle_ticks(name, k):
    rows, metrics = c.simulate(plan_units([('cpu', 5), ('idle', 10)]), c.POLICIES[name]())
    f = applied(rows)
    assert f[:5 + k] == [FMAX] * (5 + k) and f[5 + k] == FMIN  # decided on idle tick k, applied next tick
    assert metrics['transitions'] == 1


def test_ramp_down_variant_steps_down():
    f = applied(c.simulate(plan_units([('cpu', 5), ('idle', 10)]), c.POLICIES['ours_k3_rampdown']())[0])
    assert [x for i, x in enumerate(f) if i == 0 or x != f[i - 1]] == list(reversed(L))


def test_fast_up_slow_down_raises_after_one_tick_and_lowers_after_k():
    f = applied(c.simulate(plan_units([('cpu', 5), ('idle', 6), ('cpu', 4)]), c.POLICIES['fast_up_slow_down']())[0])
    assert f[7] == FMAX and f[8] == FMIN  # decided on the 3rd idle tick, applied on the next
    assert FMAX in f[11:13]  # raised on the tick after the first CPU tick


def test_adaptive_k_grows_on_reversals_and_decays_when_calm():
    policy = c.AdaptiveK(L)
    c.simulate(plan_units([('cpu', 3), ('idle', 3), ('cpu', 3)]), policy)  # down, then back up within 6 ticks
    assert policy.policy.k == c.AdaptiveK.K_START + 1
    c.simulate(plan_units([('cpu', 40)]), policy)  # 10 calm ticks per decrement, floor at K_MIN
    assert policy.policy.k == c.AdaptiveK.K_MIN


def test_schedutil_style_rounds_up_and_boosts_on_io():
    s = c.SchedutilStyle(L)
    assert s.step(dict(util_pct=100.0, iowait_pct=0.0)) == FMAX
    assert s.step(dict(util_pct=30.0, iowait_pct=0.0)) == FMIN
    assert s.step(dict(util_pct=70.0, iowait_pct=0.0)) == L[2]  # 1.25 * 0.7 * 5.1 GHz = 4.46 -> 4.67
    boosted = c.SchedutilStyle(L, io_boost=True)
    assert boosted.step(dict(util_pct=10.0, iowait_pct=50.0)) == FMIN  # boost starts at fmin
    assert boosted.step(dict(util_pct=10.0, iowait_pct=50.0)) == FMAX  # doubles, capped at fmax
    assert c.SchedutilStyle(L).step(dict(util_pct=10.0, iowait_pct=50.0)) == FMIN  # no boost without the option


def test_every_policy_completes_every_scenario_shape():
    rows = c.run_matrix({'io_heavy': c.SCENARIOS['io_heavy']}, seeds=1)
    assert {r['policy'] for r in rows} == set(c.POLICIES)
    assert all(r['completion_s'] >= 65.0 - 1e-6 for r in rows)  # nothing beats running at fmax


# Evidence integrity

def test_committed_evidence_verifies_and_regenerates_identically():
    from presentation.adapter import verify_archive
    assert {p.name for p in verify_archive(EVIDENCE)} == {
        'runs.csv', 'summary.csv', 'summary.md', 'energy_vs_completion.png', 'PROVENANCE.json'}
    rows, summary = c.tables()
    assert (EVIDENCE / 'runs.csv').read_bytes() == c.csv_text(rows, c.RUN_COLUMNS).encode()
    assert (EVIDENCE / 'summary.csv').read_bytes() == c.csv_text(summary, c.SUMMARY_COLUMNS).encode()
    assert (EVIDENCE / 'summary.md').read_bytes() == c.summary_text(summary).encode()


def test_refuses_existing_outputs(tmp_path):
    (tmp_path / 'runs.csv').write_text('x')
    with pytest.raises(SystemExit):
        c.main(['--outdir', str(tmp_path)])
