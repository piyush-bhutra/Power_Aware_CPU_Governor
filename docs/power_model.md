# Power estimation model

**All figures produced by this model are ESTIMATED / MODELLED. Nothing is measured.**
No wattmeter, no RAPL counters, no physical instrumentation. Every chart axis,
table header, and report sentence using these numbers must say so.

## Formula

Dynamic power in CMOS logic:

    P_dyn = a * C * V^2 * f

Over a DVFS operating range the supply voltage V tracks frequency f roughly
linearly, so substituting V ∝ f gives P_dyn ∝ f^3. Adding a constant static
(leakage) term, and scaling the dynamic term by utilisation:

    P(f) = P_static + P_dyn_max * (f / f_max)^3 * (util / 100)

Implemented in [`power_model/estimate.py`](../power_model/estimate.py).

## Constants — assumptions, not measurements

| Constant | Value | Basis |
|---|---|---|
| `STATIC_W` | 2.0 W | placeholder; set from a cited TDP breakdown for the host CPU |
| `DYNAMIC_W_AT_FMAX` | 13.0 W | placeholder; set so P(f_max, 100%) ≈ host CPU TDP |

**TODO before Review II:** replace both with values derived from the host CPU's
published TDP and cite the source. Cite a textbook/paper for the V ∝ f and
P ∝ f^3 relations (e.g. a standard CMOS low-power design text) — required for
the ≥15 MLA references.

## Stated limitations

- Voltage is not read; the linear V–f relation is assumed, not verified.
- Ignores memory, uncore, and platform power entirely — CPU core only.
- Utilisation scaling is linear, which is a simplification.
- Running in a VM, the guest's view of frequency may not reflect host silicon.
