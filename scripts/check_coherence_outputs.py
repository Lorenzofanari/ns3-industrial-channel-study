#!/usr/bin/env python3
"""Instrumentation sanity checks for the coherence-time experiment (Agent 5).

Verifies the per-attempt logs, channel traces and aggregate CSV are internally
consistent and physically sensible. Writes:
  analysis/sanity_check_report.md
  analysis/sanity_check_summary.csv
  analysis/failed_tests.md   (only if something fails)
Exits non-zero if any hard check fails.
"""

from __future__ import annotations

import argparse
import sys
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_utils import ROOT  # noqa: E402

OFDM_SYMBOL_US = 16.0


def read_aggregate(path: Path) -> pd.DataFrame:
    lines = [l for l in path.read_text().splitlines() if not l.startswith("#")]
    return pd.read_csv(StringIO("\n".join(lines)))


def acf_at_lag(g: np.ndarray, lag: int) -> float:
    gd = g - g.mean()
    var = np.dot(gd, gd)
    if var <= 0 or lag >= len(gd):
        return np.nan
    return np.dot(gd[: len(gd) - lag], gd[lag:]) / var


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", default="debug")
    args = ap.parse_args()
    root = ROOT / "results/coherence_time_experiment" / args.matrix
    out_dir = root / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = []  # (name, passed, detail)

    def check(name, passed, detail=""):
        results.append((name, bool(passed), detail))

    # ---- per-attempt log checks ----
    attempt_files = sorted((root / "attempt_logs").glob("attempt_*.csv"))
    mono_ok = True
    cooldown_ok = True
    nojam_ok = True
    fixedru_ok = True
    retarget_logged = False
    for f in attempt_files:
        df = pd.read_csv(f, na_values=["NA"])
        if df.empty:
            continue
        # cooldown_us == cooldown_symbols * 16
        cu = df["cooldown_us"].to_numpy()
        cs = df["cooldown_symbols"].to_numpy()
        if not np.allclose(cu, cs * OFDM_SYMBOL_US, atol=1e-6):
            cooldown_ok = False
        # timestamps monotonic within packet
        for _, sub in df.groupby("packet_id"):
            ts = sub.sort_values("attempt_id")["timestamp_us"].to_numpy()
            if np.any(np.diff(ts) < -1e-6):
                mono_ok = False
                break
        # no-jammer files must have jammer_state_first_tx all 0
        if "_none_" in f.name:
            if df["jammer_state_first_tx"].fillna(0).abs().sum() != 0:
                nojam_ok = False
        # fixed-RU (baseline_pf) -> ru_changed all 0
        if "baseline_pf" in f.name:
            if df["ru_changed"].fillna(0).abs().sum() != 0:
                fixedru_ok = False
        # retargeting policy under jammer -> some ru_changed == 1
        if "cooldown_plus_retarget" in f.name and "narrowband" in f.name:
            if df["ru_changed"].fillna(0).sum() > 0:
                retarget_logged = True

    check("attempt_log_present", len(attempt_files) > 0, f"{len(attempt_files)} files")
    check("cooldown_us_equals_symbols_x_16us", cooldown_ok)
    check("timestamps_monotonic_within_packet", mono_ok)
    check("no_jammer_has_no_jammer_on_state", nojam_ok)
    check("fixed_ru_baseline_keeps_ru_constant", fixedru_ok)
    check("retargeting_policy_logs_ru_changes", retarget_logged)

    # ---- channel-trace autocorrelation monotonicity (AR(1)) ----
    trace_files = sorted((root / "channel_traces").glob("trace_ar1_*.csv"))
    acf_by_tc = {}
    for f in trace_files:
        df = pd.read_csv(f)
        if df.empty:
            continue
        tc = float(df["coherence_time_ms"].iloc[0])
        t = df["time_us"].to_numpy(dtype=float)
        g = df["channel_gain_db"].to_numpy(dtype=float)
        dt_ms = (t[1] - t[0]) / 1000.0
        lag = max(1, int(round(1.0 / dt_ms)))  # ACF at ~1 ms lag
        acf_by_tc.setdefault(tc, []).append(acf_at_lag(g, lag))
    tcs = sorted(acf_by_tc)
    means = [np.nanmean(acf_by_tc[tc]) for tc in tcs]
    mono_acf = all(means[i] <= means[i + 1] + 1e-6 for i in range(len(means) - 1)) if len(means) >= 2 else False
    check("ar1_autocorr_increases_with_Tc", mono_acf,
          "; ".join(f"Tc={tc}:acf@1ms={m:.3f}" for tc, m in zip(tcs, means)))

    # ---- latency increases with cooldown (aggregate) ----
    lat_ok = True
    lat_detail = ""
    agg_path = root / "aggregate.csv"
    if agg_path.exists():
        agg = read_aggregate(agg_path)
        cdp = agg[agg["policy"].isin(["cooldown_only", "cooldown_plus_retarget"])]
        # Group by every non-cooldown axis so the p95-vs-cooldown comparison stays
        # within a single cell. jammer_phase_ms must be included: the full matrix
        # sweeps phases {0,5,10}, and mixing phases would compare the lowest- and
        # highest-cooldown rows across different phases (a grouping artefact, not a
        # physical non-monotonicity).
        keys = ["channel_correlation_model", "coherence_time_ms", "jammer_ru_mode",
                "jammer_phase_ms", "policy", "mcs", "payload_bits", "distance_m", "seed"]
        n_ok = n_tot = 0
        for _, sub in cdp.groupby(keys):
            sub = sub.sort_values("cooldown_symbols")
            if sub["cooldown_symbols"].nunique() < 2:
                continue
            lo = sub.iloc[0]["p95_latency_ms"]
            hi = sub.iloc[-1]["p95_latency_ms"]
            n_tot += 1
            if hi + 1e-9 >= lo:
                n_ok += 1
        lat_ok = (n_tot == 0) or (n_ok / n_tot >= 0.95)
        lat_detail = f"{n_ok}/{n_tot} cooldown groups have p95 non-decreasing in cooldown"
    check("latency_nondecreasing_with_cooldown", lat_ok, lat_detail)

    # ---- write report ----
    summary = pd.DataFrame(results, columns=["check", "passed", "detail"])
    summary.to_csv(out_dir / "sanity_check_summary.csv", index=False)
    n_pass = int(summary["passed"].sum())
    lines = [f"# Sanity-check report ({args.matrix} matrix)\n",
             f"{n_pass}/{len(summary)} checks passed.\n"]
    for name, passed, detail in results:
        mark = "PASS" if passed else "FAIL"
        lines.append(f"- [{mark}] {name}" + (f" — {detail}" if detail else ""))
    (out_dir / "sanity_check_report.md").write_text("\n".join(lines) + "\n")

    failed = summary[~summary["passed"]]
    if not failed.empty:
        fl = ["# Failed sanity checks\n"] + [f"- {r['check']}: {r['detail']}" for _, r in failed.iterrows()]
        (out_dir / "failed_tests.md").write_text("\n".join(fl) + "\n")
    else:
        (out_dir / "failed_tests.md").unlink(missing_ok=True)

    print("\n".join(lines))
    if not failed.empty:
        sys.exit(1)


if __name__ == "__main__":
    main()
