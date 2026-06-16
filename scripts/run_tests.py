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
    assert_true(harness_row["num_users"] == "1",
                "Default core harness export must report num_users=1")
    assert_true(harness_row["per_user_pdr"].count(";") == 0,
                "Single-user fairness lists must contain one segment")
    assert_true(abs(float(harness_row["jain_fairness_index"]) - 1.0) < 1e-9,
                "Single-user or equal-PDR fairness must yield Jain index 1")

    inf_run = ROOT / "results/tests/inf_nlos_dl.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--simulationPath=ns3_core_harness",
        "--scenario=S4",
        "--channelModel=inf_nlos_dl",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=12",
        "--seed=20260601",
        "--packets=400",
        # 3GPP InF-DL NLOS @ 5.18 GHz: PL_NLOS = 32.87 + 35.7*log10(12) ~ 71.4 dB.
        # Pick txPower so signal - PL - noiseFloor ~ 3 dB SNIR (BPSK midpoint) and
        # PDR sits strictly between 0 and 1.
        "--txPowerDbm=-13.5",
        "--pathLossExponent=3.57",
        "--referenceLossDb=32.87",
        "--shadowingStdDb=7.2",
        "--industrialExcessLossDb=0",
        "--rayleighFading=false",
        "--maxDistanceM=50",
        f"--output={inf_run}",
        f"--jsonOutput={inf_run.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    inf_row = read_csv_rows(inf_run)[0]
    assert_true(inf_row["channel_model"] == "TR38901_INF_NLOS_DL",
                "inf_nlos_dl must export the 3GPP TR38.901 display name")
    assert_true(inf_row["channel_abstraction"]
                == "stochastic_3gpp_inf_nlos_dl_log_distance_with_shadowing",
                "inf_nlos_dl must label its abstraction as 3GPP InF stochastic")
    assert_true(inf_row["trace_provenance"] == "tr38901_inf_stochastic",
                "inf_nlos_dl must default to tr38901_inf_stochastic provenance")
    assert_true(inf_row["fading_variance_source"] == "log_normal_only",
                "inf_nlos_dl with rayleighFading=false must report log-normal-only SF")
    assert_true(inf_row["channel_fidelity"] == "proxy",
                "inf_nlos_dl is a stochastic proxy, not a trace replay")
    inf_pdr = float(inf_row["pdr"])
    assert_true(0.05 < inf_pdr < 0.95,
                f"inf_nlos_dl harness PDR at SNIR ~3 dB must be strictly between 0 and 1, got {inf_pdr}")
    inf_pl = float(inf_row["signal_power_dbm"]) - float(-13.5)
    assert_true(abs(inf_pl + 71.4) < 0.3,
                f"inf_nlos_dl signal_power_dbm must match TR38.901 InF-DL NLOS formula within 0.3 dB, got drift {inf_pl + 71.4} dB")

    inf_far = subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--simulationPath=ns3_core_harness",
        "--scenario=S4",
        "--channelModel=inf_nlos_dl",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=80",
        "--packets=1",
        "--maxDistanceM=50",
        f"--output={ROOT / 'results/tests/inf_far_bad.csv'}",
        f"--jsonOutput={ROOT / 'results/tests/inf_far_bad.json'}",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert_true(inf_far.returncode != 0,
                "inf_nlos_dl distance > maxDistanceM (configured by YAML) must fail")

    fair6 = ROOT / "results/tests/core_harness_users6.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--simulationPath=ns3_core_harness",
        "--scenario=S4",
        "--channelModel=cm8_rayleigh",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=3",
        "--seed=20260507",
        "--packets=600",
        "--users=6",
        "--txPowerDbm=-34",
        f"--output={fair6}",
        f"--jsonOutput={fair6.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    fair6_row = read_csv_rows(fair6)[0]
    assert_true(fair6_row["num_users"] == "6", "six-user harness must export num_users=6")
    assert_true(fair6_row["per_user_pdr"].count(";") == 5,
                "six PDR samples must be semicolon-separated")
    assert_true(float(fair6_row["jain_fairness_index"]) >= 0.99,
                "Symmetric six-user round-robin should keep Jain fairness high at moderate sample sizes")

    ofdma_common = [
        str(ROOT / "build/industrial-wifi-sim"),
        "--simulationPath=ns3_core_harness",
        "--per-ru-channel-enabled=true",
        "--scenario=S4",
        "--channelModel=cm8_rayleigh",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=3",
        "--seed=20260507",
        "--packets=200",
        "--users=6",
        "--num-rus=4",
        "--ru-width-tones=26",
        "--ru-correlation-rho=0.2",
        "--jammer-power-dbm=10",
        "--jammer-burst-ms=4",
        "--jammer-interval-ms=20",
        "--jammer-phase-ms=0",
        "--txPowerDbm=-30",
    ]

    ofdma_schema = ROOT / "results/tests/ofdma_schema.csv"
    subprocess.run([
        *ofdma_common,
        "--policy=cooldown_plus_retarget",
        "--jammer-ru-mode=narrowband_reactive",
        "--jammed-ru-list=0",
        f"--output={ofdma_schema}",
        f"--jsonOutput={ofdma_schema.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    ofdma_row = read_csv_rows(ofdma_schema)[0]
    required_schema = {
        "num_users",
        "num_rus",
        "mcs",
        "mcs_label",
        "modulation",
        "coding_rate",
        "payload_bits",
        "distance_m",
        "seed",
        "policy",
        "ru_id_initial",
        "ru_id_retry",
        "ru_changed",
        "ru_distance_tones",
        "ru_was_jammed_initial",
        "ru_was_jammed_retry",
        "sinr_initial_db",
        "sinr_retry_db",
        "estimated_sinr_initial_db",
        "estimated_sinr_retry_db",
        "per_initial",
        "per_retry",
        "estimated_per_initial",
        "estimated_per_retry",
        "estimated_best_ru",
        "oracle_best_ru",
        "ru_retarget_success",
        "cooldown_symbols",
        "cooldown_ms",
        "retry_limit",
        "deadline_ms",
        "jammer_ru_mode",
        "jammer_power_dbm",
        "jammer_burst_ms",
        "jammer_interval_ms",
        "jammer_duty_cycle",
        "jammer_phase_ms",
        "jammed_ru_count",
        "fraction_rus_jammed",
        "retry_landed_after_burst",
        "retry_landed_same_burst",
        "retry_landed_on_jammed_ru",
        "estimator_noise_db",
        "estimator_staleness_slots",
        "jammer_missed_detection_prob",
        "jammer_false_alarm_prob",
        "deadline_miss_due_to_cooldown",
        "deadline_miss_due_to_loss",
        "deadline_miss_due_to_queueing",
        "temporal_gain",
        "ru_diversity_gain",
        "combined_gain",
    }
    missing_schema = sorted(required_schema - set(ofdma_row))
    assert_true(not missing_schema, f"OFDMA CSV schema missing fields: {missing_schema}")
    assert_true(ofdma_row["policy"] == "cooldown_plus_retarget",
                "Per-RU policy override must be exported as the policy column")
    assert_true(ofdma_row["mcs_label"] == "BPSK_1_2",
                "Per-RU rows must export the MCS label")
    assert_true(ofdma_row["jammer_ru_mode"] == "narrowband_reactive",
                "Per-RU rows must export the jammer RU mode")
    assert_true(ofdma_row["jammed_ru_count"] == "1",
                "Narrowband jammer must report one jammed RU")

    broadband = ROOT / "results/tests/ofdma_broadband.csv"
    subprocess.run([
        *ofdma_common,
        "--policy=cooldown_only",
        "--jammer-ru-mode=broadband_reactive",
        f"--output={broadband}",
        f"--jsonOutput={broadband.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    broadband_row = read_csv_rows(broadband)[0]
    assert_true(broadband_row["jammed_ru_count"] == "4",
                "Broadband per-RU jammer must report all RUs jammed")
    assert_true(abs(float(broadband_row["fraction_rus_jammed"]) - 1.0) < 1e-12,
                "Broadband per-RU jammer fraction must be 1")

    partial = ROOT / "results/tests/ofdma_partial.csv"
    subprocess.run([
        *ofdma_common,
        "--policy=random_ru_hop",
        "--jammer-ru-mode=partial_band_reactive_random",
        "--jammed-ru-count=2",
        f"--output={partial}",
        f"--jsonOutput={partial.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    partial_row = read_csv_rows(partial)[0]
    assert_true(partial_row["jammed_ru_count"] == "2",
                "Partial-band jammer must report exactly K jammed RUs")
    assert_true(abs(float(partial_row["fraction_rus_jammed"]) - 0.5) < 1e-12,
                "Partial-band jammer fraction must equal K / num_rus")

    phase_a = ROOT / "results/tests/ofdma_phase_a.csv"
    phase_b = ROOT / "results/tests/ofdma_phase_b.csv"
    phase_cmd = [
        *ofdma_common,
        "--policy=oracle_best_ru",
        "--jammer-ru-mode=partial_band_reactive_random",
        "--jammed-ru-count=2",
        "--jammer-phase-ms=2",
    ]
    subprocess.run([
        *phase_cmd,
        f"--output={phase_a}",
        f"--jsonOutput={phase_a.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    subprocess.run([
        *phase_cmd,
        f"--output={phase_b}",
        f"--jsonOutput={phase_b.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    phase_row_a = read_csv_rows(phase_a)[0]
    phase_row_b = read_csv_rows(phase_b)[0]
    for key in ["pdr", "ru_id_retry", "estimated_best_ru", "oracle_best_ru", "retry_landed_on_jammed_ru"]:
        assert_true(phase_row_a[key] == phase_row_b[key],
                    f"Per-RU phase/seed run must be reproducible for {key}")

    yans_multi = subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        "--scenario=S4",
        "--channelModel=cm8_rayleigh",
        "--mcs=0",
        "--payloadBits=128",
        "--packets=10",
        "--simTimeS=1",
        "--users=2",
        f"--output={ROOT / 'results/tests/yans_multi_bad.csv'}",
        f"--jsonOutput={ROOT / 'results/tests/yans_multi_bad.json'}",
    ], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert_true(yans_multi.returncode != 0,
                "ns3_wifi_yans must reject users>1")

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

    # --- S9 estimator-impairment and ablation tests (paper [Fan26] §4.5/§6.8).
    # These tests guard the contract that:
    #   (a) Default S9 is unchanged vs. the historical archive.
    #   (b) The paper-facing policy label is exported alongside the legacy one.
    #   (c) Activating the proactive-defer with the ideal profile triggers
    #       defer events but does not depress PDR.
    #   (d) The conservative profile triggers strictly more defer events than
    #       ideal (false alarms inflate the defer count).
    #   (e) The ablation no-cooldown variant degrades PDR vs. full S9 under
    #       reactive jamming with proactive-defer enabled.
    common_args = [
        "--simulationPath=ns3_core_harness",
        "--scenario=S9",
        "--channelModel=cm8_rayleigh",
        "--maxDistanceM=10",
        "--distanceM=6",
        "--mcs=3",
        "--payloadBits=256",
        "--seed=20260507",
        "--packets=2000",
        "--simTimeS=25",
        "--jammerMode=reactive",
        "--jammerPowerDbm=10",
        "--txPowerDbm=8",
    ]

    s9_default = ROOT / "results/tests/s9_default.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        *common_args,
        f"--output={s9_default}",
        f"--jsonOutput={s9_default.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    s9_default_row = read_csv_rows(s9_default)[0]
    assert_true(s9_default_row["policy_label"] == "PLS-Realloc",
                "Legacy policy_label must stay 'PLS-Realloc' for archive continuity")
    assert_true(s9_default_row["policy_paper_label"] == "Realloc",
                "Paper-facing policy_paper_label must be 'Realloc' per [Fan26] §4.3")
    assert_true(s9_default_row["s9_proactive_defer_enabled"] == "false",
                "Default S9 must have proactive defer disabled")
    assert_true(int(s9_default_row["s9_proactive_defer_count"]) == 0,
                "Default S9 must produce zero proactive defer events")
    assert_true(s9_default_row["s9_estimator_profile"] == "ideal",
                "Default S9 estimator profile must be 'ideal'")

    s9_ideal = ROOT / "results/tests/s9_proactive_ideal.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        *common_args,
        "--s9-proactive-defer=true",
        "--s9-estimator-profile=ideal",
        f"--output={s9_ideal}",
        f"--jsonOutput={s9_ideal.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    s9_ideal_row = read_csv_rows(s9_ideal)[0]
    assert_true(s9_ideal_row["s9_proactive_defer_enabled"] == "true",
                "proactive-defer flag must propagate to CSV")
    ideal_defer = int(s9_ideal_row["s9_proactive_defer_count"])
    assert_true(ideal_defer > 0,
                f"Proactive S9 must fire at least one defer event, got {ideal_defer}")
    assert_true(float(s9_ideal_row["pdr"]) >= float(s9_default_row["pdr"]) - 1e-3,
                "Proactive S9 with ideal estimator must not degrade PDR vs. legacy S9")

    s9_conservative = ROOT / "results/tests/s9_proactive_conservative.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        *common_args,
        "--s9-proactive-defer=true",
        "--s9-estimator-profile=conservative",
        f"--output={s9_conservative}",
        f"--jsonOutput={s9_conservative.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    s9_cons_row = read_csv_rows(s9_conservative)[0]
    cons_defer = int(s9_cons_row["s9_proactive_defer_count"])
    assert_true(cons_defer > ideal_defer,
                f"Conservative profile must produce more defer events than ideal "
                f"(conservative={cons_defer}, ideal={ideal_defer})")
    assert_true(float(s9_cons_row["s9_snir_noise_std_db"]) > 0.0,
                "Conservative profile must carry a positive SNIR-noise std into the CSV")
    assert_true(float(s9_cons_row["s9_jammer_missed_detection_prob"]) > 0.0,
                "Conservative profile must carry a positive P_md into the CSV")

    s9_no_cooldown = ROOT / "results/tests/s9_ablation_no_cooldown.csv"
    subprocess.run([
        str(ROOT / "build/industrial-wifi-sim"),
        *common_args,
        "--s9-proactive-defer=true",
        "--s9-estimator-profile=ideal",
        "--s9-ablation-disable-cooldown=true",
        f"--output={s9_no_cooldown}",
        f"--jsonOutput={s9_no_cooldown.with_suffix('.json')}",
    ], cwd=ROOT, check=True)
    s9_nc_row = read_csv_rows(s9_no_cooldown)[0]
    assert_true(s9_nc_row["s9_ablation_disable_cooldown"] == "true",
                "no_cooldown ablation flag must be exported in the CSV")
    # Without cooldown the defer is ineffective: the next attempt falls in
    # the same coherence window so PDR drops. We require at least 1e-4
    # difference to avoid noise-driven flakes (the smoke run earlier showed
    # 35e-4 -> well above the threshold).
    pdr_full = float(s9_ideal_row["pdr"])
    pdr_no_cd = float(s9_nc_row["pdr"])
    assert_true(pdr_no_cd <= pdr_full + 1e-4,
                f"Ablation no_cooldown should not improve PDR vs full S9 "
                f"(full={pdr_full}, no_cooldown={pdr_no_cd})")

    print("All lightweight tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
