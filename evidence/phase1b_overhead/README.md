# Phase 1B governor self-overhead run (Ubuntu VM)

**Scope: MEASURED process CPU time of the governor loop inside a VirtualBox VM.**
Frequency control was simulated (no hardware writes). Nothing here is electrical
power or energy.

Produced by `.venv/bin/python -m benchmark.overhead` at commit f47e288 on 2026-10-19,
on the Ubuntu VM (VirtualBox guest on a Ryzen 7 7840HS laptop). The run took about
27 minutes. Original output folder: `data/overhead-20261019T091947Z`. The two CSV files
reached the Windows checkout with `.xls` appended to their names during transfer; their
contents are plain CSV and are archived under their original names (details in
`PROVENANCE.json`). `SHA256SUMS` covers the three outputs and `PROVENANCE.json` (not
this README or itself); the folder is `-text` in `.gitattributes`, so bytes match on
every checkout. Verify:

```bash
cd evidence/phase1b_overhead && sha256sum -c SHA256SUMS
```

`tests/test_overhead_evidence.py` also checks that `overhead_net.csv` recomputes from
`overhead_runs.csv` and that `overhead_summary.md` regenerates byte-identically from it.

## Plan

Intervals 0.5, 1, 2 and 5 s; 60 s of ticks per run; 3 repetitions; each run once with
the real governor pipeline (read /proc/stat, compute signals, classify, Policy,
SimulatedSetter) and once with a sleep-only control. **24 runs ok, 0 failed.**

## Results (net = governor minus control; median [min, max] over 3 repetitions)

| Interval | Net CPU ms per tick (mean) | Net CPU % of one core (derived) | Net CPU-s per hour (derived) |
|---|---|---|---|
| 0.5 s | 0.5988 [0.5554, 0.6218] | 0.1198 [0.1111, 0.1244] | 4.312 [3.999, 4.477] |
| 1 s | 0.6168 [0.5390, 0.6694] | 0.0617 [0.0539, 0.0669] | 2.221 [1.940, 2.410] |
| 2 s | 0.5483 [0.4642, 0.5703] | 0.0274 [0.0232, 0.0285] | 0.987 [0.836, 1.027] |
| 5 s | 0.5861 [0.4591, 0.5964] | 0.0117 [0.0092, 0.0119] | 0.422 [0.331, 0.429] |

Governor resident memory: median 17,712 to 17,716 KiB (about 17.3 MiB), the same as the
control loop. Net wake-ups per second (voluntary context switches): medians between
-0.180 and 0.001, i.e. no measurable difference from the control.

## VM timer overshoot (actual / planned elapsed time, median [min, max])

| Interval | Governor | Control |
|---|---|---|
| 0.5 s | 1.5718 [1.0529, 1.7161] | 1.0845 [1.0445, 1.3772] |
| 1 s | 1.0397 [1.0117, 1.3459] | 1.0217 [1.0156, 1.0373] |
| 2 s | 1.0164 [1.0073, 1.0479] | 1.0280 [1.0181, 1.0321] |
| 5 s | 1.0014 [1.0011, 1.0031] | 1.0014 [1.0013, 1.0529] |

Single sleeps overshot by up to 3.21 s (maximum per-tick overshoot 3210 ms in a 0.5 s
governor run). The 5 s runs have only 12 ticks each. Full per-tick figures are in
`overhead_summary.md`.

## Limits on interpretation

- Process CPU time, not electrical power or energy.
- Measured inside a VM; native hardware is untested.
- Excludes CSV logging and terminal/dashboard rendering.
- Derived percentages assume the nominal tick rate; because ticks ran late, they are
  upper bounds.
- The /proc/self/stat columns are quantized to the 10 ms kernel clock.
- No hash was recorded on the VM before transfer; integrity is established by the
  internal consistency checks above, not by an end-to-end hash.
