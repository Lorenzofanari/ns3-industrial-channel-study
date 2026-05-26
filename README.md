# ns3-industrial-channel-study

Standalone ns-3 project for industrial wireless channel evaluation with
IEEE 802.11ax / 802.11be-like PHY configurations.

The study evaluates three OFDMA-like scheduler policies under industrial
NLOS channel proxies and reactive jamming:

- **S4 / Baseline-PF** -- proportional-fair reference;
- **S8 / RTX-Assist** -- conservative retransmission-assisted scheduler
  (legacy CSV label `PLS-RTX`);
- **S9 / Realloc** -- AP-side SNIR-estimate-driven RU reallocation with a
  76-symbol anti-oscillation cooldown (legacy CSV label `PLS-Realloc`).

The simulator is the ns-3 scheduler-harness implementation that backs the
manuscript [Fan26] -- *"Resilient OFDMA Scheduling under Reactive Jamming in
Industrial IEEE 802.11ax-like Networks: An ns-3 Scheduler-Harness Study"*.
The paper validates **reliability and resilience metrics** (PDR, PLR/PER,
p95 delay, recovery time, deadline miss, jammer-ON/OFF behaviour, Jain
fairness); it does not export information-theoretic secrecy capacity. The
`PLS-*` labels in the CSV archive are retained for historical continuity and
do not imply secrecy claims; the paper-facing names live in
`policy_paper_label`. See [BIBLIOGRAPHY.md](BIBLIOGRAPHY.md) for the full
citation map.

Results are never smoothed, deleted, or post-processed to force a desired
trend. If PLR/PER do not improve under physically better conditions, inspect
the channel, PHY, MAC, traffic, and metric extraction path.

## Project Attribution

This work was developed as a collaboration between EUNEIZ and the University of
Cagliari.

Supervisor: Lorenzo Fanari, lorenzo.fanari@euneiz.com

## Bibliography & Citing

Every calibration constant in the codebase points back to a literature source.
The full citation chain lives in [`BIBLIOGRAPHY.md`](BIBLIOGRAPHY.md) (human
readable, with a "where it lands in the source tree" table) and in
[`paper.bib`](paper.bib) (BibTeX, ready to be imported into an
IEEE / Elsevier manuscript). Key references:

- **CM8 industrial NLOS**: Molisch et al., *IEEE TAP* 2009 [Mol09] +
  IEEE 802.15-04/0662 [Mol04].
- **3GPP Indoor Factory NLOS** (new `inf_nlos_dl` channel): 3GPP TR 38.901
  §7.4.1 [3GPP38901].
- **5 GHz industrial channel empirical fit**: Tanghe et al., *IEEE TWC* 2008
  [Tan08]; Trassl et al., *PIMRC* 2018 [Tra18].
- **QuaDRiGa**: Jaeckel et al., *IEEE TAP* 2014 [Jae14].
- **IEEE 802.11ax PHY / HE-MCS rates**: Khorov et al., *IEEE COMST* 2019
  [Kho19].
- **PER waterfall sigmoid calibration**: TGax evaluation methodology
  [TGax571] + RBIR PHY abstraction [Iyy22].
- **Reactive jamming on 802.11**: Bayraktaroglu et al., *INFOCOM* 2008
  [Bay08] / *MONET* 2013 [Bay13]; Pelechrinis et al., *IEEE COMST* 2011
  [Pel11]; Pirayesh & Zeng, *IEEE COMST* 2022 [Gri21].
- **PLS / secure HARQ** (S8 PLS-RTX, S9 PLS-Realloc): Bloch & Barros,
  Cambridge 2011 [Blo11] + Bloch et al., *IEEE TIT* 2008 [Blo08]; Tang, Liu,
  Spasojevic, Poor, *IEEE TIT* 2009 [Tan09].
