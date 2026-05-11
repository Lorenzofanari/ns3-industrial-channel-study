#!/usr/bin/env bash
# End-to-end post-processing after scripts/launch_paper_campaign.sh completes:
#   1. Merge the per-seed shards into results/paper_v2/{results.csv,
#      cm8/results.csv, quadriga/results.csv}.
#   2. Validate physical trends (writes results/paper_v2/trend_violations.txt
#      + .json).
#   3. Build the summary table (results/paper_v2/summary.csv) and the
#      reproducibility report (results/paper_v2/REPORT.md).
#   4. Generate all gnuplot plots into results/paper_v2/plots/.
#   5. Print an archive sizing summary the operator can quote in the paper.

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

OUT="results/paper_v2"
PLOTS_DIR="$OUT/plots"
mkdir -p "$OUT" "$PLOTS_DIR"

echo "[1/5] Merging shards..."
python3 scripts/merge_paper_shards.py --root "$OUT"

echo "[2/5] Validating trends..."
python3 scripts/validate_trends.py \
  --input "$OUT/results.csv" \
  --output "$OUT/trend_violations.txt" \
  --json-output "$OUT/trend_violations.json"

echo "[3/5] Building summary + reproducibility report..."
python3 scripts/parse_results.py --input "$OUT/results.csv" --output "$OUT/summary.csv"
python3 scripts/make_report.py \
  --input "$OUT/results.csv" \
  --trend-report "$OUT/trend_violations.txt" \
  --output "$OUT/REPORT.md"

echo "[4/5] Generating plots..."
# Generate plots split by channel so the legend stays focused per figure, and
# a combined version for global views.
python3 scripts/plot_results.py --input "$OUT/cm8/results.csv" --output-dir "$PLOTS_DIR/cm8"
python3 scripts/plot_results.py --input "$OUT/quadriga/results.csv" --output-dir "$PLOTS_DIR/quadriga"
python3 scripts/plot_results.py --input "$OUT/results.csv" --output-dir "$PLOTS_DIR"

echo "[5/5] Archive sizing..."
{
  echo "--- merged CSV ---"
  wc -l "$OUT/results.csv" 2>/dev/null
  echo "--- per-channel CSVs ---"
  wc -l "$OUT"/{cm8,quadriga}/results.csv 2>/dev/null
  echo "--- plots ---"
  ls -lh "$PLOTS_DIR"/*.png 2>/dev/null | head
  echo "--- total on-disk ---"
  du -sh "$OUT" 2>/dev/null
  echo "--- launched packets total ---"
  python3 - <<'PY'
import csv
from pathlib import Path
total = 0
with Path('results/paper_v2/results.csv').open() as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            total += int(row['transmitted_packets'])
        except (KeyError, ValueError):
            pass
print(f"launched_packets={total:,}")
PY
} | tee "$OUT/ARCHIVE_SUMMARY.txt"

echo "Done. See $OUT/REPORT.md and $PLOTS_DIR/."
