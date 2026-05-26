#!/usr/bin/env python3
"""Collapse the S9 ablation campaign into paper Table 11.

Reads `results/s9_ablation/runs/*.csv` (or the directory passed via
`--input-dir`) and emits, for each MCS and ablation variant, the mean PDR,
jammer-active PDR, p95 delay, and Jain's fairness index, as documented in
[Fan26] §6.8.

The ablation variant is encoded in the row's `s9_ablation_disable_*` boolean
columns. The mapping below mirrors `S9_ABLATION_VARIANTS` in run_sweep.py.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple

from config_utils import ROOT, read_csv_rows, to_float, to_int


VARIANT_ORDER = ["full", "no_jammer_flag", "no_cooldown", "snir_only"]


def _classify_variant(row: Dict[str, str]) -> str:
    """Reverse-map the four boolean flags to one of the named variants. Rows
    that match no variant signature (e.g. an unconfigured combination) are
    returned as ``"other"`` and filtered out in the aggregator."""
    disable = {
        "jammer": row.get("s9_ablation_disable_jammer_flag", "false") == "true",
        "cooldown": row.get("s9_ablation_disable_cooldown", "false") == "true",
        "snir": row.get("s9_ablation_disable_snir_margin", "false") == "true",
        "per": row.get("s9_ablation_disable_per_margin", "false") == "true",
    }
    if not any(disable.values()):
        return "full"
    if disable["jammer"] and disable["per"] and not disable["cooldown"] and not disable["snir"]:
        return "snir_only"
    if disable["cooldown"] and not (disable["jammer"] or disable["snir"] or disable["per"]):
        return "no_cooldown"
    if disable["jammer"] and not (disable["cooldown"] or disable["snir"] or disable["per"]):
        return "no_jammer_flag"
    return "other"


def _load_rows(input_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in sorted(input_dir.rglob("*.csv")):
        rows.extend(read_csv_rows(path))
    return rows


def _aggregate(rows: List[Dict[str, str]], jammer_mode: str) -> Dict[Tuple[int, str], Dict[str, float]]:
    bucket: Dict[Tuple[int, str], List[Dict[str, float]]] = defaultdict(list)
    for row in rows:
        if row.get("jammer_mode") != jammer_mode:
            continue
        if row.get("policy") != "S9":
            continue
        variant = _classify_variant(row)
        if variant == "other":
            continue
        mcs = to_int(row, "mcs")
        bucket[(mcs, variant)].append(
            {
                "pdr": to_float(row, "pdr"),
                "pdr_jammer_on": to_float(row, "pdr_jammer_on"),
                "p95_delay_ms": to_float(row, "p95_delay_s") * 1000.0,
                "jain": to_float(row, "jain_fairness_index", default=1.0),
            }
        )
    aggregated: Dict[Tuple[int, str], Dict[str, float]] = {}
    for key, samples in bucket.items():
        aggregated[key] = {
            "pdr": mean(s["pdr"] for s in samples),
            "pdr_jammer_on": mean(s["pdr_jammer_on"] for s in samples),
            "p95_delay_ms": mean(s["p95_delay_ms"] for s in samples),
            "jain": mean(s["jain"] for s in samples),
            "n": float(len(samples)),
        }
    return aggregated


def _format_table(agg: Dict[Tuple[int, str], Dict[str, float]]) -> str:
    if not agg:
        return "_No matching rows. Did you run `configs/s9_ablation.yaml`?_\n"
    mcs_values = sorted({k[0] for k in agg})
    lines: List[str] = []
    lines.append("| MCS | Variant | PDR | PDR jammer-ON | p95 delay [ms] | Jain |")
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for mcs in mcs_values:
        for variant in VARIANT_ORDER:
            metrics = agg.get((mcs, variant))
            if not metrics:
                continue
            lines.append(
                f"| {mcs} | {variant} | {metrics['pdr']:.4f} | "
                f"{metrics['pdr_jammer_on']:.4f} | {metrics['p95_delay_ms']:.3f} | "
                f"{metrics['jain']:.4f} |"
            )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "results/s9_ablation",
        help="Campaign output directory produced by run_sweep.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results/s9_ablation/tab11_ablation.md",
        help="Markdown file to write",
    )
    args = parser.parse_args()

    rows = _load_rows(args.input_dir)
    if not rows:
        raise SystemExit(
            f"No CSV rows found under {args.input_dir}. "
            "Run `python3 scripts/run_sweep.py --config configs/s9_ablation.yaml` first."
        )

    reactive = _aggregate(rows, "reactive")
    clean = _aggregate(rows, "none")

    out_lines: List[str] = []
    out_lines.append("# Tab. 11 -- S9 component ablation (paper [Fan26] §6.8)\n")
    out_lines.append("CM8 reactive jamming, 10 dBm, 20 dB target SNR, six-user round-robin\n"
                    "fairness subset, three seeds, three payload sizes, two distances.\n")
    out_lines.append("## Reactive jamming\n")
    out_lines.append(_format_table(reactive))
    out_lines.append("\n## Clean baseline\n")
    out_lines.append(_format_table(clean))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out_lines))
    print(f"Wrote {args.output}")
    print()
    print("\n".join(out_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
