"""The dev machine's host CPU, written down once. Import from here; never restate.

The dev VM exposes no cpufreq (docs/vm_feasibility.md, Outcome B), so every
frequency the governor, the benchmarks and the mock sysfs tree use comes from
this ladder rather than from hardware.
"""

# AMD Ryzen 7 7840HS: 3.8 GHz base to 5.1 GHz boost, 4 evenly spaced steps (kHz).
# A tuple so no importer can mutate the shared copy.
RYZEN_7840HS_LADDER_KHZ = (3_800_000, 4_233_333, 4_666_667, 5_100_000)
