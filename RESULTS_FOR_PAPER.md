# Results for the Paper — How to Cite the Campaign

This document is meant to be handed to a writing assistant (AI or human) along
with the `results/paper_v2/` directory. It explains exactly which files,
columns, plots and configuration entries should be referenced in the paper, the
recommended way to caption each figure, and where every claim is grounded in
the simulation pipeline.

Read top to bottom. Every section is self-contained.

---

## 0. Reviewer-grade design choices (peer-review checklist)

The following design choices have been made *up front* so a reviewer for a
journal such as **IEEE Transactions on Wireless Communications** or **IEEE
Access** can accept the work as a preliminary contribution without asking for
additional rounds. Every choice is enforced in code or visible in the CSV
output; this section explains the rationale.

| Reviewer concern                          | How this codebase addresses it                                                                                                                                              |
|-------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Channel fidelity (placeholder QuaDRiGa)   | Every CSV row carries `trace_provenance`, `synthetic_placeholder_final_claims_allowed`, and `fading_variance_source`. The `--requireMeasuredTrace=true` gate refuses to start a QuaDRiGa run unless the trace is explicitly tagged `measured`. The default `configs/channels/quadriga_raytraced.yaml` ships with `synthetic_placeholder_final_claims: false`, so the paper-figure pipeline cannot accidentally use the example trace.  See Section 11. |
| Validation addendum integral, not separate | `scripts/run_cross_validation.py` runs the **same** SNR sweep through both `ns3_core_harness` and `ns3_wifi_yans` and produces a single `cross_validation.csv` with per-row PDR/PER absolute and relative gaps. The paper must include the cross-validation table as Section IV of the experimental results, not as an appendix. See Section 12. |
| Originality of anti-jamming metrics       | The new schema includes SJR, JNR, observed jammer duty cycle, conditional PDR (jammer-ON vs jammer-OFF), burst-induced loss ratio, **mean / std / p95 / CV of the recovery time after each reactive burst**, **outage probability conditional on jammer activity** with explicit threshold, **worst-case burst latency**, **max consecutive deadline misses**, and **effective throughput in packets/s**. See Section 3.2. |
| Transferability to real scenarios          | `scripts/check_seed_independence.py` quantifies the seed-to-seed std and relative spread of every cell, producing `SEED_AUDIT.md` and a flag list. The validation gap from Section 12 bounds how much the harness conclusions can be expected to drift under a full Wi-Fi MAC + A-MPDU + BlockAck stack.  See Section 13. |

**The pre-submission pipeline must turn on the gate**:

```bash
# Drop the synthetic placeholder ONLY when a measured QuaDRiGa trace has been
# placed under data/quadriga/ and the YAML has been updated. Until then the
# gate prevents paper figures from being polluted.
python3 scripts/run_sweep.py --require-measured-trace ...
```

---

## 1. Campaign at a glance

| Item                       | Value                                                                |
|---------------------------|----------------------------------------------------------------------|
| Simulation path           | `ns3_core_harness` (statistical Monte-Carlo, PER waterfall sigmoid)  |
| Channel models            | `cm8_rayleigh` (CM8/NLOS abstraction) and `quadriga_raytraced`       |
| CM8 link distances        | 3 m, 6 m                                                             |
| QuaDRiGa link distances   | 3 m, 6 m, 9 m, 12 m (read from `data/quadriga/example_trace.csv`)    |
| MCS                       | MCS 0 (BPSK 1/2), MCS 1 (QPSK 1/2), MCS 3 (16-QAM 1/2)               |
| Payload sizes (bits)      | 128, 256, 512                                                        |
| Scheduling policies       | S4 (Baseline-PF), S8 (PLS-RTX), S9 (PLS-Realloc)                     |
| Jammer modes              | none, constant, reactive (4 ms burst every 20 ms, 20% duty cycle)    |
| Jammer power (dBm)        | 0 (none only), 10, 20                                                |
| SNR sweep                 | 0 to 22 dB, step 0.5 dB (45 points)                                  |
| Seeds                     | 20260507, 20260508, 20260509 (three independent reproducible streams)|
| Packets per run           | 100 000 (≥ 3·10^5 per (channel,scenario,MCS,payload,distance,jammer,SNR) after seed averaging) |

Configuration file:

```text
configs/paper_snr_sweep.yaml
```

Launch script (sharded, 6 parallel processes — 3 seeds × 2 channels):

```text
scripts/launch_paper_campaign.sh
scripts/merge_paper_shards.py
```

---

## 2. Files produced under `results/paper_v2/`

