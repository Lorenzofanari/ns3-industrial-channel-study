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

