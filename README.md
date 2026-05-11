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

SOA-comparable PER waterfall (CM8 vs QuaDRiGa, SNIR sweep, MCS 0/1/3):

```bash
python3 scripts/run_sweep.py \
  --simulation-path ns3_core_harness \
  --config configs/paper_snr_sweep.yaml \
  --channel-model cm8_rayleigh \
  --output-dir results/paper_snr_cm8 \
  --snr-min 0 --snr-max 25 --snr-step 0.5 \
  --packets-per-run 10000

python3 scripts/run_sweep.py \
  --simulation-path ns3_core_harness \
  --config configs/paper_snr_sweep.yaml \
  --channel-model quadriga_raytraced \
  --output-dir results/paper_snr_quad \
  --snr-min 0 --snr-max 25 --snr-step 0.5 \
  --packets-per-run 10000
```

The CM8 PER waterfall spreads across SNIR due to Rayleigh + log-normal
shadowing; the QuaDRiGa waterfall is steeper because the scalar trace replay
contains no additional small-scale fading (the trace itself is presumed to
already include the multipath structure).

## Reproducing The Paper

Main paper archive:

- simulation path: `ns3_core_harness`
- channel fidelity: `proxy`
- policies: `S4`, `S8`, `S9`
- seeds: `20260507`, `20260508`, `20260509`
- SNIR sweep: `0` to `25` dB in `0.5` dB steps, `51` points
- packet count per point: `300000`
- archive scale: `9.9144e9` launched packets, `33048` CSV rows

Validation addendum:

- simulation path: `ns3_wifi_yans`
- channel fidelity: `proxy` or `scalar_geometry_trace`
- purpose: packet-level contention/BlockAck validation for a subset of
  configurations
- output must remain separate from the main paper archive

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
