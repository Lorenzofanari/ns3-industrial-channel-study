#!/usr/bin/env python3
"""Run factorial ns-3 experiments and combine one-row outputs."""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import subprocess
from pathlib import Path

from config_utils import ROOT, env_with_git, ensure_binary, load_simple_yaml, quadriga_distances, read_csv_rows, scenario_retry_limit


CHANNEL_YAML = {
    # Engineering proxy historically shipped with the repository (lighter than
    # CM8 NLOS literature; see BIBLIOGRAPHY.md for the explicit deviation).
    "cm8_rayleigh": "configs/channels/cm8_rayleigh_20mhz.yaml",
    # 3GPP TR 38.901 §7.4.1 Indoor Factory NLOS Dense Clutter Low BS
    # [3GPP38901]. Modern literature reference for industrial wireless at
    # 0.5-100 GHz; this study uses fc = 5.18 GHz.
    "inf_nlos_dl": "configs/channels/inf_nlos_dl_5ghz.yaml",
    # External geometry trace replay (QuaDRiGa [Jae14]); scalar path-loss only
    # until the spectrum/SpectrumWifiPhy path is wired up.
    "quadriga_raytraced": "configs/channels/quadriga_raytraced.yaml",
}


# S9 ablation variants from [Fan26] §6.8 (Tab. 11). Each name maps to a set of
# `--s9-ablation-disable-*` CLI flags. `full` is the no-ablation reference and
# therefore emits no flag, so the row coincides with default S9 modulo the
# proactive-defer enablement (which is always true for ablation campaigns).
S9_ABLATION_VARIANTS = {
    "full": {},
    "no_jammer_flag": {"s9-ablation-disable-jammer-flag": True},
    "no_cooldown": {"s9-ablation-disable-cooldown": True},
    "snir_only": {
        "s9-ablation-disable-jammer-flag": True,
        "s9-ablation-disable-per-margin": True,
    },
}


def channel_args(name: str, root: Path) -> dict[str, str]:
    if name in ("cm8_rayleigh", "inf_nlos_dl"):
        cfg = load_simple_yaml(root / CHANNEL_YAML[name])
        return {
            "--txPowerDbm": str(cfg["tx_power_dbm"]),
            "--noiseFigureDb": str(cfg["noise_figure_db"]),
            "--bandwidthMHz": str(float(cfg["bandwidth_hz"]) / 1e6),
            "--pathLossExponent": str(cfg["path_loss_exponent"]),
            "--referenceLossDb": str(cfg["reference_loss_db"]),
            "--shadowingStdDb": str(cfg["shadowing_std_db"]),
            "--coherenceTimeMs": str(cfg["coherence_time_ms"]),
            "--industrialExcessLossDb": str(cfg["industrial_excess_loss_db"]),
            "--rayleighFading": "true" if cfg.get("rayleigh_fading", False) else "false",
            "--maxDistanceM": str(cfg.get("max_distance_m", 6.0)),
        }
    if name == "quadriga_raytraced":
        cfg = load_simple_yaml(root / "configs/channels/quadriga_raytraced.yaml")
        # `synthetic_placeholder_allowed`/`final_claims` are surfaced in every
        # CSV row so reviewers can immediately tell whether a number relies on
        # the documented placeholder trace or on measured data. The default
        # YAML ships with `synthetic_placeholder_final_claims: false` so the
        # safety gate is ON.
        synthetic_placeholder_allowed = bool(cfg.get("synthetic_placeholder_allowed", True))
        synthetic_placeholder_final_claims = bool(cfg.get("synthetic_placeholder_final_claims", False))
        # Default provenance: synthetic_placeholder when the YAML still allows
        # the placeholder trace. The operator can override --traceProvenance
        # to `measured` once data/quadriga/<file>.csv has been replaced with
        # measured QuaDRiGa data.
        trace_provenance = "measured" if not synthetic_placeholder_allowed else "synthetic_placeholder"
        return {
            "--txPowerDbm": str(cfg["tx_power_dbm"]),
            "--noiseFigureDb": str(cfg["noise_figure_db"]),
            "--bandwidthMHz": str(float(cfg["bandwidth_hz"]) / 1e6),
            "--tracePath": str(root / cfg["trace_path"]),
            "--shadowingStdDb": str(cfg.get("shadowing_std_db", 0.0)),
            "--rayleighFading": "true" if cfg.get("rayleigh_fading", False) else "false",
            "--traceProvenance": trace_provenance,
            "--syntheticPlaceholderFinalClaimsAllowed": "true" if synthetic_placeholder_final_claims else "false",
        }
    raise ValueError(f"unsupported channel {name}")


