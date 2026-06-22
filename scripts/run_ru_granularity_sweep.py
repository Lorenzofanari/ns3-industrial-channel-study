#!/usr/bin/env python3
"""RU-granularity sensitivity sweep (scheduler-harness scalability evidence).

Tests whether the cooldown-on-failure result depends on the number of
scheduler-visible RUs. This is NOT a full IEEE 802.11ax 80/160 MHz PHY/MAC
validation and NOT a calibrated PHY: RUs are abstract scheduler-visible units
with seed-controlled per-RU fading; jammer occupancy is expressed as a fraction
of RUs, not physical MHz. The physical noise bandwidth (--bandwidthMHz) is held
fixed at 20 MHz so this isolates RU granularity, not bandwidth.

Minimal diagnostic matrix (Agent 7):
  MCS 3, 128 bit, 3 m, deadline 10 ms, Ton=4 ms, Tcyc=20 ms, AR(1) per-RU fading,
  T_c=5 ms, 3 paper seeds.
  policies     : baseline_pf, ru_retarget_only, cooldown_only, cooldown_plus_retarget
  jammer modes : broadband_reactive (all RUs),
                 narrowband_reactive (1 RU),
                 partial_band_reactive_random (~50% of RUs, random per burst)
  RU counts    : 4, 8, 16, 32, 64   (num-users = num-rus, fully-loaded cell)

Outputs under results/ru_granularity/:
  runs/*.csv            per-cell harness CSV (full metric schema)
  aggregate.csv         concatenation of all runs
  reproducibility_manifest.json
Aggregation + figures are produced by analyze_ru_granularity.py.
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

# --- diagnostic constants (match the cooldown/coherence headline cell) ---------
MCS = 3
PAYLOAD_BITS = 128
DISTANCE_M = 3
DEADLINE_MS = 10
TC_MS = 5
COOLDOWN_SYMBOLS = 76         # ~1.216 ms, the manuscript default
BANDWIDTH_MHZ = 20.0          # held fixed: RU-granularity isolation, not bandwidth
RU_WIDTH_TONES = 26           # telemetry only
RU_CORRELATION_RHO = 0.2
CHANNEL_CORR_MODEL = "ar1"    # primary; block is a separate parity option
JAMMER_BURST_MS = 4
JAMMER_INTERVAL_MS = 20
JAMMER_POWER_DBM = 20
JAMMER_DISTANCE_M = 1.0
CHANNEL_UPDATE_US = 50
PACKETS = 4000
SEEDS = [20260507, 20260508, 20260509]
BASE_FADING_SEED = 777

POLICIES = ["baseline_pf", "ru_retarget_only", "cooldown_only", "cooldown_plus_retarget"]
JAMMER_MODES = ["broadband_reactive", "narrowband_reactive", "partial_band_reactive_random"]
RU_COUNTS = [4, 8, 16, 32, 64]


def jammed_ru_count(mode: str, num_rus: int) -> int:
    """Jammer occupancy as a fraction of scheduler-visible RUs."""
    if mode == "broadband_reactive":
        return num_rus            # all RUs (count ignored by harness, set for the record)
    if mode == "narrowband_reactive":
        return 1                  # single RU; fraction shrinks as RU count grows
    if mode == "partial_band_reactive_random":
        return max(1, round(0.5 * num_rus))  # ~50% of RUs, random per burst
    return 1


def build_runs():
    runs = []
    for mode in JAMMER_MODES:
        for num_rus in RU_COUNTS:
            jcount = jammed_ru_count(mode, num_rus)
            for policy in POLICIES:
                cd = COOLDOWN_SYMBOLS if policy in COOLDOWN_POLICIES else 0
                for si, seed in enumerate(SEEDS):
                    fseed = BASE_FADING_SEED + si
                    label = f"{mode}_R{num_rus}_{policy}_cd{cd}_s{seed}"
                    runs.append(dict(label=label, mode=mode, num_rus=num_rus,
                                     jcount=jcount, policy=policy, cd=cd,
                                     seed=seed, fseed=fseed))
    return runs


def build_cmd(binary: Path, r: dict, out_csv: Path, packets: int):
    return [
        str(binary),
        "--jsonOutput=/dev/null",
        "--simulationPath=ns3_core_harness",
        "--channelModel=cm8_rayleigh",
        "--scenario=S4",
        "--per-ru-channel-enabled=true",
        f"--num-rus={r['num_rus']}",
        f"--num-users={r['num_rus']}",
        f"--ru-width-tones={RU_WIDTH_TONES}",
        f"--ru-correlation-rho={RU_CORRELATION_RHO}",
        f"--bandwidthMHz={BANDWIDTH_MHZ}",
        f"--jammer-power-dbm={JAMMER_POWER_DBM}",
        f"--jammerDistanceM={JAMMER_DISTANCE_M}",
        f"--jammer-burst-ms={JAMMER_BURST_MS}",
        f"--jammer-interval-ms={JAMMER_INTERVAL_MS}",
        f"--channel-update-period-us={CHANNEL_UPDATE_US}",
        "--intervalMs=10",
        f"--output={out_csv}",
        f"--policy={r['policy']}",
        f"--mcs={MCS}",
        f"--payloadBits={PAYLOAD_BITS}",
        f"--distanceM={DISTANCE_M}",
        f"--jammer-ru-mode={r['mode']}",
        f"--jammed-ru-count={r['jcount']}",
        "--jammer-phase-ms=0",
        f"--s9-cooldown-symbols={r['cd']}",
        f"--coherenceTimeMs={TC_MS}",
        f"--channel-correlation-model={CHANNEL_CORR_MODEL}",
        f"--fading-seed={r['fseed']}",
        f"--deadlineMs={DEADLINE_MS}",
        f"--packets={packets}",
        f"--seed={r['seed']}",
        f"--run-id={r['label']}",
    ]


def concat(runs_dir: Path, out_csv: Path) -> int:
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--jobs", type=int, default=0, help="0 -> all CPUs")
    ap.add_argument("--packets", type=int, default=PACKETS)
    args = ap.parse_args()

    binary = ROOT / "build/industrial-wifi-sim"
    if not binary.exists():
        subprocess.run(["make", "-j"], cwd=ROOT, check=True)

    out_root = ROOT / "results/ru_granularity"
    runs_dir = out_root / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    runs = build_runs()
    print(f"[run] {len(runs)} runs x {args.packets} packets "
          f"({len(JAMMER_MODES)} modes x {len(RU_COUNTS)} RU-counts x "
          f"{len(POLICIES)} policies x {len(SEEDS)} seeds)")

    def _run(r):
        cmd = build_cmd(binary, r, runs_dir / f"{r['label']}.csv", args.packets)
        p = subprocess.run(cmd, capture_output=True, text=True)
        return r["label"], p.returncode, p.stderr

    t0 = time.time()
    failures = []
    jobs = args.jobs if args.jobs > 0 else None
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = [ex.submit(_run, r) for r in runs]
        for i, fut in enumerate(as_completed(futs), 1):
            label, rc, err = fut.result()
            if rc != 0:
                failures.append((label, err[:300]))
            if i % 30 == 0 or i == len(futs):
                print(f"   {i}/{len(futs)} done", flush=True)
    elapsed = time.time() - t0

    agg = out_root / "aggregate.csv"
    n_rows = concat(runs_dir, agg)
    manifest = dict(
        experiment="ru_granularity_sensitivity",
        git_commit=git_commit(),
        python=platform.python_version(),
        platform=platform.platform(),
        packets_per_run=args.packets,
        seeds=SEEDS,
        ru_counts=RU_COUNTS,
        policies=POLICIES,
        jammer_modes=JAMMER_MODES,
        cooldown_symbols=COOLDOWN_SYMBOLS,
        bandwidth_mhz=BANDWIDTH_MHZ,
        channel_correlation_model=CHANNEL_CORR_MODEL,
        coherence_time_ms=TC_MS,
        n_runs=len(runs),
        n_aggregate_rows=n_rows,
        elapsed_s=round(elapsed, 1),
        failures=len(failures),
        note=("Abstract scheduler-visible RUs; jammer occupancy = fraction of RUs; "
              "bandwidth/noise held fixed at 20 MHz; NOT a calibrated 802.11ax PHY "
              "and NOT a full 80/160 MHz validation."),
    )
    (out_root / "reproducibility_manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[run] elapsed {elapsed:.1f}s; failures={len(failures)}; "
          f"aggregate -> {agg} ({n_rows} rows)")
    if failures:
        print("First failure:", failures[0])
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
