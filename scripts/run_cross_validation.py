#!/usr/bin/env python3
"""Run the same SNR sweep on ns3_core_harness AND ns3_wifi_yans, then
compute the per-cell gap so the paper can present the validation addendum
as an integral part of the main results.

Why this script exists:
- A reviewer can rightly ask whether the harness PDR/PER claims hold when the
  full Wi-Fi MAC, A-MPDU and BlockAck are in play. The Yans path provides
  exactly that envelope on a small subset; this script makes the gap
  observable in one CSV.

Outputs (under `results/cross_validation/`):
- `harness/results.csv` and `yans/results.csv`: full sweeps, one per backend.
- `cross_validation.csv`: one row per (scenario, mcs, payload, distance,
  jammer_mode, jammer_power_dbm, target_snr_db, seed); columns
  `pdr_harness`, `pdr_yans`, `pdr_abs_gap`, `pdr_rel_gap`, idem for PLR/PER.
- `cross_validation_summary.md`: aggregated statistics (mean and p95 of the
  absolute gap, max, count).

Default execution time is ~1 minute on an 8-core machine because the subset
is intentionally tiny; expand `configs/cross_validation_subset.yaml` if you
want a wider envelope.
"""

from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
from pathlib import Path

from config_utils import ROOT, read_csv_rows


JOIN_KEYS = [
    "scenario",
    "channel_model",
    "mcs",
    "payload_bits",
    "distance_m",
    "jammer_mode",
    "jammer_power_dbm",
    "target_snr_db",
    "seed",
]

METRICS = ["pdr", "plr", "per"]


def run_backend(backend: str, output_dir: Path, config: Path, snr_min: float,
                snr_max: float, snr_step: float, channel: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable,
        str(ROOT / "scripts/run_sweep.py"),
        "--config", str(config),
        "--output-dir", str(output_dir),
        "--channel-model", channel,
        "--simulation-path", backend,
        "--snr-min", str(snr_min),
        "--snr-max", str(snr_max),
        "--snr-step", str(snr_step),
        "--no-build",
    ]
    print(f"  $ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=ROOT, check=True)


def join_rows(harness_rows: list[dict], yans_rows: list[dict]) -> list[dict]:
    by_key = {tuple(r.get(k, "") for k in JOIN_KEYS): r for r in yans_rows}
    joined: list[dict] = []
    missing: list[tuple] = []
    for r in harness_rows:
        key = tuple(r.get(k, "") for k in JOIN_KEYS)
        partner = by_key.get(key)
        if partner is None:
            missing.append(key)
            continue
        row = {k: v for k, v in zip(JOIN_KEYS, key)}
        for metric in METRICS:
            try:
                a = float(r.get(metric, "nan"))
                b = float(partner.get(metric, "nan"))
            except ValueError:
                continue
            if math.isnan(a) or math.isnan(b):
                continue
            row[f"{metric}_harness"] = a
            row[f"{metric}_yans"] = b
            row[f"{metric}_abs_gap"] = abs(a - b)
            denom = max(abs(b), 1e-6)
            row[f"{metric}_rel_gap"] = abs(a - b) / denom
        joined.append(row)
    if missing:
        print(f"  WARNING: {len(missing)} harness rows had no Yans partner (skipped)")
    return joined


def summarise(joined: list[dict]) -> str:
    if not joined:
        return "No joined rows; the two backends produced disjoint matrices."
    lines = [
        "# Cross-Validation Summary",
        "",
        f"Joined rows: {len(joined)}",
        "",
        "| metric | mean abs gap | p95 abs gap | max abs gap | mean rel gap |",
        "|--------|--------------|-------------|-------------|---------------|",
    ]
    for metric in METRICS:
        gaps = sorted(row[f"{metric}_abs_gap"] for row in joined if f"{metric}_abs_gap" in row)
        rels = [row[f"{metric}_rel_gap"] for row in joined if f"{metric}_rel_gap" in row]
        if not gaps:
            continue
        p95_idx = max(0, min(len(gaps) - 1, int(round(0.95 * (len(gaps) - 1)))))
        mean_abs = sum(gaps) / len(gaps)
        p95_abs = gaps[p95_idx]
        max_abs = gaps[-1]
        mean_rel = sum(rels) / len(rels) if rels else float("nan")
        lines.append(f"| `{metric}` | {mean_abs:.4f} | {p95_abs:.4f} | {max_abs:.4f} | {mean_rel:.4f} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "- `abs_gap`: |PDR_harness - PDR_yans| at the same (scenario, MCS, payload, distance, jammer, SNR, seed).",
        "- `rel_gap`: `abs_gap / max(PDR_yans, 1e-6)`. Use this when PDR is small.",
        "- A small gap (mean < 0.05, p95 < 0.10) lets the paper claim that the harness",
        "  conclusions on relative policy ranking and PER waterfall slope hold under the",
        "  full Wi-Fi stack as well. A large gap is an HONEST signal: do not smooth or",
        "  hide it; investigate MAC contention, A-MPDU handling, or rate adaptation.",
        "- The harness models packet reception via a PER waterfall sigmoid only; the",
        "  Yans path additionally applies a receiver sensitivity gate (~ -89 dBm for HE",
        "  MCS0 at 20 MHz). Use --snr-min/--snr-max to keep the cross-validation inside",
        "  the high-SNR regime where the harness is meant to be valid; running below the",
        "  sensitivity cliff will produce a large but expected gap.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/cross_validation_subset.yaml")
    parser.add_argument("--output", default="results/cross_validation")
    # The harness models packet reception purely through the PER waterfall
    # sigmoid; the Yans path additionally applies a receiver-sensitivity gate
    # (~ -89 dBm for HE MCS0 at 20 MHz). The default cross-validation range
    # therefore lives in the high-SNR regime where the receive power is well
    # above sensitivity AND the PER waterfall is still informative (sigmoid
    # tail). Operators can drop snr-min/snr-max to deliberately probe the
    # sensitivity-cliff regime; the resulting gap should be reported in the
    # paper as a calibration boundary, not smoothed away.
    parser.add_argument("--snr-min", type=float, default=10.0)
    parser.add_argument("--snr-max", type=float, default=20.0)
    parser.add_argument("--snr-step", type=float, default=2.0)
    parser.add_argument("--channel", default="cm8_rayleigh")
    args = parser.parse_args()

    out = ROOT / args.output
    out.mkdir(parents=True, exist_ok=True)
    config = ROOT / args.config

    print("[1/3] Running ns3_core_harness backend...")
    run_backend("ns3_core_harness", out / "harness", config, args.snr_min, args.snr_max,
                args.snr_step, args.channel)
    print("[2/3] Running ns3_wifi_yans backend...")
    run_backend("ns3_wifi_yans", out / "yans", config, args.snr_min, args.snr_max,
                args.snr_step, args.channel)

    harness_rows = read_csv_rows(out / "harness" / "results.csv")
    yans_rows = read_csv_rows(out / "yans" / "results.csv")
    joined = join_rows(harness_rows, yans_rows)

    csv_path = out / "cross_validation.csv"
    if joined:
        fieldnames = list(joined[0].keys())
        with csv_path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(joined)
        print(f"Wrote {csv_path} ({len(joined)} joined rows)")

    summary = summarise(joined)
    md_path = out / "cross_validation_summary.md"
    md_path.write_text(summary + "\n")
    print(f"Wrote {md_path}")
    print("[3/3] Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