def noise_floor_dbm(bandwidth_hz: float, noise_figure_db: float) -> float:
    return -174.0 + 10.0 * math.log10(bandwidth_hz) + noise_figure_db


def log_distance_path_loss_db(channel: str, distance_m: float, root: Path) -> float:
    """Shared log-distance + log-normal SF math used by both cm8_rayleigh and
    inf_nlos_dl. Mirrors CalculateCm8PathLossDb() in
    src/channel/cm8-rayleigh-channel.cc."""
    cfg = load_simple_yaml(root / CHANNEL_YAML[channel])
    reference_distance_m = float(cfg.get("reference_distance_m", 1.0))
    d = max(distance_m, reference_distance_m)
    return (
        float(cfg["reference_loss_db"])
        + 10.0 * float(cfg["path_loss_exponent"]) * math.log10(d / reference_distance_m)
        + float(cfg.get("industrial_excess_loss_db", 0.0))
    )


def cm8_path_loss_db(distance_m: float, root: Path) -> float:
    return log_distance_path_loss_db("cm8_rayleigh", distance_m, root)


def quadriga_path_loss_db(distance_m: float, root: Path) -> float:
    cfg = load_simple_yaml(root / "configs/channels/quadriga_raytraced.yaml")
    rows = read_csv_rows(root / cfg["trace_path"])
    if not rows:
        raise ValueError("QuaDRiGa trace has no rows")
    best = min(rows, key=lambda row: abs(float(row["distance_m"]) - distance_m))
    return float(best["path_loss_db"])


def nominal_path_loss_db(channel: str, distance_m: float, root: Path) -> float:
    if channel in ("cm8_rayleigh", "inf_nlos_dl"):
        return log_distance_path_loss_db(channel, distance_m, root)
    if channel == "quadriga_raytraced":
        return quadriga_path_loss_db(distance_m, root)
    raise ValueError(f"unsupported channel {channel}")


def snr_values(min_db: float | None, max_db: float | None, step_db: float | None) -> list[float | None]:
    if min_db is None and max_db is None and step_db is None:
        return [None]
    if min_db is None or max_db is None or step_db is None:
        raise ValueError("--snr-min, --snr-max and --snr-step must be provided together")
    if step_db <= 0.0:
        raise ValueError("--snr-step must be positive")
    count = int(round((max_db - min_db) / step_db))
    values = [round(min_db + i * step_db, 10) for i in range(count + 1)]
    if not values or values[-1] < max_db - 1e-9:
        values.append(max_db)
    return values


def distance_values(channel: str, base: dict, root: Path, smoke: bool) -> list[float]:
    if channel in ("cm8_rayleigh", "inf_nlos_dl"):
        # `inf_nlos_dl_distance_m` is optional: when omitted we fall back to
        # the YAML preset's `distance_m` (default reviewer subset of the
        # 3GPP InF validity range, see configs/channels/inf_nlos_dl_5ghz.yaml).
        if channel == "inf_nlos_dl":
            distances = base["sweep"].get("inf_nlos_dl_distance_m") or load_simple_yaml(
                root / CHANNEL_YAML["inf_nlos_dl"]
            ).get("distance_m", [3, 6, 9, 12])
        else:
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


def recompute_policy_gains(rows: list[dict[str, str]]) -> None:
    keys = [
        "channel_model",
        "mcs",
        "payload_bits",
        "distance_m",
        "seed",
        "num_users",
        "num_rus",
        "jammer_ru_mode",
        "jammer_power_dbm",
        "jammer_burst_ms",
        "jammer_interval_ms",
        "jammer_phase_ms",
        "jammed_ru_count",
        "cooldown_symbols",
        "target_snr_db",
    ]
    grouped: dict[tuple[str, ...], dict[str, dict[str, str]]] = {}
    for row in rows:
        key = tuple(row.get(k, "") for k in keys)
        grouped.setdefault(key, {})[row.get("policy", "")] = row
    for members in grouped.values():
        baseline = members.get("baseline_pf")
        cooldown = members.get("cooldown_only")
        cdr = members.get("cooldown_plus_retarget")
        if not (baseline and cooldown and cdr):
            continue
        pdr_baseline = float(baseline["pdr"])
        pdr_cooldown = float(cooldown["pdr"])
        pdr_cdr = float(cdr["pdr"])
        temporal = pdr_cooldown - pdr_baseline
        ru_diversity = pdr_cdr - pdr_cooldown
        combined = pdr_cdr - pdr_baseline
        for row in members.values():
            row["temporal_gain"] = str(temporal)
            row["ru_diversity_gain"] = str(ru_diversity)
            row["combined_gain"] = str(combined)