- **Jain's fairness index**: Jain, Chiu, Hawe, DEC-TR-301 1984 [Jai84].
- **ns-3 simulator**: Henderson, Lacage, Riley, *SIGCOMM* 2008 [HLR08];
  Lacage & Henderson, *WNS2* 2006 [LH06].
- **Industrial cyber-physical control deadline targets**: 3GPP TS 22.104
  [TS22104], IEEE 802.1Qbv [IEEE802Qbv], IEEE 802.1CB [IEEE802CB].

Search the codebase for the bracketed reference key (e.g. `[Mol09]`,
`[Bay08]`, `[Jai84]`) to locate every place where each citation is used.

## Fidelity Matrix

| simulation_path | channel_fidelity | purpose | CSV tag |
|---|---|---|---|
| `ns3_core_harness` | `proxy` | Main paper statistical campaign using ns3::Simulator/RNG only; no YansWifiPhy, MAC contention, trigger frames, BlockAck, or A-MPDU. | `simulation_path=ns3_core_harness`, `channel_fidelity=proxy` |
| `ns3_wifi_yans` | `proxy` | Packet-level behavioral validation addendum using community Wi-Fi stack with calibrated profile parameters. | `simulation_path=ns3_wifi_yans`, `channel_fidelity=proxy` |
| `ns3_wifi_yans` | `scalar_geometry_trace` | Packet-level validation addendum with scalar path-loss snapshots replayed through YansWifiPhy. | `simulation_path=ns3_wifi_yans`, `channel_fidelity=scalar_geometry_trace` |
| future `ns3_wifi_spectrum` | `cir_cfr_trace` | Full frequency-selective CIR/CFR replay via SpectrumWifiPhy. TODO, not implemented. | `channel_fidelity=cir_cfr_trace` |

Proxy and trace-based rows must not be aggregated silently.  The sweep
aggregator raises at runtime if one output CSV would mix `channel_fidelity`
values.

## Channels

Three channel models are supported. Each one comes with a documented
calibration source in [`BIBLIOGRAPHY.md`](BIBLIOGRAPHY.md) /
[`paper.bib`](paper.bib); see also the inline comments in
`src/channel/cm8-rayleigh-channel.cc` and
`src/channel/channel-abstraction.cc`.

- `cm8_rayleigh` -- log-distance + log-normal SF + optional Rayleigh, labelled
  after IEEE 802.15.4a CM8 "Industrial NLOS" [Mol09, Mol04]. The default YAML
  preset (`configs/channels/cm8_rayleigh_20mhz.yaml`) is an **engineering
  proxy** (`n=2.2, sigma_S=2 dB, PL_0=43 dB, max_distance=6 m`), not a strict
  CM8 replica. To reproduce results with the literature-faithful CM8 NLOS
  parameters use `configs/channels/cm8_strict_nlos.yaml` (`n=2.15, sigma_S=6
  dB, PL_0=56.7 dB, validity 1-10 m`) or pass the corresponding `--*`
  overrides on the CLI.
- `inf_nlos_dl` -- **3GPP TR 38.901 §7.4.1 Indoor Factory NLOS, Dense Clutter,
  Low BS** [3GPP38901]. The same C++ engine as `cm8_rayleigh` is reused with
  the InF-DL parameter set:
  `PL_NLOS(d, fc) = 18.6 + 35.7*log10(d) + 20*log10(fc[GHz])`, sigma_SF = 7.2
  dB, 1 m <= d <= 600 m. Preset:
  `configs/channels/inf_nlos_dl_5ghz.yaml`. CSV rows are labelled
  `channel_model=TR38901_INF_NLOS_DL`,
  `channel_abstraction=stochastic_3gpp_inf_nlos_dl_log_distance_with_shadowing`,
  `trace_provenance=tr38901_inf_stochastic`.
- `quadriga_raytraced` -- scalar geometry/path-loss trace replay through the
  Yans path [Jae14]. CSV rows label this as
  `QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE`. The shipped placeholder trace is
  synthetic; see the **Paper Use of QuaDRiGa** section.

