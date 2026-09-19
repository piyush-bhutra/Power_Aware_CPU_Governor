"""The mock cpufreq tree must behave like real sysfs where the governor can tell
the difference - otherwise code that passes here breaks on bare metal."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import setter.freq_setter as fs
from hardware_profile import RYZEN_7840HS_LADDER_KHZ as LADDER
from setter import mock_kernel
from setter.backend import MockBackend
from setter.freq_setter import SysfsSetter


@pytest.fixture
def mock(tmp_path, monkeypatch):
    b = MockBackend(str(tmp_path))
    monkeypatch.setattr(fs, "BACKEND", b)
    return b


def test_real_setter_runs_unmodified_on_the_mock(mock):
    s = SysfsSetter(fs.available_freqs_khz())
    assert s.freqs == list(LADDER)
    assert s.set(LADDER[2]) == LADDER[2]
    assert mock.read(0, "scaling_cur_freq") == str(LADDER[2])
    assert s.ineffective_writes == 0


def test_max_clamp_is_caught_by_self_verification(mock):
    s = SysfsSetter(fs.available_freqs_khz())
    mock.write(0, "scaling_max_freq", LADDER[1])
    assert s.set(LADDER[-1]) == LADDER[1]
    assert s.ineffective_writes == 1


def test_kernel_refusals(mock):
    with pytest.raises(OSError):
        mock.write(0, "scaling_governor", "turbo")
    with pytest.raises(PermissionError):
        mock.write(0, "scaling_cur_freq", 1_000_000)  # read-only on real hardware
    mock.write(0, "scaling_governor", "ondemand")
    with pytest.raises(OSError):
        mock.write(0, "scaling_setspeed", 1_000_000)  # only valid under userspace


def test_static_governors_pin_frequency(mock):
    mock.write(1, "scaling_governor", "performance")
    assert mock.read(1, "scaling_cur_freq") == str(LADDER[-1])
    mock.write(1, "scaling_governor", "powersave")
    assert mock.read(1, "scaling_cur_freq") == str(LADDER[0])
    assert mock.read(0, "scaling_cur_freq") == str(LADDER[1])  # other cpus untouched


def test_ondemand_nudges_toward_max_under_load_and_min_when_idle(mock):
    mock.write(0, "scaling_governor", "ondemand")
    d, seen = mock.path(0, ""), []
    for _ in range(12):
        mock_kernel.step(d, 100)
        seen.append(int(mock.read(0, "scaling_cur_freq")))
    assert seen == sorted(seen) and seen[0] < LADDER[-1] and seen[-1] == LADDER[-1]
    for _ in range(12):
        mock_kernel.step(d, 0)
    assert mock.read(0, "scaling_cur_freq") == str(LADDER[0])


def test_time_in_state_accumulates_at_current_freq(mock):
    d = mock.path(0, "")
    p = os.path.join(d, "stats", "time_in_state")
    t = os.path.getmtime(p) - 1.0
    os.utime(p, (t, t))  # pretend a second has passed at the start frequency
    mock_kernel.step(d, 0)
    table = dict(line.split() for line in mock.read(0, "stats/time_in_state").splitlines())
    assert 100 <= int(table[str(LADDER[1])]) < 150  # + real time since create()
