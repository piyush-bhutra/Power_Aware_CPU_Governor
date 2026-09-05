"""Self-checks for the logic that can be verified without Linux. Run: python tests/test_core.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor.reader import parse_stat, compute_signals
from classifier.rules import classify, CPU_BOUND, IO_BOUND, IDLE
from policy.governor_policy import Policy
from power_model.estimate import estimate_power_w

STAT = """cpu  {user} 0 {sys} {idle} {iowait} 0 {softirq} 0 0 0
cpu0 1 2 3 4 5 6 7 0 0 0
intr 100
ctxt {ctxt}
btime 1700000000
procs_running {run}
procs_blocked {blk}
"""


def snap(user=0, sys_=0, idle=0, iowait=0, softirq=0, ctxt=0, run=1, blk=0):
    return parse_stat(STAT.format(user=user, sys=sys_, idle=idle, iowait=iowait,
                                  softirq=softirq, ctxt=ctxt, run=run, blk=blk))


def test_deltas():
    # Cumulative counters must be differenced, not read as totals.
    prev = snap(user=1000, idle=1000, ctxt=5000)
    cur = snap(user=1090, idle=1010, ctxt=5300)
    s = compute_signals(prev, cur, 1.0)
    assert abs(s["util_pct"] - 90.0) < 0.01, s
    assert s["ctxt_per_s"] == 300.0
    # A large shared history must not drag the rate toward a constant.
    prev2 = snap(user=10**7, idle=10**7, ctxt=10**7)
    cur2 = snap(user=10**7 + 90, idle=10**7 + 10, ctxt=10**7 + 300)
    assert compute_signals(prev2, cur2, 1.0) == s
    assert compute_signals(prev, prev, 1.0) is None  # no jiffies elapsed


def test_classify():
    cpu = {"util_pct": 94, "iowait_pct": 1, "irq_pct": 0, "ctxt_per_s": 200,
           "procs_running": 2, "procs_blocked": 0}
    io = {"util_pct": 8, "iowait_pct": 76, "irq_pct": 5, "ctxt_per_s": 9000,
          "procs_running": 1, "procs_blocked": 1}
    idle = {"util_pct": 2, "iowait_pct": 0, "irq_pct": 0, "ctxt_per_s": 50,
            "procs_running": 1, "procs_blocked": 0}
    assert classify(cpu) == CPU_BOUND
    assert classify(io) == IO_BOUND
    assert classify(idle) == IDLE
    # An I/O burst with high util must not read as CPU-bound.
    assert classify({**io, "util_pct": 85}) == IO_BOUND


def test_hysteresis():
    p = Policy([1000, 2000, 3000], k=3)
    assert p.decide(IO_BOUND) == 3000   # k not reached, hold
    assert p.decide(CPU_BOUND) == 3000  # flapping resets the streak
    assert p.decide(IO_BOUND) == 3000
    assert p.decide(IO_BOUND) == 3000
    assert p.decide(IO_BOUND) == 2000   # 3 consecutive ticks -> act (0.3 of range)
    p2 = Policy([1000, 2000, 3000], k=1, ramp_down_step=1)
    assert p2.decide(IDLE) == 2000      # asymmetric: one step down, not min


def test_power():
    assert estimate_power_w(3000, 3000) > estimate_power_w(1500, 3000)
    assert estimate_power_w(0, 3000) == 2.0  # static floor only


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
