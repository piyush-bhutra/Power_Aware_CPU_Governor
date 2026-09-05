"""Module 5 - ESTIMATED power. Nothing here is measured. See docs/power_model.md.

CMOS dynamic power P_dyn = a*C*V^2*f. Supply voltage tracks frequency roughly
linearly over a DVFS range, so with V normalised to f the dynamic term scales
as f^3. A constant static (leakage) term is added.
"""

# Fitted to a nominal TDP at f_max; both constants are documented assumptions,
# not measurements. Tune in docs/power_model.md once f_max is known from Phase 0.
STATIC_W = 2.0
DYNAMIC_W_AT_FMAX = 13.0


def estimate_power_w(freq_khz, f_max_khz, util_pct=100.0):
    """Estimated package power in watts. Labelled 'estimated' everywhere it is used."""
    r = freq_khz / f_max_khz
    return STATIC_W + DYNAMIC_W_AT_FMAX * (r ** 3) * (util_pct / 100.0)


def estimate_energy_j(power_w, interval_s):
    return power_w * interval_s