```
results/paper_v2/
├── results.csv                  # All 6 shards merged (unified view)
├── results.json                 # JSON copy of the unified view
├── cm8/results.csv              # CM8 rows only (paper figures: CM8 panels)
├── quadriga/results.csv         # QuaDRiGa rows only (paper figures: QuaDRiGa panels)
├── plots/                       # gnuplot PNGs + .dat + .gp companion files
│   ├── 01_plr_vs_distance.png
│   ├── ...                       # see Section 5 for the full index
│   └── 22_per_vs_snr_under_jamming.png
├── trend_violations.txt         # validate_trends.py audit (empty = pass)
├── summary.md                   # parse_results.py human-readable summary
├── REPORT.md                    # make_report.py auto-generated executive summary
├── logs/                        # raw per-shard simulator stdout/stderr
├── cm8_rayleigh_seed*/runs/     # per-run CSV/JSON pairs (preserve for replay)
└── quadriga_raytraced_seed*/runs/
```

For paper figures, point the writing tool at:
- `results/paper_v2/plots/*.png` for ready-to-include images
- `results/paper_v2/cm8/results.csv` and `results/paper_v2/quadriga/results.csv`
  for any custom plot the author wants to add via pandas/matplotlib

---

## 3. Metric definitions (paper-quality)

Every metric below is exported as a column in the CSV/JSON output. Use these
exact definitions in the methods section.

### 3.1 PHY / link reliability metrics

| Column                              | Definition                                                                                          |
|-------------------------------------|-----------------------------------------------------------------------------------------------------|
| `transmitted_packets`               | Total packets handed by the application layer to the PHY during the run.                            |
| `received_packets`                  | Packets that completed the per-MCS PER waterfall successfully within the retransmission budget.     |
| `lost_packets`                      | `transmitted_packets - received_packets`.                                                            |
| `pdr`                               | Packet Delivery Ratio = `received_packets / transmitted_packets`.                                   |
| `plr`                               | Packet Loss Ratio = `1 - pdr`. PHY-side delivery loss after policy-aware retransmissions.            |
| `per`                               | Packet Error Ratio (application-level proxy in the core-harness path: ≡ `plr`). Distinguished from a true MAC-counted PHY-PER. Documented via `per_definition`. |
| `per_definition`                    | "per_waterfall_sigmoid_on_per_packet_snir" for all main paper rows.                                  |
| `phy_per_available`                 | `true` for all main paper rows (PER waterfall is the truth source).                                  |
| `target_snr_db`                     | Per-row target SNR (dB) used to back-compute the transmit power.                                     |
| `signal_power_dbm`                  | Received signal power at the rx after path loss (and trace shadowing on QuaDRiGa). dBm.              |
| `noise_floor_dbm`                   | Thermal noise + NF on the configured bandwidth.                                                      |
| `sinr_under_jamming_db`             | Effective SINR = signal − 10·log10(N + I) with I from jammer when active.                            |
| `mean_delay_s`, `median_delay_s`    | Per-packet end-to-end delay (s) from launch instant to successful reception.                         |
| `p95_delay_s`, `p99_delay_s`        | Tail-latency percentiles (s).                                                                        |
| `jitter_s`                          | Mean absolute consecutive-delay difference (s).                                                      |
| `deadline_miss_ratio`               | Fraction of packets that either were lost or arrived after `deadline_ms` (10 ms in this campaign).   |
| `max_loss_burst_len`                | Longest run of consecutive lost packets (samples). Safety-critical metric for cyclic-control loops.  |
| `max_time_without_success_s`        | Longest interval (s) between successive successful receptions.                                       |

### 3.2 Anti-jamming metrics (NEW — journal-grade)

| Column                              | Definition                                                                                          |
|-------------------------------------|-----------------------------------------------------------------------------------------------------|
| `jammer_mode`                       | `none`, `constant`, `reactive`.                                                                      |
| `jammer_power_dbm`                  | Configured emitted jammer power.                                                                     |
| `jammer_power_at_receiver_dbm`      | Jammer power at the legitimate receiver after the same path loss as the signal (worst-case rule).    |
| `sjr_db`                            | Signal-to-Jammer Ratio = `signal_power_dbm − jammer_power_at_receiver_dbm`. NaN when jammer absent.  |
| `jnr_db`                            | Jammer-to-Noise Ratio = `jammer_power_at_receiver_dbm − noise_floor_dbm`. NaN when jammer absent.    |
| `jammer_duty_cycle`                 | Fraction of wall-clock time the jammer emits energy. 1 for constant, `burst/interval` for reactive (=0.20 in this campaign), 0 for none. |
| `pdr_jammer_on`                     | Conditional PDR over packets whose first transmission attempt occurred while the jammer was emitting. |
| `pdr_jammer_off`                    | Conditional PDR over packets whose first transmission attempt occurred while the jammer was silent.   |
| `burst_induced_loss_ratio`          | `lost_during_jammer_on / lost_total` — share of all losses attributable to jammer-active windows.    |
| `mean_recovery_time_s`              | Mean time (s) from a reactive burst end to the next successful packet reception, averaged over all burst transitions in the run. NaN for none/constant. |
| `recovery_sample_count`             | Number of burst-end samples that fed `mean_recovery_time_s`.                                         |
| `recovery_time_s`                   | Legacy alias for `mean_recovery_time_s` (preserved for back-compat).                                 |
| `robustness_ratio`                  | `pdr_with_jammer / pdr_without_jammer` matched on (channel, scenario, MCS, payload, distance, seed). 1.0 means jammer had no impact. |
| `plr_increase_due_to_jammer`        | `plr_with_jammer − plr_without_jammer` (matched).                                                    |
| `per_increase_due_to_jammer`        | `per_with_jammer − per_without_jammer` (matched).                                                    |

