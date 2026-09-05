"""Module 3 - Policy engine. Class -> target frequency, with hysteresis.

Hysteresis is the mitigation for frequency thrashing (PRD S12): a class must
persist for K consecutive ticks before the frequency changes.
"""
from classifier.rules import CPU_BOUND, IO_BOUND, IDLE, MIXED, classify

# Fraction of the available frequency range each class targets.
TARGET = {CPU_BOUND: 1.0, MIXED: 0.6, IO_BOUND: 0.3, IDLE: 0.0}


class Policy:
    def __init__(self, available_khz, k=3, ramp_down_step=None):
        """available_khz: sorted ascending list from scaling_available_frequencies.

        ramp_down_step: max steps to drop per decision (asymmetric response -
        ramp up instantly to protect performance, down gradually). None = jump.
        """
        self.freqs = sorted(available_khz)
        self.k = k
        self.ramp_down_step = ramp_down_step
        self.current = self.freqs[-1]
        self._pending = None
        self._streak = 0
        self.stable_class = None

    def _target_freq(self, cls):
        i = round(TARGET[cls] * (len(self.freqs) - 1))
        return self.freqs[i]

    def decide(self, cls):
        """Feed one tick's classification, get the frequency to set."""
        if cls == self._pending:
            self._streak += 1
        else:
            self._pending, self._streak = cls, 1

        if self._streak < self.k or cls == self.stable_class:
            return self.current

        self.stable_class = cls
        target = self._target_freq(cls)
        if self.ramp_down_step and target < self.current:
            i = self.freqs.index(self.current)
            target = max(target, self.freqs[max(0, i - self.ramp_down_step)])
        self.current = target
        return self.current

    def step(self, sig):
        """Uniform entrypoint shared with benchmark.baselines: every governor
        exposes step(sig) -> khz, so governor.run() and the benchmark harness
        can swap policies without knowing which one they're driving.

        Classifies internally, then defers to decide(cls) - the K-tick
        hysteresis logic stays exactly as tested in isolation above; this is
        purely a thin adapter, not a behaviour change.
        """
        return self.decide(classify(sig))
