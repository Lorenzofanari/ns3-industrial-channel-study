#!/usr/bin/env python3
"""
Regenerate the OJ-IES paper figures from results/paper_v2/results.csv with a
clean, colorblind-safe matplotlib styling.

Outputs both PNG (300 dpi, for screen and review) and PDF (vector, for the
camera-ready PDF) under paper/figs/.

Conventions:
  * Paul Tol's "bright" qualitative palette for the three policies
  * Distinct line styles per policy:
        S4 Baseline-PF  : blue,  dashed (--)
        S8 RTX-Assist   : orange, dash-dot (-.)
        S9 Realloc      : red,   solid (-) and thicker
  * Distinct markers for the three MCSs
  * Legend with frame, large fontsize, deterministic position
  * Grid on with alpha=0.35 to keep eyes on the curves
  * Log-y when the metric spans more than 2 orders of magnitude
  * NaN-as-empty CSV cells preserved (do NOT impute zero)

Reproducibility: this script is bound to commit `git_commit` of the CSV
rows it consumes. Re-running with a different CSV produces a different
figure set but does not change the script itself.

Usage:
    cd ns3-industrial-channel-study
    python3 paper/regen_figures.py

If matplotlib complains about MPLCONFIGDIR, set it to a writable path:
    MPLCONFIGDIR=/tmp/mplconfig python3 paper/regen_figures.py
"""

from __future__ import annotations

import os
import sys
import math
import pathlib
import warnings

# Silence the rcParams "FixedLocator" warning that matplotlib emits when we
# set explicit minor ticks on log axes; the warning is cosmetic.
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import LogLocator, NullFormatter, ScalarFormatter

# --- Paths --------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = REPO_ROOT / "results" / "paper_v2" / "results.csv"
OUT_DIR = REPO_ROOT / "paper" / "figs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# --- Style --------------------------------------------------------------
# Paul Tol's "bright" qualitative palette - colorblind-safe.
TOL_BRIGHT = {
    "blue":    "#4477AA",
    "cyan":    "#66CCEE",
    "green":   "#228833",
    "yellow":  "#CCBB44",
    "red":     "#EE6677",
    "purple":  "#AA3377",
    "grey":    "#BBBBBB",
}

# Mapping policy -> (color, linestyle, marker, zorder)
POLICY_STYLE = {
    "S4": dict(color=TOL_BRIGHT["blue"],   ls="--",  marker="o", lw=1.8, ms=5,
               label="S4 / Baseline-PF"),
    "S8": dict(color=TOL_BRIGHT["yellow"], ls="-.",  marker="s", lw=1.8, ms=5,
               label="S8 / RTX-Assist"),
    "S9": dict(color=TOL_BRIGHT["red"],    ls="-",   marker="^", lw=2.4, ms=6,
               label="S9 / Realloc"),
}

# Mapping MCS -> (color, marker)
MCS_STYLE = {
    0: dict(color=TOL_BRIGHT["blue"],  marker="o", label="MCS 0 (BPSK 1/2)"),
    1: dict(color=TOL_BRIGHT["green"], marker="s", label="MCS 1 (QPSK 1/2)"),
    3: dict(color=TOL_BRIGHT["red"],   marker="^", label="MCS 3 (16-QAM 1/2)"),
}

# Mapping channel model -> (color)
CHANNEL_LABEL = {
    "cm8_rayleigh":                  "CM8 industrial NLOS (proxy)",
    "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE": "QuaDRiGa trace (synthetic placeholder)",
}

# Mapping jammer mode -> (color)
JAMMER_STYLE = {
    "none":     dict(color=TOL_BRIGHT["green"], ls="-",  marker="o", label="No jammer"),
    "constant": dict(color=TOL_BRIGHT["red"],   ls="-",  marker="x", label="Constant jammer"),
    "reactive": dict(color=TOL_BRIGHT["purple"], ls="--", marker="s", label="Reactive jammer (\u03B4=0.20)"),
}

