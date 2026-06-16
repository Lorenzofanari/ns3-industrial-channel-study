#!/usr/bin/env python3
"""Run the coherence-time experiment campaign.

Separates the cooldown-on-failure gain into jammer-phase decorrelation vs
channel-coherence-time decorrelation. Self-contained (does not modify the
general run_sweep.py) so the legacy archives stay bit-reproducible.

Three stages:
  1. channel traces  : uniform-time fading probe per (model, Tc, seed) for the
                       autocorrelation-based Tc estimation (channel only).
  2. aggregate sweep : pruned factorial of policy x cooldown x jammer x Tc x
                       model x mcs x payload x distance x seed -> aggregate.csv
  3. attempt logs    : focused subset with per-(packet,attempt) logging.

Usage:
  scripts/run_coherence_experiment.py --matrix debug
  scripts/run_coherence_experiment.py --matrix reduced --jobs 8
  scripts/run_coherence_experiment.py --matrix full   --jobs 16   # ~hour
"""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_utils import ROOT, git_commit, load_simple_yaml  # noqa: E402

COOLDOWN_POLICIES = {"cooldown_only", "cooldown_plus_retarget", "full_cdr_s9"}


def _as_list(value):
    return value if isinstance(value, list) else [value]


def trim_sweep(sweep: dict, matrix: str) -> dict:
    """Return the (possibly reduced) per-axis value lists for a matrix size."""
    s = {k: _as_list(v) for k, v in sweep.items()}
    if matrix == "full":
        return s
    if matrix == "reduced":
        return {
            "channel_correlation_model": ["ar1", "block"],
            "coherence_time_ms": [1, 5, 20],
            "policy": ["baseline_pf", "cooldown_only", "ru_retarget_only", "cooldown_plus_retarget"],
            "cooldown_symbols": [0, 19, 38, 76, 152, 304],
            "jammer_ru_mode": ["none", "broadband_reactive", "narrowband_reactive"],
            "jammer_phase_ms": [0],
            "mcs": [0, 3],
            "payload_bits": [128, 512],
            "distance_m": [3],
            "seeds": s["seeds"],
            "deadline_ms": [10],
        }
    # debug
    return {
        "channel_correlation_model": ["ar1"],
        "coherence_time_ms": [1, 20],
        "policy": ["baseline_pf", "cooldown_plus_retarget"],
        "cooldown_symbols": [0, 76],
        "jammer_ru_mode": ["none", "narrowband_reactive"],
        "jammer_phase_ms": [0],
        "mcs": [0],
        "payload_bits": [128],
        "distance_m": [3],
        "seeds": s["seeds"][:1],
        "deadline_ms": [10],
    }


def base_cmd(binary: Path, sim: dict) -> list[str]:
    return [
        str(binary),
        "--jsonOutput=/dev/null",
        "--simulationPath=ns3_core_harness",
        f"--channelModel={sim['channel_model']}",
        "--scenario=S4",
        "--per-ru-channel-enabled=true",
        f"--num-rus={sim['num_rus']}",
        f"--num-users={sim['num_users']}",
        f"--ru-width-tones={sim['ru_width_tones']}",
        f"--ru-correlation-rho={sim['ru_correlation_rho']}",
        f"--jammer-power-dbm={sim['jammer_power_dbm']}",
        f"--jammerDistanceM={sim['jammer_distance_m']}",
        f"--jammer-burst-ms={sim['jammer_burst_ms']}",
        f"--jammer-interval-ms={sim['jammer_interval_ms']}",
        f"--channel-update-period-us={sim['channel_update_period_us']}",
        "--intervalMs=10",
    ]


