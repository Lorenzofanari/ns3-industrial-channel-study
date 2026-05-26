#!/usr/bin/env python3
"""Merge per-seed shards produced by scripts/launch_paper_campaign.sh.

Each shard directory holds a `results.csv` and `results.json` produced by
`run_sweep.py` for a single (channel, seed) pair. This helper concatenates the
six shards into the unified CSV/JSON files consumed by the parse/validate/plot
pipeline.

Usage:
    python3 scripts/merge_paper_shards.py --root results/paper_v2
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path

from config_utils import ROOT, read_csv_rows


SHARD_RE = re.compile(r"^(cm8_rayleigh|inf_nlos_dl|quadriga_raytraced)_seed\d+$")


def find_shards(root: Path) -> list[Path]:
    shards = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and SHARD_RE.match(child.name) and (child / "results.csv").exists():
            shards.append(child)
    return shards


def merge_csv(shards: list[Path], output: Path) -> None:
    rows: list[dict[str, str]] = []
    fieldnames: list[str] | None = None
    for shard in shards:
        shard_rows = read_csv_rows(shard / "results.csv")
        for row in shard_rows:
            rows.append(row)
        if shard_rows and fieldnames is None:
            fieldnames = list(shard_rows[0].keys())
    if not rows or fieldnames is None:
        raise SystemExit("No shard rows found; cannot merge")
    # Maintain header from the first shard but extend with any keys observed in
    # later shards. This is defensive: all shards should share the same header.
    extra = sorted({k for r in rows for k in r.keys() if k not in fieldnames})
    fieldnames = fieldnames + extra
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})
    print(f"Wrote {output} ({len(rows)} rows, {len(fieldnames)} columns)")


def merge_json(shards: list[Path], output: Path) -> None:
    merged: list[dict] = []
    for shard in shards:
        path = shard / "results.json"
        if path.exists():
            merged.extend(json.loads(path.read_text()))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(merged, indent=2) + "\n")
    print(f"Wrote {output} ({len(merged)} entries)")


def split_by_channel(rows: list[dict[str, str]]):
    by_channel: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        # Use the run_name prefix to disambiguate, fallback to channel_model.
        run_name = row.get("run_name", "")
        if "cm8" in run_name:
            key = "cm8"
        elif "quadriga" in run_name or "QD_" in row.get("channel_model", ""):
            key = "quadriga"
        else:
            key = row.get("channel_model", "unknown").split("_")[0]
        by_channel.setdefault(key, []).append(row)
    return by_channel


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default="results/paper_v2",
                        help="Directory containing per-shard subdirectories")
    parser.add_argument("--keep-shards", action="store_true",
                        help="Skip the optional shard cleanup step")
    args = parser.parse_args()

    root = Path(args.root)
    if not root.is_absolute():
        root = ROOT / root
    shards = find_shards(root)
    if not shards:
        print(f"No shards found under {root}", file=sys.stderr)
        return 1
    print(f"Merging {len(shards)} shards from {root}")
    for shard in shards:
        print(f"  - {shard.relative_to(root)}")

    # Unified output (all channels, all seeds): kept for global views/notes.
    merge_csv(shards, root / "results.csv")
    merge_json(shards, root / "results.json")

    # Channel-specific outputs: needed because plot_results.py / validate_trends
    # / parse_results expect a single channel_fidelity per file in some flows
    # and because the paper figures are typically generated separately per
    # channel.
    rows = read_csv_rows(root / "results.csv")
    by_channel = split_by_channel(rows)
    for chan, chan_rows in by_channel.items():
        out_csv = root / chan / "results.csv"
        out_csv.parent.mkdir(parents=True, exist_ok=True)
        fieldnames = list(chan_rows[0].keys())
        with out_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(chan_rows)
        print(f"Wrote per-channel CSV: {out_csv} ({len(chan_rows)} rows)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