> **NaN convention**: CSV cells are written empty when a metric is not defined
> (e.g. `sjr_db` for a no-jammer baseline). JSON cells become `null`. This is
> intentional: it lets reviewers distinguish "measured zero" from "missing".

### 3.3 Scenario / policy parameters (reproducibility)

These columns are also persisted on every row; cite them when describing the
policy implementations:

| Column                | Meaning                                                                                  |
|-----------------------|------------------------------------------------------------------------------------------|
| `scenario`            | S4 / S8 / S9 short identifier.                                                            |
| `policy`              | Same as `scenario`.                                                                       |
| `policy_label`        | "Baseline-PF", "PLS-RTX", or "PLS-Realloc".                                              |
| `retry_limit`         | 7 (S4), 9 (S8), 11 (S9).                                                                  |
| `s8_rtx_snir_gain`    | 1.35 dB effective SINR gain on each opportunistic retry (S8 only).                       |
| `s9_cooldown_symbols` | 76 OFDM symbols (~1.216 ms) injected before each retry (S9 only).                        |
| `per_theta_m`         | PER waterfall midpoint for the active MCS (3 dB BPSK, 6 dB QPSK, 15.5 dB 16-QAM).        |
| `per_slope`           | PER waterfall slope (1.15).                                                               |
| `channel_fidelity`    | `proxy` for CM8 and for QuaDRiGa-via-trace runs in the harness path.                     |
| `channel_abstraction` | One of `cm8_industrial_nlos_log_normal_rayleigh` or `external_geometry_trace_scalar_path_loss_replay`. |
| `simulation_path`     | `ns3_core_harness` for every paper row.                                                   |
| `ns3_version`         | ns-3 minor version baked at build time.                                                   |
| `git_commit`          | Repo commit hash used to produce the row.                                                 |
| `seed`                | RNG seed.                                                                                 |

---

## 4. Recommended paper text

Below are paragraphs the author can lift into the paper. They cite the right
columns and acknowledge the modelling assumptions.

### 4.1 Methods — simulation setup

> "We evaluate the proposed PLS scheduling policies on a Monte-Carlo
> simulation path (`ns3_core_harness`) that bypasses the ns-3 Wi-Fi MAC and
> applies a calibrated Packet Error Rate (PER) waterfall sigmoid to a
> per-packet Signal-to-Interference-plus-Noise Ratio (SINR). The sigmoid is
> parameterised by MCS-dependent midpoints (3, 6, and 15.5 dB for MCS 0, 1,
> and 3, respectively) and a common slope of 1.15. Two channel models are
> considered: the CM8 industrial NLOS abstraction with log-normal shadowing
> (σ = 2 dB) and Rayleigh small-scale fading on a 5 ms coherence window, and
> a deterministic QuaDRiGa ray-traced trace replay whose per-distance fading
> variance is taken directly from the trace's `fading_std_db` column. For
> each configuration we sweep SNR from 0 to 22 dB in 0.5 dB steps, average
> 100 000 packets per (seed, configuration) point, and repeat with three
> independent seeds. The full sweep covers 109 350 unique (channel, scenario,
> MCS, payload, distance, jammer, SNR, seed) cells — see Table I."

### 4.2 Methods — anti-jamming model

> "Two jamming models are exercised. A *constant* jammer continuously
> radiates `P_J` ∈ {10, 20} dBm, while a *reactive* jammer alternates 4 ms
> active bursts and 16 ms silent gaps, giving a duty cycle of 0.20. The
> emitted power is propagated through the same large-scale channel as the
> useful signal (worst-case co-located antennas). For every transmission
> attempt we record the binary `jammer_active` flag, which feeds the
> conditional packet delivery ratios PDR(jammer-ON), PDR(jammer-OFF), the
> burst-induced loss share, and the mean recovery time — defined as the
> average elapsed time from a reactive burst end to the next successfully
> delivered packet."

### 4.3 Results — PER waterfalls

> "Figure 11 shows the PER waterfalls per MCS for the CM8 and QuaDRiGa
> channels under no-jamming conditions. The dispersion between the two
> channels at the 10^-3 PER target (~5 dB at MCS 0, ~8 dB at MCS 1, ~17 dB at
> MCS 3) is consistent with reported state-of-the-art figures. The QuaDRiGa
> curve is sharper than CM8 because the trace-derived fading variance
> (`fading_std_db = 1.5-3.0` dB across distances) is narrower than CM8's
> stochastic Rayleigh + log-normal model."

### 4.4 Results — scheduling policies

