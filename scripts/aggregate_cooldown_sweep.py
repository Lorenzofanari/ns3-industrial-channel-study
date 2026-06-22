#!/usr/bin/env python3
"""Aggregate the EXISTING cooldown-length sweep into a manuscript table + figure.

This script performs NO new simulation. It reads already-generated ns-3
scheduler-harness CSV outputs and aggregates the empirical cooldown-length sweep
T_cd in {0, 19, 38, 76, 152, 304} OFDM symbols for the diagnostic broadband
reactive-jamming cell (MCS 3), plus a multi-deadline narrowband view.

Inputs (read-only):
  results/coherence_time_experiment/full/aggregate.csv   (headline broadband cell)
  results/deadline_sensitivity/results.csv               (multi-deadline narrowband)

Outputs (written under results/cooldown_sweep_analysis/):
  cooldown_sweep_broadband_mcs3.csv / .md
  deadline_miss_vs_cooldown_narrowband.csv / .md
  fig_cooldown_reliability_latency.pdf / .png
  PROVENANCE.txt

Claim-boundary rules enforced here:
  * Zero observed losses are reported with a finite-campaign upper bound
    (rule-of-three / Clopper-Pearson), never as "zero loss probability".
  * All numbers are aggregated across the three paper seeds with seed std.
  * Results are labelled as observed in the scheduler-harness matrix.
"""
from __future__ import annotations

import argparse
import math
import platform
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

try:
    from scipy.stats import beta as _beta  # type: ignore

    _HAVE_SCIPY = True
except Exception:  # pragma: no cover
    _HAVE_SCIPY = False

# ---- canonical diagnostic slice (headline broadband cell) -------------------
HEADLINE = dict(
    mcs=3,
    jammer_ru_mode="broadband_reactive",
    jammer_burst_ms=4,
    jammer_interval_ms=20,
    jammer_phase_ms=0,
    deadline_ms=10,
    coherence_time_ms=5,
    channel_correlation_model="block",
    payload_bits=128,
    distance_m=3,
)
COOLDOWNS = [0, 19, 38, 76, 152, 304]
PAPER_SEEDS = [20260507, 20260508, 20260509]
SYMBOL_US = 16.0  # OFDM symbol duration used by the harness (T_cd[ms] = sym*16/1000)


