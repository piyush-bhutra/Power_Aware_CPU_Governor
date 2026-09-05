"""Run our governor and every stock baseline over the SAME trace.

This is the only way to test the project's core claim (PRD S17: "Policy engine
demonstrably behaves differently from ondemand") - everything else in the repo
tests our own governor in isolation.
"""
from benchmark.baselines import BASELINES
from governor import run
from policy.governor_policy import Policy
from setter.freq_setter import SimulatedSetter


def run_comparison(source_factory, available_khz, k=3, ramp_down_step=None):
    """source_factory: a zero-arg callable returning a FRESH iterator each call.

    Must be a factory, not a shared generator - every governor needs to replay
    the identical trace from tick 0, and a generator can only be consumed once.
    monitor.synthetic.source(plan, seed=N) is deterministic for a fixed seed,
    so `lambda: synth(plan, seed=N)` is exactly this.

    Returns {governor_name: rows}, always including "ours" alongside every
    entry in benchmark.baselines.BASELINES.
    """
    results = {}

    for name, cls in BASELINES.items():
        setter = SimulatedSetter(available_khz)
        results[name] = list(run(source_factory(), setter, cls(available_khz)))

    ours_setter = SimulatedSetter(available_khz)
    ours_policy = Policy(available_khz, k=k, ramp_down_step=ramp_down_step)
    results["ours"] = list(run(source_factory(), ours_setter, ours_policy))

    return results


if __name__ == "__main__":
    from monitor.synthetic import source as synth
    from benchmark.summarize import compare_table

    plan = [("cpu", 10), ("io", 10), ("idle", 6), ("mixed", 8)]
    freqs = [1_000_000, 1_800_000, 2_600_000, 3_400_000]

    results = run_comparison(lambda: synth(plan, seed=7), freqs)
    compare_table(results)