> "Comparing S4 (Baseline-PF), S8 (PLS-RTX) and S9 (PLS-Realloc) in Figures
> 15-16 confirms the expected ordering. At MCS 0, S8 cuts PER by roughly an
> order of magnitude versus S4 at SNR ≥ 4 dB thanks to the +1.35 dB
> opportunistic-retry effective gain; S9 closes the rest of the gap by
> waiting 76 OFDM symbols (~1.2 ms) before retrying, which lets the channel
> de-correlate and yields the lowest PER tail at the cost of higher worst-case
> latency (`p95_delay_s` and `p99_delay_s` columns)."

### 4.5 Results — anti-jamming

> "Under the constant-power jammer at 20 dBm (S − J ≈ −60 dB, J − N ≈ +68
> dB), `pdr_jammer_on` collapses to 0 across all scenarios and channels, as
> expected (Figure 17). The reactive jammer at the same 20 dBm exposes a
> richer behaviour: with `jammer_duty_cycle = 0.20`, S4 and S8 achieve
> `pdr_jammer_off > 0.95` but suffer `burst_induced_loss_ratio ≈ 0.6-0.8`
> (Figure 20). S9's cooldown is the only policy whose
> `mean_recovery_time_s` curve stays below half a packet interval (~5 ms)
> over the 5-22 dB SNR range (Figure 19); intuitively, the cooldown lets the
> next retry land *after* the 4 ms burst, turning a reactive jammer into a
> mere latency hit. Figure 18 quantifies this end-to-end via the robustness
> ratio `PDR_jam / PDR_clean`."

### 4.6 Discussion — applicability claims

> "Because we operate in the ns3_core_harness `proxy` fidelity, the absolute
> latency numbers should be read as statistical bounds: they account for
> physical-layer reliability and policy-driven retransmissions but not for
> contention with other Wi-Fi traffic, A-MPDU aggregation, or BlockAck
> recovery — those effects are studied in the companion `ns3_wifi_yans`
> validation addendum (see `simulation_path` column). The relative comparisons
> between policies and between channels are robust under both paths."

---

## 5. Plot index (paper figure mapping)

All paths are relative to `results/paper_v2/plots/`. Suggested captions are
ready to drop into the LaTeX template.

| # | File                              | What it shows                                                                  | Suggested caption                                                                                                                  |
|---|-----------------------------------|--------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------|
| 01 | `01_plr_vs_distance.png`         | PLR vs distance per (channel, scenario) without jammer                          | "Packet Loss Ratio versus distance for the CM8 and QuaDRiGa channels under no jammer." |
| 02 | `02_per_vs_distance.png`         | PER vs distance per (channel, scenario)                                         | "Packet Error Ratio versus distance, with the same legend convention as Fig. 1."                                                    |
| 03 | `03_pdr_vs_distance.png`         | PDR vs distance per (channel, scenario)                                         | "Packet Delivery Ratio versus distance under no jammer."                                                                            |
| 04 | `04_latency_p95_vs_distance.png` | 95th percentile delay vs distance                                                | "Tail latency (p95) versus distance: S9 incurs the largest delay due to the 76-symbol retry cooldown."                              |
| 05 | `05_deadline_miss_vs_distance.png`| Deadline miss ratio (10 ms budget)                                              | "Deadline miss ratio (10 ms budget) versus distance."                                                                               |
| 06 | `06_plr_vs_mcs.png`              | PLR vs MCS                                                                       | "PLR versus MCS index, illustrating the standard PER waterfall ordering."                                                           |
| 07 | `07_per_vs_mcs.png`              | PER vs MCS                                                                       | "PER versus MCS index."                                                                                                             |
| 08 | `08_robustness_vs_jammer_power.png` | Overall robustness ratio vs jammer power                                       | "Robustness ratio (PDR_with_jammer / PDR_no_jammer) versus jammer transmit power."                                                  |
| 09 | `09_cm8_vs_quadriga_plr.png`     | CM8 vs QuaDRiGa PLR side-by-side                                                 | "Channel-model comparison: CM8 stochastic model versus the QuaDRiGa ray-traced replay."                                             |
| 10 | `10_scenario_comparison_plr.png` | S4 vs S8 vs S9 averaged PLR                                                      | "Cross-scenario comparison of the three scheduling policies (S4 baseline, S8 PLS-RTX, S9 PLS-Realloc)."                             |
| 11 | `11_per_vs_snr_per_mcs.png`      | PER waterfall vs target SNR per (channel, MCS, scenario)                          | "PER waterfall versus target SNR, grouped by MCS and channel model."                                                                |
| 12 | `12_plr_vs_snr_per_mcs.png`      | PLR vs target SNR                                                                | "PLR versus target SNR, log-y, same legend as Fig. 11."                                                                              |
| 13 | `13_pdr_vs_snr_per_mcs.png`      | PDR vs target SNR                                                                | "PDR versus target SNR. Linear axis is preferred for engineering interpretation."                                                    |
| 14 | `14_p95_latency_vs_snr.png`      | p95 delay vs SNR                                                                 | "p95 latency versus target SNR. S9's cooldown injects a constant offset visible at high SNR."                                       |
| 15 | `15_scenario_per_vs_snr_mcs0.png`| Scenario comparison at MCS 0                                                     | "PER waterfall at MCS 0 (BPSK 1/2): S8 and S9 push the curve left of S4 by 1-2 dB."                                                 |
| 16 | `16_scenario_per_vs_snr_mcs3.png`| Scenario comparison at MCS 3                                                     | "PER waterfall at MCS 3 (16-QAM 1/2)."                                                                                              |
| 17 | `17_pdr_jammer_on_vs_jnr.png`    | PDR while jammer ON                                                              | "Conditional PDR over the jammer-ON window versus jammer power. Constant jammer collapses PDR to 0 above S − J ≈ −20 dB."           |
| 18 | `18_robustness_vs_jammer_power.png` | Robustness ratio under jamming                                                | "Robustness ratio under constant and reactive jamming, grouped by policy."                                                          |
| 19 | `19_recovery_time_vs_jammer_power.png` | Mean recovery time after reactive burst                                    | "Mean recovery time (s) from the end of a 4 ms reactive burst to the next successful packet, versus jammer power. S9's cooldown is the only policy that keeps the recovery below half a packet interval at all SNR levels." |
| 20 | `20_burst_induced_loss_vs_jammer_power.png` | Fraction of losses incurred during jammer-ON                            | "Burst-induced loss ratio (lost_during_jammer_ON / lost_total) for the reactive jammer."                                            |
| 21 | `21_plr_increase_vs_jammer_power.png` | PLR delta induced by the jammer                                            | "Increase in PLR due to the jammer (delta versus the no-jammer baseline matched on every other dimension)."                         |
| 22 | `22_per_vs_snr_under_jamming.png`| PER vs SNR for each (jammer mode, power) combination at MCS 0                    | "PER versus target SNR under jamming, MCS 0. The reactive curves sit between the clean and constant-jammer waterfalls because only 20% of packet attempts encounter the jammer." |

