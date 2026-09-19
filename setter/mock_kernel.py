"""A fake cpufreq "kernel" behind ./mock_sysfs/. DEV/TESTING SCAFFOLDING ONLY.

The tree mirrors /sys/devices/system/cpu/cpuN/cpufreq/ file for file, so the
mock and real backends differ only in their root. Plain files can't react to
writes, so MockBackend routes writes through kernel_write(), which does what
the cpufreq core does: reject bad values (EINVAL), refuse read-only attributes
(EACCES), clamp to [scaling_min_freq, scaling_max_freq], snap to a table entry,
and apply scaling_setspeed under the userspace governor.

Run as a loop to play the in-kernel governors too (ondemand & co. follow load):

    python -m setter.mock_kernel --load 100    # simulated CPU-bound
    python -m setter.mock_kernel --load 0      # simulated idle
    python -m setter.mock_kernel               # follow this machine's real /proc/stat

The frequency table is hardware_profile.RYZEN_7840HS_LADDER_KHZ, the same ladder
the setter falls back to. It is still a model: the real part under amd-pstate
exposes no scaling_available_frequencies at all.
"""
import argparse
import errno
import os
import time

from hardware_profile import RYZEN_7840HS_LADDER_KHZ

DEFAULT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "mock_sysfs")
NCPU = 4  # the dev VM's vCPU count
FREQS_KHZ = RYZEN_7840HS_LADDER_KHZ
GOVERNORS = ("performance", "powersave", "userspace", "ondemand", "conservative", "schedutil")
LOAD_FOLLOWING = ("ondemand", "conservative", "schedutil")
WRITABLE = ("scaling_governor", "scaling_setspeed", "scaling_min_freq", "scaling_max_freq")
UP_THRESHOLD = 80  # ondemand's default: at or above this, head for max


def _get(d, attr):
    with open(os.path.join(d, attr)) as f:
        return f.read().strip()


def _put(d, attr, value):
    with open(os.path.join(d, attr), "w") as f:
        f.write(f"{value}\n")


def create(root=DEFAULT_ROOT, ncpu=NCPU, start_khz=FREQS_KHZ[1]):
    """(Re)build the tree. Overwrites any existing state."""
    for n in range(ncpu):
        d = os.path.join(root, f"cpu{n}", "cpufreq")
        os.makedirs(os.path.join(d, "stats"), exist_ok=True)
        files = {
            "cpuinfo_min_freq": FREQS_KHZ[0], "cpuinfo_max_freq": FREQS_KHZ[-1],
            "scaling_min_freq": FREQS_KHZ[0], "scaling_max_freq": FREQS_KHZ[-1],
            "scaling_cur_freq": start_khz, "scaling_setspeed": start_khz,
            # acpi-cpufreq lists these descending
            "scaling_available_frequencies": " ".join(map(str, reversed(FREQS_KHZ))),
            "scaling_available_governors": " ".join(GOVERNORS),
            "scaling_driver": "acpi-cpufreq",
            # userspace so the daemon can write setspeed straight away; on real
            # hardware you must select it yourself first
            "scaling_governor": "userspace",
            "affected_cpus": n, "related_cpus": n,  # independent frequency domains
            "stats/time_in_state": "\n".join(f"{f} 0" for f in FREQS_KHZ),
        }
        for attr, value in files.items():
            _put(d, attr, value)


def _allowed(d):
    """Table entries inside [scaling_min_freq, scaling_max_freq], ascending."""
    table = sorted(int(f) for f in _get(d, "scaling_available_frequencies").split())
    lo, hi = int(_get(d, "scaling_min_freq")), int(_get(d, "scaling_max_freq"))
    return [f for f in table if lo <= f <= hi] or [table[0]]


def _snap(ok, khz):
    """Lowest allowed frequency >= khz, like CPUFREQ_RELATION_L."""
    return next((f for f in ok if f >= khz), ok[-1])


def _account(d):
    """Credit time since the last update to the current frequency, in the
    kernel's 10 ms units. The file's mtime IS the last-update time."""
    p = os.path.join(d, "stats", "time_in_state")
    last = os.path.getmtime(p)
    ticks = int((time.time() - last) * 100)
    if ticks <= 0:
        return
    cur = _get(d, "scaling_cur_freq")
    rows = [line.split() for line in _get(d, "stats/time_in_state").splitlines()]
    _put(d, "stats/time_in_state",
         "\n".join(f"{f} {int(t) + ticks if f == cur else t}" for f, t in rows))
    os.utime(p, (last + ticks / 100,) * 2)  # carry the sub-10ms remainder forward


