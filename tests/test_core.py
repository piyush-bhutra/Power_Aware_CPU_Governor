"""Self-checks for the logic that can be verified without Linux. Run: python tests/test_core.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from monitor.reader import parse_stat, compute_signals, log_csv, SIGNALS
from classifier.rules import classify, CPU_BOUND, IO_BOUND, IDLE, MIXED
from policy.governor_policy import Policy
from power_model.estimate import STATIC_W, estimate_power_w
from setter.freq_setter import SimulatedSetter
from monitor.synthetic import source as synth
from governor import run

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


def test_ratio_features():
    # Hand-checked: 100 jiffies = 60 user + 20 iowait + 20 idle
    #   util 60%, iowait 20%  -> iowait_over_util = 20/60 = 0.333...
    #   600 switches in 1s over 3 runnable -> ctxt_over_run = 200
    s = compute_signals(snap(), snap(user=60, iowait=20, idle=20, ctxt=600, run=3), 1.0)
    assert abs(s["util_pct"] - 60.0) < 1e-9 and abs(s["iowait_pct"] - 20.0) < 1e-9
    assert abs(s["iowait_over_util"] - 1 / 3) < 1e-9, s
    assert s["ctxt_over_run"] == 200.0, s


def test_ratio_features_guard_zero_denominators():
    import math
    cases = {
        # util_pct = 0 with iowait > 0 -> cap
        "util0_iowait": (snap(iowait=50, idle=50, ctxt=100, run=2), "iowait_over_util", 1000.0),
        # util_pct = 0 and iowait = 0 -> 0.0, not 0/0
        "util0_idle": (snap(idle=100, ctxt=100, run=2), "iowait_over_util", 0.0),
        # procs_running = 0 with switches -> cap
        "run0_ctxt": (snap(user=50, idle=50, ctxt=100, run=0), "ctxt_over_run", 1000.0),
        # procs_running = 0 and no switches -> 0.0
        "run0_quiet": (snap(user=50, idle=50, ctxt=0, run=0), "ctxt_over_run", 0.0),
    }
    for name, (cur, key, want) in cases.items():
        s = compute_signals(snap(), cur, 1.0)
        for k in ("iowait_over_util", "ctxt_over_run"):
            assert math.isfinite(s[k]), (name, k, s[k])
        assert s[key] == want, (name, key, s[key])


def test_log_csv_creates_missing_parent_dir(tmp_path):
    # Fresh clone: data/ is gitignored, so it doesn't exist yet.
    import csv
    path = tmp_path / "data" / "run.csv"
    assert not path.parent.exists()
    rows = [{"timestamp": 1.0, "util_pct": 90.0, "workload_class": "cpu_bound"},
            {"timestamp": 2.0, "util_pct": 10.0, "workload_class": "idle"}]
    log_csv(path, rows, extra_cols=("workload_class",))
    with open(path, newline="") as f:
        written = list(csv.reader(f))
    assert written[0] == ["timestamp", *SIGNALS, "workload_class"]
    assert len(written) == 3  # header + 2 rows
    assert written[1][0] == "1.0" and written[1][-1] == "cpu_bound"


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
    assert estimate_power_w(0, 3000) == STATIC_W  # static floor only


def test_synthetic_matches_ground_truth():
    # The rules must reproduce the label the generator was asked for. This checks
    # the rules against INVENTED signals, so it proves the wiring, not the
    # thresholds - those still need real stress-ng traces (PRD S8.3).
    plan = [("cpu", 4), ("io", 4), ("idle", 4), ("mixed", 4)]
    setter = SimulatedSetter([1000, 2000, 3000, 4000])
    rows = list(run(synth(plan, seed=1), setter, Policy(setter.freqs, k=3)))
    expect = {"cpu": CPU_BOUND, "io": IO_BOUND, "idle": IDLE, "mixed": MIXED}
    assert len(rows) == 16
    for r in rows:
        assert r["workload_class"] == expect[r["expected"]], r


def test_hysteresis_suppresses_a_blip():
    # A 2-tick I/O blip inside a CPU-bound run must not move the frequency at
    # all when k=3. This is the anti-thrashing claim, tested end to end.
    plan = [("cpu", 8), ("io", 2), ("cpu", 8)]
    setter = SimulatedSetter([1000, 2000, 3000, 4000])
    list(run(synth(plan, seed=2), setter, Policy(setter.freqs, k=3)))
    assert setter.writes == 0, f"thrashed {setter.writes} times on a 2-tick blip"
    # Same trace with no hysteresis does thrash - proving the test has teeth.
    naive = SimulatedSetter([1000, 2000, 3000, 4000])
    list(run(synth(plan, seed=2), naive, Policy(naive.freqs, k=1)))
    assert naive.writes >= 2, naive.writes


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
