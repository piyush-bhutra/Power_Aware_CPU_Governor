# Mock cpufreq sysfs — dev/testing scaffolding only

The VirtualBox dev VM has no cpufreq at all (`/sys/devices/system/cpu/cpu0/cpufreq/`
is missing, no driver loaded), so the governor gets a fake tree to run against.

> **Nothing measured on the mock is a result.** The frequency table is
> `RYZEN_7840HS_LADDER_KHZ` from `hardware_profile.py` (a model, not read from
> hardware), switching is instant, and there is no power draw. Final benchmarks
> must run with `CPUFREQ_BACKEND=real` on bare metal.

## Switching backends

| `CPUFREQ_BACKEND` | Root | Use |
|---|---|---|
| `real` (default) | `/sys/devices/system/cpu` | bare metal, final benchmarks |
| `mock` | `./mock_sysfs` (override with `MOCK_SYSFS_ROOT`) | VM / Windows development |

`setter/backend.py` is the only code that knows about paths. The setter, monitor
and governor call `BACKEND.read/write`, so they run unmodified on either backend.

```bash
CPUFREQ_BACKEND=mock .venv/bin/python governor.py --synthetic
```

The tree gets built on first use. It mirrors the real layout file for file:
`mock_sysfs/cpu{0..3}/cpufreq/{scaling_governor, scaling_cur_freq, scaling_setspeed,
scaling_min_freq, scaling_max_freq, scaling_available_frequencies,
scaling_available_governors, scaling_driver, cpuinfo_*_freq, stats/time_in_state}`.
It is gitignored. Rebuild it with `python -m setter.mock_kernel --reset`.

## What behaves like the kernel

Writes through the backend go via `setter/mock_kernel.py`, which gives them
real sysfs semantics:

- Unknown governors and non-numeric frequencies fail with `EINVAL`.
- Writes to `scaling_cur_freq` and other read-only files fail with `EACCES`.
  The governor sets frequency through `scaling_setspeed`, the same as on real hardware.
- `scaling_setspeed` works only under the `userspace` governor (`EINVAL` otherwise).
  The mock starts in `userspace`. On bare metal you must select it yourself.
- Every change is clamped to `[scaling_min_freq, scaling_max_freq]` and snapped to a
  table entry. Lowering `scaling_max_freq` lets you reproduce the partial-clamp case
  that `SysfsSetter`'s write check detects.
- `performance`/`powersave` pin the frequency to max/min, and `stats/time_in_state`
  accumulates in 10 ms units.

Writing the files directly from a shell (`echo … >`) bypasses the checks above.

## Load simulator (optional)

```bash
python -m setter.mock_kernel --load 100   # simulated CPU-bound
python -m setter.mock_kernel --load 0     # simulated idle
python -m setter.mock_kernel              # follow the VM's real /proc/stat (run stress-ng)
```

On each tick, CPUs running `ondemand`/`conservative`/`schedutil` move one P-state
toward max under load (≥80 %), or toward a load-proportional target when load is
lower. All three governors share this one rule. CPUs on the other governors hold
their frequency.

Tests: `tests/test_mock_sysfs.py`.
