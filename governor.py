"""The control loop: sense -> classify -> decide -> act -> log (PRD S6).

Source-agnostic on purpose. It consumes signal dicts, so the same loop runs on
real /proc counters, on synthetic ones, or on a replayed CSV later.
"""
import argparse

from classifier.rules import classify
from monitor.reader import SIGNALS, log_csv, sample
from policy.governor_policy import Policy
from power_model.estimate import estimate_power_w
from setter.freq_setter import open_setter

EXTRA_COLS = ("workload_class", "target_khz", "est_power_w", "expected")


def run(source, setter, policy):
    """Yield one fully-annotated row per tick."""
    f_max = setter.freqs[-1]
    for sig in source:
        # observed frequency at sample time, i.e. before this tick acts
        sig.setdefault("freq_khz", setter.current)
        cls = classify(sig)
        target = policy.decide(cls)
        setter.set(target)
        yield {**sig, "workload_class": cls, "target_khz": target,
               # estimated / modelled - never measured. See docs/power_model.md
               "est_power_w": round(estimate_power_w(target, f_max, sig["util_pct"]), 3)}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--synthetic", action="store_true",
                    help="run on invented signals instead of /proc (no VM needed)")
    ap.add_argument("--interval", type=float, default=1.0, help="seconds per tick")
    ap.add_argument("--ticks", type=int, help="stop after N ticks (default: forever)")
    ap.add_argument("--k", type=int, default=3, help="hysteresis: ticks before acting")
    ap.add_argument("--csv", help="append the log here")
    args = ap.parse_args()

    setter, is_real = open_setter()
    if args.synthetic:
        from monitor.synthetic import source as synth
        plan = [("cpu", 5), ("io", 5), ("idle", 3), ("mixed", 4), ("cpu", 3)]
        src = synth(plan, args.interval)
    else:
        src = sample(args.interval, args.ticks)

    print(f"setter: {type(setter).__name__} ({'REAL' if is_real else 'SIMULATED'}), "
          f"freqs={setter.freqs}, k={args.k}")
    rows = run(src, setter, Policy(setter.freqs, k=args.k))
    if args.csv:
        log_csv(args.csv, rows, EXTRA_COLS)
        return
    for row in rows:
        print(f"{row['workload_class']:>9}  util={row['util_pct']:5.1f}%  "
              f"iowait={row['iowait_pct']:5.1f}%  ctxt={row['ctxt_per_s']:8.0f}/s  "
              f"blk={row['procs_blocked']}  -> {row['target_khz']:>8} kHz  "
              f"~{row['est_power_w']:5.2f} W (est)")


if __name__ == "__main__":
    main()
