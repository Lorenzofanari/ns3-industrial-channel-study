# Reproducibility

Every run writes:

- git commit hash if available;
- ns-3 version string if available from the binary;
- seed;
- scenario;
- channel model;
- MCS;
- payload size;
- distance;
- jammer configuration;
- PHY parameters;
- MAC parameters;
- simulation time;
- reliability, latency, safety and anti-jamming metrics.

Recommended workflow:

```bash
cmake -S . -B build
cmake --build build -j
python3 scripts/run_sweep.py --smoke
python3 scripts/validate_trends.py --input results/sweep/results.csv --output results/sweep/trend_report.md
python3 scripts/plot_results.py --input results/sweep/results.csv --output-dir results/sweep/plots
python3 scripts/make_report.py --input results/sweep/results.csv --trend-report results/sweep/trend_report.md --output results/sweep/reproducibility_report.md
```

## Cooldown-length sweep and deadline-tail analysis

These scripts support the scheduler-paper claims about cooldown-on-failure retry
timing. All outputs land under `results/cooldown_sweep_analysis/` (git-ignored;
regenerated on demand) and each writes a `PROVENANCE*.txt` (git commit, seeds,
exact command). See `RESULTS_FOR_PAPER.md` Section 15 for the interpretation and
claim boundaries.

```bash
# 1. Cooldown-length sweep (aggregation of the existing coherence campaign):
#    reliability vs latency across T_cd in {0,19,38,76,152,304} OFDM symbols.
python3 scripts/aggregate_cooldown_sweep.py

# 2. Broadband multi-deadline deadline-tail (small NEW attempt-log campaign,
#    ~11 s / 84 runs): deadline-miss ratio for D in {1,5,10} ms derived offline
#    from per-packet latency; AR(1) primary + block parity; 3 seeds.
python3 scripts/cooldown_multideadline_broadband.py

# 3. PDR / conditional-PDR(jammer-ON) with seed uncertainty (aggregation only):
#    mean +/- seed std over the 3 paper seeds; PDR also bounded by Clopper-Pearson.
python3 scripts/plot_pdr_seed_uncertainty.py
```

Claim boundaries enforced by these scripts: engineering AR(1)/block channel model
(NOT a calibrated 802.11ax PHY); scheduler-harness Monte-Carlo matrix only; zero
*observed* misses reported as rule-of-three 95% upper bounds, never as zero
probability; the scenarios stay distinct (S4 baseline-PF, S8 retarget-only,
S9 full cooldown-on-failure).