GLOBAL_RC = {
    "font.family":   "serif",
    "font.size":     11,
    "axes.titlesize": 12,
    "axes.labelsize": 11,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "legend.frameon":   True,
    "legend.framealpha":0.92,
    "legend.edgecolor": "#444444",
    "axes.grid":     True,
    "grid.alpha":    0.35,
    "grid.linestyle":"--",
    "axes.linewidth":0.9,
    "lines.linewidth":1.8,
    "figure.figsize":(7.2, 4.4),
    "figure.dpi":    110,
    "savefig.dpi":   300,
    "savefig.bbox":  "tight",
    "pdf.fonttype":  42,   # editable text
    "ps.fonttype":   42,
}
plt.rcParams.update(GLOBAL_RC)


# --- Helpers ------------------------------------------------------------
def save(fig, name: str) -> None:
    """Write both PNG and PDF for the same figure."""
    png = OUT_DIR / f"{name}.png"
    pdf = OUT_DIR / f"{name}.pdf"
    fig.savefig(png)
    fig.savefig(pdf)
    print(f"  saved {png.relative_to(REPO_ROOT)} (+pdf)")
    plt.close(fig)


def policy_paper_label(scenario: str) -> str:
    return {"S4": "Baseline-PF", "S8": "RTX-Assist", "S9": "Realloc"}.get(scenario, scenario)


def aggregate(
    df: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    agg: str = "mean",
) -> pd.DataFrame:
    """Group + aggregate but preserve NaN explicitly."""
    return df.groupby(group_cols, dropna=False)[value_col].agg(agg).reset_index()


def epsfloor(x, eps=1e-6):
    return np.where(x <= 0, eps, x)


# --- Load CSV -----------------------------------------------------------
print(f"Reading {CSV_PATH.relative_to(REPO_ROOT)} ...")
df = pd.read_csv(CSV_PATH, low_memory=False)
df.columns = [c.strip() for c in df.columns]
print(f"  rows={len(df):,}, cols={len(df.columns)}")

# Sanity normalisations
df["scenario"] = df["scenario"].astype(str).str.upper().str.strip()
df["jammer_mode"] = df["jammer_mode"].astype(str).str.strip()
df["channel_model"] = df["channel_model"].astype(str).str.strip()


# =======================================================================
# Figure 1 - PER waterfall vs target SNR, CM8 only (no jammer)
# QuaDRiGa equivalent lives in fig_per_waterfall_quadriga_appendix
# =======================================================================
def _per_waterfall_panel(ax, channel: str) -> None:
    sub = df[(df["jammer_mode"] == "none") & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) & (df["channel_model"] == channel)].copy()
    for mcs in (0, 1, 3):
        for scen in ("S4", "S8", "S9"):
            cell = sub[(sub["scenario"] == scen) & (sub["mcs"] == mcs)]
            if cell.empty: continue
            g = aggregate(cell, ["target_snr_db"], "per")
            style = POLICY_STYLE[scen].copy()
            style["color"] = MCS_STYLE[mcs]["color"]
            style["marker"] = MCS_STYLE[mcs]["marker"]
            style["label"] = f"MCS {mcs} - {policy_paper_label(scen)}"
            style["ms"] = 4
            style["mfc"] = "white"
            style["mew"] = 0.9
            ax.plot(g["target_snr_db"], epsfloor(g["per"]), **style)
    ax.set_yscale("log")
    ax.set_ylim(1e-5, 1.0)
    ax.set_xlim(0, 22)
    ax.set_xlabel("Target SNR [dB]")
    ax.grid(True, which="both", alpha=0.3)
    ax.yaxis.set_major_locator(LogLocator(base=10.0, numticks=10))
    ax.yaxis.set_minor_formatter(NullFormatter())


def fig_per_waterfall():
    """Main-paper Figure 1: CM8 industrial NLOS PER waterfall only.
    QuaDRiGa side-by-side panel has been moved to the supplementary
    figure fig_per_waterfall_quadriga_appendix to avoid presenting
    placeholder-trace results in the main figures (reviewer M3)."""
    fig, ax = plt.subplots(figsize=(7.4, 4.6))
    _per_waterfall_panel(ax, "cm8_rayleigh")
    ax.set_ylabel("Packet Error Ratio (PER)")
    ax.set_title("PER waterfall on the CM8 industrial NLOS proxy"
                 " (no jammer, 128-bit, 3 m)")
    ax.legend(loc="lower left", ncol=3, fontsize=8, columnspacing=0.9,
              handletextpad=0.4)
    save(fig, "fig_per_waterfall")


