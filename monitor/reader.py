"""Module 1 - Monitor. Parses /proc/stat, converts cumulative counters to rates.

Parsing is split from file I/O so the logic is testable off-Linux (see tests/).
"""
import csv
import time

# /proc/stat "cpu" line fields, in kernel order (Linux Documentation/filesystems/proc.rst)
CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq",
              "softirq", "steal", "guest", "guest_nice")

# Signals written to CSV, in order.
SIGNALS = ("util_pct", "iowait_pct", "irq_pct", "ctxt_per_s",
           "procs_running", "procs_blocked", "freq_khz")


def parse_stat(text):
    """/proc/stat text -> raw cumulative counters. Missing trailing fields -> 0."""
    out = {}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        key, vals = parts[0], parts[1:]
        if key == "cpu":  # aggregate line only; per-cpu lines are cpu0, cpu1...
            nums = [int(v) for v in vals] + [0] * len(CPU_FIELDS)
            out.update(zip(CPU_FIELDS, nums))
        elif key in ("ctxt", "procs_running", "procs_blocked", "intr", "btime"):
            out[key] = int(vals[0])
    return out


def compute_signals(prev, cur, interval_s):
    """Difference two parse_stat() snapshots into rates/percentages.

    THE bug this exists to prevent: /proc/stat counters are cumulative since
    boot. Using raw totals makes utilization converge to a constant.
    """
    d = {f: cur[f] - prev[f] for f in CPU_FIELDS}
    total = sum(d.values())
    if total <= 0:  # interval too short to tick a jiffy, or counters reset
        return None
    busy = total - d["idle"] - d["iowait"]
    return {
        "util_pct": 100.0 * busy / total,
        "iowait_pct": 100.0 * d["iowait"] / total,
        "irq_pct": 100.0 * (d["irq"] + d["softirq"]) / total,
        "ctxt_per_s": (cur["ctxt"] - prev["ctxt"]) / interval_s,
        # queue depths are instantaneous gauges, not counters - no delta
        "procs_running": cur["procs_running"],
        "procs_blocked": cur["procs_blocked"],
    }


def read_stat(path="/proc/stat"):
    with open(path) as f:
        return parse_stat(f.read())


def read_freq_khz(cpu=0):
    """Current core frequency, or None when cpufreq is not exposed (VM Outcome B)."""
    try:
        with open(f"/sys/devices/system/cpu/cpu{cpu}/cpufreq/scaling_cur_freq") as f:
            return int(f.read().strip())
    except OSError:
        return None


def sample(interval_s=1.0, count=None):
    """Yield one signal dict per tick. Runs forever unless count is given."""
    prev = read_stat()
    n = 0
    while count is None or n < count:
        time.sleep(interval_s)
        cur = read_stat()
        sig = compute_signals(prev, cur, interval_s)
        prev = cur
        n += 1
        if sig is None:
            continue
        sig["freq_khz"] = read_freq_khz()
        sig["timestamp"] = time.time()
        yield sig


def log_csv(path, rows, extra_cols=()):
    """Append rows to a CSV, writing the header on first use."""
    cols = ("timestamp",) + SIGNALS + tuple(extra_cols)
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if f.tell() == 0:
            w.writeheader()
        for row in rows:
            w.writerow(row)
            f.flush()  # so a killed run still leaves usable data


if __name__ == "__main__":
    for row in sample(1.0, 5):
        print(row)
