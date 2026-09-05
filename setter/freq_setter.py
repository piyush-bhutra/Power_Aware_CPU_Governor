"""Module 4 - Frequency setter. Deliberately thin and swappable.

Phase 0 decides which implementation is used; nothing above this line changes
either way. Both classes expose the same two members: set(khz) and current.
"""
import os

CPUFREQ = "/sys/devices/system/cpu/cpu{}/cpufreq/{}"


def _read(cpu, attr):
    with open(CPUFREQ.format(cpu, attr)) as f:
        return f.read().strip()


def available_freqs_khz(cpu=0):
    """Frequencies this core can be set to, ascending.

    Falls back to a synthesised ladder between min and max, because intel_pstate
    exposes no scaling_available_frequencies file at all - only the limits.
    """
    try:
        return sorted(int(v) for v in _read(cpu, "scaling_available_frequencies").split())
    except OSError:
        pass
    lo, hi = int(_read(cpu, "cpuinfo_min_freq")), int(_read(cpu, "cpuinfo_max_freq"))
    return [lo + (hi - lo) * i // 4 for i in range(5)]  # 5 evenly spaced steps


class SimulatedSetter:
    """Outcome B, and the only setter usable off-Linux. Records state, writes nothing."""

    def __init__(self, available_khz):
        self.freqs = sorted(available_khz)
        self.current = self.freqs[-1]
        self.writes = 0

    def set(self, khz):
        if khz != self.current:
            self.writes += 1
        self.current = khz
        return khz


class SysfsSetter:
    """Outcome A. Requires root and the userspace governor already selected."""

    def __init__(self, available_khz, cpus=(0,)):
        self.freqs = sorted(available_khz)
        self.cpus = tuple(cpus)
        self.writes = 0
        self.current = self.read_back()

    def set(self, khz):
        for cpu in self.cpus:
            with open(CPUFREQ.format(cpu, "scaling_setspeed"), "w") as f:
                f.write(str(khz))
        self.writes += 1
        self.current = khz
        return khz

    def read_back(self, cpu=0):
        """Verify the write landed - a silent no-op is exactly the Outcome B symptom."""
        return int(_read(cpu, "scaling_cur_freq"))


def open_setter(cpus=(0,)):
    """Pick a setter by probing the machine. Returns (setter, is_real)."""
    try:
        freqs = available_freqs_khz(cpus[0])
    except OSError:
        return SimulatedSetter([1_000_000, 1_800_000, 2_600_000, 3_400_000]), False
    if os.access(CPUFREQ.format(cpus[0], "scaling_setspeed"), os.W_OK):
        return SysfsSetter(freqs, cpus), True
    return SimulatedSetter(freqs), False