def fig_per_waterfall_quadriga_appendix():
    """Supplementary Figure: side-by-side CM8 vs QuaDRiGa-placeholder
    PER waterfall, explicitly flagged as illustrative."""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True)
    for ax, channel in zip(axes, ("cm8_rayleigh",
                                  "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE")):
        _per_waterfall_panel(ax, channel)
        ax.set_title(CHANNEL_LABEL[channel])
    axes[0].set_ylabel("Packet Error Ratio (PER)")
    handles, labels = axes[0].get_legend_handles_labels()
    by_label = dict(zip(labels, handles))
    fig.legend(by_label.values(), by_label.keys(),
               loc="lower center", ncol=3, bbox_to_anchor=(0.5, -0.02),
               frameon=True, fontsize=9)
    fig.text(0.5, -0.07,
             r"$^{\dagger}$ QuaDRiGa rows use the documented synthetic "
             "placeholder trace; the side-by-side is illustrative only.",
             ha="center", va="top", fontsize=8, color="#555555", style="italic")
    fig.subplots_adjust(bottom=0.25)
    save(fig, "fig_per_waterfall_quadriga_appendix")


# =======================================================================
# Figure 2 - PDR vs target SNR (no jammer)
# =======================================================================
def fig_pdr_vs_snr():
    sub = df[(df["jammer_mode"] == "none") & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) & (df["channel_model"] == "cm8_rayleigh")].copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for scen in ("S4", "S8", "S9"):
        for mcs in (0, 1, 3):
            cell = sub[(sub["scenario"] == scen) & (sub["mcs"] == mcs)]
            if cell.empty: continue
            g = aggregate(cell, ["target_snr_db"], "pdr")
            style = POLICY_STYLE[scen].copy()
            style["color"] = MCS_STYLE[mcs]["color"]
            style["marker"] = MCS_STYLE[mcs]["marker"]
            style["label"] = f"MCS {mcs} - {policy_paper_label(scen)}"
            style["ms"] = 4
            style["mfc"] = "white"
            style["mew"] = 0.9
            ax.plot(g["target_snr_db"], g["pdr"], **style)
    ax.set_xlabel("Target SNR [dB]")
    ax.set_ylabel("Packet Delivery Ratio (PDR)")
    ax.set_xlim(0, 22)
    ax.set_ylim(-0.02, 1.02)
    ax.set_title("PDR vs. target SNR (CM8 NLOS, no jammer, 128-bit, 3 m)")
    ax.legend(loc="lower right", ncol=3, fontsize=8, columnspacing=0.9, handletextpad=0.5)
    save(fig, "fig_pdr_vs_snr")


# =======================================================================
# Figure 3 - Cross-scenario averaged PLR comparison
# =======================================================================
def fig_scenario_comparison():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["jammer_mode"].isin(["none", "reactive"]))].copy()
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6), sharey=True)
    for ax, jam in zip(axes, ("none", "reactive")):
        for scen in ("S4", "S8", "S9"):
            cell = sub[(sub["scenario"] == scen) & (sub["jammer_mode"] == jam)]
            if cell.empty: continue
            g = aggregate(cell, ["target_snr_db"], "plr")
            style = POLICY_STYLE[scen].copy()
            style["mfc"] = "white"
            style["mew"] = 0.9
            style["ms"] = 4
            ax.plot(g["target_snr_db"], epsfloor(g["plr"]), **style)
        ax.set_yscale("log")
        ax.set_xlim(0, 22)
        ax.set_ylim(1e-5, 1.0)
        ax.set_xlabel("Target SNR [dB]")
        ax.set_title({"none": "No jammer", "reactive": "Reactive jammer (\u03B4=0.20)"}[jam])
        ax.grid(True, which="both", alpha=0.3)
    axes[0].set_ylabel("PLR (averaged over MCS / payload / distance)")
    axes[0].legend(loc="lower left", fontsize=9)
    save(fig, "fig_scenario_comparison")


