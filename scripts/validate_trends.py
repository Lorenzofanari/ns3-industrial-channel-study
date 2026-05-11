#!/usr/bin/env python3
"""Flag physically suspicious PLR/PER trends without deleting anomalies."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from config_utils import read_csv_rows, to_float, to_int


CAUSES = [
    "insufficient number of seeds",
    "incorrect channel mapping",
    "unrealistic transmit power",
    "wrong sensitivity or packet-detection threshold",
    "wrong noise figure or bandwidth",
    "wrong MCS mapping",
    "hidden MAC retransmissions masking PHY errors",
    "incorrect PER/PLR definition",
    "saturated traffic or jammer self-contention",
    "simulation duration too short",
]


def mean(values):
    return sum(values) / max(len(values), 1)


def grouped_means(rows, group_keys, x_key, metric):
    tmp = defaultdict(lambda: defaultdict(list))
    for row in rows:
        group = tuple(row.get(k, "") for k in group_keys)
        tmp[group][to_float(row, x_key)].append(to_float(row, metric))
    out = {}
    for group, by_x in tmp.items():
        out[group] = {x: mean(values) for x, values in by_x.items()}
    return out


def check_monotonic_distance(rows, metric, tolerance):
    keys = ["channel_model", "scenario", "mcs", "payload_bits", "jammer_mode", "jammer_power_dbm"]
    violations = []
    for group, series in grouped_means(rows, keys, "distance_m", metric).items():
        points = sorted(series.items())
        if len(points) < 2:
            continue
        for (d0, y0), (d1, y1) in zip(points, points[1:]):
            if y1 + tolerance < y0:
                violations.append({
                    "check": f"{metric}_distance_monotonic",
                    "group": dict(zip(keys, group)),
                    "from_distance_m": d0,
                    "to_distance_m": d1,
                    "from_value": y0,
                    "to_value": y1,
                })
    return violations


def check_mcs_order(rows, metric, tolerance):
    keys = ["channel_model", "scenario", "payload_bits", "distance_m", "jammer_mode", "jammer_power_dbm"]
    violations = []
    for group, series in grouped_means(rows, keys, "mcs", metric).items():
        if not {0.0, 1.0, 3.0}.issubset(series):
            continue
        if series[1.0] + tolerance < series[0.0] or series[3.0] + tolerance < series[1.0]:
            violations.append({
                "check": f"{metric}_mcs_robustness_order",
                "group": dict(zip(keys, group)),
                "mcs0": series[0.0],
                "mcs1": series[1.0],
                "mcs3": series[3.0],
            })
    return violations


def check_jammer(rows, metric, tolerance):
    keys = ["channel_model", "scenario", "mcs", "payload_bits", "distance_m"]
    by_group = defaultdict(lambda: defaultdict(list))
    for row in rows:
        group = tuple(row.get(k, "") for k in keys)
        jammer = row.get("jammer_mode", "none")
        by_group[group][jammer].append(to_float(row, metric))
    violations = []
    for group, modes in by_group.items():
        if "none" not in modes:
            continue
        baseline = mean(modes["none"])
        for mode, values in modes.items():
            if mode == "none":
                continue
            value = mean(values)
            if value + tolerance < baseline:
                violations.append({
                    "check": f"{metric}_jammer_not_lower_than_no_jammer",
                    "group": dict(zip(keys, group)),
                    "jammer_mode": mode,
                    "no_jammer": baseline,
                    "with_jammer": value,
                })
    return violations


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--json-output", default=None)
    parser.add_argument("--tolerance", type=float, default=0.02)
    args = parser.parse_args()

    rows = read_csv_rows(Path(args.input))
    violations = []
    for metric in ["plr", "per"]:
        violations.extend(check_monotonic_distance(rows, metric, args.tolerance))
        violations.extend(check_mcs_order(rows, metric, args.tolerance))
        violations.extend(check_jammer(rows, metric, args.tolerance))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Trend Validation Report",
        "",
        f"Input rows: {len(rows)}",
        f"Tolerance: {args.tolerance}",
        "",
    ]
    if not violations:
        lines += ["No trend violations above tolerance were detected.", ""]
    else:
        lines += [
            f"Detected {len(violations)} warning(s). Results were not removed or modified.",
            "",
            "Possible causes to inspect:",
        ]
        lines += [f"- {cause}" for cause in CAUSES]
        lines += ["", "## Warnings", ""]
        for i, violation in enumerate(violations, 1):
            lines.append(f"### Warning {i}: {violation['check']}")
            for key, value in violation.items():
                if key != "check":
                    lines.append(f"- `{key}`: `{value}`")
            lines.append("")
    output.write_text("\n".join(lines))

    json_output = Path(args.json_output) if args.json_output else output.with_suffix(".json")
    json_output.write_text(json.dumps({"violations": violations, "possible_causes": CAUSES}, indent=2) + "\n")
    print(f"Wrote {output}")
    print(f"Wrote {json_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