def campaign_runs(sim, sw, runs_dir):
    seeds = sw["seeds"]
    base_fseed = int(sim["fading_seed"])
    runs = []
    for model in sw["channel_correlation_model"]:
        for tc in sw["coherence_time_ms"]:
            for si, seed in enumerate(seeds):
                fseed = base_fseed + si
                for jmode in sw["jammer_ru_mode"]:
                    phases = sw["jammer_phase_ms"] if jmode != "none" else [0]
                    for phase in phases:
                        for policy in sw["policy"]:
                            cds = sw["cooldown_symbols"] if policy in COOLDOWN_POLICIES else [0]
                            for cd in cds:
                                for mcs in sw["mcs"]:
                                    for pl in sw["payload_bits"]:
                                        for dist in sw["distance_m"]:
                                            for dl in sw["deadline_ms"]:
                                                label = (
                                                    f"{model}_tc{tc}_s{seed}_{jmode}_ph{phase}_"
                                                    f"{policy}_cd{cd}_mcs{mcs}_pl{pl}_d{dist}_dl{dl}"
                                                )
                                                out = runs_dir / f"{label}.csv"
                                                runs.append(
                                                    dict(
                                                        label=label, out=out, model=model, tc=tc,
                                                        seed=seed, fseed=fseed, jmode=jmode,
                                                        phase=phase, policy=policy, cd=cd, mcs=mcs,
                                                        payload=pl, dist=dist, deadline=dl,
                                                    )
                                                )
    return runs


def build_campaign_cmd(binary, sim, r, packets):
    cmd = base_cmd(binary, sim)
    cmd += [
        f"--output={r['out']}",
        f"--policy={r['policy']}",
        f"--mcs={r['mcs']}",
        f"--payloadBits={r['payload']}",
        f"--distanceM={r['dist']}",
        f"--jammer-ru-mode={r['jmode']}",
        f"--jammer-phase-ms={r['phase']}",
        f"--s9-cooldown-symbols={r['cd']}",
        f"--coherenceTimeMs={r['tc']}",
        f"--channel-correlation-model={r['model']}",
        f"--fading-seed={r['fseed']}",
        f"--deadlineMs={r['deadline']}",
        f"--packets={packets}",
        f"--seed={r['seed']}",
        f"--run-id={r['label']}",
    ]
    return cmd


def trace_runs(sim, sw, trace_dir):
    base_fseed = int(sim["fading_seed"])
    runs = []
    for model in sw["channel_correlation_model"]:
        for tc in sw["coherence_time_ms"]:
            for si, seed in enumerate(sw["seeds"]):
                fseed = base_fseed + si
                label = f"trace_{model}_tc{tc}_s{seed}"
                runs.append(dict(label=label, out=trace_dir / f"{label}.csv",
                                 model=model, tc=tc, seed=seed, fseed=fseed))
    return runs


def build_trace_cmd(binary, sim, r, packets):
    # Channel only: no jammer, baseline policy; we only consume the trace file.
    cmd = base_cmd(binary, sim)
    cmd += [
        f"--output=/dev/null",
        "--policy=baseline_pf",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=3",
        "--jammer-ru-mode=none",
        "--jammer-phase-ms=0",
        "--s9-cooldown-symbols=0",
        f"--coherenceTimeMs={r['tc']}",
        f"--channel-correlation-model={r['model']}",
        f"--fading-seed={r['fseed']}",
        f"--channel-trace-log={r['out']}",
        f"--packets={packets}",
        f"--seed={r['seed']}",
        f"--run-id={r['label']}",
    ]
    return cmd


def attempt_runs(sim, sw, attempt_dir):
    """Focused per-attempt-log subset: both models, all Tc, the two key policies,
    jammer off vs narrowband reactive, one mcs/payload/distance, first seed."""
    base_fseed = int(sim["fading_seed"])
    seed = sw["seeds"][0]
    runs = []
    for model in sw["channel_correlation_model"]:
        for tc in sw["coherence_time_ms"]:
            for jmode in ("none", "narrowband_reactive"):
                for policy in ("baseline_pf", "cooldown_plus_retarget"):
                    cd = 76 if policy in COOLDOWN_POLICIES else 0
                    label = f"attempt_{model}_tc{tc}_{jmode}_{policy}"
                    runs.append(dict(label=label, out=attempt_dir / f"{label}.csv",
                                     model=model, tc=tc, seed=seed, fseed=base_fseed,
                                     jmode=jmode, policy=policy, cd=cd))
    return runs


def build_attempt_cmd(binary, sim, r, packets):
    cmd = base_cmd(binary, sim)
    cmd += [
        f"--output=/dev/null",
        f"--policy={r['policy']}",
        "--mcs=0",
        "--payloadBits=128",
        "--distanceM=3",
        f"--jammer-ru-mode={r['jmode']}",
        "--jammer-phase-ms=0",
        f"--s9-cooldown-symbols={r['cd']}",
        f"--coherenceTimeMs={r['tc']}",
        f"--channel-correlation-model={r['model']}",
        f"--fading-seed={r['fseed']}",
        f"--attempt-log={r['out']}",
        f"--packets={packets}",
        f"--seed={r['seed']}",
        f"--run-id={r['label']}",
    ]
    return cmd