# =======================================================================
# Figure 4 - p95 latency vs target SNR
# =======================================================================
def fig_p95_latency_vs_snr():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["mcs"] == 0) & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) &
             (df["jammer_mode"].isin(["none", "reactive"]))].copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for scen in ("S4", "S8", "S9"):
        for jam, ls_suffix in (("none", ""), ("reactive", " (jammer)")):
            cell = sub[(sub["scenario"] == scen) & (sub["jammer_mode"] == jam)]
            if cell.empty: continue
            g = aggregate(cell, ["target_snr_db"], "p95_delay_s")
            style = POLICY_STYLE[scen].copy()
            style["label"] = f"{policy_paper_label(scen)}{ls_suffix}"
            if jam == "reactive":
                style["ls"] = ":"
                style["lw"] = 1.5
            style["ms"] = 4
            style["mfc"] = "white"
            style["mew"] = 0.9
            ax.plot(g["target_snr_db"], g["p95_delay_s"] * 1000.0, **style)
    ax.set_xlabel("Target SNR [dB]")
    ax.set_ylabel("p95 end-to-end latency [ms]")
    ax.set_xlim(0, 22)
    ax.set_title("p95 latency vs. target SNR (CM8, MCS 0, 128-bit, 3 m)")
    ax.legend(loc="best", ncol=2, fontsize=8)
    save(fig, "fig_p95_latency_vs_snr")


# =======================================================================
# Figure 5 - PDR jammer-ON vs jammer power
# =======================================================================
def fig_pdr_jammer_on():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["mcs"] == 0) & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) &
             (df["jammer_mode"].isin(["constant", "reactive"]))].copy()
    sub["pdr_jammer_on"] = pd.to_numeric(sub["pdr_jammer_on"], errors="coerce")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for scen in ("S4", "S8", "S9"):
        for jam in ("constant", "reactive"):
            cell = sub[(sub["scenario"] == scen) & (sub["jammer_mode"] == jam)]
            if cell.empty: continue
            g = aggregate(cell, ["jammer_power_dbm"], "pdr_jammer_on")
            style = POLICY_STYLE[scen].copy()
            style["label"] = f"{policy_paper_label(scen)} - {jam}"
            if jam == "constant":
                style["ls"] = ":"
                style["lw"] = 1.5
            style["ms"] = 7
            style["mfc"] = "white"
            style["mew"] = 1.1
            ax.plot(g["jammer_power_dbm"], g["pdr_jammer_on"], **style)
    ax.set_xlabel("Jammer transmit power [dBm]")
    ax.set_ylabel(r"Conditional PDR$_{\mathrm{jammer-ON}}$")
    ax.set_xticks([10, 20])
    ax.set_ylim(-0.02, 1.05)
    ax.set_title("Jammer-ON PDR vs. jammer power (CM8, MCS 0, 128-bit, 3 m)")
    ax.legend(loc="center right", ncol=2, fontsize=8)
    save(fig, "fig_pdr_jammer_on")


