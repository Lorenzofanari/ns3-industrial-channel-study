#!/usr/bin/env python3
"""Coherence-time experiment analysis (Agent 7).

Decides whether the cooldown-on-failure gain correlates better with
chi_cd = T_cd / T_on  (jammer-phase decorrelation) or
chi_c  = T_cd / T_c   (channel-coherence-time decorrelation),
and whether RU/frequency retargeting or deadline effects confound it.

Outputs (under results/coherence_time_experiment/<matrix>/analysis/):
  estimated_Tc_by_group.csv     autocorrelation-based Tc per (model, Tc, seed)
  autocorrelation_curves.csv    R_gamma(tau) per (model, configured Tc)
  performance_deltas.csv        Delta-PDR/latency vs no-cooldown reference
  coherence_correlations.csv    Pearson/Spearman of gains vs chi_cd, chi_c, ...
  coherence_regression_summary.csv  linear + random-forest importances
  coherence_analysis_summary.md
  reviewer_safe_interpretation.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config_utils import ROOT  # noqa: E402

try:
    from scipy.stats import pearsonr, spearmanr
    HAVE_SCIPY = True
except Exception:  # pragma: no cover
    HAVE_SCIPY = False

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.linear_model import LinearRegression
    HAVE_SKLEARN = True
except Exception:  # pragma: no cover
    HAVE_SKLEARN = False

# Jammer timing from the campaign config (ms).
T_ON_MS = 4.0
T_OFF_MS = 16.0
T_CYC_MS = 20.0


def read_aggregate(path: Path) -> pd.DataFrame:
    lines = [l for l in path.read_text().splitlines() if not l.startswith("#")]
    from io import StringIO
    df = pd.read_csv(StringIO("\n".join(lines)))
    return df


def estimate_tc_from_trace(time_us: np.ndarray, gain_db: np.ndarray):
    """Return (Tc@0.5, Tc@1/e) in ms from a uniformly-sampled gain trace."""
    g = gain_db - gain_db.mean()
    n = len(g)
    var = np.dot(g, g)
    if var <= 0 or n < 4:
        return np.nan, np.nan
    dt_ms = (time_us[1] - time_us[0]) / 1000.0
    max_lag = min(n - 1, int(50.0 / dt_ms) + 2)  # up to ~50 ms of lag
    acf = np.array([np.dot(g[: n - k], g[k:]) / var for k in range(max_lag + 1)])

    def crossing(threshold):
        for k in range(1, len(acf)):
            if acf[k] <= threshold:
                # linear interpolation between k-1 and k
                a0, a1 = acf[k - 1], acf[k]
                frac = 0.0 if a0 == a1 else (a0 - threshold) / (a0 - a1)
                return (k - 1 + frac) * dt_ms
        return np.nan

    return crossing(0.5), crossing(1.0 / np.e)


def analyse_traces(trace_dir: Path, out_dir: Path):
    rows = []
    curves = {}
    for f in sorted(trace_dir.glob("trace_*.csv")):
        df = pd.read_csv(f)
        if df.empty:
            continue
        model = df["channel_correlation_model"].iloc[0]
        tc_cfg = float(df["coherence_time_ms"].iloc[0])
        seed = int(df["seed"].iloc[0])
        t = df["time_us"].to_numpy(dtype=float)
        g = df["channel_gain_db"].to_numpy(dtype=float)
        tc05, tc1e = estimate_tc_from_trace(t, g)
        rows.append(dict(channel_correlation_model=model, coherence_time_ms=tc_cfg, seed=seed,
                         estimated_Tc_corr_05_ms=tc05, estimated_Tc_corr_1e_ms=tc1e))
        # store ACF curve (first seed per group only, for the figure)
        key = (model, tc_cfg)
        if key not in curves:
            gd = g - g.mean()
            var = np.dot(gd, gd)
            n = len(gd)
            dt_ms = (t[1] - t[0]) / 1000.0
            max_lag = min(n - 1, int(30.0 / dt_ms))
            acf = [np.dot(gd[: n - k], gd[k:]) / var for k in range(max_lag + 1)]
            curves[key] = (dt_ms, acf)
    tc_df = pd.DataFrame(rows)
    if not tc_df.empty:
        tc_df.to_csv(out_dir / "estimated_Tc_by_group.csv", index=False)
    # autocorrelation_curves.csv (long format)
    crows = []
    for (model, tc_cfg), (dt_ms, acf) in curves.items():
        for k, v in enumerate(acf):
            crows.append(dict(channel_correlation_model=model, coherence_time_ms=tc_cfg,
                              lag_ms=k * dt_ms, acf=v))
    if crows:
        pd.DataFrame(crows).to_csv(out_dir / "autocorrelation_curves.csv", index=False)
    return tc_df


def tc_lookup(tc_df: pd.DataFrame) -> dict:
    """(model, configured_tc) -> mean estimated Tc (1/e), falling back to 0.5."""
    out = {}
    if tc_df.empty:
        return out
    g = tc_df.groupby(["channel_correlation_model", "coherence_time_ms"])
    for (model, tc), sub in g:
        est = sub["estimated_Tc_corr_1e_ms"].mean()
        if not np.isfinite(est):
            est = sub["estimated_Tc_corr_05_ms"].mean()
        out[(model, float(tc))] = est
    return out


GROUP_KEYS = ["channel_correlation_model", "coherence_time_ms", "jammer_ru_mode",
              "jammer_phase_ms", "policy", "mcs", "payload_bits", "distance_m",
              "seed", "deadline_ms"]
COOLDOWN_POLICIES = {"cooldown_only", "cooldown_plus_retarget", "full_cdr_s9"}


def compute_deltas(df: pd.DataFrame, tcmap: dict) -> pd.DataFrame:
    """Within-policy cooldown effect: metric(cd) - metric(cd=0), for cooldown
    policies, plus policy_vs_baseline retargeting contrast."""
    metrics = ["PDR", "PDR_on", "PDR_off", "p95_latency_ms", "deadline_miss_ratio",
               "retry_landed_after_burst", "retry_landed_same_burst"]
    out = []

    # (a) cooldown sweep within each cooldown policy
    cd_df = df[df["policy"].isin(COOLDOWN_POLICIES)].copy()
    for keys, sub in cd_df.groupby(GROUP_KEYS):
        ref = sub[sub["cooldown_symbols"] == 0]
        if ref.empty:
            continue
        ref = ref.iloc[0]
        model = keys[0]
        tc_cfg = float(keys[1])
        est_tc = tcmap.get((model, tc_cfg), np.nan)
        for _, r in sub.iterrows():
            cd_ms = float(r["cooldown_ms"])
            if r["cooldown_symbols"] == 0:
                continue
            rec = dict(zip(GROUP_KEYS, keys))
            rec.update(
                comparison="cooldown_sweep",
                cooldown_symbols=int(r["cooldown_symbols"]),
                cooldown_ms=cd_ms,
                estimated_Tc_1e_ms=est_tc,
                chi_cd=cd_ms / T_ON_MS,
                chi_c=cd_ms / est_tc if (est_tc and np.isfinite(est_tc) and est_tc > 0) else np.nan,
                chi_c_configured=cd_ms / tc_cfg if tc_cfg > 0 else np.nan,
                chi_D=cd_ms / float(r["deadline_ms"]),
                retry_after_burst=float(r["retry_landed_after_burst"]) if pd.notna(r["retry_landed_after_burst"]) else np.nan,
                retry_same_burst=float(r["retry_landed_same_burst"]) if pd.notna(r["retry_landed_same_burst"]) else np.nan,
            )
            for m in metrics:
                rv = r.get(m)
                fv = ref.get(m)
                rec[f"delta_{m}"] = (float(rv) - float(fv)) if (pd.notna(rv) and pd.notna(fv)) else np.nan
            out.append(rec)

    # (b) policy-vs-baseline at matched non-cooldown settings (cd=0) to expose
    #     pure RU-retargeting contribution.
    base_keys = ["channel_correlation_model", "coherence_time_ms", "jammer_ru_mode",
                 "jammer_phase_ms", "mcs", "payload_bits", "distance_m", "seed", "deadline_ms"]
    cd0 = df[df["cooldown_symbols"] == 0]
    for keys, sub in cd0.groupby(base_keys):
        base = sub[sub["policy"] == "baseline_pf"]
        if base.empty:
            continue
        base = base.iloc[0]
        for _, r in sub.iterrows():
            if r["policy"] == "baseline_pf":
                continue
            rec = dict(zip(base_keys, keys))
            rec.update(comparison="policy_vs_baseline", policy=r["policy"],
                       cooldown_symbols=0, cooldown_ms=0.0)
            for m in metrics:
                rv = r.get(m)
                fv = base.get(m)
                rec[f"delta_{m}"] = (float(rv) - float(fv)) if (pd.notna(rv) and pd.notna(fv)) else np.nan
            out.append(rec)

    return pd.DataFrame(out)


def correlations(deltas: pd.DataFrame) -> pd.DataFrame:
    sweep = deltas[deltas["comparison"] == "cooldown_sweep"].copy()
    rows = []
    predictors = ["chi_cd", "chi_c", "chi_c_configured", "chi_D",
                  "retry_after_burst", "retry_same_burst"]
    targets = ["delta_PDR", "delta_PDR_on", "delta_PDR_off", "delta_p95_latency_ms",
               "delta_deadline_miss_ratio"]
    strata = [("all", sweep)]
    for jm, sub in sweep.groupby("jammer_ru_mode"):
        strata.append((f"jammer={jm}", sub))
    for model, sub in sweep.groupby("channel_correlation_model"):
        strata.append((f"model={model}", sub))
    for sname, sub in strata:
        for tgt in targets:
            for pred in predictors:
                d = sub[[pred, tgt]].dropna()
                if len(d) < 4 or d[pred].nunique() < 2 or d[tgt].nunique() < 2:
                    continue
                if HAVE_SCIPY:
                    pr, pp = pearsonr(d[pred], d[tgt])
                    sr, sp = spearmanr(d[pred], d[tgt])
                else:
                    pr = d[pred].corr(d[tgt])
                    sr = d[pred].corr(d[tgt], method="spearman")
                    pp = sp = np.nan
                rows.append(dict(stratum=sname, target=tgt, predictor=pred, n=len(d),
                                 pearson_r=pr, pearson_p=pp, spearman_r=sr, spearman_p=sp))
    return pd.DataFrame(rows)


def regression(deltas: pd.DataFrame) -> pd.DataFrame:
    if not HAVE_SKLEARN:
        return pd.DataFrame()
    sweep = deltas[deltas["comparison"] == "cooldown_sweep"].copy()
    feats = ["chi_cd", "chi_c", "chi_D", "retry_after_burst", "mcs", "payload_bits", "distance_m"]
    rows = []
    for tgt in ["delta_PDR_on", "delta_PDR", "delta_PDR_off"]:
        d = sweep[feats + [tgt]].apply(pd.to_numeric, errors="coerce").dropna()
        if len(d) < 8 or d[tgt].nunique() < 2:
            continue
        X, y = d[feats].to_numpy(), d[tgt].to_numpy()
        lin = LinearRegression().fit(X, y)
        rf = RandomForestRegressor(n_estimators=300, random_state=0).fit(X, y)
        for i, f in enumerate(feats):
            rows.append(dict(target=tgt, feature=f, linear_coef=lin.coef_[i],
                             rf_importance=rf.feature_importances_[i],
                             r2_linear=lin.score(X, y), n=len(d)))
    return pd.DataFrame(rows)


def best_predictor(corr: pd.DataFrame, target: str, stratum: str):
    sub = corr[(corr["target"] == target) & (corr["stratum"] == stratum)]
    sub = sub.dropna(subset=["spearman_r"])
    if sub.empty:
        return None
    sub = sub.reindex(sub["spearman_r"].abs().sort_values(ascending=False).index)
    return sub.iloc[0]


def interpret(deltas: pd.DataFrame, corr: pd.DataFrame, tc_df: pd.DataFrame) -> tuple[str, str]:
    sweep = deltas[deltas["comparison"] == "cooldown_sweep"]
    pvb = deltas[deltas["comparison"] == "policy_vs_baseline"]

    def mean_gain(df, jm, col):
        s = df[df["jammer_ru_mode"] == jm][col].dropna()
        return float(s.mean()) if len(s) else np.nan

    gain_on_jam = mean_gain(sweep, "narrowband_reactive", "delta_PDR_on")
    gain_on_bb = mean_gain(sweep, "broadband_reactive", "delta_PDR_on")
    gain_nojam = mean_gain(sweep, "none", "delta_PDR")
    # RU-retargeting confound: pure ru_retarget_only gain vs baseline.
    ru_only = pvb[pvb["policy"] == "ru_retarget_only"]
    ru_gain_jam = ru_only[ru_only["jammer_ru_mode"] == "narrowband_reactive"]["delta_PDR_on"].dropna()
    ru_confound = float(ru_gain_jam.mean()) if len(ru_gain_jam) else np.nan

    bp_on = best_predictor(corr, "delta_PDR_on", "jammer=narrowband_reactive")
    bp_nojam = best_predictor(corr, "delta_PDR", "jammer=none")

    EPS = 0.01  # 1 PDR-point threshold for "meaningful" gain
    has_jam_gain = np.isfinite(gain_on_jam) and gain_on_jam > EPS
    has_nojam_gain = np.isfinite(gain_nojam) and gain_nojam > EPS

    # Decision logic (A=jammer-phase, B=channel-time, C=mixed, D=inconclusive).
    verdict = "D_INCONCLUSIVE"
    reason = []
    if has_jam_gain and not has_nojam_gain:
        verdict = "A_JAMMER_PHASE_DOMINATES"
        reason.append("Cooldown gain is concentrated under the reactive jammer "
                      "(Delta PDR_on > 0) and is absent without a jammer.")
    elif has_nojam_gain and bp_nojam is not None and bp_nojam["predictor"] in ("chi_c", "chi_c_configured") and abs(bp_nojam["spearman_r"]) > 0.4:
        if has_jam_gain:
            verdict = "C_MIXED"
            reason.append("Gain appears both under jamming and without it; the "
                          "no-jammer gain correlates with chi_c.")
        else:
            verdict = "B_CHANNEL_TIME"
            reason.append("Gain appears even without a jammer and correlates with "
                          "chi_c = T_cd/T_c.")
    elif has_jam_gain:
        verdict = "A_JAMMER_PHASE_DOMINATES"
        reason.append("Cooldown gain is present under jamming; no clean chi_c "
                      "signal in the no-jammer stratum.")

    if bp_on is not None:
        reason.append(f"Strongest |Spearman| predictor of Delta PDR_on under "
                      f"narrowband jamming: {bp_on['predictor']} "
                      f"(rho={bp_on['spearman_r']:.2f}, n={int(bp_on['n'])}).")
    if np.isfinite(ru_confound) and ru_confound > EPS:
        reason.append(f"CONFOUND: pure RU-retargeting (ru_retarget_only) already "
                      f"yields Delta PDR_on={ru_confound:.3f} vs baseline, so part "
                      f"of the cooldown_plus_retarget gain is frequency diversity, "
                      f"not temporal decorrelation.")

    # Markdown summary
    lines = ["# Coherence-time analysis summary\n",
             f"- Mean Delta PDR_on (cooldown sweep, narrowband jammer): "
             f"{gain_on_jam:.4f}",
             f"- Mean Delta PDR_on (cooldown sweep, broadband jammer): {gain_on_bb:.4f}",
             f"- Mean Delta PDR (cooldown sweep, NO jammer): {gain_nojam:.4f}",
             f"- Pure RU-retarget Delta PDR_on vs baseline (narrowband): {ru_confound:.4f}",
             ""]
    if not tc_df.empty:
        lines.append("## Estimated coherence time (autocorrelation)\n")
        agg = tc_df.groupby(["channel_correlation_model", "coherence_time_ms"]).agg(
            tc05=("estimated_Tc_corr_05_ms", "mean"),
            tc1e=("estimated_Tc_corr_1e_ms", "mean")).reset_index()
        for _, r in agg.iterrows():
            lines.append(f"- {r['channel_correlation_model']} configured Tc="
                         f"{r['coherence_time_ms']} ms -> estimated Tc@0.5="
                         f"{r['tc05']:.3f} ms, Tc@1/e={r['tc1e']:.3f} ms")
        lines.append("")
    lines.append(f"## Verdict (data-driven): {verdict}\n")
    for r in reason:
        lines.append(f"- {r}")
    summary_md = "\n".join(lines) + "\n"

    # Reviewer-safe interpretation
    rs = ["# Reviewer-safe interpretation\n",
          "This experiment uses a documented engineering channel model (AR(1)/"
          "Ornstein-Uhlenbeck fading) and a PER-waterfall PHY abstraction; it is "
          "NOT a calibrated IEEE 802.11ax PHY/MAC validation and provides NO "
          "physical-layer anti-jamming protection.\n",
          f"**Data-driven verdict: {verdict}.**\n"]
    rs += [f"- {r}" for r in reason]
    rs += ["",
           "Preserved primary interpretation: cooldown-on-failure is a "
           "scheduler-level jammer-phase decorrelation mechanism. The "
           "channel-coherence-time effect is only claimed to the extent that the "
           "no-jammer / jammer-OFF strata and the autocorrelation-estimated Tc "
           "support it; see validation_verdict.md for the allowed/forbidden "
           "claim list."]
    return summary_md, "\n".join(rs) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--matrix", default="debug")
    args = ap.parse_args()

    root = ROOT / "results/coherence_time_experiment" / args.matrix
    agg_path = root / "aggregate.csv"
    if not agg_path.exists():
        sys.exit(f"missing {agg_path}; run the campaign first")
    out_dir = root / "analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    tc_df = analyse_traces(root / "channel_traces", out_dir)
    tcmap = tc_lookup(tc_df)

    df = read_aggregate(agg_path)
    deltas = compute_deltas(df, tcmap)
    deltas.to_csv(out_dir / "performance_deltas.csv", index=False)

    corr = correlations(deltas)
    corr.to_csv(out_dir / "coherence_correlations.csv", index=False)

    reg = regression(deltas)
    if not reg.empty:
        reg.to_csv(out_dir / "coherence_regression_summary.csv", index=False)

    summary_md, reviewer_md = interpret(deltas, corr, tc_df)
    (out_dir / "coherence_analysis_summary.md").write_text(summary_md)
    (out_dir / "reviewer_safe_interpretation.md").write_text(reviewer_md)
    print(summary_md)
    print(f"Analysis written to {out_dir}")


if __name__ == "__main__":
    main()