For core-harness archives, `QD_INDUSTRIAL_NLOS_PROXY` means proxy
parameterization inspired by QuaDRiGa industrial NLOS behavior, not full
QuaDRiGa geometry trace replay.

A reviewer can swap the active channel model on a single run with
`--channelModel=cm8_rayleigh | inf_nlos_dl | quadriga_raytraced`, and the
factorial sweep in `scripts/run_sweep.py` (see `--channel-model`) accepts the
same values. The companion file `BIBLIOGRAPHY.md` lists every paper that
backs the calibration constants used by each model.

## Paper Use of QuaDRiGa

QuaDRiGa is usable for papers as a channel-trace source when the trace is a real
external dataset or a documented QuaDRiGa generation campaign with reproducible
layout, carrier, bandwidth, antenna, mobility, industrial scenario, seed and
export settings.  In that case, the simulator should be run with the measured
trace gate enabled and every CSV row should carry `trace_provenance=measured`.

The traces currently shipped in this repository are not publishable as final
scientific evidence.  `data/quadriga/example_trace.csv` is a synthetic
placeholder that exists to exercise the importer and the reproducibility
pipeline.  Rows generated from it are exported with
`trace_provenance=synthetic_placeholder` and
`synthetic_placeholder_final_claims_allowed=false`; they may support a simulator
proposal, workflow validation, figure-layout testing and reviewer-visible
metadata checks, but they must not support final quantitative channel claims.

Recommended publication stance:

- publishable now: the simulator architecture, reproducibility metadata,
  anti-jamming telemetry, trend checks, seed audit, plotting pipeline and the
  documented distinction between proxy, packet-level and trace-replay paths;
- publishable as proxy evidence only: CM8 and core-harness policy-ranking
  results, provided the text states that they are statistical/proxy simulations;
- not publishable as final QuaDRiGa performance evidence yet: numerical claims
  from the included synthetic QuaDRiGa placeholder;
- publishable after trace replacement: QuaDRiGa results regenerated with real
  measured/external traces and `--requireMeasuredTrace=true`.

## Simulator Proposal

This project proposes a reproducible two-level ns-3 workflow for industrial
anti-jamming evaluation:

1. `ns3_core_harness` performs broad Monte-Carlo sweeps over policy, MCS,
   payload, distance, jammer mode and SNIR.  It is intended for rapid
   policy-ranking studies and exports explicit proxy/fidelity metadata.
2. `ns3_wifi_yans` provides a packet-level validation addendum for payload,
   latency, retry and deadline behavior.  It is not silently merged with the
   core harness because its PER definition and PHY/MAC path differ.
3. `quadriga_raytraced` is treated as external trace replay.  The repository
   includes only a synthetic placeholder trace; the camera-ready scientific
   pipeline must replace it with a measured or reproducibly generated external
   QuaDRiGa trace.
4. Every result row preserves reproducibility metadata: seed, ns-3 version, git
   hash when available, scenario, channel, PHY/MAC path, payload, distance,
   jammer configuration and simulation time.

The intended contribution is therefore not "synthetic QuaDRiGa results", but a
guarded simulator pipeline that prevents placeholder traces from being mistaken
for measured scientific evidence.

## Policies

- `S4`: `Baseline-PF`
- `S8`: `PLS-RTX`
- `S9`: `PLS-Realloc`
- `S0`: `NoPLS`, gated behind `--enable-nopls-baseline=true`

CSV exports the short policy in `policy` (and preserves `scenario` for legacy
grouping) plus the descriptive alias in `policy_label`.

## Build

```bash
cmake -S . -B build
cmake --build build -j
```

If CMake is unavailable:

```bash
make -j
```

## Run One Experiment

Main paper campaign (PER-waterfall Monte Carlo, no Wi-Fi stack):

