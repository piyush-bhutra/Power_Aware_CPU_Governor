"""Fake signal source for developing without a VM.

Generates CUMULATIVE counters in /proc/stat's shape and pushes them through the
real compute_signals(), so the delta path is exercised rather than bypassed.

These numbers are invented. They are for wiring up and demoing the pipeline -
never for tuning thresholds or training the classifier. Both of those need real
stress-ng traces (PRD S8.3).
"""
import random

from monitor.reader import CPU_FIELDS, compute_signals

HZ = 100  # kernel jiffies per second per CPU (USER_HZ; verify with getconf CLK_TCK)

# jiffy shares out of 100, plus ctxt/s and the two queue depths
PROFILES = {
    "cpu":   dict(user=92, system=4, idle=3, iowait=1, softirq=0, ctxt=200, run=2, blk=0),
    "io":    dict(user=6, system=10, idle=8, iowait=70, softirq=6, ctxt=9000, run=1, blk=1),
    "idle":  dict(user=1, system=1, idle=98, iowait=0, softirq=0, ctxt=60, run=1, blk=0),
    "mixed": dict(user=45, system=8, idle=25, iowait=12, softirq=10, ctxt=3000, run=2, blk=0),
    # PRD S2's actual motivating case: data arrives, the process briefly parses/
    # copies it (util spikes high), then blocks again waiting for the next chunk.
    # iowait alone (12%) stays under our iowait_high threshold (20%), so this
    # profile only classifies correctly via the second OR clause in classify()
    # (blocked>0 and ctxt_per_s high) - if that clause is ever removed or its
    # threshold raised, this profile is the one that catches the regression.
    # util_pct lands ~83%, which is ALSO above ondemand's up_threshold (80%) -
    # this is the trace that should make ours and ondemand actually diverge,
    # unlike the plain "io" profile above, where both happen to agree.
    "io_burst": dict(user=60, system=15, idle=5, iowait=12, softirq=8, ctxt=8000, run=1, blk=1),
}


def source(plan, interval_s=1.0, ncpu=1, noise=0.1, seed=0):
    """plan: profile names, or (name, ticks) pairs. Yields signal dicts."""
    rng = random.Random(seed)
    t = 0.0  # simulated clock, so a synthetic run is reproducible byte for byte
    counters = {f: 0 for f in CPU_FIELDS}
    counters.update(ctxt=0, procs_running=1, procs_blocked=0)
    prev = dict(counters)

    for item in plan:
        name, ticks = item if isinstance(item, tuple) else (item, 1)
        p = PROFILES[name]
        for _ in range(ticks):
            # jitter the shares, then renormalise so they still sum to the budget
            shares = {k: max(0.0, p[k] * (1 + rng.gauss(0, noise)))
                      for k in ("user", "system", "idle", "iowait", "softirq")}
            budget = HZ * ncpu * interval_s
            scale = budget / sum(shares.values())
            for k, v in shares.items():
                counters[k] += round(v * scale)
            counters["ctxt"] += round(p["ctxt"] * interval_s * (1 + rng.gauss(0, noise)))
            counters["procs_running"] = p["run"]
            counters["procs_blocked"] = p["blk"]

            sig = compute_signals(prev, counters, interval_s)
            prev = dict(counters)
            t += interval_s
            sig["timestamp"] = t
            sig["expected"] = name  # ground-truth label, as stress-ng would give
            yield sig
