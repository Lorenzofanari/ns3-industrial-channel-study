#!/usr/bin/env python3
"""Aggregate + visualise the RU-granularity sensitivity sweep.

Reads results/ru_granularity/aggregate.csv (produced by
run_ru_granularity_sweep.py) and writes, under results/ru_granularity/:
  ru_granularity_summary.csv          per (jammer_mode, num_rus, policy) stats
  ru_granularity_mechanism_table.md   compact mechanism-separation table
  claim_to_evidence.md                claim -> evidence -> boundary
  fig_pdr_vs_ru.{pdf,png}             PDR vs RU count, panel per jammer mode
  fig_pdron_vs_ru.{pdf,png}           conditional PDR(jammer-ON) vs RU count
  fig_deadline_miss_vs_ru.{pdf,png}   deadline-miss ratio vs RU count
  PROVENANCE_analysis.txt

Stats: seed mean/std; PDR and deadline-miss pooled Clopper-Pearson 95% CI;
rule-of-three 95% upper bound for zero observed deadline misses (never zero
probability). Scheduler-harness, abstract RUs, fixed 20 MHz noise bandwidth.
"""
from __future__ import annotations

import csv
import math
import platform
import subprocess
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

try:
    from scipy.stats import beta as _beta
    _HAVE_SCIPY = True
except Exception:
    _HAVE_SCIPY = False

REPO = Path("/home/lorenzofanari/ns3-industrial-channel-study")
OUT = REPO / "results/ru_granularity"
SRC = OUT / "aggregate.csv"

POLICIES = ["baseline_pf", "ru_retarget_only", "cooldown_only", "cooldown_plus_retarget"]
POLICY_LABEL = {
    "baseline_pf": "S4 baseline-PF",
    "ru_retarget_only": "S8 retarget-only",
    "cooldown_only": "cooldown-only",
    "cooldown_plus_retarget": "S9 cooldown+retarget",
}
MODES = ["broadband_reactive", "narrowband_reactive", "partial_band_reactive_random"]
MODE_LABEL = {
    "broadband_reactive": "Broadband (all RUs)",
    "narrowband_reactive": "Narrowband (1 RU)",
    "partial_band_reactive_random": "Partial-band (~50% RUs)",
}
RU_COUNTS = [4, 8, 16, 32, 64]


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


def ro3_upper(n, conf=0.95):
    return float("nan") if n <= 0 else 1.0 - (1.0 - conf) ** (1.0 / n)


def fnum(x, k):
    try:
        return float(x[k])
    except (KeyError, ValueError):
        return float("nan")


