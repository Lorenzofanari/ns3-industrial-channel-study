#!/usr/bin/env python3
"""Build a reproducibility report from a sweep result CSV."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from config_utils import read_csv_rows, to_float


def metric_range(rows, key):
    values = [to_float(row, key) for row in rows]
    if not values:
        return "n/a"
    return f"{min(values):.6g} to {max(values):.6g}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--trend-report", default=None)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.input))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    counts = {
        "channel_fidelity": Counter(row.get("channel_fidelity", "") for row in rows),
        "channel_model": Counter(row.get("channel_model", "") for row in rows),
        "scenario": Counter(row.get("scenario", "") for row in rows),
        "mcs": Counter(row.get("mcs", "") for row in rows),
        "payload_bits": Counter(row.get("payload_bits", "") for row in rows),
        "jammer_mode": Counter(row.get("jammer_mode", "") for row in rows),
    }
    lines = [
        "# Reproducibility Report",
        "",
        f"Input: `{args.input}`",
        f"Rows: {len(rows)}",
        "",
        "## Coverage",
        "",
    ]
    for key, counter in counts.items():
        lines.append(f"### {key}")
        for value, count in sorted(counter.items()):
            lines.append(f"- `{value}`: {count}")
        lines.append("")
    lines += [
        "## Metric Ranges",
        "",
        f"- PDR: {metric_range(rows, 'pdr')}",
        f"- PLR: {metric_range(rows, 'plr')}",
        f"- PER: {metric_range(rows, 'per')}",
        f"- p95 delay: {metric_range(rows, 'p95_delay_s')} s",
        f"- deadline miss ratio: {metric_range(rows, 'deadline_miss_ratio')}",
        f"- SINR: {metric_range(rows, 'sinr_under_jamming_db')} dB",
        "",
        "## Interpretation Notes",
        "",
        "- `PER` is currently a packet-error proxy equal to application-observed lost/corrupted packets unless `phy_per_available=true` appears in the CSV.",
        "- MAC retransmissions can hide PHY errors; use both application-level PLR/PDR and PHY/MAC traces once explicit drop callbacks are added.",
        "- Synthetic QuaDRiGa placeholder traces are importer tests only and must not support final scientific claims.",
        "- Never aggregate rows with different `channel_fidelity` values into one scientific estimate.",
        "- Do not remove trend violations; investigate the channel, PHY sensitivity, traffic load, seeds and metric definitions.",
        "",
    ]
    if args.trend_report and Path(args.trend_report).exists():
        lines += ["## Trend Report", "", Path(args.trend_report).read_text()]
    output.write_text("\n".join(lines))
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
