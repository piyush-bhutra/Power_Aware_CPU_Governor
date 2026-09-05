"""Module 2 - Rule-based workload classifier.

THRESHOLDS ARE PLACEHOLDERS. They are guesses until Phase 2 tunes them against
recorded stress-ng runs; every final value must be justified in docs/thresholds.md
with the data that produced it.
"""

CPU_BOUND, IO_BOUND, IDLE, MIXED = "cpu_bound", "io_bound", "idle", "mixed"

THRESHOLDS = {
    "util_high": 70.0,      # above this, the core is genuinely computing
    "util_idle": 10.0,      # below this with no iowait, nothing is happening
    "iowait_high": 20.0,    # above this, a device is the bottleneck
    "ctxt_high": 2000.0,    # switches/sec typical of short I/O-blocked bursts
}


def classify(sig, th=THRESHOLDS):
    """Signal dict (from monitor.compute_signals) -> workload class."""
    util, iowait = sig["util_pct"], sig["iowait_pct"]
    blocked, ctxt = sig["procs_blocked"], sig["ctxt_per_s"]

    # I/O first: an I/O-bound burst can show high util, so util alone misleads.
    if iowait >= th["iowait_high"] or (blocked > 0 and ctxt >= th["ctxt_high"]):
        return IO_BOUND
    if util >= th["util_high"] and blocked == 0:
        return CPU_BOUND
    if util < th["util_idle"] and sig["procs_running"] <= 1:
        return IDLE
    return MIXED