# =======================================================================
# Figure 6 - Robustness ratio vs jammer power
# =======================================================================
def fig_robustness_vs_jammer():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["mcs"] == 0) & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) &
             (df["jammer_mode"].isin(["constant", "reactive"]))].copy()
    sub["robustness_ratio"] = pd.to_numeric(sub["robustness_ratio"], errors="coerce")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for scen in ("S4", "S8", "S9"):
        for jam in ("constant", "reactive"):
            cell = sub[(sub["scenario"] == scen) & (sub["jammer_mode"] == jam)]
            if cell.empty: continue
            g = aggregate(cell, ["jammer_power_dbm"], "robustness_ratio")
            style = POLICY_STYLE[scen].copy()
            style["label"] = f"{policy_paper_label(scen)} - {jam}"
            if jam == "constant":
                style["ls"] = ":"
                style["lw"] = 1.5
            style["ms"] = 7
            style["mfc"] = "white"
            style["mew"] = 1.1
            ax.plot(g["jammer_power_dbm"], g["robustness_ratio"], **style)
    ax.axhline(1.0, color=TOL_BRIGHT["grey"], lw=1.0, ls="-", zorder=0,
               label="No degradation")
    ax.set_xlabel("Jammer transmit power [dBm]")
    ax.set_ylabel(r"Robustness ratio $\mathrm{PDR}_{\mathrm{jam}}/\mathrm{PDR}_{\mathrm{clean}}$")
    ax.set_xticks([10, 20])
    ax.set_ylim(-0.02, 1.10)
    ax.set_title("Robustness ratio vs. jammer power")
    ax.legend(loc="best", ncol=2, fontsize=8)
    save(fig, "fig_robustness_vs_jammer")


# =======================================================================
# Figure 7 - Mean recovery time vs jammer power
# =======================================================================
def fig_recovery_vs_jammer():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["mcs"] == 0) & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) &
             (df["jammer_mode"] == "reactive")].copy()
    sub["mean_recovery_time_s"] = pd.to_numeric(sub["mean_recovery_time_s"], errors="coerce")
    sub["p95_recovery_time_s"] = pd.to_numeric(sub.get("p95_recovery_time_s", np.nan), errors="coerce")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for scen in ("S4", "S8", "S9"):
        cell = sub[sub["scenario"] == scen]
        if cell.empty: continue
        g_mean = aggregate(cell, ["jammer_power_dbm"], "mean_recovery_time_s")
        g_p95 = aggregate(cell, ["jammer_power_dbm"], "p95_recovery_time_s")
        style = POLICY_STYLE[scen].copy()
        style["label"] = f"{policy_paper_label(scen)} - mean"
        style["ms"] = 7
        style["mfc"] = "white"
        style["mew"] = 1.1
        ax.plot(g_mean["jammer_power_dbm"], g_mean["mean_recovery_time_s"] * 1000.0, **style)
        style2 = dict(color=style["color"], ls=":", marker=style["marker"],
                      lw=1.3, ms=6, mfc="white", mew=0.9,
                      label=f"{policy_paper_label(scen)} - p95")
        ax.plot(g_p95["jammer_power_dbm"], g_p95["p95_recovery_time_s"] * 1000.0, **style2)
    ax.axhline(5.0, color=TOL_BRIGHT["grey"], lw=1.0, ls="--", zorder=0,
               label="Half packet interval (5 ms)")
    ax.set_xlabel("Jammer transmit power [dBm]")
    ax.set_ylabel("Recovery time after reactive burst [ms]")
    ax.set_xticks([10, 20])
    ax.set_title("Mean and p95 recovery time vs. reactive-jammer power")
    ax.legend(loc="best", ncol=2, fontsize=8)
    save(fig, "fig_recovery_vs_jammer")


# =======================================================================
# Figure 8 - Burst-induced loss ratio vs jammer power
# =======================================================================
def fig_burst_induced_loss():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["mcs"] == 0) & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) &
             (df["jammer_mode"] == "reactive")].copy()
    sub["burst_induced_loss_ratio"] = pd.to_numeric(sub["burst_induced_loss_ratio"], errors="coerce")
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    width = 2.0
    powers = sorted(sub["jammer_power_dbm"].unique())
    x = np.arange(len(powers)) * (len(POLICY_STYLE) * width + 2)
    for i, scen in enumerate(("S4", "S8", "S9")):
        g = aggregate(sub[sub["scenario"] == scen], ["jammer_power_dbm"],
                      "burst_induced_loss_ratio")
        offset = (i - 1) * width
        vals = [float(g[g["jammer_power_dbm"] == p]["burst_induced_loss_ratio"].iloc[0])
                if not g[g["jammer_power_dbm"] == p].empty else 0.0
                for p in powers]
        style = POLICY_STYLE[scen]
        ax.bar(x + offset, vals, width=width * 0.9,
               color=style["color"], edgecolor="black", lw=0.7,
               label=policy_paper_label(scen))
    ax.set_xticks(x)
    ax.set_xticklabels([f"{int(p)} dBm" for p in powers])
    ax.set_ylabel("Burst-induced loss ratio")
    ax.set_xlabel("Reactive jammer transmit power")
    ax.set_ylim(0, 1.05)
    ax.set_title("Burst-induced loss ratio (lost during jammer-ON / total losses)")
    ax.legend(loc="best", fontsize=9)
    ax.set_axisbelow(True)
    save(fig, "fig_burst_induced_loss")