def clopper_pearson(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Two-sided Clopper-Pearson interval for a binomial proportion."""
    if n == 0:
        return (float("nan"), float("nan"))
    if _HAVE_SCIPY:
        lo = 0.0 if k == 0 else _beta.ppf(alpha / 2, k, n - k + 1)
        hi = 1.0 if k == n else _beta.ppf(1 - alpha / 2, k + 1, n - k)
        return (float(lo), float(hi))
    # Wilson fallback
    z = 1.959963984540054
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def rule_of_three_upper(n: int, conf: float = 0.95) -> float:
    """One-sided upper bound on an unobserved-event probability (p_hat = 0)."""
    if n <= 0:
        return float("nan")
    return 1.0 - (1.0 - conf) ** (1.0 / n)


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def load_headline(repo: Path) -> pd.DataFrame:
    path = repo / "results/coherence_time_experiment/full/aggregate.csv"
    df = pd.read_csv(path, low_memory=False)
    m = (
        (_num(df["mcs"]) == HEADLINE["mcs"])
        & (df["jammer_ru_mode"] == HEADLINE["jammer_ru_mode"])
        & (_num(df["jammer_burst_ms"]) == HEADLINE["jammer_burst_ms"])
        & (_num(df["jammer_interval_ms"]) == HEADLINE["jammer_interval_ms"])
        & (_num(df["jammer_phase_ms"]) == HEADLINE["jammer_phase_ms"])
        & (_num(df["deadline_ms"]) == HEADLINE["deadline_ms"])
        & (_num(df["coherence_time_ms"]) == HEADLINE["coherence_time_ms"])
        & (df["channel_correlation_model"] == HEADLINE["channel_correlation_model"])
        & (_num(df["payload_bits"]) == HEADLINE["payload_bits"])
        & (_num(df["distance_m"]) == HEADLINE["distance_m"])
    )
    return df.loc[m].copy(), path


def aggregate_headline(df: pd.DataFrame) -> pd.DataFrame:
    metrics = {
        "pdr": "pdr",
        "pdr_jammer_on": "pdr_jammer_on",
        "p95_latency_ms": "p95_latency_ms",
        "p99_latency_ms": "p99_latency_ms",
        "worst_case_latency_ms": "worst_case_latency_ms",
        "deadline_miss_ratio": "deadline_miss_ratio",
        "plr": "plr",
    }
    rows = []
    for (policy, cd), g in df.groupby(["policy", df["cooldown_symbols"].astype(int)]):
        n_seeds = g["seed"].nunique()
        rec = {
            "policy": policy,
            "cooldown_symbols": int(cd),
            "cooldown_ms": round(int(cd) * SYMBOL_US / 1000.0, 4),
            "n_seeds": int(n_seeds),
        }
        # pooled binomial for PDR CI
        tx = int(_num(g["transmitted_packets"]).sum())
        pdr_mean = float(_num(g["pdr"]).mean())
        k = int(round(pdr_mean * (tx / max(n_seeds, 1)) * n_seeds)) if tx else 0
        k = int(round(pdr_mean * tx))
        lo, hi = clopper_pearson(k, tx)
        rec["pdr_tx_pooled"] = tx
        rec["pdr_cp_lo"] = round(lo, 6)
        rec["pdr_cp_hi"] = round(hi, 6)
        for out, col in metrics.items():
            vals = _num(g[col])
            rec[f"{out}_mean"] = round(float(vals.mean()), 6)
            rec[f"{out}_std"] = round(float(vals.std(ddof=0)), 6)
        # finite-campaign upper bound when a loss metric is exactly zero (observed)
        if rec["deadline_miss_ratio_mean"] == 0.0:
            rec["deadline_miss_ub_ro3"] = round(rule_of_three_upper(tx), 8)
        else:
            rec["deadline_miss_ub_ro3"] = ""
        if rec["plr_mean"] == 0.0:
            rec["plr_ub_ro3"] = round(rule_of_three_upper(tx), 8)
        else:
            rec["plr_ub_ro3"] = ""
        rows.append(rec)
    out = pd.DataFrame(rows).sort_values(["policy", "cooldown_symbols"]).reset_index(drop=True)
    return out


def load_narrowband_deadline(repo: Path) -> tuple[pd.DataFrame, Path]:
    path = repo / "results/deadline_sensitivity/results.csv"
    df = pd.read_csv(path, low_memory=False)
    m = (_num(df["mcs"]) == 3) & (_num(df["num_users"]) == 6) & (_num(df["payload_bits"]) == 128)
    df = df.loc[m].copy()
    return df, path


def aggregate_narrowband_deadline(df: pd.DataFrame, deadlines=(1, 5, 10)) -> pd.DataFrame:
    df = df[_num(df["deadline_ms"]).isin(deadlines)].copy()
    rows = []
    for (policy, cd, dl), g in df.groupby(
        ["policy", df["cooldown_symbols"].astype(int), _num(df["deadline_ms"]).astype(int)]
    ):
        tx = int(_num(g["transmitted_packets"]).sum())
        dm = _num(g["deadline_miss_ratio"])
        rec = {
            "policy": policy,
            "cooldown_symbols": int(cd),
            "deadline_ms": int(dl),
            "n_seeds": int(g["seed"].nunique()),
            "deadline_miss_mean": round(float(dm.mean()), 6),
            "deadline_miss_std": round(float(dm.std(ddof=0)), 6),
        }
        if rec["deadline_miss_mean"] == 0.0:
            rec["deadline_miss_ub_ro3"] = round(rule_of_three_upper(tx), 8)
        else:
            rec["deadline_miss_ub_ro3"] = ""
        rows.append(rec)
    return pd.DataFrame(rows).sort_values(["policy", "deadline_ms", "cooldown_symbols"]).reset_index(drop=True)


def write_md_table(df: pd.DataFrame, path: Path, title: str, note: str) -> None:
    cols = list(df.columns)
    lines = [f"# {title}", "", note, ""]
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["---"] * len(cols)) + "|")
    for _, r in df.iterrows():
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def make_figure(agg: pd.DataFrame, out_dir: Path) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))

    sweep_policies = ["cooldown_only", "cooldown_plus_retarget"]
    # Left panel: reliability (PDR & PDR_on) vs cooldown length
    ax = axes[0]
    for pol in sweep_policies:
        d = agg[(agg["policy"] == pol) & (agg["cooldown_symbols"].isin(COOLDOWNS))].sort_values(
            "cooldown_symbols"
        )
        if d.empty:
            continue
        ax.errorbar(
            d["cooldown_symbols"], d["pdr_mean"], yerr=d["pdr_std"],
            marker="o", capsize=3, label=f"{pol} PDR",
        )
        ax.errorbar(
            d["cooldown_symbols"], d["pdr_jammer_on_mean"], yerr=d["pdr_jammer_on_std"],
            marker="s", linestyle="--", capsize=3, label=f"{pol} PDR_on",
        )
    # baseline reference (cooldown=0 baseline_pf)
    base = agg[(agg["policy"] == "baseline_pf")]
    if not base.empty:
        ax.axhline(float(base["pdr_mean"].iloc[0]), color="grey", linestyle=":", label="Baseline-PF PDR")
    ax.axvline(76, color="black", linestyle="-", alpha=0.3)
    ax.set_xlabel("Cooldown length $T_{cd}$ (OFDM symbols)")
    ax.set_ylabel("Packet delivery ratio")
    ax.set_title("(a) Reliability vs cooldown length")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")

    # Right panel: latency tail (worst-case) vs cooldown length
    ax = axes[1]
    for pol in sweep_policies:
        d = agg[(agg["policy"] == pol) & (agg["cooldown_symbols"].isin(COOLDOWNS))].sort_values(
            "cooldown_symbols"
        )
        if d.empty:
            continue
        ax.errorbar(
            d["cooldown_symbols"], d["worst_case_latency_ms_mean"],
            yerr=d["worst_case_latency_ms_std"], marker="o", capsize=3,
            label=f"{pol} worst-case",
        )
    ax.axvline(76, color="black", linestyle="-", alpha=0.3, label="$T_{cd}=76$")
    ax.set_xlabel("Cooldown length $T_{cd}$ (OFDM symbols)")
    ax.set_ylabel("Worst-case burst latency (ms)")
    ax.set_title("(b) Latency tail vs cooldown length")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")

    fig.suptitle(
        "Cooldown-length sweep (MCS 3, broadband reactive jammer, 4 ms/20 ms, 10 ms deadline, "
        "$T_c$=5 ms; observed in the scheduler-harness matrix, 3 seeds)",
        fontsize=9,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    pdf = out_dir / "fig_cooldown_reliability_latency.pdf"
    png = out_dir / "fig_cooldown_reliability_latency.png"
    fig.savefig(pdf)
    fig.savefig(png, dpi=150)
    plt.close(fig)
    return pdf


def git_commit(repo: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-c", "safe.directory=*", "log", "-1", "--format=%H"],
            cwd=repo, capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="/home/lorenzofanari/ns3-industrial-channel-study")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    repo = Path(args.repo)
    out_dir = Path(args.out) if args.out else repo / "results/cooldown_sweep_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    head_df, head_src = load_headline(repo)
    if head_df.empty:
        print("ERROR: headline slice empty; check filters.", file=sys.stderr)
        return 1
    agg = aggregate_headline(head_df)
    agg.to_csv(out_dir / "cooldown_sweep_broadband_mcs3.csv", index=False)
    write_md_table(
        agg, out_dir / "cooldown_sweep_broadband_mcs3.md",
        "Cooldown-length sweep - broadband reactive, MCS 3 (headline diagnostic cell)",
        f"Source: `{head_src.relative_to(repo)}`. Slice: MCS 3, broadband_reactive, burst 4 ms / "
        f"interval 20 ms, phase 0, deadline 10 ms, coherence 5 ms (block), 128 bit, 3 m. "
        f"Seeds {PAPER_SEEDS}. Means +/- seed std (ddof=0). `pdr_cp_*` = pooled Clopper-Pearson 95% CI. "
        f"`*_ub_ro3` = finite-campaign upper bound for exactly-zero observed losses (never reported as zero "
        f"probability). NO new simulation; aggregation only.",
    )

    nb_df, nb_src = load_narrowband_deadline(repo)
    nb_agg = aggregate_narrowband_deadline(nb_df)
    nb_agg.to_csv(out_dir / "deadline_miss_vs_cooldown_narrowband.csv", index=False)
    write_md_table(
        nb_agg, out_dir / "deadline_miss_vs_cooldown_narrowband.md",
        "Deadline-miss ratio vs cooldown length and deadline - narrowband reactive, MCS 3",
        f"Source: `{nb_src.relative_to(repo)}`. Slice: MCS 3, narrowband_reactive, 6 users, 128 bit. "
        f"Deadlines D in {{1,5,10}} ms. Means +/- seed std. `*_ub_ro3` = rule-of-three upper bound for "
        f"zero observed misses. NO new simulation; aggregation only.",
    )

    fig = make_figure(agg, out_dir)

    prov = out_dir / "PROVENANCE.txt"
    prov.write_text(
        "Cooldown-length sweep aggregation (no new simulation)\n"
        f"git_commit: {git_commit(repo)}\n"
        f"python: {platform.python_version()}\n"
        f"numpy: {np.__version__}; scipy_available: {_HAVE_SCIPY}; matplotlib: {matplotlib.__version__}\n"
        f"inputs:\n  {head_src}\n  {nb_src}\n"
        f"seeds: {PAPER_SEEDS}\n"
        f"headline_slice: {HEADLINE}\n"
        f"cooldown_symbols: {COOLDOWNS}\n"
        "command: python3 scripts/aggregate_cooldown_sweep.py\n",
        encoding="utf-8",
    )

    print("Wrote:")
    for p in sorted(out_dir.glob("*")):
        print("  ", p)
    print("\nHeadline aggregate (PDR / PDR_on / worst-case latency by policy,cooldown):")
    show = agg[[
        "policy", "cooldown_symbols", "cooldown_ms", "pdr_mean", "pdr_std",
        "pdr_cp_lo", "pdr_cp_hi", "pdr_jammer_on_mean", "worst_case_latency_ms_mean",
        "deadline_miss_ratio_mean", "deadline_miss_ub_ro3",
    ]]
    with pd.option_context("display.max_rows", None, "display.width", 200):
        print(show.to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