```bash
./build/industrial-wifi-sim \
  --simulationPath=ns3_core_harness \
  --scenario=S4 \
  --channelModel=cm8_rayleigh \
  --mcs=0 \
  --payloadBits=128 \
  --distanceM=3 \
  --jammerMode=none \
  --seed=20260507 \
  --packets=2000 \
  --txPowerDbm=-34 \
  --output=results/one_run.csv \
  --jsonOutput=results/one_run.json
```

Packet-level behavioral validation addendum (default, uses YansWifiPhy):

```bash
./build/industrial-wifi-sim \
  --simulationPath=ns3_wifi_yans \
  --scenario=S4 \
  --channelModel=cm8_rayleigh \
  --mcs=0 \
  --payloadBits=128 \
  --distanceM=3 \
  --jammerMode=none \
  --seed=1 \
  --output=results/one_run.csv \
  --jsonOutput=results/one_run.json
```

Both paths share the same CSV/JSON schema.  CSV files begin with reviewer-facing
metadata comments that describe the active `simulation_path`, then a normal
header row.  Downstream scripts skip comment lines.

For the core harness path the CSV row exports
`phy_per_available=true` and
`per_definition=per_waterfall_sigmoid_on_per_packet_snir`.
For the Yans path it exports
`phy_per_available=false` and the existing application-loss-proxy definition.

## Run Sweeps

Run proxy and trace outputs separately, and keep main-paper rows
(`ns3_core_harness`) separated from the validation addendum rows
(`ns3_wifi_yans`):

```bash
python3 scripts/run_sweep.py --simulation-path ns3_core_harness --config configs/base.yaml --channel-model cm8_rayleigh --output-dir results/sweep_proxy_core
python3 scripts/run_sweep.py --simulation-path ns3_core_harness --config configs/base.yaml --channel-model quadriga_raytraced --output-dir results/sweep_trace_core
python3 scripts/run_sweep.py --simulation-path ns3_wifi_yans --config configs/base.yaml --channel-model cm8_rayleigh --output-dir results/sweep_proxy_yans
```

`run_sweep.py` refuses to aggregate rows whose `simulation_path` differs into a
single CSV.

SOA-comparable PER waterfall (CM8 vs QuaDRiGa, SNIR sweep, MCS 0/1/3) and
journal-grade anti-jamming campaign:

```bash
# Launch the full paper campaign (6 sharded parallel processes, ~1 hour wall
# time on an 8-core box). Edit SNR_MIN / SNR_MAX / SNR_STEP env vars to
# narrow the matrix.
scripts/launch_paper_campaign.sh

# Once all six shards exit, merge them into the single results.csv expected
# by validate_trends / parse_results / plot_results / make_report:
python3 scripts/merge_paper_shards.py --root results/paper_v2
```

Or run a single (channel, seed) shard manually:

```bash
python3 scripts/run_sweep.py \
  --simulation-path ns3_core_harness \
  --config configs/paper_snr_sweep.yaml \
  --channel-model cm8_rayleigh \
  --output-dir results/paper_v2/cm8_rayleigh_seed20260507 \
  --snr-min 0 --snr-max 22 --snr-step 0.5 \
  --seed 20260507
```

The CM8 PER waterfall spreads across SNIR due to Rayleigh + log-normal
shadowing; the QuaDRiGa waterfall is steeper because the scalar trace replay
relies on the per-distance `fading_std_db` baked into the trace itself, with
no extra synthetic Rayleigh.

## Reproducing The Paper

Main paper archive (see `RESULTS_FOR_PAPER.md` for the full plot/metric
index and journal-ready captions):

- simulation path: `ns3_core_harness`
- channel fidelity: `proxy`
- channels: CM8 at 3 m and 6 m, QuaDRiGa at 3/6/9/12 m
- MCS: 0, 1, 3 (BPSK 1/2, QPSK 1/2, 16-QAM 1/2)
- payloads: 128, 256, 512 bits
- policies: `S4`, `S8`, `S9`
- jammer matrix: none/constant/reactive at 10 dBm and 20 dBm
- seeds: `20260507`, `20260508`, `20260509`
- SNIR sweep: `0` to `22` dB in `0.5` dB steps, `45` points
- packet count per point: `100000`
- archive scale: ~1.09e5 CSV rows, ~1.09e10 launched packets

