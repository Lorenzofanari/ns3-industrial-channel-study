#!/usr/bin/env bash
# Coherence-time experiment: FULL matrix.
# WARNING: ~6e4 single-link Monte-Carlo runs. On a workstation at ~50 ms/run
# this is ~50-60 min single-threaded; use JOBS to parallelise (the runs are
# independent). Set MATRIX=reduced for the documented ~few-minute campaign.
set -euo pipefail
cd "$(dirname "$0")/.."

make -j >/dev/null
JOBS="${JOBS:-$(nproc)}"
MATRIX="${MATRIX:-full}"

python3 scripts/run_coherence_experiment.py --matrix "${MATRIX}" --jobs "${JOBS}"
python3 scripts/check_coherence_outputs.py  --matrix "${MATRIX}"
python3 scripts/analyze_coherence_time.py   --matrix "${MATRIX}"
python3 scripts/plot_coherence_figures.py   --matrix "${MATRIX}"

echo "Campaign (${MATRIX}) complete -> results/coherence_time_experiment/${MATRIX}/"
