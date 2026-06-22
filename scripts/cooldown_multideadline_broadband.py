#!/usr/bin/env python3
"""Broadband multi-deadline cooldown analysis via attempt-logs (small new runs).

Runs the diagnostic broadband reactive cell (MCS 3, burst 4 ms / interval 20 ms,
128 bit, 3 m, T_c = 5 ms; AR(1) primary + block parity) with per-attempt logging
enabled, for the full cooldown sweep T_cd in {0,19,38,76,152,304} OFDM symbols
across the three paper seeds, then derives deadline-miss ratios for
D in {1, 5, 10} ms from per-packet latency (one attempt-logged run covers all D).

This is a *small* targeted campaign (84 runs x 4000 packets) needed only because
no broadband attempt logs existed; all harness constants are taken verbatim from
configs/coherence_time_sweep.yaml so the cell matches the existing aggregate
sweep exactly.

Outputs under results/cooldown_sweep_analysis/:
  attempt_logs_broadband/*.csv
  deadline_miss_vs_cooldown_broadband.csv / .md
  PROVENANCE_broadband_multideadline.txt

Claim-boundary rules: zero observed misses -> rule-of-three upper bound, never
"zero probability"; all values aggregated across seeds with std; scheduler-harness
matrix only.
"""
from __future__ import annotations

import csv
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

REPO = Path("/home/lorenzofanari/ns3-industrial-channel-study")
sys.path.insert(0, str(REPO / "scripts"))
from config_utils import ROOT, git_commit, load_simple_yaml  # noqa: E402
from run_coherence_experiment import base_cmd  # noqa: E402

CONFIG = REPO / "configs/coherence_time_sweep.yaml"
OUT_DIR = REPO / "results/cooldown_sweep_analysis"
ATTEMPT_DIR = OUT_DIR / "attempt_logs_broadband"

COOLDOWN_POLICIES = {"cooldown_only", "cooldown_plus_retarget", "full_cdr_s9"}
COOLDOWNS = [0, 19, 38, 76, 152, 304]
POLICIES = ["baseline_pf", "cooldown_only", "ru_retarget_only", "cooldown_plus_retarget"]
MODELS = ["ar1", "block"]
TC_MS = 5
MCS = 3
PAYLOAD = 128
DIST = 3
JMODE = "broadband_reactive"
DEADLINES_MS = [1, 5, 10]


def rule_of_three_upper(n: int, conf: float = 0.95) -> float:
    return float("nan") if n <= 0 else 1.0 - (1.0 - conf) ** (1.0 / n)


def build_runs(sim: dict):
    seeds = [20260507, 20260508, 20260509]
    base_fseed = int(sim["fading_seed"])
    runs = []
    for model in MODELS:
        for si, seed in enumerate(seeds):
            fseed = base_fseed + si
            for policy in POLICIES:
                cds = COOLDOWNS if policy in COOLDOWN_POLICIES else [0]
                for cd in cds:
                    label = f"bb_{model}_tc{TC_MS}_s{seed}_{policy}_cd{cd}_mcs{MCS}_pl{PAYLOAD}"
                    runs.append(dict(label=label, model=model, seed=seed, fseed=fseed,
                                     policy=policy, cd=cd))
    return runs


def build_cmd(binary: Path, sim: dict, r: dict, packets: int):
    cmd = base_cmd(binary, sim)
    cmd += [
        "--output=/dev/null",
        f"--policy={r['policy']}",
        f"--mcs={MCS}",
        f"--payloadBits={PAYLOAD}",
        f"--distanceM={DIST}",
        f"--jammer-ru-mode={JMODE}",
        "--jammer-phase-ms=0",
        f"--s9-cooldown-symbols={r['cd']}",
        f"--coherenceTimeMs={TC_MS}",
        f"--channel-correlation-model={r['model']}",
        f"--fading-seed={r['fseed']}",
        f"--attempt-log={ATTEMPT_DIR / (r['label'] + '.csv')}",
        f"--packets={packets}",
        f"--seed={r['seed']}",
        f"--run-id={r['label']}",
    ]
    return cmd


def per_packet_outcomes(attempt_csv: Path):
    """Return list of (delivered: bool, final_latency_us: float|None) per packet."""
    delivered = {}
    latency = {}
    with attempt_csv.open() as f:
        reader = csv.DictReader(l for l in f if not l.startswith("#"))
        for row in reader:
            try:
                pid = int(row["packet_id"])
            except (KeyError, ValueError):
                continue
            succ = str(row.get("packet_success", "")).strip() in ("1", "1.0", "true", "True")
            if succ:
                delivered[pid] = True
                try:
                    latency[pid] = float(row.get("latency_us", "nan"))
                except ValueError:
                    latency[pid] = float("nan")
            else:
                delivered.setdefault(pid, False)
    out = []
    for pid, dv in delivered.items():
        out.append((dv, latency.get(pid)))
    return out


