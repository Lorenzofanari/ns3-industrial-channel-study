#!/usr/bin/env python3
"""Exploratory correlation analysis for merged simulation CSV files."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from sklearn.feature_selection import mutual_info_regression


INPUT_VARIABLES = [
    "policy",
    "num_users",
    "num_rus",
    "mcs",
    "mcs_label",
    "payload_bits",
    "distance_m",
    "target_snr_db",
    "ru_width_tones",
    "ru_correlation_rho",
    "cooldown_symbols",
    "cooldown_ms",
    "retry_limit",
    "deadline_ms",
    "jammer_ru_mode",
    "jammer_power_dbm",
    "jammer_burst_ms",
    "jammer_interval_ms",
    "jammer_duty_cycle",
    "jammer_phase_ms",
    "jammed_ru_count",
    "fraction_rus_jammed",
    "ru_changed",
    "ru_distance_tones",
    "ru_was_jammed_initial",
    "ru_was_jammed_retry",
    "sinr_initial_db",
    "sinr_retry_db",
    "estimated_sinr_initial_db",
    "estimated_sinr_retry_db",
    "per_initial",
    "per_retry",
    "estimated_per_initial",
    "estimated_per_retry",
    "estimator_noise_db",
    "estimator_staleness_slots",
    "jammer_missed_detection_prob",
    "jammer_false_alarm_prob",
]

OUTPUT_VARIABLES = [
    "PDR",
    "PDR_on",
    "PDR_off",
    "PLR",
    "PER",
    "p95_latency_ms",
    "p99_latency_ms",
    "worst_case_latency_ms",
    "mean_recovery_time_ms",
    "p95_recovery_time_ms",
    "burst_induced_loss_ratio",
    "robustness_ratio",
    "max_consecutive_losses",
    "max_consecutive_deadline_misses",
    "deadline_miss_ratio",
    "deadline_miss_due_to_cooldown",
    "deadline_miss_due_to_loss",
    "temporal_gain",
    "ru_diversity_gain",
    "combined_gain",
    "jain_index_pdr",
    "jain_index_throughput",
]

TARGET_FILES = {
    "PDR": "top_correlations_pdr.csv",
    "PDR_on": "top_correlations_pdr_on.csv",
    "PDR_off": "top_correlations_pdr_off.csv",
    "p95_latency_ms": "top_correlations_latency_p95.csv",
    "deadline_miss_ratio": "top_correlations_deadline_miss.csv",
    "temporal_gain": "top_correlations_temporal_gain.csv",
    "ru_diversity_gain": "top_correlations_ru_diversity_gain.csv",
}

GROUP_COLUMNS = ["mcs", "jammer_ru_mode", "policy", "num_rus", "num_users"]


def read_merged_csv(paths: Iterable[Path]) -> pd.DataFrame:
    frames = []
    for path in paths:
        frames.append(pd.read_csv(path, comment="#"))
    if not frames:
        raise ValueError("at least one CSV input is required")
    return pd.concat(frames, ignore_index=True, sort=False)


def present(columns: Iterable[str], df: pd.DataFrame) -> list[str]:
    return [col for col in columns if col in df.columns]


def numeric_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for col in columns:
        series = df[col]
        if series.dtype == bool:
            out[col] = series.astype(float)
        else:
            mapped = series.astype("string").str.lower().map({"true": 1.0, "false": 0.0})
            numeric = pd.to_numeric(series, errors="coerce")
            out[col] = numeric.where(numeric.notna(), mapped)
    out = out.replace([np.inf, -np.inf], np.nan)
    return out


def split_numeric_categorical(df: pd.DataFrame, columns: list[str]) -> tuple[list[str], list[str]]:
    numeric_cols = []
    categorical_cols = []
    for col in columns:
        converted = numeric_frame(df, [col])[col]
        if converted.notna().any():
            numeric_cols.append(col)
        else:
            categorical_cols.append(col)
    return numeric_cols, categorical_cols


def drop_constant_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    constants = []
    keep = []
    for col in df.columns:
        non_na = df[col].dropna()
        if non_na.empty or non_na.nunique(dropna=True) <= 1:
            constants.append(col)
        else:
            keep.append(col)
    return df[keep], constants


def save_matrix(df: pd.DataFrame, path: Path, method: str) -> None:
    if df.empty or len(df.columns) < 2:
        pd.DataFrame().to_csv(path)
        return
    df.corr(method=method, min_periods=3).to_csv(path)


def one_hot_frame(df: pd.DataFrame, numeric_cols: list[str], categorical_cols: list[str]) -> pd.DataFrame:
    num = numeric_frame(df, numeric_cols)
    cat = pd.get_dummies(df[categorical_cols].astype("string"), dummy_na=True) if categorical_cols else pd.DataFrame(index=df.index)
    return pd.concat([num, cat], axis=1).replace([np.inf, -np.inf], np.nan)


def cramers_v(confusion: pd.DataFrame) -> float:
    if confusion.empty:
        return math.nan
    chi2 = chi2_contingency(confusion, correction=False)[0]
    n = confusion.to_numpy().sum()
    if n == 0:
        return math.nan
    r, k = confusion.shape
    denom = n * (min(k - 1, r - 1))
    return math.sqrt(chi2 / denom) if denom > 0 else math.nan


def categorical_associations(df: pd.DataFrame, categorical_cols: list[str]) -> pd.DataFrame:
    rows = []
    for i, left in enumerate(categorical_cols):
        for right in categorical_cols[i + 1:]:
            table = pd.crosstab(df[left].fillna("<NA>"), df[right].fillna("<NA>"))
            rows.append({"left": left, "right": right, "cramers_v": cramers_v(table), "n": int(table.to_numpy().sum())})
    return pd.DataFrame(rows)


def mutual_information(df: pd.DataFrame, feature_cols: list[str], target_cols: list[str], categorical_cols: list[str]) -> pd.DataFrame:
    rows = []
    if not feature_cols or not target_cols:
        return pd.DataFrame(rows)
    numeric_cols = [col for col in feature_cols if col not in categorical_cols]
    x = one_hot_frame(df, numeric_cols, [col for col in categorical_cols if col in feature_cols])
    x = x.dropna(axis=1, how="all")
    if x.empty:
        return pd.DataFrame(rows)
    x = x.fillna(x.median(numeric_only=True)).fillna(0.0)
    for target in target_cols:
        y = pd.to_numeric(df[target], errors="coerce").replace([np.inf, -np.inf], np.nan)
        mask = y.notna()
        if mask.sum() < 5 or y[mask].nunique() <= 1:
            continue
        scores = mutual_info_regression(x.loc[mask], y.loc[mask], random_state=20260507)
        for feature, score in zip(x.columns, scores):
            rows.append({"target": target, "feature": feature, "mutual_information": score, "n": int(mask.sum())})
    return pd.DataFrame(rows).sort_values(["target", "mutual_information"], ascending=[True, False])


def top_correlations(matrix_pearson: pd.DataFrame, matrix_spearman: pd.DataFrame, target: str) -> pd.DataFrame:
    if target not in matrix_spearman.columns:
        return pd.DataFrame(columns=["target", "feature", "pearson", "spearman", "abs_spearman", "rank_type"])
    rows = []
    for feature, spearman in matrix_spearman[target].drop(labels=[target], errors="ignore").dropna().items():
        pearson = matrix_pearson[target].get(feature, np.nan) if target in matrix_pearson else np.nan
        rows.append({"target": target, "feature": feature, "pearson": pearson, "spearman": spearman, "abs_spearman": abs(spearman)})
    ranked = pd.DataFrame(rows)
    if ranked.empty:
        return ranked
    positive = ranked.sort_values("spearman", ascending=False).head(20).assign(rank_type="positive")
    negative = ranked.sort_values("spearman", ascending=True).head(20).assign(rank_type="negative")
    absolute = ranked.sort_values("abs_spearman", ascending=False).head(20).assign(rank_type="absolute")
    return pd.concat([positive, negative, absolute], ignore_index=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="+", type=Path, help="Merged simulation CSV files")
    parser.add_argument("--output-dir", type=Path, default=Path("results/correlation_matrix"))
    args = parser.parse_args()

    out_dir = args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    df = read_merged_csv(args.csv)
    df = df.replace([np.inf, -np.inf], np.nan)

    input_cols = present(INPUT_VARIABLES, df)
    output_cols = present(OUTPUT_VARIABLES, df)
    analysis_cols = list(dict.fromkeys(input_cols + output_cols))
    numeric_cols, categorical_cols = split_numeric_categorical(df, analysis_cols)
    numeric = numeric_frame(df, numeric_cols)
    numeric, constant_numeric = drop_constant_columns(numeric)

    save_matrix(numeric, out_dir / "pearson_global.csv", "pearson")
    save_matrix(numeric, out_dir / "spearman_global.csv", "spearman")
    save_matrix(numeric, out_dir / "kendall_global.csv", "kendall")

    encoded = one_hot_frame(df, list(numeric.columns), categorical_cols)
    encoded, constant_encoded = drop_constant_columns(encoded)
    save_matrix(encoded, out_dir / "pearson_onehot_global.csv", "pearson")
    save_matrix(encoded, out_dir / "spearman_onehot_global.csv", "spearman")

    mi = mutual_information(df, input_cols, output_cols, categorical_cols)
    mi.to_csv(out_dir / "mutual_information_targets.csv", index=False)

    cat_assoc = categorical_associations(df, categorical_cols)
    cat_assoc.to_csv(out_dir / "categorical_associations.csv", index=False)

    pearson = pd.read_csv(out_dir / "pearson_global.csv", index_col=0) if (out_dir / "pearson_global.csv").stat().st_size else pd.DataFrame()
    spearman = pd.read_csv(out_dir / "spearman_global.csv", index_col=0) if (out_dir / "spearman_global.csv").stat().st_size else pd.DataFrame()
    for target, file_name in TARGET_FILES.items():
        top_correlations(pearson, spearman, target).to_csv(out_dir / file_name, index=False)

    grouped_files = []
    for group_col in GROUP_COLUMNS:
        if group_col not in df.columns:
            continue
        for value, group in df.groupby(group_col, dropna=False):
            group_numeric = numeric_frame(group, analysis_cols)
            group_numeric, _ = drop_constant_columns(group_numeric)
            safe_value = str(value).replace("/", "_").replace(" ", "_").replace(".", "p")
            path = out_dir / f"grouped_{group_col}_{safe_value}_spearman.csv"
            save_matrix(group_numeric, path, "spearman")
            grouped_files.append(path.name)

    missing_inputs = sorted(set(INPUT_VARIABLES) - set(input_cols))
    missing_outputs = sorted(set(OUTPUT_VARIABLES) - set(output_cols))
    report = [
        "# Correlation Report",
        "",
        f"Sample size N: {len(df)}",
        "",
        "This is exploratory association analysis. It does not establish causality; causal claims require controlled ablation runs.",
        "",
        f"Numeric constant or empty columns dropped: {', '.join(constant_numeric) if constant_numeric else 'none'}",
        f"One-hot constant columns dropped: {len(constant_encoded)}",
        "",
        f"Missing input variables: {', '.join(missing_inputs) if missing_inputs else 'none'}",
        f"Missing output variables: {', '.join(missing_outputs) if missing_outputs else 'none'}",
        "",
        "Generated matrices:",
        "- pearson_global.csv",
        "- spearman_global.csv",
        "- kendall_global.csv",
        "- pearson_onehot_global.csv",
        "- spearman_onehot_global.csv",
        "- mutual_information_targets.csv",
        "- categorical_associations.csv",
        "",
        "Grouped Spearman matrices:",
        *(f"- {name}" for name in grouped_files[:100]),
    ]
    if len(grouped_files) > 100:
        report.append(f"- ... {len(grouped_files) - 100} more")
    (out_dir / "correlation_report.md").write_text("\n".join(report) + "\n")
    print(f"Wrote correlation outputs to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
