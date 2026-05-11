# ns3-industrial-channel-study

Standalone ns-3 project for industrial wireless channel evaluation with
IEEE 802.11ax / 802.11be-like PHY configurations.

The study compares secrecy-aware scheduling labels `S4`, `S8`, and `S9` while
keeping simulation fidelity metadata explicit in every CSV row.  Results are
never smoothed, deleted, or post-processed to force a desired trend.  If PLR/PER
do not improve under physically better conditions, inspect the channel, PHY,
MAC, traffic, and metric extraction path.

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

- `cm8_rayleigh`: CM8-like industrial Rayleigh/NLOS proxy abstraction at
  20 MHz, limited to 1-6 m.
- `quadriga_raytraced`: scalar geometry/path-loss trace replay through the
  Yans path.  CSV rows label this as
  `QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE`.

For core-harness archives, `QD_INDUSTRIAL_NLOS_PROXY` means proxy
parameterization inspired by QuaDRiGa industrial NLOS behavior, not full
QuaDRiGa geometry trace replay.

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
