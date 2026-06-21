#!/usr/bin/env python3
"""Render correlation heatmaps from scripts/analyze_correlations.py outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


RELIABILITY = ["PDR", "PDR_on", "PDR_off", "PLR", "PER", "burst_induced_loss_ratio", "robustness_ratio"]
LATENCY = ["p95_latency_ms", "p99_latency_ms", "worst_case_latency_ms", "mean_recovery_time_ms", "p95_recovery_time_ms"]
GAIN = ["temporal_gain", "ru_diversity_gain", "combined_gain"]


def read_matrix(path: Path) -> pd.DataFrame:
    if not path.exists() or path.stat().st_size == 0:
        return pd.DataFrame()
    try:
        return pd.read_csv(path, index_col=0)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def plot_matrix(matrix: pd.DataFrame, path_base: Path, title: str) -> None:
    path_base.parent.mkdir(parents=True, exist_ok=True)
    if matrix.empty:
        fig, ax = plt.subplots(figsize=(7, 3))
        ax.text(0.5, 0.5, "No correlation data", ha="center", va="center")
        ax.set_axis_off()
    else:
        size = max(6, min(18, 0.35 * max(len(matrix.index), len(matrix.columns))))
        fig, ax = plt.subplots(figsize=(size, size))
        values = matrix.to_numpy(dtype=float)
        im = ax.imshow(values, vmin=-1, vmax=1, cmap="coolwarm", aspect="auto")
        ax.set_title(title)
        ax.set_xticks(np.arange(len(matrix.columns)))
        ax.set_xticklabels(matrix.columns, rotation=90, fontsize=7)
        ax.set_yticks(np.arange(len(matrix.index)))
        ax.set_yticklabels(matrix.index, fontsize=7)
        fig.colorbar(im, ax=ax, shrink=0.75)
        fig.tight_layout()
    fig.savefig(path_base.with_suffix(".png"), dpi=180)
    fig.savefig(path_base.with_suffix(".pdf"))
    plt.close(fig)


def focused_matrix(matrix: pd.DataFrame, variables: list[str]) -> pd.DataFrame:
    if matrix.empty:
        return matrix
    present = [col for col in variables if col in matrix.columns]
    if not present:
        return pd.DataFrame()
    related = sorted(set(present + [idx for idx in matrix.index if idx in matrix.columns]))
    return matrix.loc[[idx for idx in related if idx in matrix.index], [col for col in related if col in matrix.columns]]


def grouped_panel(input_dir: Path, prefix: str, output_base: Path, title: str) -> None:
    files = sorted(input_dir.glob(f"{prefix}_*_spearman.csv"))[:9]
    if not files:
        plot_matrix(pd.DataFrame(), output_base, title)
        return
    fig, axes = plt.subplots(3, 3, figsize=(14, 12))
    im = None
    for ax, path in zip(axes.flat, files):
        matrix = read_matrix(path)
        if matrix.empty:
            ax.text(0.5, 0.5, "empty", ha="center", va="center")
            ax.set_axis_off()
            continue
        values = matrix.to_numpy(dtype=float)
        im = ax.imshow(values, vmin=-1, vmax=1, cmap="coolwarm", aspect="auto")
        ax.set_title(path.stem.replace(prefix + "_", ""), fontsize=8)
        ax.set_xticks([])
        ax.set_yticks([])
    for ax in axes.flat[len(files):]:
        ax.set_axis_off()
    fig.suptitle(title)
    if im is not None:
        fig.colorbar(im, ax=axes.ravel().tolist(), shrink=0.7)
    fig.savefig(output_base.with_suffix(".png"), dpi=180)
    fig.savefig(output_base.with_suffix(".pdf"))
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=Path("results/correlation_matrix"))
    args = parser.parse_args()

    input_dir = args.input_dir
    pearson = read_matrix(input_dir / "pearson_global.csv")
    spearman = read_matrix(input_dir / "spearman_global.csv")

    plot_matrix(pearson, input_dir / "pearson_global_heatmap", "Pearson Global Correlation")
    plot_matrix(spearman, input_dir / "spearman_global_heatmap", "Spearman Global Correlation")
    plot_matrix(focused_matrix(spearman, RELIABILITY), input_dir / "reliability_focused_heatmap", "Reliability-Focused Spearman Correlation")
    plot_matrix(focused_matrix(spearman, LATENCY), input_dir / "latency_focused_heatmap", "Latency-Focused Spearman Correlation")
    plot_matrix(focused_matrix(spearman, GAIN), input_dir / "gain_focused_heatmap", "Gain-Focused Spearman Correlation")

    grouped_panel(input_dir, "grouped_mcs", input_dir / "grouped_mcs_heatmaps", "Grouped Spearman by MCS")
    grouped_panel(input_dir, "grouped_jammer_ru_mode", input_dir / "grouped_jammer_mode_heatmaps", "Grouped Spearman by Jammer Mode")
    grouped_panel(input_dir, "grouped_policy", input_dir / "grouped_policy_heatmaps", "Grouped Spearman by Policy")
    print(f"Wrote heatmaps to {input_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
