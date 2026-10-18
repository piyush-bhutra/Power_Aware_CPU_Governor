"""Module 3 - Policy engine. Class -> target frequency, with hysteresis.

Hysteresis is the mitigation for frequency thrashing (PRD S12): a class must
persist for K consecutive ticks before the frequency changes.
"""
from bisect import bisect_right

from classifier.rules import CPU_BOUND, IO_BOUND, IDLE, MIXED, classify

# Fraction of the available frequency range each class targets.
TARGET = {CPU_BOUND: 1.0, MIXED: 0.6, IO_BOUND: 0.3, IDLE: 0.0}


def _positive_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f'{name} must be an integer >= 1, got {value!r}')


class Policy:
    def __init__(self, available_khz, k=3, ramp_down_step=None):
        """available_khz: strictly ascending ladder, e.g. scaling_available_frequencies.

        ramp_down_step: max steps to drop per decision (asymmetric response -
        ramp up instantly to protect performance, down gradually). None = jump.
        """
        freqs = list(available_khz)
        if not freqs:
            raise ValueError('frequency ladder must not be empty')
        if any(isinstance(f, bool) or not isinstance(f, (int, float)) or not f > 0 for f in freqs):
            raise ValueError(f'frequency ladder must contain positive numbers, got {freqs!r}')
        if any(a >= b for a, b in zip(freqs, freqs[1:])):
            raise ValueError(f'frequency ladder must be strictly ascending, got {freqs!r}')
        _positive_int(k, 'k')
        if ramp_down_step is not None:
            _positive_int(ramp_down_step, 'ramp_down_step')
        self.freqs = freqs
        self.k = k
        self.ramp_down_step = ramp_down_step
        self.current = self.freqs[-1]
        self._pending = None
        self._streak = 0
        self.stable_class = None
        # Intended frequency for the stable class, kept apart from self.current
        # (last applied/confirmed). Ramp-down and clamp resync both rely on this.
        self._goal = None

    def _target_freq(self, cls):
        if cls not in TARGET:
            raise ValueError(f'unknown workload class {cls!r}; expected one of {sorted(TARGET)}')
        i = round(TARGET[cls] * (len(self.freqs) - 1))
        return self.freqs[i]

    def decide(self, cls):
        """Feed one tick's classification, get the frequency to set."""
        if cls not in TARGET:
            raise ValueError(f'unknown workload class {cls!r}; expected one of {sorted(TARGET)}')
        if cls == self._pending:
            self._streak += 1
        else:
            self._pending, self._streak = cls, 1

        if self._streak < self.k:
            return self.current
        if cls != self.stable_class:
            self.stable_class = cls
            self._goal = self._target_freq(cls)
        elif self.current == self._goal:
            return self.current

        target = self._goal
        if self.ramp_down_step and target < self.current:
            # Index of the highest ladder step not above current (current may be
            # an off-ladder hardware readback after sync()).
            i = max(0, bisect_right(self.freqs, self.current) - 1)
            target = max(target, self.freqs[max(0, i - self.ramp_down_step)])
        self.current = target
        return self.current

    def sync(self, actual_khz):
        """Record the frequency the setter actually reached (e.g. a hardware clamp).

        The stable-class goal is kept, so later ticks keep requesting it.
        """
        self.current = actual_khz

    def step(self, sig):
        """Uniform entrypoint shared with benchmark.baselines: every governor
        exposes step(sig) -> khz, so governor.run() and the benchmark harness
        can swap policies without knowing which one they're driving.

        Classifies internally, then defers to decide(cls) - the K-tick
        hysteresis logic stays exactly as tested in isolation above; this is
        purely a thin adapter, not a behaviour change.
        """
        return self.decide(classify(sig))
