#!/usr/bin/env python3
"""Figure generation for the coherence-time experiment (Agent 8).

Generates only figures the data support; otherwise records the gap in a
"Temporal mechanisms and validation status" table. IEEE-readable, grayscale-safe,
vector PDF (+ PNG). No invented values.

Figures:
  A  R_gamma(tau) vs lag for different configured Tc (AR(1)).
  B  Delta PDR_on vs chi_cd = T_cd/T_on (jammer on).
  C  Delta PDR / Delta PDR_off vs chi_c = T_cd/T_c (no-jammer / jammer-off).
  D  retry_same_burst & retry_after_burst vs cooldown.
  E  2-D heatmap of Delta PDR_on over (chi_cd, chi_c).
  F  Mechanism-separation bars (jammer-phase vs channel-time vs RU retargeting).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_utils import ROOT  # noqa: E402

plt.rcParams.update({
    "font.size": 9, "axes.grid": True, "grid.alpha": 0.3,
    "figure.figsize": (3.5, 2.6), "savefig.bbox": "tight", "savefig.dpi": 200,
})
MARKERS = ["o", "s", "^", "D", "v", "x", "*"]
LINES = ["-", "--", "-.", ":"]


def save(fig, fig_dir, name):
    fig.savefig(fig_dir / f"{name}.pdf")
    fig.savefig(fig_dir / f"{name}.png")
    plt.close(fig)


def fig_a(curves_path, fig_dir, status):
    if not curves_path.exists():
        status["A"] = "skipped: no autocorrelation_curves.csv"
        return
    df = pd.read_csv(curves_path)
    ar1 = df[df["channel_correlation_model"] == "ar1"]
    if ar1.empty:
        status["A"] = "skipped: no AR(1) traces"
        return
    fig, ax = plt.subplots()
    for i, (tc, sub) in enumerate(ar1.groupby("coherence_time_ms")):
        sub = sub.sort_values("lag_ms")
        ax.plot(sub["lag_ms"], sub["acf"], LINES[i % len(LINES)], marker=MARKERS[i % len(MARKERS)],
                markevery=max(1, len(sub) // 8), ms=3, color="black",
                alpha=0.4 + 0.6 * i / max(1, ar1["coherence_time_ms"].nunique() - 1),
                label=f"Tc={tc:g} ms")
    ax.axhline(1 / np.e, color="gray", lw=0.8, ls=":")
    ax.set_xlabel("lag $\\tau$ (ms)")
    ax.set_ylabel("$R_\\Gamma(\\tau)$")
    ax.set_xlim(left=0)
    ax.legend(fontsize=6, ncol=2)
    save(fig, fig_dir, "fig_A_autocorrelation")
    status["A"] = "ok"


def _scatter_trend(ax, x, y, label, marker, color):
    ax.scatter(x, y, s=14, marker=marker, color=color, alpha=0.7, label=label)
    if len(x) >= 2 and np.ptp(x) > 0:
        b, a = np.polyfit(x, y, 1)
        xs = np.linspace(min(x), max(x), 50)
        ax.plot(xs, a + b * xs, color=color, lw=1.0)


def fig_b(deltas, fig_dir, status):
    sweep = deltas[(deltas["comparison"] == "cooldown_sweep") &
                   (deltas["jammer_ru_mode"] != "none")]
    d = sweep[["chi_cd", "delta_PDR_on"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(d) < 3:
        status["B"] = "skipped: <3 jammer-on cooldown points"
        return
    fig, ax = plt.subplots()
    _scatter_trend(ax, d["chi_cd"].to_numpy(), d["delta_PDR_on"].to_numpy(),
                   "jammer on", MARKERS[0], "black")
    ax.set_xlabel("$\\chi_{cd}=T_{cd}/T_{on}$")
    ax.set_ylabel("$\\Delta$PDR$_{on}$")
    ax.legend(fontsize=7)
    save(fig, fig_dir, "fig_B_dpdron_vs_chi_cd")
    status["B"] = "ok"


def fig_c(deltas, fig_dir, status):
    sweep = deltas[deltas["comparison"] == "cooldown_sweep"]
    nojam = sweep[sweep["jammer_ru_mode"] == "none"]
    d = nojam[["chi_c", "delta_PDR"]].apply(pd.to_numeric, errors="coerce").dropna()
    target, src = "delta_PDR", nojam
    if len(d) < 3:
        # fall back to jammer-off PDR_off
        d = sweep[["chi_c", "delta_PDR_off"]].apply(pd.to_numeric, errors="coerce").dropna()
        target = "delta_PDR_off"
    if len(d) < 3:
        status["C"] = "skipped: <3 no-jammer/jammer-off points with finite chi_c"
        return
    fig, ax = plt.subplots()
    _scatter_trend(ax, d["chi_c"].to_numpy(), d.iloc[:, 1].to_numpy(),
                   "no/low jammer", MARKERS[1], "black")
    ax.set_xlabel("$\\chi_c=T_{cd}/T_c$")
    ax.set_ylabel(f"$\\Delta$PDR ({'overall' if target=='delta_PDR' else 'jammer-off'})")
    ax.legend(fontsize=7)
    save(fig, fig_dir, "fig_C_dpdr_vs_chi_c")
    status["C"] = f"ok ({target})"


def fig_d(agg, fig_dir, status):
    cdp = agg[agg["policy"].isin(["cooldown_only", "cooldown_plus_retarget"])].copy()
    for c in ["retry_landed_same_burst", "retry_landed_after_burst", "cooldown_symbols"]:
        cdp[c] = pd.to_numeric(cdp[c], errors="coerce")
    cdp = cdp[cdp["jammer_ru_mode"] != "none"]
    g = cdp.groupby("cooldown_symbols").agg(
        same=("retry_landed_same_burst", "mean"),
        after=("retry_landed_after_burst", "mean")).reset_index().dropna(how="all")
    if g["cooldown_symbols"].nunique() < 2:
        status["D"] = "skipped: <2 cooldown values"
        return
    fig, ax = plt.subplots()
    ax.plot(g["cooldown_symbols"], g["same"], "-o", color="black", ms=3, label="same burst")
    ax.plot(g["cooldown_symbols"], g["after"], "--s", color="gray", ms=3, label="after burst")
    ax.set_xlabel("cooldown (OFDM symbols)")
    ax.set_ylabel("retry-landing fraction")
    ax.legend(fontsize=7)
    save(fig, fig_dir, "fig_D_retry_landing_vs_cooldown")
    status["D"] = "ok"


def fig_e(deltas, fig_dir, status):
    sweep = deltas[(deltas["comparison"] == "cooldown_sweep") &
                   (deltas["jammer_ru_mode"] != "none")]
    d = sweep[["chi_cd", "chi_c", "delta_PDR_on"]].apply(pd.to_numeric, errors="coerce").dropna()
    if len(d) < 6 or d["chi_cd"].nunique() < 2 or d["chi_c"].nunique() < 2:
        status["E"] = "skipped: insufficient (chi_cd, chi_c) coverage"
        return
    # bin into a small grid and average
    nb = min(6, max(2, int(np.sqrt(len(d) / 2))))
    d = d.copy()
    d["bx"] = pd.cut(d["chi_cd"], nb)
    d["by"] = pd.cut(d["chi_c"], nb)
    piv = d.groupby(["by", "bx"], observed=True)["delta_PDR_on"].mean().unstack()
    fig, ax = plt.subplots()
    im = ax.imshow(piv.to_numpy(dtype=float), origin="lower", aspect="auto", cmap="gray_r")
    ax.set_xlabel("$\\chi_{cd}=T_{cd}/T_{on}$ (binned)")
    ax.set_ylabel("$\\chi_c=T_{cd}/T_c$ (binned)")
    fig.colorbar(im, ax=ax, label="$\\Delta$PDR$_{on}$")
    save(fig, fig_dir, "fig_E_heatmap_dpdron")
    status["E"] = "ok"


def fig_f(deltas, fig_dir, status):
    sweep = deltas[deltas["comparison"] == "cooldown_sweep"]
    pvb = deltas[deltas["comparison"] == "policy_vs_baseline"]
    bars = {}
    jam = sweep[sweep["jammer_ru_mode"] == "narrowband_reactive"]["delta_PDR_on"]
    bars["jammer-phase\n(cooldown,\njammer on)"] = jam.dropna().mean() if len(jam.dropna()) else np.nan
    nojam = sweep[sweep["jammer_ru_mode"] == "none"]["delta_PDR"]
    bars["channel-time\n(cooldown,\nno jammer)"] = nojam.dropna().mean() if len(nojam.dropna()) else np.nan
    ru = pvb[(pvb["policy"] == "ru_retarget_only") &
             (pvb["jammer_ru_mode"] == "narrowband_reactive")]["delta_PDR_on"]
    bars["RU retarget\n(vs baseline,\njammer on)"] = ru.dropna().mean() if len(ru.dropna()) else np.nan
    vals = [bars[k] for k in bars]
    if all(not np.isfinite(v) for v in vals):
        status["F"] = "skipped: no finite mechanism estimates"
        return
    fig, ax = plt.subplots()
    xs = np.arange(len(bars))
    ax.bar(xs, [0 if not np.isfinite(v) else v for v in vals],
           color=["0.2", "0.5", "0.75"])
    ax.set_xticks(xs)
    ax.set_xticklabels(list(bars.keys()), fontsize=6)
    ax.set_ylabel("mean $\\Delta$PDR")
    ax.axhline(0, color="black", lw=0.6)
    save(fig, fig_dir, "fig_F_mechanism_separation")
    status["F"] = "ok"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", default="debug")
    args = ap.parse_args()
    root = ROOT / "results/coherence_time_experiment" / args.matrix
    ana = root / "analysis"
    fig_dir = root / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    deltas_path = ana / "performance_deltas.csv"
    if not deltas_path.exists():
        sys.exit(f"missing {deltas_path}; run analyze_coherence_time.py first")
    deltas = pd.read_csv(deltas_path)
    lines = [l for l in (root / "aggregate.csv").read_text().splitlines() if not l.startswith("#")]
    from io import StringIO
    agg = pd.read_csv(StringIO("\n".join(lines)))

    status = {}
    fig_a(ana / "autocorrelation_curves.csv", fig_dir, status)
    fig_b(deltas, fig_dir, status)
    fig_c(deltas, fig_dir, status)
    fig_d(agg, fig_dir, status)
    fig_e(deltas, fig_dir, status)
    fig_f(deltas, fig_dir, status)

    # captions
    caps = {
        "A": "Estimated temporal autocorrelation $R_\\Gamma(\\tau)$ of the AR(1) "
             "fading process for the configured coherence times. Larger $T_c$ "
             "decorrelates more slowly; the dotted line marks the $1/e$ level.",
        "B": "Cooldown-induced $\\Delta$PDR under reactive jamming versus "
             "$\\chi_{cd}=T_{cd}/T_{on}$ (jammer-phase decorrelation axis).",
        "C": "Cooldown-induced $\\Delta$PDR without (or with low) jamming versus "
             "$\\chi_c=T_{cd}/T_c$ (channel-coherence-time axis).",
        "D": "Fraction of retries landing in the same versus a later jammer burst "
             "as the cooldown grows.",
        "E": "Mean $\\Delta$PDR$_{on}$ over the ($\\chi_{cd}$, $\\chi_c$) plane.",
        "F": "Mechanism separation: mean $\\Delta$PDR attributable to jammer-phase "
             "decorrelation, channel-time decorrelation, and RU retargeting.",
    }
    tex = []
    for k in "ABCDEF":
        if status.get(k, "").startswith("ok"):
            name = {"A": "fig_A_autocorrelation", "B": "fig_B_dpdron_vs_chi_cd",
                    "C": "fig_C_dpdr_vs_chi_c", "D": "fig_D_retry_landing_vs_cooldown",
                    "E": "fig_E_heatmap_dpdron", "F": "fig_F_mechanism_separation"}[k]
            tex.append(f"% Figure {k}\n\\caption{{{caps[k]}}}\n% file: figures/{name}.pdf\n")
    (fig_dir / "figure_captions.tex").write_text("\n".join(tex))

    # summary + temporal-mechanisms table (for gaps)
    md = ["# Figures summary\n"]
    for k in "ABCDEF":
        md.append(f"- Figure {k}: {status.get(k, 'not attempted')}")
    md.append("\n## Temporal mechanisms and validation status\n")
    md.append("| Mechanism | Evidence axis | Figure | Status |")
    md.append("|---|---|---|---|")
    md.append(f"| Jammer-phase decorrelation | chi_cd=T_cd/T_on, retry_after_burst | B/D | {status.get('B','-')} |")
    md.append(f"| Channel-time decorrelation | chi_c=T_cd/T_c, no-jammer gain | A/C | {status.get('C','-')} |")
    md.append(f"| RU/frequency retargeting | RU_changed, ru_retarget_only | F | {status.get('F','-')} |")
    (fig_dir / "figures_summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))
    print(f"\nFigures written to {fig_dir}")


if __name__ == "__main__":
    main()
