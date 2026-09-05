"""SysfsSetter's actual sysfs I/O can't be tested off-Linux (no /sys to read).
What CAN be tested here, with a fake in-memory 'hardware': the self-verification
logic in set() - does it correctly detect when a write didn't land? That's the
Outcome B silent-no-op symptom (PRD S5), and it's pure Python logic once the
file I/O is faked out.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import setter.freq_setter as fs
from setter.freq_setter import SysfsSetter


class FakeHardware:
    """Stands in for a real cpufreq sysfs tree. clamp_to, if set, simulates a
    hypervisor that silently refuses to move past some frequency - the exact
    partial-Outcome-B case a one-time init check wouldn't catch.
    """
    def __init__(self, start_khz, clamp_to=None):
        self.cur = start_khz
        self.clamp_to = clamp_to

    def read(self, cpu, attr):
        assert attr == "scaling_cur_freq"
        return str(self.cur)

    def write(self, cpu, attr, value):
        assert attr == "scaling_setspeed"
        # Simulate a write that's silently ignored past the clamp.
        if self.clamp_to is not None and int(value) > self.clamp_to:
            return
        self.cur = int(value)


def _patch(monkeypatch, hw):
    monkeypatch.setattr(fs, "_read", hw.read)
    monkeypatch.setattr(fs, "_write", hw.write)


def test_set_reports_the_frequency_that_actually_landed(monkeypatch):
    hw = FakeHardware(start_khz=1_000_000)
    _patch(monkeypatch, hw)
    s = SysfsSetter([1_000_000, 2_000_000, 3_000_000])
    result = s.set(2_000_000)
    assert result == 2_000_000
    assert s.current == 2_000_000
    assert s.ineffective_writes == 0


def test_set_detects_a_silent_no_op(monkeypatch):
    # Hypervisor accepts the write syscall but the frequency never moves past
    # 1.5MHz - exactly the Outcome B failure mode this check exists to catch.
    hw = FakeHardware(start_khz=1_000_000, clamp_to=1_500_000)
    _patch(monkeypatch, hw)
    s = SysfsSetter([1_000_000, 2_000_000, 3_000_000])

    result = s.set(3_000_000)
    assert result == 1_000_000, "should report what the hardware actually did, not the request"
    assert s.current == 1_000_000
    assert s.ineffective_writes == 1

    # A second ineffective write increments the counter again.
    s.set(3_000_000)
    assert s.ineffective_writes == 2


if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-v"]))