def _set_cur(d, khz):
    _account(d)  # old frequency gets the time up to now
    _put(d, "scaling_cur_freq", khz)


def _settle(d):
    """Re-evaluate scaling_cur_freq after any policy change, as the kernel does."""
    ok = _allowed(d)
    gov = _get(d, "scaling_governor")
    target = {"performance": ok[-1], "powersave": ok[0],
              "userspace": int(_get(d, "scaling_setspeed"))}.get(gov, int(_get(d, "scaling_cur_freq")))
    _set_cur(d, _snap(ok, target))


def kernel_write(d, attr, value):
    """Write one attribute of the cpufreq dir d, with real sysfs semantics."""
    path, value = os.path.join(d, attr), str(value).strip()
    if attr not in WRITABLE:
        raise PermissionError(errno.EACCES, "read-only in real sysfs", path)
    if attr == "scaling_governor":
        if value not in GOVERNORS:
            raise OSError(errno.EINVAL, f"unknown governor {value!r}", path)
        if value == "userspace":
            _put(d, "scaling_setspeed", _get(d, "scaling_cur_freq"))
    elif not value.isdigit():
        raise OSError(errno.EINVAL, f"not a frequency: {value!r}", path)
    elif attr == "scaling_setspeed" and _get(d, "scaling_governor") != "userspace":
        raise OSError(errno.EINVAL, "scaling_setspeed needs the userspace governor", path)
    _put(d, attr, value)
    _settle(d)


def step(d, load_pct):
    """One tick of the in-kernel governor on cpufreq dir d. Load-following
    governors move ONE table step toward their target per tick."""
    if _get(d, "scaling_governor") not in LOAD_FOLLOWING:
        _account(d)  # nothing to decide, but time_in_state keeps running
        return
    # ponytail: one ondemand-style rule for all three; conservative/schedutil
    # differ in ramp shape, not direction. Model them separately if a baseline needs it.
    ok = _allowed(d)
    cur = _snap(ok, int(_get(d, "scaling_cur_freq")))
    want = ok[-1] if load_pct >= UP_THRESHOLD else _snap(ok, ok[0] + (ok[-1] - ok[0]) * load_pct / 100)
    i, j = ok.index(cur), ok.index(want)
    _set_cur(d, ok[i + (j > i) - (j < i)])


def cpu_dirs(root):
    return sorted(os.path.join(root, n, "cpufreq") for n in os.listdir(root)
                  if n.startswith("cpu") and n[3:].isdigit())


def main():
    ap = argparse.ArgumentParser(description="Run the mock cpufreq kernel (dev only).")
    ap.add_argument("--root", default=os.environ.get("MOCK_SYSFS_ROOT", DEFAULT_ROOT))
    ap.add_argument("--load", type=float, help="fixed load %% (default: real /proc/stat)")
    ap.add_argument("--interval", type=float, default=0.2, help="seconds per tick")
    ap.add_argument("--reset", action="store_true", help="rebuild the tree first")
    args = ap.parse_args()
    if args.load is None and not os.path.exists("/proc/stat"):
        ap.error("no /proc/stat here - pass --load")
    if args.reset or not os.path.isdir(os.path.join(args.root, "cpu0")):
        create(args.root)

    from monitor.reader import compute_signals, read_stat
    prev = read_stat() if args.load is None else None
    while True:
        time.sleep(args.interval)
        load = args.load
        if load is None:
            cur = read_stat()
            sig = compute_signals(prev, cur, args.interval)
            prev, load = cur, (sig["util_pct"] if sig else 0.0)
        dirs = cpu_dirs(args.root)
        for d in dirs:
            step(d, load)
        print(f"load={load:5.1f}%  " + "  ".join(
            f"{_get(d, 'scaling_governor')[:5]}:{int(_get(d, 'scaling_cur_freq')) // 1000}MHz"
            for d in dirs), flush=True)


if __name__ == "__main__":
    main()
