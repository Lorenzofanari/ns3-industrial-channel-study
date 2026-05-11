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
    subprocess.run(["make", "test"], cwd=ROOT, check=True)
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
    assert_true(row["simulation_path"] == "ns3_wifi_yans", "Yans path must export simulation_path")
    assert_true(row["policy"] == "S4", "policy column must export short form")
    assert_true(row["channel_fidelity"] == "proxy", "CM8 profile run must export proxy fidelity")
    assert_true(row["policy_label"] == "Baseline-PF", "S4 must export Baseline-PF policy label")
    assert_true(row["per_theta_m"] == "3", "MCS0 must export default PER theta")
    assert_true(row["per_slope"] == "1.15", "Default PER slope must be exported")
    assert_true(row["s8_rtx_snir_gain"] == "1.35", "Default S8 RTX SNIR gain must be exported")
    assert_true(row["s9_cooldown_symbols"] == "76", "Default S9 cooldown symbols must be exported")
    assert_true(row["eve_estimation_ideal"] == "true", "Default Eve estimation should be ideal")

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
    assert_true(json_row["channel_model"] == "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE", "Trace display name should disambiguate QD geometry replay")
    assert_true(json_row["channel_fidelity"] == "scalar_geometry_trace", "Trace replay run must export scalar geometry fidelity")

    harness = ROOT / "results/tests/core_harness.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--simulationPath=ns3_core_harness",
        "--scenario=S4",
        "--channelModel=cm8_rayleigh",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=3",
        "--seed=20260507",
        "--packets=2000",
        # txPower chosen so that signal - pathLoss - noiseFloor ~= 3 dB SNIR
        # (BPSK PER waterfall midpoint) -> PDR must sit strictly between 0 and 1.
        "--txPowerDbm=-34",
        f"--output={harness}",
        f"--jsonOutput={harness.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    harness_row = read_csv_rows(harness)[0]
    assert_true(harness_row["simulation_path"] == "ns3_core_harness",
                "Core harness run must export simulation_path=ns3_core_harness")
    assert_true(harness_row["channel_fidelity"] == "proxy",
                "CM8 harness run must remain proxy fidelity")
    assert_true(harness_row["phy_per_available"] == "true",
                "Core harness applies PER waterfall, so phy_per_available must be true")
    assert_true(harness_row["per_definition"] == "per_waterfall_sigmoid_on_per_packet_snir",
                "Core harness must declare the PER waterfall sigmoid definition")
    pdr = float(harness_row["pdr"])
    assert_true(0.05 < pdr < 0.95,
                f"Core harness PDR at SNIR ~3 dB (BPSK midpoint) must be strictly between 0 and 1, got {pdr}")
    assert_true(int(harness_row["transmitted_packets"]) == 2000,
                "Core harness must launch the requested packet count")

    nopls = ROOT / "results/tests/nopls.csv"
    gated = subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--scenario=S0",
        "--packets=1",
        "--simTimeS=1",
        f"--output={nopls}",
        f"--jsonOutput={nopls.with_suffix('.json')}",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert_true(gated.returncode != 0, "S0/NoPLS should be gated by default")
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--scenario=S0",
        "--enable-nopls-baseline=true",
        "--packets=1",
        "--simTimeS=1",
        f"--output={nopls}",
        f"--jsonOutput={nopls.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    nopls_row = read_csv_rows(nopls)[0]
    assert_true(nopls_row["scenario"] == "S0", "S0 run should preserve scenario string S0")
    assert_true(nopls_row["policy"] == "S0", "S0 run should export policy string S0")
    assert_true(nopls_row["policy_label"] == "NoPLS", "S0 run should export NoPLS label")
    print("All lightweight tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
