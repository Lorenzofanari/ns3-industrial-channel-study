#!/usr/bin/env python3
"""Bootstrap confidence intervals for run-level simulation metrics."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_METRICS = [
    "pdr",
    "PDR",
    "p95_latency_ms",
    "p99_latency_ms",
    "temporal_gain",
    "ru_diversity_gain",
    "combined_gain",
]


def bootstrap_mean(values: np.ndarray, reps: int, confidence: float, rng: np.random.Generator) -> dict:
    values = values[np.isfinite(values)]
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": np.nan, "ci_low": np.nan, "ci_high": np.nan, "note": "empty"}
    mean = float(np.mean(values))
    if n < 2:
        return {"n": n, "mean": mean, "ci_low": mean, "ci_high": mean, "note": "n<2_degenerate"}
    draws = rng.choice(values, size=(reps, n), replace=True).mean(axis=1)
    alpha = 1.0 - confidence
    return {
        "n": n,
        "mean": mean,
        "ci_low": float(np.quantile(draws, alpha / 2.0)),
        "ci_high": float(np.quantile(draws, 1.0 - alpha / 2.0)),
        "note": "run_level_bootstrap",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/bootstrap_ci"))
    parser.add_argument("--group-by", default="jammer_ru_mode,target_snr_db,policy")
    parser.add_argument("--metrics", default=",".join(DEFAULT_METRICS))
    parser.add_argument("--bootstrap-reps", type=int, default=2000)
    parser.add_argument("--confidence", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=20260507)
    args = parser.parse_args()

    df = pd.read_csv(args.csv, comment="#").replace([np.inf, -np.inf], np.nan)
    group_cols = [c for c in args.group_by.split(",") if c and c in df.columns]
    metrics = [c for c in args.metrics.split(",") if c and c in df.columns]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(args.seed)

    rows = []
    groups = [((), df)] if not group_cols else df.groupby(group_cols, dropna=False)
    for key, group in groups:
        if group_cols and not isinstance(key, tuple):
            key = (key,)
        base = {col: value for col, value in zip(group_cols, key)}
        for metric in metrics:
            values = pd.to_numeric(group[metric], errors="coerce").to_numpy(dtype=float)
            stat = bootstrap_mean(values, args.bootstrap_reps, args.confidence, rng)
            rows.append({**base, "metric": metric, **stat})

    out = pd.DataFrame(rows)
    out_path = args.output_dir / "bootstrap_ci.csv"
    out.to_csv(out_path, index=False)
    report = [
        "# Bootstrap Confidence Intervals",
        "",
        f"Input CSV: `{args.csv}`",
        f"Rows: {len(df)}",
        f"Group columns: {', '.join(group_cols) if group_cols else 'global'}",
        f"Metrics: {', '.join(metrics)}",
        f"Bootstrap reps: {args.bootstrap_reps}",
        f"Confidence: {args.confidence}",
        "",
        "Intervals are run-level bootstrap intervals. They do not replace packet-level",
        "binomial intervals and should not be used for final claims unless every",
        "reported group has enough independent seed/run samples.",
        "",
        f"Output: `{out_path}`",
    ]
    (args.output_dir / "bootstrap_report.md").write_text("\n".join(report) + "\n")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
