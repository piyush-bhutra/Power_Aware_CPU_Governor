"""Where cpufreq attributes live - the one thing that differs between the dev VM and bare metal.

    CPUFREQ_BACKEND=real  (default) /sys/devices/system/cpu/cpuN/cpufreq/
    CPUFREQ_BACKEND=mock            ./mock_sysfs/cpuN/cpufreq/  - dev/testing only, see docs/mock_sysfs.md

Everything above this (setter, monitor, governor) calls BACKEND.read/write and
never builds a path itself, so the same code runs unmodified on either.
"""
import os

REAL_ROOT = "/sys/devices/system/cpu"


class RealBackend:
    name = "real"

    def __init__(self, root=REAL_ROOT):
        self.root = root

    def path(self, cpu, attr):
        return os.path.join(self.root, f"cpu{cpu}", "cpufreq", attr)

    def read(self, cpu, attr):
        with open(self.path(cpu, attr)) as f:
            return f.read().strip()

    def write(self, cpu, attr, value):
        with open(self.path(cpu, attr), "w") as f:
            f.write(str(value))


class MockBackend(RealBackend):
    """Same layout under another root. Reads are plain file reads; writes go
    through mock_kernel so they get the side effects real sysfs has (EINVAL,
    clamping, setspeed -> scaling_cur_freq)."""
    name = "mock"

    def __init__(self, root=None):
        from setter import mock_kernel
        self._kernel = mock_kernel
        super().__init__(root or os.environ.get("MOCK_SYSFS_ROOT", mock_kernel.DEFAULT_ROOT))
        if not os.path.isdir(os.path.join(self.root, "cpu0")):
            mock_kernel.create(self.root)

    def write(self, cpu, attr, value):
        self._kernel.kernel_write(self.path(cpu, ""), attr, value)


def get_backend(name=None):
    name = name or os.environ.get("CPUFREQ_BACKEND", "real")
    if name == "real":
        return RealBackend()
    if name == "mock":
        return MockBackend()
    raise ValueError(f"CPUFREQ_BACKEND must be 'real' or 'mock', got {name!r}")


BACKEND = get_backend()
