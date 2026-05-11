#!/usr/bin/env python3
"""Generate journal-oriented plots with gnuplot and CSV-friendly data files."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from collections import defaultdict
from pathlib import Path

from config_utils import read_csv_rows, to_float


def mean(values):
    return sum(values) / max(len(values), 1)


def aggregate(rows, x_key, y_key, line_keys, filters=None):
    filters = filters or {}
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if any(str(row.get(k, "")) != str(v) for k, v in filters.items()):
            continue
        line = tuple(row.get(k, "") for k in line_keys)
        groups[line][to_float(row, x_key)].append(to_float(row, y_key))
    return {line: sorted((x, mean(v)) for x, v in series.items()) for line, series in groups.items()}


# Lookup tables used by the legend formatter. Kept inline so a paper-prep
# operator can tweak labels without touching the aggregation code.
CHANNEL_LABELS = {
    "cm8_rayleigh": "CM8 (Rayleigh/NLOS)",
    "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE": "QuaDRiGa (NLOS trace)",
    "quadriga_raytraced": "QuaDRiGa (NLOS trace)",
}

SCENARIO_LABELS = {
    "S4": "S4 (Baseline-PF)",
    "S8": "S8 (PLS-RTX)",
    "S9": "S9 (PLS-Realloc)",
}

MCS_LABELS = {
    "0": "MCS 0 (BPSK 1/2)",
    "1": "MCS 1 (QPSK 1/2)",
    "2": "MCS 2 (QPSK 3/4)",
    "3": "MCS 3 (16-QAM 1/2)",
    "4": "MCS 4 (16-QAM 3/4)",
}

JAMMER_LABELS = {
    "none": "no jammer",
    "constant": "constant jammer",
    "reactive": "reactive jammer",
}


def _format_key_value(key: str, value):
    text = str(value)
    if key in ("channel_model",):
        return CHANNEL_LABELS.get(text, text)
    if key == "scenario":
        return SCENARIO_LABELS.get(text, text)
    if key == "mcs":
        return MCS_LABELS.get(text, f"MCS {text}")
    if key == "payload_bits":
        return f"{text}-bit payload"
    if key == "distance_m":
        try:
            return f"d={float(text):g} m"
        except ValueError:
            return f"d={text} m"
    if key == "jammer_mode":
        return JAMMER_LABELS.get(text, text)
    if key == "jammer_power_dbm":
        try:
            return f"J={float(text):g} dBm"
        except ValueError:
            return f"J={text} dBm"
    if key == "channel_fidelity":
        # Suppress when channel_model is in the same label; fidelity is
        # otherwise rendered as a parenthetical tag.
        return None if text in ("proxy",) else text
    return text


def format_series_label(line_keys, line_values) -> str:
    parts = []
    for key, value in zip(line_keys, line_values):
        formatted = _format_key_value(key, value)
        if formatted:
            parts.append(formatted)
    return " | ".join(parts) if parts else "all"


def write_dat(path: Path, series, line_keys):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        # Tab separator keeps spaces and pipes inside legend labels intact;
        # gnuplot's `set datafile separator tab` will recover the third column
        # as a single string, which is what `columnheader(3)` returns.
        for label, points in sorted(series.items()):
            human = format_series_label(line_keys, label)
            f.write(f"x\ty\t{human}\n")
            for x, y in points:
                f.write(f"{x}\t{y}\n")
            f.write("\n")


def gnuplot_line(dat: Path, png: Path, title: str, xlabel: str, ylabel: str, logy: bool = False):
    gp = png.with_suffix(".gp")
    log_cmd = "set logscale y\nset yrange [1e-5:*]\n" if logy else ""
    gp.write_text(
        "set terminal pngcairo size 1600,1000 enhanced font 'Arial,22'\n"
        f"set output '{png}'\n"
        "set datafile separator '\\t'\n"
        "set key outside right top spacing 1.2 box opaque\n"
        "set grid lt 0 lw 1 lc rgb '#cccccc'\n"
        "set border lw 1.5\n"
        f"{log_cmd}"
        f"set title '{title}' offset 0,0.5\n"
        f"set xlabel '{xlabel}'\n"
        f"set ylabel '{ylabel}'\n"
        f"plot for [IDX=0:*] '{dat}' index IDX using 1:2 with linespoints linewidth 3 pointsize 1.2 title columnheader(3)\n"
    )
    if shutil.which("gnuplot"):
        subprocess.run(["gnuplot", str(gp)], check=True)


def make_plot(rows, outdir, name, x_key, y_key, line_keys, title, xlabel, ylabel, logy=False, filters=None):
    series = aggregate(rows, x_key, y_key, line_keys, filters)
    dat = outdir / f"{name}.dat"
    png = outdir / f"{name}.png"
    write_dat(dat, series, line_keys)
    has_positive = any(y > 0 for points in series.values() for _, y in points)
    gnuplot_line(dat, png, title, xlabel, ylabel, logy and has_positive)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.input))
    outdir = Path(args.output_dir)
    outdir.mkdir(parents=True, exist_ok=True)

    no_jammer = {"jammer_mode": "none"}
    make_plot(rows, outdir, "01_plr_vs_distance", "distance_m", "plr", ["channel_fidelity", "channel_model", "scenario"], "PLR vs distance", "distance (m)", "PLR", True, no_jammer)
    make_plot(rows, outdir, "02_per_vs_distance", "distance_m", "per", ["channel_fidelity", "channel_model", "scenario"], "PER vs distance", "distance (m)", "PER", True, no_jammer)
    make_plot(rows, outdir, "03_pdr_vs_distance", "distance_m", "pdr", ["channel_fidelity", "channel_model", "scenario"], "PDR vs distance", "distance (m)", "PDR", False, no_jammer)
    make_plot(rows, outdir, "04_latency_p95_vs_distance", "distance_m", "p95_delay_s", ["channel_fidelity", "channel_model", "scenario"], "p95 latency vs distance", "distance (m)", "p95 delay (s)", False, no_jammer)
    make_plot(rows, outdir, "05_deadline_miss_vs_distance", "distance_m", "deadline_miss_ratio", ["channel_fidelity", "channel_model", "scenario"], "deadline misses vs distance", "distance (m)", "deadline miss ratio", True, no_jammer)
    make_plot(rows, outdir, "06_plr_vs_mcs", "mcs", "plr", ["channel_fidelity", "channel_model", "scenario"], "PLR vs MCS", "MCS", "PLR", True, no_jammer)
    make_plot(rows, outdir, "07_per_vs_mcs", "mcs", "per", ["channel_fidelity", "channel_model", "scenario"], "PER vs MCS", "MCS", "PER", True, no_jammer)
    make_plot(rows, outdir, "08_robustness_vs_jammer_power", "jammer_power_dbm", "robustness_ratio", ["channel_fidelity", "channel_model", "scenario", "jammer_mode"], "anti-jamming robustness", "jammer power (dBm)", "PDR_jammer / PDR_no_jammer", False)
    make_plot(rows, outdir, "09_cm8_vs_quadriga_plr", "distance_m", "plr", ["channel_fidelity", "channel_model"], "CM8 vs QuaDRiGa PLR", "distance (m)", "PLR", True, no_jammer)
    make_plot(rows, outdir, "10_scenario_comparison_plr", "distance_m", "plr", ["scenario"], "S4 vs S8 vs S9 PLR", "distance (m)", "PLR", True, no_jammer)

    # SNR-axis plots: only valid when the sweep is parameterised by target_snr_db.
    snr_rows = [row for row in rows if row.get("target_snr_db", "")]
    if snr_rows:
        make_plot(snr_rows, outdir, "11_per_vs_snr_per_mcs", "target_snr_db", "per", ["channel_fidelity", "channel_model", "mcs", "scenario"], "PER waterfall vs target SNR", "target SNIR (dB)", "PER", True, no_jammer)
        make_plot(snr_rows, outdir, "12_plr_vs_snr_per_mcs", "target_snr_db", "plr", ["channel_fidelity", "channel_model", "mcs", "scenario"], "PLR vs target SNR", "target SNIR (dB)", "PLR", True, no_jammer)
        make_plot(snr_rows, outdir, "13_pdr_vs_snr_per_mcs", "target_snr_db", "pdr", ["channel_fidelity", "channel_model", "mcs", "scenario"], "PDR vs target SNR", "target SNIR (dB)", "PDR", False, no_jammer)
        make_plot(snr_rows, outdir, "14_p95_latency_vs_snr", "target_snr_db", "p95_delay_s", ["channel_fidelity", "channel_model", "mcs", "scenario"], "p95 latency vs target SNR", "target SNIR (dB)", "p95 delay (s)", False, no_jammer)
        make_plot(snr_rows, outdir, "15_scenario_per_vs_snr_mcs0", "target_snr_db", "per", ["scenario"], "S4 vs S8 vs S9 PER at MCS 0", "target SNIR (dB)", "PER", True, {**no_jammer, "mcs": "0"})
        make_plot(snr_rows, outdir, "16_scenario_per_vs_snr_mcs3", "target_snr_db", "per", ["scenario"], "S4 vs S8 vs S9 PER at MCS 3", "target SNIR (dB)", "PER", True, {**no_jammer, "mcs": "3"})

    # Anti-jamming dedicated plots. Limit to rows that actually carry jamming
    # telemetry; the matched no-jammer baseline rows are kept for context where
    # robustness or PDR_off comparisons are useful.
    jammed_rows = [row for row in rows if row.get("jammer_mode", "none") != "none"]
    if jammed_rows:
        make_plot(jammed_rows, outdir, "17_pdr_jammer_on_vs_jnr", "jammer_power_dbm", "pdr_jammer_on",
                  ["channel_model", "scenario", "jammer_mode"],
                  "PDR while jammer ON vs jammer power", "jammer power at TX (dBm)", "PDR (jammer ON)", False)
        make_plot(jammed_rows, outdir, "18_robustness_vs_jammer_power", "jammer_power_dbm", "robustness_ratio",
                  ["channel_model", "scenario", "jammer_mode"],
                  "Robustness ratio (PDR_jam / PDR_clean) vs jammer power", "jammer power at TX (dBm)", "robustness ratio", False)
        make_plot(jammed_rows, outdir, "19_recovery_time_vs_jammer_power", "jammer_power_dbm", "mean_recovery_time_s",
                  ["channel_model", "scenario", "jammer_mode"],
                  "Mean recovery time after reactive burst vs jammer power", "jammer power at TX (dBm)", "mean recovery time (s)", False,
                  {"jammer_mode": "reactive"})
        make_plot(jammed_rows, outdir, "20_burst_induced_loss_vs_jammer_power", "jammer_power_dbm", "burst_induced_loss_ratio",
                  ["channel_model", "scenario", "jammer_mode"],
                  "Fraction of losses occurring while jammer is ON", "jammer power at TX (dBm)", "burst-induced loss ratio", False,
                  {"jammer_mode": "reactive"})
        make_plot(jammed_rows, outdir, "21_plr_increase_vs_jammer_power", "jammer_power_dbm", "plr_increase_due_to_jammer",
                  ["channel_model", "scenario", "jammer_mode"],
                  "PLR increase induced by the jammer", "jammer power at TX (dBm)", "Delta PLR vs clean baseline", False)
        if snr_rows:
            jammed_snr = [row for row in snr_rows if row.get("jammer_mode", "none") != "none"]
            if jammed_snr:
                make_plot(jammed_snr, outdir, "22_per_vs_snr_under_jamming", "target_snr_db", "per",
                          ["channel_model", "scenario", "jammer_mode", "jammer_power_dbm"],
                          "PER vs target SNR under jamming", "target SNIR (dB)", "PER", True,
                          {"mcs": "0"})

    notes = outdir / "PLOT_NOTES.md"
    notes.write_text(
        "# Plot Notes\n\n"
        "- Reliability loss metrics (`PLR`, `PER`, deadline misses) use log-y plots when nonzero values span orders of magnitude.\n"
        "- `PDR` and latency are kept on linear axes for direct engineering interpretation.\n"
        "- Each `.png` has a matching `.dat` and `.gp` file so figures can be regenerated or restyled for a journal template. Data files are tab-separated and the third column carries the human-readable legend label used by gnuplot via `columnheader(3)`.\n"
        "- Series labels are produced by `format_series_label()` in `scripts/plot_results.py`. Override by editing the CHANNEL/SCENARIO/MCS/JAMMER lookup tables if your paper uses different short forms (e.g. `S4-BPF` instead of `S4 (Baseline-PF)`).\n"
        "- Plots `01`-`16` use the no-jammer baseline; plots `17`-`22` are dedicated to anti-jamming analyses. `19` and `20` are reactive-jammer only (constant jammer has no burst boundaries).\n"
        "- These scripts include `channel_fidelity` in series labels so proxy and trace rows are not silently merged.\n"
        "- These scripts aggregate over unspecified dimensions. For final paper figures, filter the input CSV first to the exact channel/MCS/payload/jammer condition being discussed.\n"
    )
    print(f"Wrote plots/data to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
