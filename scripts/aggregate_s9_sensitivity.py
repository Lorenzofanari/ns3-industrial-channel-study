#!/usr/bin/env python3
"""Collapse the S9 estimator-sensitivity campaign into paper Table 10.

Reads `results/s9_estimator_sensitivity/runs/*.csv` (or the directory passed
via `--input-dir`) and emits, for each MCS and estimator profile, the mean
PDR, PLR/PER, jammer-active PDR, and p95 delay (ms) averaged over the seeds /
payloads / distances dimensions, as documented in [Fan26] §6.7.

Output is a Markdown table that can be dropped directly into the manuscript.

Reactive-jammer rows only feed the table; clean (jammer_mode=none) rows are
exported in a separate `clean` section so reviewers can verify the policy
behaves correctly without interference too.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Dict, List, Tuple

from config_utils import ROOT, read_csv_rows, to_float, to_int


PROFILE_ORDER = ["ideal", "moderate", "conservative"]


def _load_rows(input_dir: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for path in sorted(input_dir.rglob("*.csv")):
        # `combined.csv` and partial-output files share the same headers; let
        # the DictReader skip metadata lines starting with '#'.
        rows.extend(read_csv_rows(path))
    return rows


def _aggregate(rows: List[Dict[str, str]], jammer_mode: str) -> Dict[Tuple[int, str], Dict[str, float]]:
    bucket: Dict[Tuple[int, str], List[Dict[str, float]]] = defaultdict(list)
    for row in rows:
        if row.get("jammer_mode") != jammer_mode:
            continue
        if row.get("policy") != "S9":
            continue
        profile = row.get("s9_estimator_profile", "ideal")
        mcs = to_int(row, "mcs")
        bucket[(mcs, profile)].append(
            {
                "pdr": to_float(row, "pdr"),
                "per": to_float(row, "per"),
                "pdr_jammer_on": to_float(row, "pdr_jammer_on"),
                "p95_delay_ms": to_float(row, "p95_delay_s") * 1000.0,
                "defer_count": float(to_int(row, "s9_proactive_defer_count")),
            }
        )
    aggregated: Dict[Tuple[int, str], Dict[str, float]] = {}
    for key, samples in bucket.items():
        aggregated[key] = {
            "pdr": mean(s["pdr"] for s in samples),
            "per": mean(s["per"] for s in samples),
            "pdr_jammer_on": mean(s["pdr_jammer_on"] for s in samples),
            "p95_delay_ms": mean(s["p95_delay_ms"] for s in samples),
            "defer_count": mean(s["defer_count"] for s in samples),
            "n": float(len(samples)),
        }
    return aggregated


def _format_table(agg: Dict[Tuple[int, str], Dict[str, float]], with_jammer_column: bool) -> str:
    if not agg:
        return "_No matching rows. Did you run `configs/s9_estimator_sensitivity.yaml`?_\n"
    mcs_values = sorted({k[0] for k in agg})
    lines: List[str] = []
    if with_jammer_column:
        lines.append("| MCS | Profile | PDR | PLR/PER | PDR jammer-ON | p95 delay [ms] | # defer |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    else:
        lines.append("| MCS | Profile | PDR | PLR/PER | p95 delay [ms] | # defer |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
    for mcs in mcs_values:
        for profile in PROFILE_ORDER:
            metrics = agg.get((mcs, profile))
            if not metrics:
                continue
            if with_jammer_column:
                lines.append(
                    f"| {mcs} | {profile} | {metrics['pdr']:.4f} | {metrics['per']:.4f} | "
                    f"{metrics['pdr_jammer_on']:.4f} | {metrics['p95_delay_ms']:.3f} | "
                    f"{int(round(metrics['defer_count']))} |"
                )
            else:
                lines.append(
                    f"| {mcs} | {profile} | {metrics['pdr']:.4f} | {metrics['per']:.4f} | "
                    f"{metrics['p95_delay_ms']:.3f} | "
                    f"{int(round(metrics['defer_count']))} |"
                )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=ROOT / "results/s9_estimator_sensitivity",
        help="Campaign output directory produced by run_sweep.py",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "results/s9_estimator_sensitivity/tab10_sensitivity.md",
        help="Markdown file to write",
    )
    args = parser.parse_args()

    rows = _load_rows(args.input_dir)
    if not rows:
        raise SystemExit(
            f"No CSV rows found under {args.input_dir}. "
            "Run `python3 scripts/run_sweep.py --config configs/s9_estimator_sensitivity.yaml` first."
        )

    reactive = _aggregate(rows, "reactive")
    clean = _aggregate(rows, "none")

    out_lines: List[str] = []
    out_lines.append("# Tab. 10 -- S9 estimator-impairment sensitivity (paper [Fan26] §6.7)\n")
    out_lines.append("CM8 reactive jamming, 10 dBm, 20 dB target SNR, three seeds, three payload\n"
                    "sizes, two distances. Each row aggregates the matching CSV rows from the\n"
                    "`s9_estimator_sensitivity` campaign.\n")
    out_lines.append("## Reactive jamming\n")
    out_lines.append(_format_table(reactive, with_jammer_column=True))
    out_lines.append("\n## Clean baseline\n")
    out_lines.append(_format_table(clean, with_jammer_column=False))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(out_lines))
    print(f"Wrote {args.output}")
    print()
    print("\n".join(out_lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
