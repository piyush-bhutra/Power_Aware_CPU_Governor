"""Module 1 - Monitor. Parses /proc/stat, converts cumulative counters to rates.

Parsing is split from file I/O so the logic is testable off-Linux (see tests/).
"""
import csv
import math
import os
import time

# /proc/stat "cpu" line fields, in kernel order (Linux Documentation/filesystems/proc.rst)
CPU_FIELDS = ("user", "nice", "system", "idle", "iowait", "irq",
              "softirq", "steal", "guest", "guest_nice")

# Signals written to CSV, in order.
SIGNALS = ("util_pct", "iowait_pct", "irq_pct", "ctxt_per_s",
           "procs_running", "procs_blocked", "freq_khz",
           "iowait_over_util", "ctxt_over_run", "elapsed_s",
           "delta_total_jiffies", "iowait_decreased")
RAW_FIELDS = CPU_FIELDS + ("ctxt",)
RAW_COLS = tuple(f"raw_{side}_{field}" for side in ("prev", "cur") for field in RAW_FIELDS)


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
    if not math.isfinite(interval_s) or interval_s <= 0:
        raise ValueError("elapsed interval must be finite and positive")
    # guest and guest_nice are already included in user and nice by Linux.
    d = {f: cur[f] - prev[f] for f in CPU_FIELDS[:8]}
    ctxt_delta = cur["ctxt"] - prev["ctxt"]
    if any(v < 0 for f, v in d.items() if f != "iowait") or ctxt_delta < 0:
        return None  # reset/hotplug anomaly: rebaseline, never emit invalid rates
    iowait_decreased = d["iowait"] < 0
    d["iowait"] = max(0, d["iowait"])  # Linux documents that this counter may decrease
    total = sum(d.values())
    if total <= 0:  # interval too short to tick a jiffy, or counters reset
        return None
    busy = total - d["idle"] - d["iowait"]
    sig = {
        "util_pct": 100.0 * busy / total,
        "iowait_pct": 100.0 * d["iowait"] / total,
        "irq_pct": 100.0 * (d["irq"] + d["softirq"]) / total,
        "ctxt_per_s": ctxt_delta / interval_s,
        "elapsed_s": interval_s,
        "delta_total_jiffies": total,
        "iowait_decreased": iowait_decreased,
        # queue depths are instantaneous gauges, not counters - no delta
        "procs_running": cur["procs_running"],
        "procs_blocked": cur["procs_blocked"],
    }
    # Derived ratio features for the Review II ML classifier only - classify()
    # does not read them. See docs/Research_Paper_Summary.md, paper 4.
    sig["iowait_over_util"] = _safe_ratio(sig["iowait_pct"], sig["util_pct"])
    sig["ctxt_over_run"] = _safe_ratio(sig["ctxt_per_s"], sig["procs_running"])
    return sig


def _safe_ratio(numerator, denominator, cap=1000.0):
    if denominator <= 1e-9:
        return cap if numerator > 0 else 0.0
    return min(numerator / denominator, cap)


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


def sample(interval_s=1.0, count=None, *, observer=None):
    """Yield one signal dict per tick. Runs forever unless count is given."""
    if not math.isfinite(interval_s) or interval_s <= 0:
        raise ValueError("sampling interval must be finite and positive")
    if count is not None and count < 0:
        raise ValueError("sample count must be non-negative")
    prev = read_stat()
    previous_time = time.monotonic()
    if observer:
        observer(dict(event='baseline', monotonic_s=previous_time, raw=prev))
    n = 0
    while count is None or n < count:
        time.sleep(interval_s)
        cur = read_stat()
        now = time.monotonic()
        sig = compute_signals(prev, cur, now - previous_time)
        if observer:
            observer(dict(event='interval', attempt=n+1, elapsed_s=now-previous_time,
                          valid=sig is not None, raw_prev=prev, raw_cur=cur))
        if sig is not None:
            for side, snapshot in (("prev", prev), ("cur", cur)):
                sig.update({f"raw_{side}_{f}": snapshot[f] for f in RAW_FIELDS})
        prev = cur
        previous_time = now
        n += 1
        if sig is None:
            continue
        sig["freq_khz"] = read_freq_khz()
        sig["timestamp"] = time.time()
        yield sig


def log_csv(path, rows, extra_cols=(), *, mode="a"):
    """Append rows to a CSV, writing the header on first use."""
    cols = ("timestamp",) + SIGNALS + RAW_COLS + tuple(extra_cols)
    # data/ is gitignored and absent on a fresh clone. Bare filenames have no
    # parent, and os.makedirs("") raises, hence the guard.
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if mode == "a" and os.path.exists(path) and os.path.getsize(path):
        with open(path, newline="") as existing:
            if next(csv.reader(existing)) != list(cols):
                raise ValueError("CSV header mismatch; use a new output path")
    with open(path, mode, newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if f.tell() == 0:
            w.writeheader()
            f.flush()
        for row in rows:
            w.writerow(row)
            f.flush()  # so a killed run still leaves usable data


if __name__ == "__main__":
    for row in sample(1.0, 5):
        print(row)
