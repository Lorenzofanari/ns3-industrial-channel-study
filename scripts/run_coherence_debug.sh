#!/usr/bin/env bash
# Coherence-time experiment: DEBUG matrix (smoke; completes in seconds).
# Builds the binary if needed, runs the tiny matrix, analyses and plots.
set -euo pipefail
cd "$(dirname "$0")/.."

make -j >/dev/null
JOBS="${JOBS:-$(nproc)}"

python3 scripts/run_coherence_experiment.py --matrix debug --jobs "${JOBS}"
python3 scripts/check_coherence_outputs.py  --matrix debug
python3 scripts/analyze_coherence_time.py   --matrix debug
python3 scripts/plot_coherence_figures.py   --matrix debug

echo "Debug run complete -> results/coherence_time_experiment/debug/"
