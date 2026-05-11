#!/usr/bin/env python3
"""Run factorial ns-3 experiments and combine one-row outputs."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import subprocess
from pathlib import Path

from config_utils import ROOT, env_with_git, ensure_binary, load_simple_yaml, quadriga_distances, read_csv_rows, scenario_retry_limit


def channel_args(name: str, root: Path) -> dict[str, str]:
    if name == "cm8_rayleigh":
        cfg = load_simple_yaml(root / "configs/channels/cm8_rayleigh_20mhz.yaml")
        return {
            "--txPowerDbm": str(cfg["tx_power_dbm"]),
            "--noiseFigureDb": str(cfg["noise_figure_db"]),
            "--bandwidthMHz": str(float(cfg["bandwidth_hz"]) / 1e6),
            "--pathLossExponent": str(cfg["path_loss_exponent"]),
            "--referenceLossDb": str(cfg["reference_loss_db"]),
            "--shadowingStdDb": str(cfg["shadowing_std_db"]),
            "--coherenceTimeMs": str(cfg["coherence_time_ms"]),
            "--industrialExcessLossDb": str(cfg["industrial_excess_loss_db"]),
            "--rayleighFading": "true" if cfg["rayleigh_fading"] else "false",
        }
    if name == "quadriga_raytraced":
        cfg = load_simple_yaml(root / "configs/channels/quadriga_raytraced.yaml")
        return {
            "--txPowerDbm": str(cfg["tx_power_dbm"]),
            "--noiseFigureDb": str(cfg["noise_figure_db"]),
            "--bandwidthMHz": str(float(cfg["bandwidth_hz"]) / 1e6),
            "--tracePath": str(root / cfg["trace_path"]),
        }
    raise ValueError(f"unsupported channel {name}")


def distance_values(channel: str, base: dict, root: Path, smoke: bool) -> list[float]:
    if channel == "cm8_rayleigh":
        distances = base["sweep"]["cm8_distance_m"]
        return [float(d) for d in (distances[:2] if smoke else distances)]
    trace_path = root / base["quadriga"]["trace_path"]
    distances = quadriga_distances(trace_path)
    return distances[:2] if smoke else distances


def recompute_jammer_deltas(rows: list[dict[str, str]]) -> None:
    baseline = {}
    keys = ["channel_model", "scenario", "mcs", "payload_bits", "distance_m", "seed"]
    for row in rows:
        if row.get("jammer_mode") == "none":
            baseline[tuple(row.get(k, "") for k in keys)] = row
    for row in rows:
        base = baseline.get(tuple(row.get(k, "") for k in keys))
        if not base:
            continue
        pdr = float(row["pdr"])
        plr = float(row["plr"])
        per = float(row["per"])
        base_pdr = float(base["pdr"])
        base_plr = float(base["plr"])
        base_per = float(base["per"])
        row["robustness_ratio"] = str(pdr / base_pdr if base_pdr > 0 else 0.0)
        row["plr_increase_due_to_jammer"] = str(plr - base_plr)
        row["per_increase_due_to_jammer"] = str(per - base_per)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--binary", default="build/industrial-wifi-sim")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    args = parser.parse_args()

    root = ROOT
    base = load_simple_yaml(root / args.config)
    output_dir = root / (args.output_dir or base["simulation"]["output_dir"])
    if args.smoke:
        output_dir = root / "results/smoke_sweep"
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    binary = root / args.binary
    if not args.no_build:
        ensure_binary(binary)

    seeds = base["simulation"]["seeds"]
    channels = base["sweep"]["channel_model"]
    scenarios = base["sweep"]["scenario"]
    mcs_values = base["sweep"]["mcs"]
    payload_bits_values = base["sweep"]["payload_bits"]
    jammer_modes = base["sweep"]["jammer_mode"]
    jammer_powers = base["sweep"]["jammer_power_dbm"]

    if args.smoke:
        seeds = seeds[:1]
        channels = channels[:2]
        scenarios = scenarios[:2]
        mcs_values = [mcs_values[0], mcs_values[-1]]
        payload_bits_values = payload_bits_values[:1]
        jammer_modes = ["none", "constant"]
        jammer_powers = [0, 10]

    all_rows: list[dict[str, str]] = []
    all_json: list[dict] = []
    planned_runs = []
    for channel in channels:
        for combo in itertools.product(
            seeds,
            scenarios,
            mcs_values,
            payload_bits_values,
            distance_values(channel, base, root, args.smoke),
            jammer_modes,
            jammer_powers,
        ):
            *_, jammer_mode, jammer_power = combo
            if jammer_mode == "none" and float(jammer_power) != 0.0:
                continue
            if jammer_mode != "none" and float(jammer_power) == 0.0:
                continue
            planned_runs.append((channel, combo))
    total = len(planned_runs)

    run_index = 0
    for channel in channels:
        chan_args = channel_args(channel, root)
        for seed, scenario, mcs, payload_bits, distance, jammer_mode, jammer_power in itertools.product(
            seeds,
            scenarios,
            mcs_values,
            payload_bits_values,
            distance_values(channel, base, root, args.smoke),
            jammer_modes,
            jammer_powers,
        ):
            if jammer_mode == "none" and float(jammer_power) != 0.0:
                continue
            if jammer_mode != "none" and float(jammer_power) == 0.0:
                continue
            run_index += 1
            interval_ms = 10.0
            packets = 50 if args.smoke else int(base["simulation"]["packets_per_run"])
            sim_time_s = max(float(base["simulation"]["simulation_time_s"]), packets * interval_ms / 1000.0 + 0.2)
            if args.smoke:
                sim_time_s = max(1.0, packets * interval_ms / 1000.0 + 0.2)
            run_name = f"run_{run_index:06d}_{channel}_{scenario}_mcs{mcs}_{payload_bits}b_{distance}m_{jammer_mode}_{jammer_power}dbm_seed{seed}"
            csv_path = runs_dir / f"{run_name}.csv"
            json_path = runs_dir / f"{run_name}.json"
            cmd = [
                str(binary),
                f"--scenario={scenario}",
                f"--channelModel={channel}",
                f"--standard=80211ax",
                f"--mcs={mcs}",
                f"--payloadBits={payload_bits}",
                f"--distanceM={distance}",
                f"--jammerMode={jammer_mode}",
                f"--jammerPowerDbm={jammer_power}",
                f"--seed={seed}",
                f"--packets={packets}",
                f"--retryLimit={scenario_retry_limit(str(scenario))}",
                f"--simTimeS={sim_time_s}",
                f"--warmupS={base['simulation']['warmup_s']}",
                f"--intervalMs={interval_ms}",
                f"--deadlineMs={base['simulation']['deadline_ms']}",
                f"--output={csv_path}",
                f"--jsonOutput={json_path}",
            ]
            for key, value in chan_args.items():
                cmd.append(f"{key}={value}")
            print(f"[{run_index}/{total}] {' '.join(cmd)}", flush=True)
            subprocess.run(cmd, cwd=root, env=env_with_git(), check=True)
            row = read_csv_rows(csv_path)[0]
            row["run_name"] = run_name
            all_rows.append(row)
            all_json.append(json.loads(json_path.read_text()))

    results_csv = output_dir / "results.csv"
    results_json = output_dir / "results.json"
    recompute_jammer_deltas(all_rows)
    if all_rows:
        fieldnames = ["run_name"] + [name for name in all_rows[0].keys() if name != "run_name"]
        with results_csv.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_rows)
    results_json.write_text(json.dumps(all_rows, indent=2) + "\n")
    print(f"Wrote {results_csv}")
    print(f"Wrote {results_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
