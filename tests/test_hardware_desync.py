"""Regression test for a real bug found during review (not by these tests
originally): SysfsSetter.set() was made to self-verify and return the
frequency that actually landed, but governor.run() logged the REQUESTED
frequency and never told the policy object its own belief was wrong.

Fully testable off-Linux with a fake setter that clamps - same pattern as
SimulatedSetter, just with a ceiling. No VM needed to catch this class of bug,
only to make it actually occur on real hardware.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governor import run
from monitor.synthetic import source as synth
from policy.governor_policy import Policy


class ClampingSetter:
    """Like SimulatedSetter, but silently refuses to go above clamp_to -
    reproduces the Outcome-A-partial-failure case (hardware accepts the write
    syscall but doesn't reach the requested frequency).
    """
    def __init__(self, available_khz, clamp_to):
        self.freqs = sorted(available_khz)
        self.current = self.freqs[-1]
        self.clamp_to = clamp_to
        self.writes = 0

    def set(self, khz):
        actual = min(khz, self.clamp_to)
        if actual != self.current:
            self.writes += 1
        self.current = actual
        return actual


def test_run_logs_the_frequency_that_actually_landed():
    freqs = [1_000_000, 2_000_000, 3_000_000, 4_000_000]
    setter = ClampingSetter(freqs, clamp_to=2_000_000)
    plan = [("cpu", 5)]  # policy wants max (4MHz) once hysteresis settles
    rows = list(run(synth(plan, seed=1), setter, Policy(freqs, k=1)))

    assert rows[0]["requested_khz"] == 4_000_000, \
        "on the first tick the policy should genuinely ask for its true target"
    assert all(r["target_khz"] == 2_000_000 for r in rows), \
        "target_khz (the log's main column) must reflect what hardware did, not the ask"


def test_known_limitation_policy_stops_retrying_after_a_clamp():
    # This documents a known gap, not a fix. After a clamped write, Policy's
    # own hysteresis guard (cls == self.stable_class -> "nothing to do")
    # trusts self.current as proof the stable class's target was reached.
    # Resyncing self.current to the clamped value (tried and reverted - see
    # governor.py's comment) makes the policy silently give up on ever
    # re-requesting the true target for as long as the class stays stable.
    # That's arguably worse than not resyncing at all, so NEITHER is done
    # here: policy.current keeps believing the ORIGINAL request succeeded,
    # and every subsequent tick of the same class keeps re-requesting it
    # unchanged (visible below: requested_khz stays 4MHz throughout, not just
    # on tick 0) - not from the policy noticing the failure and retrying, but
    # because it truly still doesn't know the write failed.
    freqs = [1_000_000, 2_000_000, 3_000_000, 4_000_000]
    setter = ClampingSetter(freqs, clamp_to=2_000_000)
    policy = Policy(freqs, k=1)
    rows = list(run(synth([("cpu", 4)], seed=1), setter, policy))

    assert all(r["requested_khz"] == 4_000_000 for r in rows), rows
    assert all(r["target_khz"] == 2_000_000 for r in rows), rows
    assert policy.current == 4_000_000, (
        "policy still believes 4MHz landed - this is the known gap. "
        "A correct fix needs Policy to separately track its own INTENDED "
        "target for the stable class vs. hardware's LAST CONFIRMED frequency; "
        "today it conflates the two in self.current. Worth resolving once "
        "Phase 0 shows whether Outcome A partial-clamping actually occurs."
    )


def test_no_desync_when_hardware_is_well_behaved():
    # Sanity check: the fix must not change behaviour on hardware that never
    # clamps (i.e. every SimulatedSetter-driven test that already passed).
    freqs = [1_000_000, 2_000_000, 3_000_000, 4_000_000]
    setter = ClampingSetter(freqs, clamp_to=4_000_000)  # never actually clamps
    policy = Policy(freqs, k=1)
    rows = list(run(synth([("cpu", 3)], seed=1), setter, policy))
    assert all(r["target_khz"] == r["requested_khz"] for r in rows)
    assert policy.current == 4_000_000


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn(); print("ok", name)
