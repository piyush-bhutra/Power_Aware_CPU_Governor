"""Module 5 - ESTIMATED power. Nothing here is measured. See docs/power_model.md.

CMOS dynamic power P_dyn = a*C*V^2*f. Supply voltage tracks frequency roughly
linearly over a DVFS range, so with V normalised to f the dynamic term scales
as f^3. A constant static term (leakage + uncore/platform power) is added.
"""

# FITTED (two-point) to AMD's published Ryzen 7 7840HS figures: 35 W at the
# 3.8 GHz base clock, 54 W at the 5.1 GHz boost clock. Derivation, source and
# the interpretive assumption behind it: docs/power_model.md.
STATIC_W = 21.6
DYNAMIC_W_AT_FMAX = 32.4


def estimate_power_w(freq_khz, f_max_khz, util_pct=100.0):
    """Estimated package power in watts. Labelled 'estimated' everywhere it is used."""
    r = freq_khz / f_max_khz
    return STATIC_W + DYNAMIC_W_AT_FMAX * (r ** 3) * (util_pct / 100.0)


def estimate_energy_j(power_w, interval_s):
    return power_w * interval_s