def deadline_miss(outcomes, d_ms: float) -> tuple[int, int]:
    thr_us = d_ms * 1000.0
    n = len(outcomes)
    miss = 0
    for dv, lat in outcomes:
        if not dv:
            miss += 1
        elif lat is None or lat != lat or lat > thr_us:  # nan or over threshold
            miss += 1
    return miss, n


def main() -> int:
    cfg = load_simple_yaml(CONFIG)
    sim = cfg["simulation"]
    packets = int(sim["packets_per_run"])
    binary = ROOT / sim["binary"]
    ATTEMPT_DIR.mkdir(parents=True, exist_ok=True)

    runs = build_runs(sim)
    print(f"[run] {len(runs)} attempt-logged broadband runs x {packets} packets")
    t0 = time.time()
    failures = []
    for i, r in enumerate(runs, 1):
        cmd = build_cmd(binary, sim, r, packets)
        p = subprocess.run(cmd, capture_output=True, text=True)
        if p.returncode != 0:
            failures.append((r["label"], p.stderr[:300]))
        if i % 10 == 0 or i == len(runs):
            print(f"   {i}/{len(runs)} done", flush=True)
    print(f"[run] elapsed {time.time()-t0:.1f}s; failures={len(failures)}")
    if failures:
        print("First failure:", failures[0])

    # ---- aggregate per (model, policy, cooldown, deadline) across seeds --------
    seeds = [20260507, 20260508, 20260509]
    rows = []
    from statistics import pstdev, mean
    grouping = {}
    for r in runs:
        f = ATTEMPT_DIR / (r["label"] + ".csv")
        if not f.exists():
            continue
        outcomes = per_packet_outcomes(f)
        for d in DEADLINES_MS:
            miss, n = deadline_miss(outcomes, d)
            key = (r["model"], r["policy"], r["cd"], d)
            grouping.setdefault(key, {"ratios": [], "tx": 0})
            grouping[key]["ratios"].append(miss / n if n else float("nan"))
            grouping[key]["tx"] += n
    for (model, policy, cd, d), agg in sorted(grouping.items()):
        ratios = agg["ratios"]
        m = mean(ratios)
        rec = {
            "model": model, "policy": policy, "cooldown_symbols": cd, "deadline_ms": d,
            "n_seeds": len(ratios),
            "deadline_miss_mean": round(m, 8),
            "deadline_miss_std": round(pstdev(ratios) if len(ratios) > 1 else 0.0, 8),
            "tx_pooled": agg["tx"],
            "deadline_miss_ub_ro3": round(rule_of_three_upper(agg["tx"]), 8) if m == 0.0 else "",
        }
        rows.append(rec)

    csv_path = OUT_DIR / "deadline_miss_vs_cooldown_broadband.csv"
    cols = ["model", "policy", "cooldown_symbols", "deadline_ms", "n_seeds",
            "deadline_miss_mean", "deadline_miss_std", "tx_pooled", "deadline_miss_ub_ro3"]
    with csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    md = OUT_DIR / "deadline_miss_vs_cooldown_broadband.md"
    lines = [
        "# Deadline-miss ratio vs cooldown length - broadband reactive, MCS 3 (multi-deadline)",
        "",
        "Derived from per-attempt logs (new small campaign; harness constants from "
        "`configs/coherence_time_sweep.yaml`). Slice: MCS 3, broadband_reactive, burst 4 ms / "
        "interval 20 ms, phase 0, 128 bit, 3 m, T_c=5 ms, 8 users / 8 RUs. AR(1) is the primary "
        "model; block is a parity baseline. Deadlines derived offline from per-packet latency. "
        "Means +/- seed std; `*_ub_ro3` = rule-of-three 95% upper bound for zero observed misses "
        "(never reported as zero probability). Scheduler-harness matrix only.",
        "",
        "| " + " | ".join(cols) + " |",
        "|" + "|".join(["---"] * len(cols)) + "|",
    ]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    (OUT_DIR / "PROVENANCE_broadband_multideadline.txt").write_text(
        "Broadband multi-deadline cooldown analysis (small attempt-log campaign)\n"
        f"git_commit: {git_commit()}\n"
        f"python: {platform.python_version()}\n"
        f"n_runs: {len(runs)}; packets_per_run: {packets}; seeds: {seeds}\n"
        f"models: {MODELS}; cooldowns: {COOLDOWNS}; deadlines_ms: {DEADLINES_MS}\n"
        f"cell: mcs={MCS} payload={PAYLOAD} dist={DIST} jammer={JMODE} burst4/int20 Tc={TC_MS} 8u/8ru\n"
        "command: python3 scripts/cooldown_multideadline_broadband.py\n",
        encoding="utf-8",
    )
    print(f"[done] wrote {csv_path}")
    print(f"[done] wrote {md}")
    # quick console view: AR(1) only
    print("\nAR(1) deadline-miss (mean) by policy/cooldown/deadline:")
    for r in rows:
        if r["model"] == "ar1":
            print(f"  {r['policy']:24s} cd={r['cooldown_symbols']:3d} D={r['deadline_ms']:2d}ms "
                  f"miss={r['deadline_miss_mean']:.6f} ub_ro3={r['deadline_miss_ub_ro3']}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
