# Review 1 synthetic policy comparison

Nine original assets were copied unchanged from shared
`results/review1_verified_20261015/` (108,680 bytes): five policy CSVs,
`summaries.json`, `metadata.json`, `synthetic_modelled_energy.png` and
`synthetic_simulated_frequency.png`. Shared originals remain untouched.

Metadata records clean source checkpoint
`4055aa2c0700f829b565f01442f392806f0dea73`, seed 11, K=3 and nominal 1 s intervals.
The plan is CPU (10 ticks), io_burst (10), idle (6), mixed (8). Each of performance,
powersave, ondemand, conservative and ours has 34 observations with the same workload
signals. The baselines are Python approximations, not kernel governor experiments.
No exact generation UTC or original output-directory argument was recorded;
PROVENANCE.json explicitly records those limits and the equivalent generator command.

These CSVs use the original 15-column schema. Current generators add 25 columns;
do not append to this archive or mistake missing raw fields for corrupted evidence.
`timestamp` is synthetic time 1..34, not wall-clock observation time. `freq_khz` is
simulated setter state before the tick; `target_khz`/`requested_khz` are simulated
choices. `expected` is the invented scenario label. Class outputs are not a real
labelled accuracy evaluation. Modelled per-tick watts integrate over nominal 1 s.

All five CSVs reproduce exactly in their original columns with the current generator;
recomputed class labels, model power and summary metrics match. Both PNGs are
byte-identical to the regenerated charts and were visually inspected. Their titles
identify synthetic replay and modelled energy/simulated frequency. The temporary
regeneration was for validation; original files were archived, not replaced.

The model assumes P = 21.6 + 32.4*(f/5100000)^3*util/100 watts and a
3.8–5.1 GHz ladder. These are modelling choices, not guest power calibration.
This is open-loop replay: it cannot prove measured electrical savings, actual
frequency actuation or preserved workload completion time. The lowest model energy
is not evidence of the best performance/energy tradeoff.

Real Linux observations are separately preserved in
[background_readiness_20261015](../background_readiness_20261015/README.md).
Those are measured guest kernel counters with no frequency actuation; these synthetic
files contain no new Linux observations. No background artifacts are duplicated here.

Verify archived originals and provenance from this directory:

```bash
sha256sum -c SHA256SUMS
```

Reproduce from the repository root with the existing virtualenv into a new directory:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MPLCONFIGDIR=/tmp/codex-mpl timeout 30s .venv/bin/python -m benchmark.review_demo --outdir data/review1-reproduction-new
```

No hardware access or artificial workload is needed. Metadata will describe the
current checkpoint; equivalent common CSV values, summaries and charts are expected,
not byte-identical metadata or the same CSV header. PROVENANCE.json contains original
hashes, source hashes computed during archival, parameters and validation details.
The five CRLF CSVs have exact-path .gitattributes rules preserving original bytes.