def assert_single_channel_fidelity(rows: list[dict[str, str]], output_path: Path) -> None:
    fidelities = sorted({row.get("channel_fidelity", "") for row in rows})
    if len(fidelities) > 1:
        raise RuntimeError(
            f"{output_path} would mix channel_fidelity values {fidelities}; "
            "filter proxy and scalar_geometry_trace runs into separate output files"
        )
    paths = sorted({row.get("simulation_path", "") for row in rows})
    if len(paths) > 1:
        raise RuntimeError(
            f"{output_path} would mix simulation_path values {paths}; "
            "main paper rows (ns3_core_harness) and addendum rows (ns3_wifi_yans) "
            "must live in separate output files"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--binary", default="build/industrial-wifi-sim")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--channel-model", action="append", default=None, help="Restrict sweep to one or more channel models; repeat for multiple models only when channel_fidelity matches")
    parser.add_argument(
        "--simulation-path",
        default=None,
        choices=["ns3_wifi_yans", "ns3_core_harness"],
        help="Active simulator backend; ns3_core_harness is the main paper statistical campaign",
    )
    parser.add_argument("--packets-per-run", type=int, default=None)
    parser.add_argument("--snr-min", type=float, default=None)
    parser.add_argument("--snr-max", type=float, default=None)
    parser.add_argument("--snr-step", type=float, default=None)
    parser.add_argument(
        "--seed",
        action="append",
        type=int,
        default=None,
        help="Override the seed list from the config file. Repeat to enumerate multiple seeds; "
             "useful when sharding a large campaign across parallel processes.",
    )
    parser.add_argument("--max-runs", type=int, default=None, help="Execute at most this many eligible runs after shard filtering")
    parser.add_argument("--shard-index", type=int, default=None, help="0-based shard index for deterministic modulo sharding")
    parser.add_argument("--shard-count", type=int, default=None, help="Total number of deterministic modulo shards")
    parser.add_argument(
        "--require-measured-trace",
        action="store_true",
        help="Forward --requireMeasuredTrace=true to the simulator binary. The camera-ready "
             "pipeline should enable this so QuaDRiGa runs refuse to start with the synthetic "
             "placeholder trace.",
    )
    args = parser.parse_args()
    if (args.shard_index is None) != (args.shard_count is None):
        raise ValueError("--shard-index and --shard-count must be provided together")
    if args.shard_count is not None:
        if args.shard_count <= 0:
            raise ValueError("--shard-count must be positive")
        if args.shard_index < 0 or args.shard_index >= args.shard_count:
            raise ValueError("--shard-index must satisfy 0 <= shard-index < shard-count")
    if args.max_runs is not None and args.max_runs <= 0:
        raise ValueError("--max-runs must be positive")

    root = ROOT
    base = load_simple_yaml(root / args.config)
    simulation_path = args.simulation_path or (base.get("simulation") or {}).get(
        "simulation_path", "ns3_wifi_yans"
    )
    fairness_cfg = base.get("fairness") or {}
    fairness_users = int(fairness_cfg.get("users", 1))
    output_dir = root / (args.output_dir or base["simulation"]["output_dir"])
    if args.smoke:
        output_dir = root / "results/smoke_sweep"
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    binary = root / args.binary
    if not args.no_build:
        ensure_binary(binary)

    seeds = args.seed if args.seed else base["simulation"]["seeds"]
    channels = args.channel_model or base["sweep"]["channel_model"]
    scenarios = base["sweep"]["scenario"]
    policies = base["sweep"].get("policy") or [None]
    mcs_values = base["sweep"]["mcs"]
    payload_bits_values = base["sweep"]["payload_bits"]
    jammer_modes = base["sweep"]["jammer_mode"]
    jammer_powers = base["sweep"]["jammer_power_dbm"]
    ofdma_cfg = base.get("ofdma") or {}
    per_ru_enabled = bool(ofdma_cfg.get("per_ru_channel_enabled", False) or base["sweep"].get("jammer_ru_mode") or base["sweep"].get("policy"))
    num_users_values = base["sweep"].get("num_users") or [fairness_users]
    num_rus_values = base["sweep"].get("num_rus") or [int(ofdma_cfg.get("num_rus", 1))]
    ru_width_tones_values = base["sweep"].get("ru_width_tones") or [int(ofdma_cfg.get("ru_width_tones", 26))]
    ru_correlation_values = base["sweep"].get("ru_correlation_rho") or [float(ofdma_cfg.get("ru_correlation_rho", 0.0))]
    jammer_ru_modes = base["sweep"].get("jammer_ru_mode") or [None]
    jammed_ru_counts = base["sweep"].get("jammed_ru_count") or [int(ofdma_cfg.get("jammed_ru_count", 1))]
    jammer_burst_values = base["sweep"].get("jammer_burst_ms") or [float(ofdma_cfg.get("jammer_burst_ms", 4.0))]
    jammer_interval_values = base["sweep"].get("jammer_interval_ms") or [float(ofdma_cfg.get("jammer_interval_ms", 20.0))]
    jammer_phase_values = base["sweep"].get("jammer_phase_ms") or [float(ofdma_cfg.get("jammer_phase_ms", 0.0))]
    cooldown_symbols_values = base["sweep"].get("cooldown_symbols") or [None]
    deadline_values = base["sweep"].get("deadline_ms") or [base["simulation"]["deadline_ms"]]

    # S9 estimator-impairment dimensions ([Fan26] §4.5 / Tab. 10 and §6.8 /
    # Tab. 11). When the YAML omits these keys the campaign reduces to a
    # single ideal-profile, full-policy combo, matching the historical archive
    # behaviour bit-for-bit.
    s9_estimator_profiles: list[str | None] = base["sweep"].get("s9_estimator_profile") or [None]
    s9_ablation_variants_list: list[str | None] = base["sweep"].get("s9_ablation_variant") or [None]
    s9_proactive_defer_flag = bool(base["sweep"].get("s9_proactive_defer", False))
    for variant in s9_ablation_variants_list:
        if variant is not None and variant not in S9_ABLATION_VARIANTS:
            raise ValueError(
                f"unknown s9_ablation_variant '{variant}'; "
                f"valid choices: {sorted(S9_ABLATION_VARIANTS)}"
            )
    target_snrs: list[float | None]
    if args.snr_min is not None or args.snr_max is not None or args.snr_step is not None:
        target_snrs = snr_values(args.snr_min, args.snr_max, args.snr_step)
    else:
        snr_cfg = base.get("snr") or {}
        if "target_snr_db" in snr_cfg:
            target_snrs = [float(x) for x in snr_cfg["target_snr_db"]]
        else:
            target_snrs = snr_values(None, None, None)

    if args.smoke:
        seeds = seeds[:1]
        channels = channels[:2]
        scenarios = scenarios[:2]
        policies = policies[:1]
        mcs_values = [mcs_values[0], mcs_values[-1]]
        payload_bits_values = payload_bits_values[:1]
        jammer_modes = ["none", "constant"]
        jammer_powers = [0, 10]
        num_users_values = num_users_values[:1]
        num_rus_values = num_rus_values[:1]
        ru_width_tones_values = ru_width_tones_values[:1]
        ru_correlation_values = ru_correlation_values[:1]
        jammer_ru_modes = jammer_ru_modes[:1]
        jammed_ru_counts = jammed_ru_counts[:1]
        jammer_burst_values = jammer_burst_values[:1]
        jammer_interval_values = jammer_interval_values[:1]
        jammer_phase_values = jammer_phase_values[:1]
        cooldown_symbols_values = cooldown_symbols_values[:1]
        deadline_values = deadline_values[:1]

    all_rows: list[dict[str, str]] = []
    all_json: list[dict] = []
    planned_runs = []
    eligible_ordinal = 0
    selected_count = 0
    def selected_by_shard(ordinal: int) -> bool:
        if args.shard_count is None:
            return True
        return (ordinal - 1) % args.shard_count == args.shard_index

    for channel in channels:
        for combo in itertools.product(
            seeds,
            scenarios,
            policies,
            mcs_values,
            payload_bits_values,
            distance_values(channel, base, root, args.smoke),
            jammer_modes,
            jammer_powers,
            jammer_ru_modes,
            jammed_ru_counts,
            jammer_burst_values,
            jammer_interval_values,
            jammer_phase_values,
            cooldown_symbols_values,
            deadline_values,
            num_users_values,
            num_rus_values,
            ru_width_tones_values,
            ru_correlation_values,
            target_snrs,
            s9_estimator_profiles,
            s9_ablation_variants_list,
        ):
            (
                _seed,
                _scenario,
                _policy,
                _mcs,
                _payload_bits,
                _distance,
                jammer_mode,
                jammer_power,
                jammer_ru_mode,
                _jammed_count,
                _jammer_burst,
                _jammer_interval,
                _jammer_phase,
                _cooldown_symbols,
                _deadline_ms,
                _num_users,
                _num_rus,
                _ru_width_tones,
                _ru_correlation,
                _target_snr,
                _s9_prof,
                _s9_abl,
            ) = combo
            active_jammer = (jammer_ru_mode or jammer_mode) != "none"
            if not active_jammer and float(jammer_power) != 0.0:
                continue
            if active_jammer and float(jammer_power) == 0.0:
                continue
            eligible_ordinal += 1
            if not selected_by_shard(eligible_ordinal):
                continue
            if args.max_runs is not None and selected_count >= args.max_runs:
                continue
            selected_count += 1
            planned_runs.append((channel, combo))
    total = len(planned_runs)

    run_index = 0
    eligible_ordinal = 0
    selected_count = 0
    for channel in channels:
        chan_args = channel_args(channel, root)
        for (
            seed,
            scenario,
            policy,
            mcs,
            payload_bits,
            distance,
            jammer_mode,
            jammer_power,
            jammer_ru_mode,
            jammed_ru_count,
            jammer_burst_ms,
            jammer_interval_ms,
            jammer_phase_ms,
            cooldown_symbols,
            deadline_ms,
            num_users,
            num_rus,
            ru_width_tones,
            ru_correlation_rho,
            target_snr,
            s9_profile,
            s9_ablation,
        ) in itertools.product(
            seeds,
            scenarios,
            policies,
            mcs_values,
            payload_bits_values,
            distance_values(channel, base, root, args.smoke),
            jammer_modes,
            jammer_powers,
            jammer_ru_modes,
            jammed_ru_counts,
            jammer_burst_values,
            jammer_interval_values,
            jammer_phase_values,
            cooldown_symbols_values,
            deadline_values,
            num_users_values,
            num_rus_values,
            ru_width_tones_values,
            ru_correlation_values,
            target_snrs,
            s9_estimator_profiles,
            s9_ablation_variants_list,
        ):
            active_jammer = (jammer_ru_mode or jammer_mode) != "none"
            if not active_jammer and float(jammer_power) != 0.0:
                continue
            if active_jammer and float(jammer_power) == 0.0:
                continue
            eligible_ordinal += 1
            if not selected_by_shard(eligible_ordinal):
                continue
            if args.max_runs is not None and selected_count >= args.max_runs:
                continue
            selected_count += 1
            run_index += 1
            interval_ms = 10.0
            packets = 50 if args.smoke else int(args.packets_per_run or base["simulation"]["packets_per_run"])
            sim_time_s = max(float(base["simulation"]["simulation_time_s"]), packets * interval_ms / 1000.0 + 0.2)
            if args.smoke:
                sim_time_s = max(1.0, packets * interval_ms / 1000.0 + 0.2)
            snr_label = "configured" if target_snr is None else f"snr{target_snr:g}db"
            # Tag the run name with the S9 sensitivity / ablation coordinate
            # only when those dimensions are active so the legacy archive layout
            # is preserved when neither knob is in use.
            s9_label_parts: list[str] = []
            if s9_profile is not None:
                s9_label_parts.append(f"prof{s9_profile}")
            if s9_ablation is not None:
                s9_label_parts.append(f"abl{s9_ablation}")
            s9_label = ("_" + "_".join(s9_label_parts)) if s9_label_parts else ""
            ofdma_label_parts: list[str] = []
            if policy is not None:
                ofdma_label_parts.append(f"pol{policy}")
            if jammer_ru_mode is not None:
                ofdma_label_parts.append(f"jru{jammer_ru_mode}")
            if per_ru_enabled:
                ofdma_label_parts.append(f"rus{num_rus}")
                ofdma_label_parts.append(f"u{num_users}")
                if cooldown_symbols is not None:
                    ofdma_label_parts.append(f"cd{cooldown_symbols}")
                ofdma_label_parts.append(f"ph{jammer_phase_ms:g}")
            ofdma_label = ("_" + "_".join(ofdma_label_parts)) if ofdma_label_parts else ""
            run_name = (
                f"run_{run_index:06d}_{channel}_{scenario}_mcs{mcs}_{payload_bits}b_"
                f"{distance}m_{jammer_mode}_{jammer_power}dbm_{snr_label}{ofdma_label}{s9_label}_seed{seed}"
            )
            csv_path = runs_dir / f"{run_name}.csv"
            json_path = runs_dir / f"{run_name}.json"
            tx_power_dbm = None
            if target_snr is not None:
                chan_cfg = load_simple_yaml(root / CHANNEL_YAML[channel])
                nf = float(chan_cfg["noise_figure_db"])
                bw_hz = float(chan_cfg["bandwidth_hz"])
                tx_power_dbm = target_snr + noise_floor_dbm(bw_hz, nf) + nominal_path_loss_db(channel, float(distance), root)
            cmd = [
                str(binary),
                f"--simulationPath={simulation_path}",
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
                f"--users={num_users}",
                f"--retryLimit={scenario_retry_limit(str(scenario))}",
                f"--simTimeS={sim_time_s}",
                f"--warmupS={base['simulation']['warmup_s']}",
                f"--intervalMs={interval_ms}",
                f"--deadlineMs={deadline_ms}",
                f"--output={csv_path}",
                f"--jsonOutput={json_path}",
            ]
            if per_ru_enabled:
                cmd.extend([
                    "--per-ru-channel-enabled=true",
                    f"--num-rus={num_rus}",
                    f"--ru-width-tones={ru_width_tones}",
                    f"--ru-correlation-rho={ru_correlation_rho}",
                    f"--jammer-ru-mode={jammer_ru_mode or 'none'}",
                    f"--jammed-ru-count={jammed_ru_count}",
                    f"--jammer-burst-ms={jammer_burst_ms}",
                    f"--jammer-interval-ms={jammer_interval_ms}",
                    f"--jammer-phase-ms={jammer_phase_ms}",
                ])
                if policy is not None:
                    cmd.append(f"--policy={policy}")
                if cooldown_symbols is not None:
                    cmd.append(f"--s9-cooldown-symbols={cooldown_symbols}")
            for key, value in chan_args.items():
                if tx_power_dbm is not None and key == "--txPowerDbm":
                    continue
                cmd.append(f"{key}={value}")
            if tx_power_dbm is not None:
                cmd.append(f"--txPowerDbm={tx_power_dbm}")
            if args.require_measured_trace:
                cmd.append("--requireMeasuredTrace=true")
            # S9 sensitivity / ablation flag plumbing. We emit the proactive-
            # defer flag whenever ANY of {s9_proactive_defer, s9_estimator_profile,
            # s9_ablation_variant} is requested by the YAML, so that the new
            # estimator behaviour actually feeds the harness logic. For pure
            # legacy archives where none of these knobs is present in the YAML,
            # no S9 flag is added and the binary keeps its default behaviour.
            need_proactive = (
                s9_proactive_defer_flag
                or s9_profile is not None
                or s9_ablation is not None
            )
            if need_proactive:
                cmd.append("--s9-proactive-defer=true")
            if s9_profile is not None:
                cmd.append(f"--s9-estimator-profile={s9_profile}")
            if s9_ablation is not None:
                for flag, value in S9_ABLATION_VARIANTS[s9_ablation].items():
                    cmd.append(f"--{flag}={'true' if value else 'false'}")
            print(f"[{run_index}/{total}] {' '.join(cmd)}", flush=True)
            subprocess.run(cmd, cwd=root, env=env_with_git(), check=True)
            row = read_csv_rows(csv_path)[0]
            row["run_name"] = run_name
            row["target_snr_db"] = "" if target_snr is None else str(target_snr)
            all_rows.append(row)
            all_json.append(json.loads(json_path.read_text()))

    results_csv = output_dir / "results.csv"
    results_json = output_dir / "results.json"
    recompute_jammer_deltas(all_rows)
    recompute_policy_gains(all_rows)
    if all_rows:
        assert_single_channel_fidelity(all_rows, results_csv)
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