# =======================================================================
# Figure 9 - PER vs SNR under jamming (MCS 0)
# =======================================================================
def fig_per_under_jamming():
    sub = df[(df["channel_model"] == "cm8_rayleigh") &
             (df["mcs"] == 0) & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) &
             (df["scenario"] == "S9")].copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for jam in ("none", "reactive", "constant"):
        powers_to_plot = [0] if jam == "none" else [10, 20]
        for p in powers_to_plot:
            cell = sub[(sub["jammer_mode"] == jam) & (sub["jammer_power_dbm"] == p)]
            if cell.empty: continue
            g = aggregate(cell, ["target_snr_db"], "per")
            style = JAMMER_STYLE[jam].copy()
            style["label"] = (f"{style['label']}" if jam == "none"
                              else f"{style['label']}, {p} dBm")
            style["ms"] = 4
            style["mfc"] = "white"
            style["mew"] = 0.9
            style["lw"] = 1.8 if jam == "none" else (2.4 if p == 20 else 1.5)
            ax.plot(g["target_snr_db"], epsfloor(g["per"]), **style)
    ax.set_yscale("log")
    ax.set_xlabel("Target SNR [dB]")
    ax.set_ylabel("PER (S9 / Realloc, MCS 0, 128-bit, 3 m)")
    ax.set_xlim(0, 22)
    ax.set_ylim(1e-5, 1.0)
    ax.set_title("PER vs. target SNR for the S9 policy under three jamming regimes")
    ax.legend(loc="lower left", fontsize=9)
    ax.grid(True, which="both", alpha=0.3)
    save(fig, "fig_per_under_jamming")


