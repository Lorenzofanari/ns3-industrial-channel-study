#!/usr/bin/env python3
"""Lightweight integration tests for formulas and pipeline helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from config_utils import ROOT, ensure_binary, load_simple_yaml, quadriga_distances, read_csv_rows


def assert_true(value, message):
    if not value:
        raise AssertionError(message)


def main() -> int:
    base = load_simple_yaml(ROOT / "configs/base.yaml")
    assert_true(base["simulation"]["seeds"][0] == 1, "YAML parser should read seed list")

    distances = quadriga_distances(ROOT / "data/quadriga/example_trace.csv")
    assert_true(distances == [3.0, 6.0, 9.0, 12.0], "QuaDRiGa example distances should parse")

    ensure_binary(ROOT / "build/industrial-wifi-sim")
    out = ROOT / "results/tests/cm8_limit.csv"
    bad = subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--channelModel=cm8_rayleigh",
        "--distanceM=7",
        f"--output={out}",
        f"--jsonOutput={out.with_suffix('.json')}",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert_true(bad.returncode != 0, "CM8 distance > 6 m must fail")

    good = ROOT / "results/tests/repro_a.csv"
    cmd = [
        str(ROOT / "build/industrial-wifi-sim"),
        "--scenario=S4",
        "--channelModel=cm8_rayleigh",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=2",
        "--seed=123",
        "--packets=20",
        "--simTimeS=1",
        f"--output={good}",
        f"--jsonOutput={good.with_suffix('.json')}",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)
    row = read_csv_rows(good)[0]
    tx = int(row["transmitted_packets"])
    rx = int(row["received_packets"])
    lost = int(row["lost_packets"])
    assert_true(tx == rx + lost, "PLR accounting should conserve packets")
    assert_true(abs(float(row["pdr"]) + float(row["plr"]) - 1.0) < 1e-9, "PDR + PLR should equal 1")

    json_trace = ROOT / "results/tests/quadriga_json.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--scenario=S4",
        "--channelModel=quadriga_raytraced",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=3",
        "--seed=123",
        "--packets=10",
        "--simTimeS=1",
        f"--tracePath={ROOT / 'data/quadriga/example_trace.json'}",
        f"--output={json_trace}",
        f"--jsonOutput={json_trace.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    json_row = read_csv_rows(json_trace)[0]
    assert_true(json_row["channel_abstraction"] == "external_geometry_trace_scalar_path_loss_replay", "JSON trace should load through the QuaDRiGa importer")
    print("All lightweight tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
