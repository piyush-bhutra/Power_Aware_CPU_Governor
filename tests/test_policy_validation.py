"""Phase 1A: ramp-down convergence and input validation (policy, classifier, monitor)."""
import math

import pytest

from classifier.rules import classify
from monitor.reader import compute_signals
from policy.governor_policy import Policy

FREQS = [1_000_000, 2_000_000, 3_000_000, 4_000_000]
SIG = dict(util_pct=50.0, iowait_pct=1.0, procs_blocked=0, ctxt_per_s=100.0, procs_running=2)


def test_ramp_down_keeps_stepping_until_target_while_class_persists():
    policy = Policy(FREQS, k=1, ramp_down_step=1)
    assert policy.decide('cpu_bound') == 4_000_000
    assert [policy.decide('idle') for _ in range(5)] == [3_000_000, 2_000_000, 1_000_000,
                                                         1_000_000, 1_000_000]


def test_ramp_down_respects_hysteresis_and_larger_steps():
    policy = Policy(FREQS, k=2, ramp_down_step=2)
    assert [policy.decide('idle') for _ in range(4)] == [4_000_000, 2_000_000, 1_000_000, 1_000_000]


def test_default_jump_behaviour_unchanged():
    policy = Policy(FREQS, k=3)
    out = [policy.decide(c) for c in ['cpu_bound'] * 3 + ['idle'] * 3 + ['mixed'] * 2 + ['idle']]
    assert out == [4_000_000] * 5 + [1_000_000] * 4
    policy = Policy(FREQS, k=1)
    assert [policy.decide(c) for c in ['idle', 'mixed', 'io_bound', 'cpu_bound']] == \
        [1_000_000, 3_000_000, 2_000_000, 4_000_000]


def test_ramp_down_from_off_ladder_synced_value():
    policy = Policy(FREQS, k=1, ramp_down_step=1)
    policy.decide('cpu_bound')
    policy.decide('idle')            # 3 MHz
    policy.sync(2_500_000)           # hardware readback between ladder steps
    assert policy.decide('idle') == 1_000_000  # one step below highest step <= 2.5 MHz


@pytest.mark.parametrize('ladder, message', [([], 'empty'), ([2, 1], 'ascending'),
                                             ([1, 1], 'ascending'), ([0, 1], 'positive')])
def test_ladder_validation(ladder, message):
    with pytest.raises(ValueError, match=message):
        Policy(ladder)


@pytest.mark.parametrize('k', [0, -1, 1.5, True, '3'])
def test_k_validation(k):
    with pytest.raises(ValueError, match='k must be an integer'):
        Policy(FREQS, k=k)


@pytest.mark.parametrize('step', [0, -2, 1.0])
def test_ramp_step_validation(step):
    with pytest.raises(ValueError, match='ramp_down_step'):
        Policy(FREQS, ramp_down_step=step)


def test_unknown_class_rejected():
    policy = Policy(FREQS)
    with pytest.raises(ValueError, match='unknown workload class'):
        policy.decide('memory_bound')
    with pytest.raises(ValueError, match='unknown workload class'):
        policy._target_freq('busy')


@pytest.mark.parametrize('change, message', [
    ({'util_pct': None}, 'missing'), ({'iowait_pct': math.nan}, 'NaN'),
    ({'ctxt_per_s': -1.0}, 'negative'), ({'procs_running': 'two'}, 'number')])
def test_classify_rejects_bad_features(change, message):
    with pytest.raises(ValueError, match=message):
        classify({**SIG, **change})
    reduced = dict(SIG)
    del reduced['procs_blocked']
    with pytest.raises(ValueError, match="missing feature 'procs_blocked'"):
        classify(reduced)


def test_classify_valid_input_unchanged():
    assert classify(SIG) == 'mixed'
    assert classify({**SIG, 'util_pct': 90.0}) == 'cpu_bound'


def _snapshot(**overrides):
    base = dict(user=100, nice=0, system=50, idle=800, iowait=10, irq=0, softirq=5, steal=0,
                guest=0, guest_nice=0, ctxt=1000, procs_running=1, procs_blocked=0)
    return {**base, **overrides}


@pytest.mark.parametrize('side, change, message', [
    ('cur', {'procs_running': None}, 'missing'), ('prev', {'ctxt': math.nan}, 'NaN'),
    ('cur', {'idle': -5}, 'negative'), ('prev', {'user': 'x'}, 'number')])
def test_compute_signals_rejects_bad_counters(side, change, message):
    prev, cur = _snapshot(), _snapshot(user=200, idle=900, ctxt=1500)
    if side == 'cur':
        cur.update(change)
    else:
        prev.update(change)
    with pytest.raises(ValueError, match=message):
        compute_signals(prev, cur, 1.0)


def test_compute_signals_valid_and_reset_paths_unchanged():
    prev, cur = _snapshot(), _snapshot(user=200, idle=900, ctxt=1500)
    assert compute_signals(prev, cur, 1.0)['util_pct'] == 50.0
    assert compute_signals(cur, prev, 1.0) is None  # counter reset still rebaselines
