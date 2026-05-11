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


def write_dat(path: Path, series):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as f:
        for label, points in sorted(series.items()):
            text = "_".join(str(x) for x in label)
            f.write(f"x y {text}\n")
            for x, y in points:
                f.write(f"{x} {y}\n")
            f.write("\n")


def gnuplot_line(dat: Path, png: Path, title: str, xlabel: str, ylabel: str, logy: bool = False):
    gp = png.with_suffix(".gp")
    log_cmd = "set logscale y\nset yrange [1e-5:*]\n" if logy else ""
    gp.write_text(
        "set terminal pngcairo size 1400,900 enhanced font 'Arial,24'\n"
        f"set output '{png}'\n"
        "set datafile separator whitespace\n"
        "set key outside right top\n"
        "set grid\n"
        f"{log_cmd}"
        f"set title '{title}'\n"
        f"set xlabel '{xlabel}'\n"
        f"set ylabel '{ylabel}'\n"
        f"plot for [IDX=0:*] '{dat}' index IDX using 1:2 with linespoints linewidth 3 pointsize 1 title columnheader(3)\n"
    )
    if shutil.which("gnuplot"):
        subprocess.run(["gnuplot", str(gp)], check=True)


def make_plot(rows, outdir, name, x_key, y_key, line_keys, title, xlabel, ylabel, logy=False, filters=None):
    series = aggregate(rows, x_key, y_key, line_keys, filters)
    dat = outdir / f"{name}.dat"
    png = outdir / f"{name}.png"
    write_dat(dat, series)
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
    make_plot(rows, outdir, "01_plr_vs_distance", "distance_m", "plr", ["channel_model", "scenario"], "PLR vs distance", "distance (m)", "PLR", True, no_jammer)
    make_plot(rows, outdir, "02_per_vs_distance", "distance_m", "per", ["channel_model", "scenario"], "PER vs distance", "distance (m)", "PER", True, no_jammer)
    make_plot(rows, outdir, "03_pdr_vs_distance", "distance_m", "pdr", ["channel_model", "scenario"], "PDR vs distance", "distance (m)", "PDR", False, no_jammer)
    make_plot(rows, outdir, "04_latency_p95_vs_distance", "distance_m", "p95_delay_s", ["channel_model", "scenario"], "p95 latency vs distance", "distance (m)", "p95 delay (s)", False, no_jammer)
    make_plot(rows, outdir, "05_deadline_miss_vs_distance", "distance_m", "deadline_miss_ratio", ["channel_model", "scenario"], "deadline misses vs distance", "distance (m)", "deadline miss ratio", True, no_jammer)
    make_plot(rows, outdir, "06_plr_vs_mcs", "mcs", "plr", ["channel_model", "scenario"], "PLR vs MCS", "MCS", "PLR", True, no_jammer)
    make_plot(rows, outdir, "07_per_vs_mcs", "mcs", "per", ["channel_model", "scenario"], "PER vs MCS", "MCS", "PER", True, no_jammer)
    make_plot(rows, outdir, "08_robustness_vs_jammer_power", "jammer_power_dbm", "robustness_ratio", ["channel_model", "scenario", "jammer_mode"], "anti-jamming robustness", "jammer power (dBm)", "PDR_jammer / PDR_no_jammer", False)
    make_plot(rows, outdir, "09_cm8_vs_quadriga_plr", "distance_m", "plr", ["channel_model"], "CM8 vs QuaDRiGa PLR", "distance (m)", "PLR", True, no_jammer)
    make_plot(rows, outdir, "10_scenario_comparison_plr", "distance_m", "plr", ["scenario"], "S4 vs S8 vs S9 PLR", "distance (m)", "PLR", True, no_jammer)

    notes = outdir / "PLOT_NOTES.md"
    notes.write_text(
        "# Plot Notes\n\n"
        "- Reliability loss metrics (`PLR`, `PER`, deadline misses) use log-y plots when nonzero values span orders of magnitude.\n"
        "- `PDR` and latency are kept on linear axes for direct engineering interpretation.\n"
        "- Each `.png` has a matching `.dat` and `.gp` file so figures can be regenerated or restyled for a journal template.\n"
        "- These scripts aggregate over unspecified dimensions. For final paper figures, filter the input CSV first to the exact channel/MCS/payload/jammer condition being discussed.\n"
    )
    print(f"Wrote plots/data to {outdir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
