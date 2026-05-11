#!/usr/bin/env python3
"""Create compact summary tables from run CSV files."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

from config_utils import read_csv_rows, to_float, write_csv_rows


GROUP_KEYS = ["channel_model", "scenario", "mcs", "payload_bits", "jammer_mode", "jammer_power_dbm"]
METRICS = ["pdr", "plr", "per", "p95_delay_s", "deadline_miss_ratio", "sinr_under_jamming_db", "robustness_ratio"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default=None)
    args = parser.parse_args()

    path = Path(args.input)
    rows = read_csv_rows(path)
    groups: dict[tuple, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[tuple(row.get(k, "") for k in GROUP_KEYS)].append(row)

    summary = []
    for key, values in sorted(groups.items()):
        out = {k: v for k, v in zip(GROUP_KEYS, key)}
        out["samples"] = len(values)
        for metric in METRICS:
            out[f"mean_{metric}"] = sum(to_float(r, metric) for r in values) / max(len(values), 1)
        summary.append(out)

    output = Path(args.output) if args.output else path.with_name("summary.csv")
    write_csv_rows(output, summary)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