# =======================================================================
# Figure 11 - Case study: closed-loop motion-control under reactive jamming
# =======================================================================
def fig_case_study_motion_control():
    """Two-panel case-study figure for the §VI case-study text.
    LEFT  : per-policy latency percentiles vs use-case deadline budgets
    RIGHT : deadline-miss ratio (= probability_exceeding_safety_deadline)
            decomposed into "delivered late" and "lost" components.
    All from the cell: CM8, MCS 0, 128-bit, 3 m, target SNR 20 dB,
    reactive jammer 10 dBm. Three seeds averaged. The simulator
    deadline is 10 ms (configured in the campaign).
    """
    sub = df[(df["channel_model"] == "cm8_rayleigh") & (df["mcs"] == 0) &
             (df["payload_bits"] == 128) & (df["distance_m"] == 3) &
             (df["target_snr_db"] == 20) & (df["jammer_mode"] == "reactive") &
             (df["jammer_power_dbm"] == 10)].copy()
    # Aggregate (mean across seeds; PDR jammer-on for the "lost" share)
    agg = sub.groupby("scenario", as_index=False).agg(
        median_delay_s=("median_delay_s", "mean"),
        p95_delay_s=("p95_delay_s", "mean"),
        p99_delay_s=("p99_delay_s", "mean"),
        worst_case_burst_latency_s=("worst_case_burst_latency_s", "mean"),
        deadline_miss_ratio=("probability_exceeding_safety_deadline", "mean"),
        plr_total=("plr", "mean"),
    )
    agg = agg.set_index("scenario").loc[["S4", "S8", "S9"]].reset_index()

    fig, (axL, axR) = plt.subplots(1, 2, figsize=(11.5, 4.8),
                                   gridspec_kw=dict(width_ratios=[1.5, 1.0]))

    # ---- LEFT panel : latency percentiles -------------------------------
    metrics = [
        ("median_delay_s",            "median", "o"),
        ("p95_delay_s",               "p95",    "s"),
        ("p99_delay_s",               "p99",    "^"),
        ("worst_case_burst_latency_s","worst",  "D"),
    ]
    x = np.arange(len(agg))
    width = 0.18
    for i, (col, lbl, mk) in enumerate(metrics):
        vals = agg[col].values * 1000.0  # to ms
        offset = (i - 1.5) * width
        for j, scen in enumerate(agg["scenario"]):
            colour = POLICY_STYLE[scen]["color"]
            axL.bar(x[j] + offset, vals[j], width=width * 0.95,
                    color=colour, edgecolor="black", lw=0.5,
                    label=lbl if j == 0 else None)
        # Marker on top of each bar (same colour, white face)
        for j, scen in enumerate(agg["scenario"]):
            axL.scatter([x[j] + offset], [agg[col].iloc[j] * 1000.0],
                        marker=mk, s=22,
                        facecolor="white",
                        edgecolor="black", lw=0.9, zorder=4)

    # Deadline budgets from Table III: motion-control 1 ms, supervisor 2 ms,
    # mobile-robot 10 ms, process-control 50 ms.
    deadlines = [
        (1.0,  TOL_BRIGHT["red"],    "Motion control (1\u202Fms)"),
        (2.0,  TOL_BRIGHT["purple"], "PROFIsafe supervisor (2\u202Fms)"),
        (10.0, TOL_BRIGHT["yellow"], "Mobile-robot / process (10\u202Fms)"),
        (50.0, TOL_BRIGHT["green"],  "Process control (50\u202Fms)"),
    ]
    for dl, col, lbl in deadlines:
        axL.axhline(dl, color=col, lw=1.0, ls=":", alpha=0.85, zorder=0)
        axL.text(-0.45, dl, lbl, fontsize=7, color=col, va="bottom", ha="left",
                 bbox=dict(facecolor="white", edgecolor="none", pad=1.0,
                           alpha=0.85))

    axL.set_xticks(x)
    axL.set_xticklabels([policy_paper_label(s) for s in agg["scenario"]])
    axL.set_yscale("log")
    axL.set_ylim(0.05, 100)
    axL.set_ylabel("Per-packet latency [ms] (log scale)")
    axL.set_title("(a) Latency percentiles vs. use-case deadlines")
    axL.grid(True, which="both", alpha=0.25)

    # Custom legend for the four metrics
    from matplotlib.lines import Line2D
    legend_metrics = [
        Line2D([0], [0], marker="o", color="black", mfc="white",
               linestyle="none", label="median (p50)"),
        Line2D([0], [0], marker="s", color="black", mfc="white",
               linestyle="none", label="p95"),
        Line2D([0], [0], marker="^", color="black", mfc="white",
               linestyle="none", label="p99"),
        Line2D([0], [0], marker="D", color="black", mfc="white",
               linestyle="none", label="worst-case burst"),
    ]
    axL.legend(handles=legend_metrics, loc="upper left", fontsize=8,
               ncol=2, columnspacing=1.0, handletextpad=0.4)

    # ---- RIGHT panel : deadline-miss ratio at 10 ms -------------------
    # Decompose miss ratio into "lost" (= plr_total) and "late but
    # delivered" (= miss_ratio - plr_total, floor at 0)
    lost = agg["plr_total"].values
    miss = agg["deadline_miss_ratio"].values
    late = np.maximum(0.0, miss - lost)
    colours = [POLICY_STYLE[s]["color"] for s in agg["scenario"]]
    xR = np.arange(len(agg))
    axR.bar(xR, lost, width=0.55, color=colours, edgecolor="black", lw=0.5,
            label=r"Lost (PDR$_{\mathrm{jam}}$ deficit)")
    axR.bar(xR, late, width=0.55, bottom=lost, color=colours,
            edgecolor="black", lw=0.5, hatch="///", alpha=0.55,
            label="Delivered after 10\u202Fms")
    for i, scen in enumerate(agg["scenario"]):
        axR.text(xR[i], miss[i] + 0.005,
                 f"{miss[i]*100:.2f}%", ha="center", va="bottom", fontsize=8)
    axR.set_xticks(xR)
    axR.set_xticklabels([policy_paper_label(s) for s in agg["scenario"]])
    axR.set_ylim(0, max(0.4, miss.max() * 1.25))
    axR.set_ylabel("Deadline-miss ratio (10\u202Fms budget)")
    axR.set_title("(b) Deadline-miss decomposition")
    axR.grid(True, axis="y", alpha=0.3)
    # Custom hatch-vs-solid legend (one entry each)
    legend_decomp = [
        plt.Rectangle((0, 0), 1, 1, facecolor="#777777", edgecolor="black",
                      label="Lost packet"),
        plt.Rectangle((0, 0), 1, 1, facecolor="#777777", edgecolor="black",
                      hatch="///", alpha=0.55, label="Late delivery"),
    ]
    axR.legend(handles=legend_decomp, loc="upper right", fontsize=8)

    fig.suptitle("Closed-loop motion-control case study"
                 " (CM8 NLOS, MCS 0, 128-bit, 3 m, target SNR 20 dB,"
                 " reactive jammer 10 dBm)", fontsize=11, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.96))
    save(fig, "fig_case_study_motion_control")