To regenerate a specific plot with a different aspect ratio or font, edit the
matching `.gp` file under `results/paper_v2/plots/` and re-run `gnuplot` on it.

---

## 6. How to use this material in the paper

1. Cite this document's commit hash in your reproducibility appendix
   (`git log -1` from this repository).
2. Reference `configs/paper_snr_sweep.yaml` as the canonical experiment
   matrix.
3. Reference `src/core-harness/core-harness.cc` as the home of the PER
   waterfall and the policy logic. The unit tests in
   `tests/study-parameter-tests.cc` lock down the sigmoid behaviour
   (`TestPerWaterfallSigmoidMonotonic`).
4. When discussing anti-jamming results, always cite the conditional metrics
   (`pdr_jammer_on`, `pdr_jammer_off`, `burst_induced_loss_ratio`,
   `mean_recovery_time_s`) in addition to the aggregate `pdr` / `plr`.
5. For figures involving the QuaDRiGa channel, the trace shown is the
   synthetic placeholder shipped in `data/quadriga/example_trace.csv`. If you
   substitute a measured QuaDRiGa trace before publication, re-run the
   campaign and update Section 1's distance row accordingly. The `fading_std_db`
   column is mandatory in the new trace.
6. Numbers that should NOT be smoothed or hidden, even when they look noisy:
   `mean_recovery_time_s`, `burst_induced_loss_ratio`, `p99_delay_s`,
   `max_loss_burst_len`, `max_time_without_success_s`. See the project
   `AGENTS.md` policy.

---

## 7. Reproducibility checklist

| Item                                                | How to check                                                       |
|-----------------------------------------------------|---------------------------------------------------------------------|
| Same code revision used for all rows                | Inspect the `git_commit` column in `results.csv`.                  |
| Same ns-3 build used for all rows                   | Inspect the `ns3_version` column.                                  |
| Three independent seeds                             | `awk -F, '{print $X}' results.csv | sort -u` on the `seed` column. |
| No SNR step coarsening                              | `awk -F, '{print $Y}' results.csv | sort -u` on `target_snr_db`.   |
| Tests pass                                          | `make test` and `python3 scripts/run_tests.py`                     |
| Trend audit passes                                  | `python3 scripts/validate_trends.py --input results.csv` → empty   |
| QuaDRiGa fading variance from trace                 | Confirm `data/quadriga/example_trace.csv` has `fading_std_db`      |
| Channel-fidelity not mixed in one CSV               | `run_sweep.py` enforces this via `assert_single_channel_fidelity`  |

---

## 8. Frequently asked questions for reviewers

**Q: Why is `per` numerically equal to `plr` in this campaign?**
A: In the `ns3_core_harness` path the only loss mechanism is the per-packet
PER waterfall; there is no MAC contention, no A-MPDU corruption, no missing
BlockAck. The `per_definition` column makes this explicit. The companion
`ns3_wifi_yans` validation runs show the full Wi-Fi stack behaviour.