Validation addendum:

- simulation path: `ns3_wifi_yans`
- channel fidelity: `proxy` or `scalar_geometry_trace`
- purpose: packet-level contention/BlockAck validation for a subset of
  configurations
- output must remain separate from the main paper archive

## Minimal Fairness Mini-Run

Do not rerun the full `paper_v2` campaign for the fairness addendum.  Use a
compact, representative CM8-only matrix:

| parameter | values |
|---|---|
| channel | `cm8_rayleigh` |
| distance | `3 m`, `6 m` |
| target SNIR | `12`, `16`, `20 dB` |
| MCS | `0`, `1`, `3` |
| jammer | `none`, `reactive` |
| payload | `256 bit` |
| seed | `20260507`, `20260508`, `20260509` |
| policies | `S4`, `S8`, `S9` |
| users | `6` |

This is a `2 x 3 x 3 x 2 x 1 x 3 x 3 = 324` point matrix before any
per-user expansion.  The parameter file is
`configs/fairness_minirun.yaml`.

The simulator CLI now exposes `--users` (core-harness only): packets are
assigned to STAs in strict round-robin with `userId = seq mod users`. Every
result row carries the fairness columns `num_users`, `per_user_pdr`,
`per_user_throughput_pps`, `per_user_p95_delay_s` and `jain_fairness_index`
(Jain on per-user PDR; segments are semicolon-separated in user-id order and
use the literal token `nan` for users that received zero packets).

Run the mini-run with the values driven entirely by the YAML
(`fairness.users`, `snr.target_snr_db`, and `simulation.simulation_path`):

```bash
python3 scripts/run_sweep.py --config configs/fairness_minirun.yaml --no-build
```

Output lives under `results/fairness_minirun/` together with a generated
`README.md` describing the per-user CSV schema.

## S9 Estimator Sensitivity and Ablation (paper [Fan26] Tab. 10 and Tab. 11)

The paper's [Fan26] §4.5 and §6.7-6.8 introduce two S9-specific campaigns
that are **not** part of the historical archive:

- **Tab. 10 -- Estimator-impairment sensitivity.** Three estimator profiles
  (`ideal`, `moderate`, `conservative`) modulate the AP-side SNIR estimate
  feeding the Algorithm 1 critical-mask defer. Profiles map to Gaussian SNIR
  noise sigma, staleness in slots, missed-detection probability `P_md` and
  false-alarm probability `P_fa` (paper Eq. 6). The defer mechanism itself is
  unchanged; only the *information* feeding the decision is degraded.
- **Tab. 11 -- Component ablation.** Four variants (`full`, `no_jammer_flag`,
  `no_cooldown`, `snir_only`) toggle individual checks of Algorithm 1 so the
  contribution of each component (jammer indicator, anti-oscillation cooldown,
  SNIR margin, PER margin) can be attributed.

Both campaigns are gated by the new opt-in switch `--s9-proactive-defer=true`.
Default behaviour is unchanged: the legacy CSV archive remains bit-identical
to the runs the paper §6.2-6.6 figures use.

Run the two campaigns and produce the publication-ready markdown tables:

```bash
# Tab. 10 (estimator sensitivity)
python3 scripts/run_sweep.py --config configs/s9_estimator_sensitivity.yaml
python3 scripts/aggregate_s9_sensitivity.py
# -> results/s9_estimator_sensitivity/tab10_sensitivity.md

# Tab. 11 (component ablation)
python3 scripts/run_sweep.py --config configs/s9_ablation.yaml
python3 scripts/aggregate_s9_ablation.py
# -> results/s9_ablation/tab11_ablation.md
```