def run_all(cmds, jobs):
    failures = []

    def _run(cmd):
        p = subprocess.run(cmd, capture_output=True, text=True)
        return cmd, p.returncode, p.stderr

    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_run, c) for c in cmds]
        for i, fut in enumerate(as_completed(futs), 1):
            cmd, rc, err = fut.result()
            if rc != 0:
                failures.append((cmd, err))
            if i % 200 == 0 or i == len(futs):
                print(f"  ... {i}/{len(futs)} runs done", flush=True)
    return failures


def concat_aggregate(runs_dir: Path, out_csv: Path):
    header = None
    n = 0
    with out_csv.open("w") as out:
        for f in sorted(runs_dir.glob("*.csv")):
            lines = [l for l in f.read_text().splitlines() if not l.startswith("#")]
            if not lines:
                continue
            if header is None:
                header = lines[0]
                out.write(header + "\n")
            for row in lines[1:]:
                out.write(row + "\n")
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="configs/coherence_time_sweep.yaml")
    ap.add_argument("--matrix", choices=["debug", "reduced", "full"], default="debug")
    ap.add_argument("--jobs", type=int, default=0, help="0 -> use all CPUs")
    ap.add_argument("--packets", type=int, default=0, help="override packets_per_run")
    ap.add_argument("--skip-traces", action="store_true")
    ap.add_argument("--skip-attempts", action="store_true")
    args = ap.parse_args()

    cfg = load_simple_yaml(ROOT / args.config)
    sim = cfg["simulation"]
    sweep = cfg["sweep"]
    sw = trim_sweep(sweep, args.matrix)
    jobs = args.jobs if args.jobs > 0 else None
    packets = args.packets or int(sim["packets_per_run"])
    if args.matrix == "debug":
        packets = args.packets or 2000

    binary = ROOT / sim["binary"]
    if not binary.exists():
        print("Binary missing; running make ...", flush=True)
        subprocess.run(["make", "-j"], cwd=ROOT, check=True)

    out_root = ROOT / sim["output_dir"] / args.matrix
    runs_dir = out_root / "runs"
    trace_dir = out_root / "channel_traces"
    attempt_dir = out_root / "attempt_logs"
    for d in (runs_dir, trace_dir, attempt_dir):
        d.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    all_failures = []

    if not args.skip_traces:
        truns = trace_runs(sim, sw, trace_dir)
        print(f"[1/3] channel traces: {len(truns)} runs", flush=True)
        cmds = [build_trace_cmd(binary, sim, r, packets) for r in truns]
        all_failures += run_all(cmds, jobs)

    cruns = campaign_runs(sim, sw, runs_dir)
    print(f"[2/3] aggregate sweep: {len(cruns)} runs", flush=True)
    cmds = [build_campaign_cmd(binary, sim, r, packets) for r in cruns]
    all_failures += run_all(cmds, jobs)
    agg_csv = out_root / "aggregate.csv"
    n_rows = concat_aggregate(runs_dir, agg_csv)
    print(f"      -> {agg_csv} ({n_rows} rows)", flush=True)

    if not args.skip_attempts:
        aruns = attempt_runs(sim, sw, attempt_dir)
        print(f"[3/3] attempt logs: {len(aruns)} runs", flush=True)
        cmds = [build_attempt_cmd(binary, sim, r, packets) for r in aruns]
        all_failures += run_all(cmds, jobs)

    elapsed = time.time() - t0
    manifest = {
        "matrix": args.matrix,
        "config": args.config,
        "git_commit": git_commit(),
        "python": platform.python_version(),
        "platform": platform.platform(),
        "packets_per_run": packets,
        "n_campaign_runs": len(cruns),
        "n_aggregate_rows": n_rows,
        "elapsed_s": round(elapsed, 1),
        "sweep_axes": sw,
        "failures": len(all_failures),
    }
    (out_root / "reproducibility_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"\nDone in {elapsed:.1f}s. Manifest: {out_root / 'reproducibility_manifest.json'}")
    if all_failures:
        print(f"WARNING: {len(all_failures)} runs failed. First error:\n{all_failures[0][1][:500]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