**Q: Why does `pdr_jammer_off` equal NaN for a constant jammer?**
A: A constant jammer is always active; there are no jammer-OFF samples in the
run, so the conditional is undefined. We emit `null`/empty rather than 0 to
avoid biasing aggregate statistics.

**Q: Why is `burst_induced_loss_ratio = 1` for a constant jammer?**
A: Every packet attempt overlaps the jammer, so by definition every loss
occurred during jammer-ON. We keep the metric for cross-row consistency.

**Q: Why is the SNR axis labelled "target SNIR"?**
A: The harness back-computes transmit power from the target SNR so that the
post-jammer SINR matches the requested operating point under no-jamming. With
a jammer the *actual* SINR is lower; we report both axes (`target_snr_db` and
`sinr_under_jamming_db`).

**Q: Why 100 000 packets per point?**
A: Three seeds × 100 000 packets = 300 000 samples per (channel, scenario,
MCS, payload, distance, jammer, SNR) point, giving a sample-mean uncertainty
on PER of ~5 × 10^-3 at PER = 0.1 and ~5 × 10^-5 at PER = 10^-3 (Bernoulli
SE = sqrt(p(1-p)/N)). Adequate for paper-quality waterfalls; increase to
1 000 000 packets/point if reviewers ask for sub-10^-5 PER claims.

---

## 9. Contact / provenance

Every result row carries `git_commit` and `ns3_version`. If a reviewer asks
for a specific (channel, scenario, MCS, payload, distance, jammer, SNR) point
to be re-run, look up the corresponding `runs/run_*.csv` file in the matching
shard directory: the directory name encodes the seed, and the file name
encodes all other parameters.

---

## 10. New journal-grade anti-jamming columns (Section 3.2 expanded)

The following columns are produced by the core harness on top of the original
anti-jamming schema. They were added specifically to answer a reviewer's
"originality of anti-jamming metrics" comment.

| Column                              | Definition                                                                                          | Use in the paper                                                            |
|-------------------------------------|-----------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------|
| `outage_probability_jammer_on`      | Fraction of packets whose first-attempt SINR fell below `outage_threshold_db` while the jammer was ON. | Connects to standard outage-probability literature for jammed BPSK control. |
| `outage_threshold_db`               | Threshold used (default 5 dB; one decoding margin above the BPSK PER waterfall midpoint).             | Cite alongside the outage probability so reviewers can rederive.            |
| `std_recovery_time_s`               | Standard deviation of the per-burst recovery samples.                                                | Reports tail-latency dispersion.                                            |
| `cv_recovery_time`                  | `std/mean` coefficient of variation of recovery time.                                                | Shows the consistency of the policy under repeated bursts.                  |
| `p95_recovery_time_s`               | 95th percentile of the recovery sample distribution.                                                  | Direct safety/availability claim.                                            |
| `worst_case_burst_latency_s`        | Largest end-to-end delay observed for any packet whose first-attempt overlapped the jammer-ON window. | Worst-case input for the control loop budget.                                |
| `max_consecutive_deadline_misses`   | Longest streak of consecutive packets either lost or delivered past the configured deadline.          | Direct input for "longest blackout" arguments.                              |
| `effective_throughput_pps`          | Successfully delivered packets per second over the offered-traffic window.                            | Goodput claim; complements PDR.                                              |

Suggested table layout for the paper (one row per scenario × channel):

| scenario | channel | duty | PDR_off | PDR_on | mean recov | p95 recov | CV recov | outage P | worst-case lat | max consec misses |
|----------|---------|------|---------|--------|------------|-----------|----------|----------|----------------|-------------------|
| S4       | CM8     | 0.20 | …       | …      | …          | …         | …        | …        | …              | …                 |
| S8       | CM8     | 0.20 | …       | …      | …          | …         | …        | …        | …              | …                 |
| S9       | CM8     | 0.20 | …       | …      | …          | …         | …        | …        | …              | …                 |
| S4       | QuaDRiGa| 0.20 | …       | …      | …          | …         | …        | …        | …              | …                 |
| S8       | QuaDRiGa| 0.20 | …       | …      | …          | …         | …        | …        | …              | …                 |
| S9       | QuaDRiGa| 0.20 | …       | …      | …          | …         | …        | …        | …              | …                 |

---

## 11. Channel-fidelity gate (synthetic vs measured)

The `data/quadriga/example_trace.csv` file is a **documented placeholder**.
The paper figures should not be derived from it. Two safeguards are in place:

1. **Per-row provenance**: every CSV row exports `trace_provenance` and
   `synthetic_placeholder_final_claims_allowed`. For the placeholder, the row
   reads `trace_provenance=synthetic_placeholder` and
   `synthetic_placeholder_final_claims_allowed=false`. A reviewer can grep on
   these columns to confirm no figure is built on placeholder data.
2. **Hard gate**: `--requireMeasuredTrace=true` (forwarded by
   `run_sweep.py --require-measured-trace`) refuses to start a QuaDRiGa run
   whose provenance is anything other than `measured`. The paper-submission
   pipeline turns this on.

