"""Stock-governor baselines for direct comparison against our workload-aware Policy.

Each class exposes step(sig) -> khz, identical to policy.governor_policy.Policy.
governor.run() and benchmark/compare.py drive them all through the same loop,
so "ours vs ondemand" is a real head-to-head on identical input, not a
reimplementation with different plumbing.

None of these read workload_class. That's the point: they're deliberately
naive about *why* the CPU is busy, reacting to util_pct alone (ondemand,
conservative) or nothing at all (performance, powersave) - the exact blind
spot this project's classifier addresses (PRD S2). Thresholds mirror the
Linux kernel's own defaults where documented (Documentation/cpu-freq/governors.txt).
"""


class Performance:
    """Always max. The performance ceiling - zero power-saving by design."""

    def __init__(self, available_khz):
        self.freqs = sorted(available_khz)
        self.current = self.freqs[-1]

    def step(self, sig):
        self.current = self.freqs[-1]
        return self.current


class Powersave:
    """Always min. The power floor - worst-case completion time by design."""

    def __init__(self, available_khz):
        self.freqs = sorted(available_khz)
        self.current = self.freqs[0]

    def step(self, sig):
        self.current = self.freqs[0]
        return self.current


class Ondemand:
    """Mirrors the kernel's ondemand: jump to max once utilisation crosses
    up_threshold (kernel default 80%), otherwise scale down roughly
    proportionally to utilisation. Reacts to util_pct alone - the same signal
    an I/O-bound burst can spike, which is exactly the failure mode our
    classifier is built to catch (PRD S2).
    """

    def __init__(self, available_khz, up_threshold=80.0):
        self.freqs = sorted(available_khz)
        self.up_threshold = up_threshold
        self.current = self.freqs[0]

    def step(self, sig):
        util = sig["util_pct"]
        if util >= self.up_threshold:
            self.current = self.freqs[-1]
        else:
            i = round((util / 100.0) * (len(self.freqs) - 1))
            self.current = self.freqs[i]
        return self.current


class Conservative:
    """Like ondemand but steps one increment per tick instead of jumping to
    max - the kernel's conservative governor avoids performance's abruptness.
    """

    def __init__(self, available_khz, up_threshold=80.0, down_threshold=20.0):
        self.freqs = sorted(available_khz)
        self.up_threshold = up_threshold
        self.down_threshold = down_threshold
        self.current = self.freqs[0]

    def step(self, sig):
        util = sig["util_pct"]
        i = self.freqs.index(self.current)
        if util >= self.up_threshold and i < len(self.freqs) - 1:
            i += 1
        elif util <= self.down_threshold and i > 0:
            i -= 1
        self.current = self.freqs[i]
        return self.current


BASELINES = {
    "performance": Performance,
    "powersave": Powersave,
    "ondemand": Ondemand,
    "conservative": Conservative,
}