# =======================================================================
# Figure 10 - CM8 vs QuaDRiGa side-by-side (PLR)
# =======================================================================
def fig_cm8_vs_quadriga():
    sub = df[(df["jammer_mode"] == "none") & (df["payload_bits"] == 128) &
             (df["distance_m"] == 3) & (df["scenario"] == "S9")].copy()
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    for ci, channel in enumerate(CHANNEL_LABEL.keys()):
        for mcs in (0, 1, 3):
            cell = sub[(sub["channel_model"] == channel) & (sub["mcs"] == mcs)]
            if cell.empty: continue
            g = aggregate(cell, ["target_snr_db"], "plr")
            style = dict(
                color=MCS_STYLE[mcs]["color"],
                marker=MCS_STYLE[mcs]["marker"],
                ls="-" if channel == "cm8_rayleigh" else "--",
                lw=1.8,
                ms=4,
                mfc="white",
                mew=0.9,
                label=(f"MCS {mcs} - CM8" if channel == "cm8_rayleigh"
                       else f"MCS {mcs} - QuaDRiGa\u2020"),
            )
            ax.plot(g["target_snr_db"], epsfloor(g["plr"]), **style)
    ax.set_yscale("log")
    ax.set_xlim(0, 22)
    ax.set_ylim(1e-5, 1.0)
    ax.set_xlabel("Target SNR [dB]")
    ax.set_ylabel("Packet Loss Ratio (PLR), S9 policy, no jammer")
    ax.set_title(r"CM8 (solid) vs. QuaDRiGa$^{\dagger}$ (dashed) channel comparison")
    ax.legend(loc="lower left", ncol=2, fontsize=8)
    fig.text(0.5, -0.04,
             r"$^{\dagger}$ QuaDRiGa rows use the documented synthetic placeholder trace.",
             ha="center", va="top", fontsize=8, color="#555555", style="italic")
    save(fig, "fig_cm8_vs_quadriga")


# --- Main ---------------------------------------------------------------
def main():
    print("Generating paper figures with colorblind-safe palette ...")
    fig_per_waterfall()
    fig_pdr_vs_snr()
    fig_scenario_comparison()
    fig_p95_latency_vs_snr()
    fig_pdr_jammer_on()
    fig_robustness_vs_jammer()
    fig_recovery_vs_jammer()
    fig_burst_induced_loss()
    fig_per_under_jamming()
    fig_cm8_vs_quadriga()                    # supplementary, channel comparison
    fig_per_waterfall_quadriga_appendix()    # supplementary, side-by-side
    fig_case_study_motion_control()
    print("\nDone. Figures in", OUT_DIR.relative_to(REPO_ROOT))


if __name__ == "__main__":
    main()