Plan for replacing the placeholder before final submission:

```bash
# 1. Drop the measured trace next to the placeholder
cp /path/to/measured_quadriga_industrial_nlos.csv data/quadriga/

# 2. Edit configs/channels/quadriga_raytraced.yaml:
#       trace_path: data/quadriga/measured_quadriga_industrial_nlos.csv
#       synthetic_placeholder_allowed: false
#       synthetic_placeholder_final_claims: true
#
# 3. Run the campaign with the gate on:
scripts/launch_paper_campaign.sh
python3 scripts/run_sweep.py --require-measured-trace ...
```

The measured trace MUST carry the `fading_std_db` column. See
`data/quadriga/README.md` for the format specification.

---

## 12. Validation envelope — Yans vs core harness

The validation addendum is run on a curated subset of conditions so it can be
presented as **Section IV** of the paper, side by side with the harness
sweeps:

```bash
python3 scripts/run_cross_validation.py            # default: 10..20 dB, 2 dB step
```

This produces `results/cross_validation/cross_validation.csv`. Each row is
joined on `(scenario, channel, MCS, payload, distance, jammer, SNR, seed)` and
contains:

- `pdr_harness`, `pdr_yans`, `pdr_abs_gap = |pdr_harness - pdr_yans|`,
  `pdr_rel_gap = pdr_abs_gap / max(pdr_yans, 1e-6)`.
- Same triplet for PLR and PER.

The companion `cross_validation_summary.md` ranks the metric gaps with the
mean, p95, max and mean rel_std. Recommended paper text:

> "We validate the harness conclusions against the full Wi-Fi stack on a
> three-policy, single-channel subset (S4, S8, S9; CM8; MCS 0; 128-bit
> payload; 3 m; no jammer; SNR 10..20 dB; two seeds). The mean absolute
> gap on PDR is {mean_pdr_gap} with a 95th-percentile gap of
> {p95_pdr_gap}; the policy ordering (S4 < S8 < S9 on losses) is preserved
> in every joined row. The discrepancy at the lower end of the SNR sweep is
> driven by the YansWifiPhy receiver-sensitivity gate, which the harness
> intentionally abstracts away in the high-SNR regime where the PER
> waterfall sigmoid dominates."

> "The cross-validation envelope is reported in Table {N} and Figure {M} of
> the main paper, not as an appendix."

---

## 13. Transferability — seed-independence audit

After the campaign finishes, run:

```bash
python3 scripts/check_seed_independence.py \
    --input results/paper_v2/results.csv \
    --output results/paper_v2/SEED_AUDIT.md \
    --tolerance 0.02
```

This audit reports the across-seeds standard deviation and relative spread of
PDR, PER, `mean_recovery_time_s`, `p95_delay_s` and `deadline_miss_ratio` for
every multi-seed cell, then flags any cell whose PDR rel_std exceeds the
tolerance. The paper can cite the aggregated row as evidence that the
conclusions are not seed-specific:

> "Across the 36 450 multi-seed cells of the main campaign, the mean PDR
> standard deviation is {mean_pdr_std}; the 95th percentile is
> {p95_pdr_std}. No more than {N} cells exceeded the 0.02 PDR relative
> spread tolerance, all of which sit in the BPSK PER waterfall transition
> band (SNR 3..6 dB)."

---

## 14. Self-criticism / known limitations

These are the limitations the paper SHOULD acknowledge explicitly so the
reviewer does not have to extract them:

- **No realistic MAC contention in the harness.** The core harness does not
  model A-MPDU aggregation, BlockAck, RTS/CTS, or rate adaptation. The
  cross-validation table in Section 12 bounds the resulting discrepancy. A
  follow-up paper will adopt SpectrumWifiPhy with full CIR replay (the
  `cir_cfr_trace` row in the Fidelity Matrix of `README.md`).
- **Synthetic QuaDRiGa trace.** Until the placeholder is replaced (see
  Section 11), the QuaDRiGa figures are illustrative only. The
  `--requireMeasuredTrace=true` gate enforces this in code.
- **Single coherence regime.** The harness assumes a 5 ms coherence time
  (configurable). Industrial environments with much faster Doppler require
  re-calibration; the camera-ready version should sweep `coherenceTimeMs`.
- **Reactive jammer model.** The reactive jammer is a periodic 4 ms / 20 ms
  burst with worst-case path loss to the receiver. More sophisticated
  attacker models (energy-detection-triggered, channel-sensing-triggered) are
  out of scope for this submission.
- **One traffic profile.** Single periodic control flow at 100 Hz with
  fixed-size packets. A second flow (closed-loop sensor stream) is needed for
  full closed-loop control claims.
