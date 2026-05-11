#!/usr/bin/env python3
"""Audit seed-to-seed variance so the paper can defend transferability.

For each (channel, scenario, MCS, payload, distance, jammer, SNR) cell in the
provided CSV, compute the std and the relative spread across seeds and flag
cells where the spread exceeds a configurable tolerance. The output report
lets the operator decide whether more seeds are needed before the camera
ready.

Why this matters for review:
- A reviewer who is skeptical about transferability will look for evidence
  that the conclusions are stable when the only thing that changes is the RNG
  seed. The auto-generated `SEED_AUDIT.md` quantifies that stability.

Usage:
    python3 scripts/check_seed_independence.py \\
        --input results/paper_v2/results.csv \\
        --output results/paper_v2/SEED_AUDIT.md \\
        --tolerance 0.02
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

from config_utils import read_csv_rows, to_float


GROUP_KEYS = [
    "channel_model",
    "scenario",
    "mcs",
    "payload_bits",
    "distance_m",
    "jammer_mode",
    "jammer_power_dbm",
    "target_snr_db",
]

METRICS = ["pdr", "per", "mean_recovery_time_s", "p95_delay_s", "deadline_miss_ratio"]


def stats(values):
    if not values:
        return None
    mean = sum(values) / len(values)
    if len(values) < 2:
        return {"mean": mean, "std": 0.0, "rel_std": 0.0, "n": len(values)}
    var = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
    std = math.sqrt(var)
    rel = std / max(abs(mean), 1e-6)
    return {"mean": mean, "std": std, "rel_std": rel, "n": len(values)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--tolerance", type=float, default=0.02,
                        help="Flag cells where std/|mean| of pdr exceeds this value")
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.input))
    grouped: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(k, "") for k in GROUP_KEYS)].append(row)

    flagged: list[dict] = []
    aggregate: dict[str, list[float]] = {m: [] for m in METRICS}
    aggregate_rel: dict[str, list[float]] = {m: [] for m in METRICS}
    n_cells_with_multi_seed = 0
    for key, cell_rows in grouped.items():
        seeds = {r.get("seed", "") for r in cell_rows}
        if len(seeds) < 2:
            continue
        n_cells_with_multi_seed += 1
        cell_summary = {k: v for k, v in zip(GROUP_KEYS, key)}
        for metric in METRICS:
            values = [to_float(r, metric) for r in cell_rows]
            s = stats(values)
            if s is None:
                continue
            cell_summary[f"{metric}_mean"] = s["mean"]
            cell_summary[f"{metric}_std"] = s["std"]
            cell_summary[f"{metric}_rel_std"] = s["rel_std"]
            aggregate[metric].append(s["std"])
            aggregate_rel[metric].append(s["rel_std"])
        if cell_summary.get("pdr_rel_std", 0.0) > args.tolerance:
            flagged.append(cell_summary)

    lines = [
        "# Seed-Independence Audit",
        "",
        f"Input: `{args.input}`",
        f"Cells with >= 2 seeds: {n_cells_with_multi_seed}",
        f"Tolerance for flagging PDR cells: rel_std > {args.tolerance}",
        f"Flagged cells: {len(flagged)}",
        "",
        "## Aggregate spread (across all multi-seed cells)",
        "",
        "| metric | mean of cell std | mean of cell rel_std |",
        "|--------|------------------|----------------------|",
    ]
    for metric in METRICS:
        if not aggregate[metric]:
            continue
        mean_std = sum(aggregate[metric]) / len(aggregate[metric])
        mean_rel = sum(aggregate_rel[metric]) / len(aggregate_rel[metric])
        lines.append(f"| `{metric}` | {mean_std:.6g} | {mean_rel:.6g} |")
    if flagged:
        lines += ["", "## Flagged cells (PDR rel_std > tolerance)", ""]
        for cell in flagged[:50]:
            keyparts = ", ".join(f"{k}={cell.get(k, '')}" for k in GROUP_KEYS)
            lines.append(f"- {keyparts}: pdr_mean={cell.get('pdr_mean', 0):.4g}, "
                         f"pdr_rel_std={cell.get('pdr_rel_std', 0):.4g}")
        if len(flagged) > 50:
            lines.append(f"- ...and {len(flagged) - 50} more")
    else:
        lines += ["", "No cells exceeded the tolerance. PDR is statistically stable across seeds.", ""]

    Path(args.output).write_text("\n".join(lines))
    print(f"Wrote {args.output}")
    if args.json_output:
        Path(args.json_output).write_text(json.dumps({
            "flagged_count": len(flagged),
            "multi_seed_cells": n_cells_with_multi_seed,
            "tolerance": args.tolerance,
            "flagged": flagged,
        }, indent=2) + "\n")
        print(f"Wrote {args.json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
