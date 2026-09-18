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

- P_static (leakage/idle power) and P_dyn_at_fmax (dynamic power at max
  frequency) are the STATIC_W and DYNAMIC_W_AT_FMAX constants in
  power_model/estimate.py.
- The util_pct scaling term is an additional simplification: it assumes
  dynamic power scales linearly with duty cycle. Reasonable for an
  estimate, not physically exact.

## Current constant values - UNFITTED PLACEHOLDERS

| Constant | Current value | Status |
|---|---|---|
| STATIC_W | 2.0 W | Placeholder. Never fitted to any measured or published figure. |
| DYNAMIC_W_AT_FMAX | 13.0 W | Placeholder. Never fitted to any measured or published figure. |

Both this document and estimate.py's docstring previously implied these
were "fitted" - neither ever was. If asked "fitted to what?" in a viva,
the honest answer today is: nothing yet, pending Phase 4.

### What "fitting" these should actually mean

Once Phase 0 reports the VM's visible CPU model (via `lscpu`) and f_max,
pick a real, cited TDP figure for a comparable physical CPU (Intel ARK or
the manufacturer's published spec sheet is the right source) and set
DYNAMIC_W_AT_FMAX to a documented fraction of it, with STATIC_W as the
idle-power fraction from the same source. Record the exact CPU model and
citation used, once chosen, in this file.

## Explicit assumptions and limitations

- V∝F is an approximation, not exact for every real CPU/DVFS
  implementation.
- Static power is treated as a constant; real leakage power varies with
  temperature, which is not modelled.
- Memory, uncore, and other platform power (RAM, chipset, I/O) are not
  modelled - this estimates CPU package power only.
- Per-core variation is not modelled - all cores are assumed identical.
- VM-specific limitation, ties directly to the PRD's Outcome A/B split:
  the frequency this project reads and estimates power from is the
  guest's VIEW of frequency. Under Outcome A that's hopefully a real
  hardware value; under Outcome B it comes from the simulated cpufreq
  layer with no physical hardware backing it at all. Either way the power
  number is an estimate; under Outcome B it is one step further removed
  from anything physical, worth stating plainly in the final report
  rather than leaving implicit.
- These constants must be re-fit once Phase 0 determines the actual host
  CPU model, f_max, and available frequency steps
  (docs/vm_feasibility.md) - see the "fitting" section above.

## Citation

"Power Management Techniques for Data Centers: A Survey"
(arXiv:1404.6681) - see docs/Research_Paper_Summary.md, paper 3, for full
context.
