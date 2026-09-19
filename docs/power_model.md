# Power estimation model

Everything in this document and in power_model/estimate.py is ESTIMATED,
never measured. No physical wattage instrumentation exists in this
project (PRD S4).

## Source formula

Standard CMOS dynamic power model, cited from "Power Management
Techniques for Data Centers: A Survey" (arXiv:1404.6681), Equation (1),
which states the TOTAL power relation as:

P = P_static + C·F·V²

where C is the capacitance of the transistor gates, F is the operating
frequency, and V is the supply voltage - this is the paper's own
notation, confirmed directly against the source text.

For the derivation below, we label the second (frequency/voltage-
dependent) term P_dyn = C·F·V² ourselves - this label is ours, not the
paper's; the paper states the additive total, not a separately-named
dynamic term.

estimate.py's own docstring writes this dynamic term with an explicit
activity factor: P_dyn = a · C · V² · F, where `a` is the activity factor
(the fraction of gates that actually switch per clock cycle, 0 < a <= 1).
The survey's form implicitly folds `a` into C, or treats a=1. Both reduce
to the same F^3 scaling once V is substituted with a term proportional to
F (below) - a presentational difference, not two different physics
assumptions, stated explicitly here so it doesn't read as a contradiction
next to Research_Paper_Summary.md, which quotes the same paper's full
P = P_static + C·F·V² form.

## Derivation of the cubic form actually implemented

Supply voltage V must scale with frequency F to maintain circuit
stability at higher clock speeds - approximately linearly across a
typical DVFS range: V ~= k · F for some constant k.

Substituting into either form of the CMOS formula:

P_dyn = a·C · F · (k·F)^2 = a·C·k^2 · F^3

So P_dyn is proportional to F^3 regardless of which form you start from.
This is the (f / f_max)^3 term in estimate_power_w().

## Full model as implemented

P = P_static + P_dyn_at_fmax · (f / f_max)^3 · (util_pct / 100)

- P_static (frequency-independent power) and P_dyn_at_fmax (dynamic power
  at max frequency) are the STATIC_W and DYNAMIC_W_AT_FMAX constants in
  power_model/estimate.py. Because the constants are fitted to whole-package
  figures (below), P_static is everything in the package that does not
  scale with f^3 - leakage plus uncore/SoC power - not leakage alone.
- The util_pct scaling term is an additional simplification: it assumes
  dynamic power scales linearly with duty cycle. Reasonable for an
  estimate, not physically exact.

## Constant values - FITTED

| Constant | Value | Status |
|---|---|---|
| STATIC_W | 21.6 W | FITTED - two-point fit to AMD's published figures (below) |
| DYNAMIC_W_AT_FMAX | 32.4 W | FITTED - two-point fit to AMD's published figures (below) |

### Source

AMD's product page for the Ryzen 7 7840HS (the host CPU confirmed by
`lscpu` in docs/vm_feasibility.md) lists: Base Clock 3.8 GHz, Max. Boost
Clock "Up to 5.1 GHz", and both Default TDP and AMD Configurable TDP (cTDP)
as 35-54W. This fit uses the two ends of that published range: 35 W and
54 W.

### Derivation

Two published operating points, two unknowns, no invented ratio:

    P(5.1 GHz) = STATIC_W + DYNAMIC_W_AT_FMAX                  = 54 W
    P(3.8 GHz) = STATIC_W + DYNAMIC_W_AT_FMAX * (3.8/5.1)^3    = 35 W

(3.8/5.1)^3 = 0.41366, so DYNAMIC_W_AT_FMAX = 19 / (1 - 0.41366) = 32.404 W
and STATIC_W = 54 - 32.404 = 21.596 W, rounded to 32.4 W and 21.6 W. With
the rounded values the model returns 54.0 W at 5.1 GHz and 35.003 W at
3.8 GHz (both at 100% utilisation).

### The one interpretive assumption

The fit reads the 35 W figure as package power at the all-core base clock
(3.8 GHz) and the 54 W figure as package power at the boost clock
(5.1 GHz), both under full load. This is the usual convention, but AMD's
page does not state it: TDP is a thermal design figure, not a
power-at-frequency measurement, and AMD defines 5.1 GHz as a single-core
boost for bursty workloads, not an all-core operating point. The fitted
constants are therefore a modelling choice anchored to published numbers,
not a physical measurement.

A static/dynamic split taken from the leakage literature was also
investigated (Kim et al., "Leakage Current: Moore's Law Meets Static
Power", IEEE Computer, 2003) and rejected: its projections are for planar
pre-FinFET processes and do not apply to the 7840HS's TSMC 4nm FinFET
process.

## Explicit assumptions and limitations

- V∝F is an approximation, not exact for every real CPU/DVFS
  implementation.
- Static power is treated as a constant; real leakage power varies with
  temperature, which is not modelled.
- Memory and other platform power outside the CPU package (RAM, chipset,
  storage) are not modelled - this estimates CPU package power only.
- The model estimates whole-package power for all 8 cores, but the dev VM
  exposes 4 vCPUs and the governor sees only those. Package power is not
  divided by the VM's share of the cores.
- Per-core variation is not modelled - all cores are assumed identical.
- VM-specific limitation, ties directly to the PRD's Outcome A/B split:
  the frequency this project reads and estimates power from is the
  guest's VIEW of frequency. Under Outcome A that's hopefully a real
  hardware value; under Outcome B it comes from the simulated cpufreq
  layer with no physical hardware backing it at all. Either way the power
  number is an estimate; under Outcome B it is one step further removed
  from anything physical, worth stating plainly in the final report
  rather than leaving implicit.
- The simulated frequency floor (3.8 GHz, the base clock) is higher than
  a real Ryzen 7840HS's actual minimum under amd-pstate, which can idle
  below base clock, so any idle/powersave energy savings in this
  project's results will read smaller than a real chip would achieve - a
  deliberate modelling simplification, not a finding.
- TDP read as power at a frequency is a modelling choice, not a physical
  measurement (see "The one interpretive assumption" above).

## Citations

- Formula: "Power Management Techniques for Data Centers: A Survey"
  (arXiv:1404.6681) - see docs/Research_Paper_Summary.md, paper 3, for full
  context.
- Constants: AMD, "AMD Ryzen 7 7840HS" product specifications,
  https://www.amd.com/en/products/processors/laptop/ryzen/7000-series/amd-ryzen-7-7840hs.html