Every row of both campaigns carries the full S9 parameter set as CSV columns
(`s9_estimator_profile`, `s9_snir_noise_std_db`, `s9_snir_bias_db`,
`s9_snir_staleness_slots`, `s9_jammer_missed_detection_prob`,
`s9_jammer_false_alarm_prob`, `s9_per_crit`, `s9_gamma_out_db`, four
`s9_ablation_disable_*` flags, `s9_proactive_defer_enabled`, and the
telemetry counter `s9_proactive_defer_count`). This implements the Data and
Reproducibility Statement of [Fan26] §9: any reviewer can rerun a row from
its CSV metadata alone.

The paper also uses paper-aligned policy names (`Baseline-PF`, `RTX-Assist`,
`Realloc`) which now appear as the dedicated CSV column `policy_paper_label`,
side by side with the legacy `policy_label` (`Baseline-PF`, `PLS-RTX`,
`PLS-Realloc`) that keeps the historical archive valid.

## Journal-Grade Anti-Jamming Telemetry

Every CSV row produced by `ns3_core_harness` now exports the following
anti-jamming columns:

| column                              | meaning                                                                  |
|-------------------------------------|--------------------------------------------------------------------------|
| `sjr_db`                            | Signal-to-Jammer Ratio (NaN/empty for no-jammer rows)                    |
| `jnr_db`                            | Jammer-to-Noise Ratio                                                    |
| `jammer_duty_cycle`                 | 0 for none, 1 for constant, `burst/interval` for reactive (=0.20 default)|
| `pdr_jammer_on`                     | Conditional PDR over packets attempted while the jammer was emitting     |
| `pdr_jammer_off`                    | Conditional PDR over packets attempted while the jammer was silent       |
| `burst_induced_loss_ratio`          | `lost_during_jammer_on / lost_total`                                     |
| `mean_recovery_time_s`              | Mean time from a reactive burst end to the next successful packet        |
| `std_recovery_time_s`               | Standard deviation of the per-burst recovery samples                     |
| `cv_recovery_time`                  | `std/mean` coefficient of variation (NaN when undefined)                 |
| `p95_recovery_time_s`               | 95th percentile of the per-burst recovery distribution                   |
| `outage_probability_jammer_on`      | P(first-attempt SINR < `outage_threshold_db`) given jammer ON            |
| `outage_threshold_db`               | Threshold used for the outage probability (5 dB by default)              |
| `worst_case_burst_latency_s`        | Worst e2e delay among packets that overlapped a jammer-ON burst           |
| `max_consecutive_deadline_misses`   | Longest run of consecutive lost / late packets                            |
| `effective_throughput_pps`          | Successfully delivered packets per second over the offered window         |
| `recovery_sample_count`             | Number of burst-end transitions sampled                                    |
| `recovery_time_s`                   | Legacy alias of `mean_recovery_time_s` (kept for back-compat)             |
| `robustness_ratio`                  | `pdr_with_jammer / pdr_no_jammer` matched on all other dimensions         |
| `plr_increase_due_to_jammer`        | `plr_with_jammer - plr_no_jammer`                                         |

NaN values are emitted as empty CSV cells / JSON `null` so reviewers can
distinguish "measured zero" from "undefined".

## Channel-Fidelity Gate (synthetic vs measured QuaDRiGa traces)

Every CSV row also carries a trace-provenance triplet so reviewers can audit
which numbers depend on a measured trace and which depend on the documented
synthetic placeholder:

| column                                          | meaning                                                                        |
|-------------------------------------------------|--------------------------------------------------------------------------------|
| `trace_provenance`                              | `cm8_stochastic_proxy`, `synthetic_placeholder`, or `measured`                  |
| `synthetic_placeholder_final_claims_allowed`    | Operator-acknowledged flag (default `false`)                                    |
| `fading_variance_source`                        | `cm8_proxy`, `trace_column`, `none`, or `trace_or_path_loss_only`               |

