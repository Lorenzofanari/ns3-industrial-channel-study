#!/usr/bin/env python3
"""PDR and conditional PDR (jammer-ON) with seed uncertainty (error bars).

Aggregation only (no new simulation). Reads the main paper campaign
results/paper_v2/results.csv, slices a single diagnostic cell, and plots
mean +/- seed std across the three paper seeds for the three scenarios, plus a
pooled Clopper-Pearson 95% CI on PDR in the companion CSV.

Outputs under results/cooldown_sweep_analysis/:
  fig_pdr_pdron_seed_uncertainty.pdf / .png
  pdr_pdron_seed_uncertainty.csv

Claim-boundary: zero observed losses are bounded (rule-of-three / CP), never
called zero probability; values are observed in the scheduler-harness matrix.
"""
from __future__ import annotations

import csv
import math
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

try:
    from scipy.stats import beta as _beta
    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False

REPO = Path("/home/lorenzofanari/ns3-industrial-channel-study")
SRC = REPO / "results/paper_v2/results.csv"
OUT = REPO / "results/cooldown_sweep_analysis"

# Diagnostic slice (matches the paper's headline / Yans-envelope cell).
SLICE = dict(mcs="0", payload_bits="128", distance_m="3", jammer_mode="broadband_reactive")
SCENARIOS = ["S4", "S8", "S9"]
SEEDS = {"20260507", "20260508", "20260509"}


def cp(k, n, alpha=0.05):
    if n == 0:
        return (float("nan"), float("nan"))
    if _HAVE_SCIPY:
        lo = 0.0 if k == 0 else _beta.ppf(alpha / 2, k, n - k + 1)
        hi = 1.0 if k == n else _beta.ppf(1 - alpha / 2, k + 1, n - k)
        return float(lo), float(hi)
    z = 1.959963984540054
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def main():
    with SRC.open() as f:
        rows = list(csv.DictReader(f))

    def keep(x):
        return all(str(x.get(k, "")) == v for k, v in SLICE.items()) and str(x.get("seed", "")) in SEEDS

    sub = [x for x in rows if keep(x)]
    # detect available reactive jammer label if broadband_reactive absent
    if not sub:
        labels = sorted({str(x.get("jammer_mode", "")) for x in rows if "reactive" in str(x.get("jammer_mode", ""))})
        if labels:
            SLICE["jammer_mode"] = labels[0]
            sub = [x for x in rows if keep(x)]
    if not sub:
        raise SystemExit("empty slice; check SLICE filters and jammer label")

    # group by (scenario, snr) -> per-seed pdr / pdr_on / tx
    agg = defaultdict(lambda: {"pdr": [], "pdron": [], "tx": 0})
    for x in sub:
        sc = str(x.get("scenario", ""))
        if sc not in SCENARIOS:
            continue
        try:
            snr = float(x["target_snr_db"])
            pdr = float(x["pdr"])
            pdron = float(x.get("pdr_jammer_on", "nan"))
            tx = int(float(x.get("transmitted_packets", 0)))
        except (KeyError, ValueError):
            continue
        a = agg[(sc, snr)]
        a["pdr"].append(pdr)
        if pdron == pdron:
            a["pdron"].append(pdron)
        a["tx"] += tx

    # build series + CSV
    OUT.mkdir(parents=True, exist_ok=True)
    rows_out = []
    series = {sc: {"snr": [], "pdr_m": [], "pdr_s": [], "pdron_m": [], "pdron_s": []} for sc in SCENARIOS}
    for (sc, snr), a in sorted(agg.items()):
        pdr = np.array(a["pdr"], dtype=float)
        pdron = np.array(a["pdron"], dtype=float) if a["pdron"] else np.array([np.nan])
        pdr_m, pdr_s = float(pdr.mean()), float(pdr.std(ddof=0))
        pdron_m, pdron_s = float(np.nanmean(pdron)), float(np.nanstd(pdron))
        k = int(round(pdr_m * a["tx"]))
        lo, hi = cp(k, a["tx"])
        rows_out.append(dict(scenario=sc, target_snr_db=snr, n_seeds=len(pdr),
                             pdr_mean=round(pdr_m, 6), pdr_std=round(pdr_s, 6),
                             pdr_cp_lo=round(lo, 6), pdr_cp_hi=round(hi, 6),
                             pdr_on_mean=round(pdron_m, 6), pdr_on_std=round(pdron_s, 6),
                             tx_pooled=a["tx"]))
        s = series[sc]
        s["snr"].append(snr); s["pdr_m"].append(pdr_m); s["pdr_s"].append(pdr_s)
        s["pdron_m"].append(pdron_m); s["pdron_s"].append(pdron_s)

    with (OUT / "pdr_pdron_seed_uncertainty.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader(); w.writerows(rows_out)

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for sc in SCENARIOS:
        s = series[sc]
        order = np.argsort(s["snr"])
        snr = np.array(s["snr"])[order]
        axes[0].errorbar(snr, np.array(s["pdr_m"])[order], yerr=np.array(s["pdr_s"])[order],
                         marker="o", markersize=3, capsize=2, label=sc)
        axes[1].errorbar(snr, np.array(s["pdron_m"])[order], yerr=np.array(s["pdron_s"])[order],
                         marker="s", markersize=3, capsize=2, label=sc)
    axes[0].set_title("(a) PDR vs SNR (reactive jammer)")
    axes[0].set_xlabel("Target SNR (dB)"); axes[0].set_ylabel("PDR (mean $\\pm$ seed std)")
    axes[1].set_title("(b) Conditional PDR during jammer-ON")
    axes[1].set_xlabel("Target SNR (dB)"); axes[1].set_ylabel("PDR$_{on}$ (mean $\\pm$ seed std)")
    for ax in axes:
        ax.grid(True, alpha=0.3); ax.legend(fontsize=8)
    fig.suptitle(
        f"PDR / PDR_on with seed uncertainty (MCS {SLICE['mcs']}, {SLICE['payload_bits']} bit, "
        f"{SLICE['distance_m']} m, {SLICE['jammer_mode']}; 3 seeds; scheduler-harness matrix)",
        fontsize=9)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    fig.savefig(OUT / "fig_pdr_pdron_seed_uncertainty.pdf")
    fig.savefig(OUT / "fig_pdr_pdron_seed_uncertainty.png", dpi=150)
    plt.close(fig)
    print(f"wrote {OUT/'fig_pdr_pdron_seed_uncertainty.png'} and CSV ({len(rows_out)} rows); "
          f"jammer label used: {SLICE['jammer_mode']}")


if __name__ == "__main__":
    main()