def main():
    rows = list(csv.DictReader(SRC.open()))
    g = defaultdict(lambda: defaultdict(list))
    for x in rows:
        key = (x["jammer_ru_mode"], int(x["num_rus"]), x["policy"])
        g[key]["pdr"].append(fnum(x, "pdr"))
        g[key]["pdron"].append(fnum(x, "pdr_jammer_on"))
        g[key]["pdroff"].append(fnum(x, "pdr_jammer_off"))
        g[key]["dmiss"].append(fnum(x, "deadline_miss_ratio"))
        g[key]["p95ms"].append(fnum(x, "p95_delay_s") * 1e3)
        g[key]["p99ms"].append(fnum(x, "p99_delay_s") * 1e3)
        g[key]["maxmiss"].append(fnum(x, "max_consecutive_deadline_misses"))
        g[key]["tx"].append(fnum(x, "transmitted_packets"))
        g[key]["fjam"].append(fnum(x, "fraction_rus_jammed"))

    summary = []
    for mode in MODES:
        for ru in RU_COUNTS:
            for pol in POLICIES:
                d = g.get((mode, ru, pol))
                if not d:
                    continue
                tx_tot = int(sum(d["tx"]))
                pdr_m = mean(d["pdr"])
                k_pdr = int(round(pdr_m * tx_tot))
                pdr_lo, pdr_hi = cp(k_pdr, tx_tot)
                dm_m = mean(d["dmiss"])
                k_dm = int(round(dm_m * tx_tot))
                dm_lo, dm_hi = cp(k_dm, tx_tot)
                rec = dict(
                    jammer_mode=mode, num_rus=ru, policy=pol,
                    n_seeds=len(d["pdr"]),
                    fraction_rus_jammed=round(mean(d["fjam"]), 4),
                    pdr_mean=round(pdr_m, 6), pdr_std=round(pstdev(d["pdr"]) if len(d["pdr"]) > 1 else 0.0, 6),
                    pdr_cp_lo=round(pdr_lo, 6), pdr_cp_hi=round(pdr_hi, 6),
                    pdr_on_mean=round(mean(d["pdron"]), 6),
                    pdr_on_std=round(pstdev(d["pdron"]) if len(d["pdron"]) > 1 else 0.0, 6),
                    pdr_off_mean=round(mean(d["pdroff"]), 6),
                    deadline_miss_mean=round(dm_m, 8),
                    deadline_miss_std=round(pstdev(d["dmiss"]) if len(d["dmiss"]) > 1 else 0.0, 8),
                    deadline_miss_cp_hi=round(dm_hi, 8),
                    deadline_miss_ub_ro3=(round(ro3_upper(tx_tot), 8) if dm_m == 0.0 else ""),
                    p95_delay_ms=round(mean(d["p95ms"]), 4),
                    p99_delay_ms=round(mean(d["p99ms"]), 4),
                    max_consec_miss_mean=round(mean(d["maxmiss"]), 2),
                    tx_pooled=tx_tot,
                )
                summary.append(rec)

    cols = list(summary[0].keys())
    with (OUT / "ru_granularity_summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(summary)

    def look(mode, ru, pol, field):
        for r in summary:
            if r["jammer_mode"] == mode and r["num_rus"] == ru and r["policy"] == pol:
                return r[field]
        return None

    # ---- mechanism-separation table -----------------------------------------
    lines = [
        "# RU-granularity sensitivity - mechanism separation (scheduler harness)",
        "",
        "Diagnostic cell: MCS 3, 128 bit, 3 m, deadline 10 ms, reactive jammer (Ton=4 ms, "
        "Tcyc=20 ms), AR(1) per-RU fading, T_c=5 ms, 3 seeds, 4000 packets/run. RUs are "
        "abstract scheduler-visible units; jammer occupancy is a fraction of RUs; physical "
        "noise bandwidth fixed at 20 MHz. **Not** a calibrated 802.11ax PHY and **not** a "
        "full 80/160 MHz validation. Conditional PDR during jammer-ON shown; deadline-miss is "
        "the mean ratio (rule-of-three 95% upper bound where zero observed).",
        "",
        "| jammer mode | RUs | frac jammed | S4 PDR_on | S8(retarget) PDR_on | cooldown-only PDR_on | S9 PDR_on | S9 deadline-miss | interpretation |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for mode in MODES:
        for ru in RU_COUNTS:
            s4 = look(mode, ru, "baseline_pf", "pdr_on_mean")
            s8 = look(mode, ru, "ru_retarget_only", "pdr_on_mean")
            co = look(mode, ru, "cooldown_only", "pdr_on_mean")
            s9 = look(mode, ru, "cooldown_plus_retarget", "pdr_on_mean")
            s9dm = look(mode, ru, "cooldown_plus_retarget", "deadline_miss_mean")
            s9ub = look(mode, ru, "cooldown_plus_retarget", "deadline_miss_ub_ro3")
            dm_txt = f"0 (UB {s9ub})" if s9dm == 0.0 and s9ub != "" else f"{s9dm:.4f}"
            if mode == "broadband_reactive":
                interp = "retarget useless (all RUs jammed); cooldown dominant"
            elif mode == "narrowband_reactive":
                interp = "retarget escapes to clean RU; cooldown also recovers"
            else:
                interp = "retarget escapes to clean RU subset; cooldown also recovers"
            lines.append(
                f"| {mode} | {ru} | {look(mode,ru,'baseline_pf','fraction_rus_jammed')} | "
                f"{s4:.3f} | {s8:.3f} | {co:.3f} | {s9:.3f} | {dm_txt} | {interp} |")
    (OUT / "ru_granularity_mechanism_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # ---- figures -------------------------------------------------------------
    def plot_metric(field, ylabel, title, fname, ylim=None):
        fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
        for ax, mode in zip(axes, MODES):
            for pol in POLICIES:
                ys = [look(mode, ru, pol, field) for ru in RU_COUNTS]
                ys = [y if y is not None else float("nan") for y in ys]
                ax.plot(RU_COUNTS, ys, marker="o", markersize=4, label=POLICY_LABEL[pol])
            ax.set_xscale("log", base=2)
            ax.set_xticks(RU_COUNTS)
            ax.set_xticklabels([str(r) for r in RU_COUNTS])
            ax.set_title(MODE_LABEL[mode], fontsize=9)
            ax.set_xlabel("scheduler-visible RUs")
            ax.grid(True, alpha=0.3)
            if ylim:
                ax.set_ylim(*ylim)
        axes[0].set_ylabel(ylabel)
        axes[0].legend(fontsize=7, loc="best")
        fig.suptitle(title + "  (abstract scheduler RUs; not a calibrated 802.11ax PHY)", fontsize=10)
        fig.tight_layout(rect=[0, 0, 1, 0.94])
        fig.savefig(OUT / f"{fname}.pdf")
        fig.savefig(OUT / f"{fname}.png", dpi=150)
        plt.close(fig)

    plot_metric("pdr_on_mean", "PDR during jammer-ON",
                "Conditional PDR(jammer-ON) vs RU granularity", "fig_pdron_vs_ru", ylim=(-0.03, 1.03))
    plot_metric("pdr_mean", "Overall PDR",
                "Overall PDR vs RU granularity", "fig_pdr_vs_ru", ylim=(0.4, 1.03))
    plot_metric("deadline_miss_mean", "Deadline-miss ratio (10 ms)",
                "Deadline-miss ratio vs RU granularity", "fig_deadline_miss_vs_ru")

    # ---- claim-to-evidence ---------------------------------------------------
    (OUT / "claim_to_evidence.md").write_text(
        "# Claim-to-evidence - RU-granularity sensitivity\n\n"
        "| Claim | Evidence (file) | Boundary |\n|---|---|---|\n"
        "| Under broadband reactive jamming, cooldown is the dominant mechanism and its "
        "effect is invariant to scheduler-visible RU count (4-64). | "
        "`ru_granularity_summary.csv`, `fig_pdron_vs_ru`: cooldown PDR_on=1.0, "
        "retarget PDR_on=0 at all RU counts. | Scheduler-harness, abstract RUs, fixed 20 MHz "
        "noise; not a calibrated PHY. |\n"
        "| RU retargeting helps only when the impairment is frequency/RU-selective. | "
        "Narrowband/partial-band: retarget PDR_on=1.0; broadband: retarget PDR_on=0. | "
        "Abstract per-RU fading; not validated PHY frequency diversity. |\n"
        "| The cooldown-on-failure result does not depend on RU granularity. | "
        "cooldown PDR_on and S9 deadline-miss flat across RU counts. | Zero observed misses "
        "reported as rule-of-three upper bounds, not zero probability. |\n"
        "| The baseline PDR_on rise under narrowband as RUs grow is a fraction effect, not a "
        "policy gain. | baseline PDR_on tracks 1 - 1/R (fraction_rus_jammed column). | "
        "Statistical artifact of shrinking jammed fraction; not a scheduler improvement. |\n",
        encoding="utf-8")

    gc = subprocess.run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"],
                        capture_output=True, text=True).stdout.strip()
    (OUT / "PROVENANCE_analysis.txt").write_text(
        "RU-granularity sensitivity analysis\n"
        f"git_commit: {gc}\npython: {platform.python_version()}\n"
        f"source: results/ru_granularity/aggregate.csv\n"
        "command: python3 scripts/analyze_ru_granularity.py\n"
        "stats: seed mean/std; pooled Clopper-Pearson 95% CI on PDR and deadline-miss; "
        "rule-of-three upper bound for zero observed misses.\n"
        "boundary: abstract scheduler-visible RUs; jammer occupancy = fraction of RUs; "
        "fixed 20 MHz noise bandwidth; NOT a calibrated 802.11ax PHY; NOT a full 80/160 MHz "
        "validation; NOT validated PHY frequency diversity.\n",
        encoding="utf-8")

    print(f"wrote summary ({len(summary)} rows), mechanism table, claim-to-evidence, 3 figures")
    # console headline
    print("\nPDR_on (S8 retarget-only vs cooldown_only) by mode @ R=4 and R=64:")
    for mode in MODES:
        for ru in (4, 64):
            print(f"  {mode:32s} R{ru:<2} retarget={look(mode,ru,'ru_retarget_only','pdr_on_mean'):.2f} "
                  f"cooldown={look(mode,ru,'cooldown_only','pdr_on_mean'):.2f}")


if __name__ == "__main__":
    main()