The simulator binary supports `--requireMeasuredTrace=true`, forwarded by
`scripts/run_sweep.py --require-measured-trace`. Turn it on for the
camera-ready pipeline: it refuses to start a QuaDRiGa run whose provenance is
anything other than `measured`. See `RESULTS_FOR_PAPER.md` Section 11 for the
measured-trace replacement plan.

## Integral Yans Validation

The companion validation pipeline runs the same SNR sweep on both
`ns3_core_harness` and `ns3_wifi_yans` and reports the per-row PDR/PER gap so
the validation envelope can sit in the main results section rather than as an
appendix:

```bash
python3 scripts/run_cross_validation.py
```

Produces `results/cross_validation/cross_validation.csv` and
`cross_validation_summary.md`. The default range is 10..20 dB at 2 dB steps,
chosen so both paths are above the YansWifiPhy receiver sensitivity gate
(~ -89 dBm at MCS 0 / 20 MHz). See `RESULTS_FOR_PAPER.md` Section 12.

## Seed-Independence Audit

```bash
python3 scripts/check_seed_independence.py \
    --input results/paper_v2/results.csv \
    --output results/paper_v2/SEED_AUDIT.md
```

Audits the across-seeds standard deviation of PDR, PER, recovery time and p95
delay for every cell, flags cells with PDR relative spread > 0.02, and writes
both Markdown and JSON outputs. Demonstrates transferability across the
documented seed list.

## Calibration Flags

PER waterfall defaults match the published calibration points:

- `--per-theta-bpsk=3.0`
- `--per-theta-qpsk=6.0`
- `--per-theta-16qam=15.5`
- `--per-slope=1.15`

S8 and S9 scaffolding:

- `--s8-rtx-snir-gain=1.35`
- `--s9-cooldown-symbols=76`

Eve estimation error scaffolding defaults to ideal/off:

- `--eve-snir-bias-db=0.0`
- `--eve-snir-noise-std-db=0.0`
- `--eve-snir-delay-slots=0`

The active values are exported in CSV columns for future sensitivity sweeps.

## Import Geometry Traces

CSV columns:

```text
tx_id,rx_id,distance_m,time_s,path_loss_db,delay_s,power_db,doppler_hz,phase_rad,fading_std_db
```

`doppler_hz`, `phase_rad` and `fading_std_db` are optional.  When
`fading_std_db` is present the `ns3_core_harness` path uses it as the per-
distance small-scale fading standard deviation (Gaussian only, no extra CM8
Rayleigh).  When absent, the importer falls back to the sample standard
deviation of `path_loss_db` across taps sharing the same distance bucket.  The
current Yans path replays scalar path loss only.  Full frequency-selective
CIR/CFR replay requires a future SpectrumWifiPhy path.

The included `data/quadriga/example_trace.csv` is synthetic and only exercises
the importer.  It is not real QuaDRiGa output and must not support final
scientific claims.

## PLR/PER Interpretation

- `PDR = received_packets / transmitted_packets`
- `PLR = lost_packets / transmitted_packets`
- `PER = packet_errors / transmitted_packets`

The current Yans binary exports `phy_per_available=false`; PER is an
application-observed packet-loss proxy until explicit PHY/MAC drop traces are
added.

## Known Limitations

- `ns3_core_harness`: no YansWifiPhy, no trigger frames, no BlockAck, no A-MPDU.
- Channel models: main campaign uses proxy parameters, not geometry traces.
- Eve estimation: ideal risk map assumed in published runs; no noise/bias/delay
  sweep was performed.
- Latency: aggregate percentiles only, no per-packet CDF archive.

## Future Validation Path

- Eve estimation error sweep using `--eve-snir-*` flags, now scaffolded.
- PER waterfall sweep using `--per-theta-*` and `--per-slope`, now scaffolded.
- Full CIR/CFR replay via SpectrumWifiPhy: TODO, not implemented.
- Hybrid S8/S9 per-flow scheduler: not implemented.

## Tests

```bash
make test
python3 scripts/run_tests.py
```
