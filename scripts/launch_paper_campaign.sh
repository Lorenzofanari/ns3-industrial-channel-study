#!/usr/bin/env bash
# Launch the paper-scale anti-jamming + PER waterfall campaign as 6 sharded
# parallel processes (3 seeds x 2 channels). Each shard writes to its own
# results/paper_v2/<channel>_seed<seed>/ directory; the post-merge step in
# scripts/merge_paper_shards.py concatenates them into the final results.csv
# consumed by validate_trends/parse_results/plot_results.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

CONFIG="configs/paper_snr_sweep.yaml"
OUT="results/paper_v2"
SNR_MIN=${SNR_MIN:-0}
SNR_MAX=${SNR_MAX:-22}
SNR_STEP=${SNR_STEP:-0.5}
SEEDS=(20260507 20260508 20260509)
CHANNELS=(cm8_rayleigh quadriga_raytraced)

mkdir -p "$OUT/logs"
echo "Launching campaign: SNR ${SNR_MIN}..${SNR_MAX} step ${SNR_STEP} dB"
echo "Channels: ${CHANNELS[*]}"
echo "Seeds:    ${SEEDS[*]}"

PIDS=()
for chan in "${CHANNELS[@]}"; do
  for seed in "${SEEDS[@]}"; do
    shard="${OUT}/${chan}_seed${seed}"
    log="${OUT}/logs/${chan}_seed${seed}.log"
    rm -rf "$shard"
    mkdir -p "$shard"
    nohup python3 -u scripts/run_sweep.py \
      --config "$CONFIG" \
      --output-dir "$shard" \
      --channel-model "$chan" \
      --simulation-path ns3_core_harness \
      --snr-min "$SNR_MIN" --snr-max "$SNR_MAX" --snr-step "$SNR_STEP" \
      --seed "$seed" \
      --no-build > "$log" 2>&1 &
    PIDS+=($!)
    echo "  shard ${chan} seed=${seed} pid=$!"
  done
done

echo "${PIDS[@]}" > "${OUT}/.pids"
echo "All shard PIDs: ${PIDS[*]}"
echo "Tail logs from ${OUT}/logs/*.log; merge with scripts/merge_paper_shards.py once all shards exit."