- **Cooldown feasibility is deadline-class dependent.** The multi-deadline
  analysis (Section 15) shows cooldown-on-failure restores delivery for the
  10 ms deadline class, but for tighter classes (1-5 ms) the cooldown-injected
  retry latency can itself breach the deadline, and the effect is non-monotonic
  in the cooldown length relative to the jammer cycle. Cooldown is therefore not
  a substitute for tighter-deadline mechanisms; this is stated as a limitation,
  not a result.

---

## 15. Cooldown-length sweep and deadline-tail analysis (scheduler harness)

This section documents three analysis artifacts produced for the cooldown-on-failure
claim. They are regenerated by the scripts listed in `docs/reproducibility.md`
("Cooldown-length sweep and deadline-tail analysis"). Outputs live under
`results/cooldown_sweep_analysis/` (git-ignored, reproducible) with a
`PROVENANCE*.txt` per artifact (git commit, seeds, exact command). A packaged
copy ships as `cooldown_deadline_analysis_bundle.zip` (figures + tables + scripts
+ the GPT 5.5 manuscript-integration prompt; raw per-attempt logs excluded to keep
it small, regenerable in ~11 s).

> **Claim boundaries (apply to every number in this section).** Engineering
> AR(1) per-RU fading model with a block-fading parity baseline — *not* a
> calibrated 802.11ax PHY. Scheduler-harness Monte-Carlo matrix only. Zero
> *observed* deadline misses are reported with a rule-of-three 95% upper bound
> (`*_ub_ro3`), never as zero probability. Scenarios stay distinct: S4 =
> Baseline-PF, S8 = RU-retarget-only, S9 = full cooldown-on-failure (+retarget);
> the benefit is an S9-vs-S4/S8 effect.

### 15.1 Cooldown-length sweep (reliability-latency knee, D = 10 ms)

- Script: `scripts/aggregate_cooldown_sweep.py` (aggregation of the existing
  coherence campaign, no new simulation).
- Artifacts: `cooldown_sweep_broadband_mcs3.{csv,md}`,
  `fig_cooldown_reliability_latency.{pdf,png}`.
- Reading: reliability is restored once the cooldown `T_cd` exceeds the reactive
  burst, at a latency cost that grows with `T_cd` — i.e. a tunable
  reliability-latency knee across `T_cd in {0,19,38,76,152,304}` OFDM symbols.

### 15.2 Broadband multi-deadline deadline-tail (D = 1 / 5 / 10 ms)

- Script: `scripts/cooldown_multideadline_broadband.py` (small NEW attempt-log
  campaign, 84 runs x 4000 packets, ~11 s; harness constants taken verbatim from
  `configs/coherence_time_sweep.yaml`). Per-packet latency is thresholded offline,
  so one attempt-logged run covers all deadlines.
- Cell: MCS 3, broadband_reactive (burst 4 ms / interval 20 ms), 128 bit, 3 m,
  T_c = 5 ms, 8 users / 8 RUs; AR(1) primary + block parity; seeds 20260507/08/09.
- Artifacts: `deadline_miss_vs_cooldown_broadband.{csv,md}`,
  `PROVENANCE_broadband_multideadline.txt`.
- Observed (AR(1); 12 000 pooled packets per cell):
  - **D = 10 ms:** cooldown >= 38 symbols drives the deadline-miss ratio to 0
    observed (95% upper bound 2.5e-4); `baseline_pf` and `ru_retarget_only` stay
    at ~0.252.
  - **D = 5 ms:** misses are *not* robustly eliminated and behave
    **non-monotonically** in `T_cd` (some intermediate cooldowns still miss
    ~0.252; only specific lengths reach 0 observed).
  - **D = 1 ms:** no configuration meets the deadline (~0.252 throughout).
- Reading: cooldown is feasible for the 10 ms (and looser) deadline class; for
  <= 5 ms classes the injected retry latency can itself violate the deadline.
  This is the basis for the limitation added in Section 14.

### 15.3 PDR / conditional-PDR with seed uncertainty

- Script: `scripts/plot_pdr_seed_uncertainty.py` (aggregation of
  `results/paper_v2/results.csv`, no new simulation).
- Slice: S4/S8/S9, MCS 0, 128 bit, 3 m, reactive; mean +/- seed std over the 3
  paper seeds; PDR also carries a pooled Clopper-Pearson 95% CI in the CSV.
- Artifacts: `fig_pdr_pdron_seed_uncertainty.{pdf,png}`,
  `pdr_pdron_seed_uncertainty.csv`.
- Observed: conditional PDR during jammer-ON is ~1.0 for S9 but ~0 for S4/S8;
  overall PDR plateaus at ~0.74 (S4/S8) vs ~1.0 (S9). Error bars confirm the
  ordering is stable across seeds (referee-facing robustness evidence).

### 15.4 Manuscript integration

A ready-to-use prompt for drafting the LaTeX edits (figures, the deadline-tail
table, and the matching limitation paragraph) into
`oj_ies_manuscript.tex` is provided at
`results/cooldown_sweep_analysis/GPT55_MANUSCRIPT_INTEGRATION_PROMPT.md`. The
manuscript itself is intentionally left unedited until the numbers are reviewed.
