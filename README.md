# ns3-industrial-channel-study

Standalone ns-3 project for industrial wireless channel evaluation with
IEEE 802.11ax / 802.11be-like PHY configurations.

The goal is to compare industrial channel models and quantify their impact on:

- latency;
- reliability;
- safety;
- anti-jamming robustness;
- PLR;
- PER.

Scientific policy: results are never smoothed, deleted or post-processed to
force a desired trend.  If PLR/PER do not improve under physically better
conditions, the model and metric pipeline must be investigated.

## Channels

- `cm8_rayleigh`: CM8-like industrial Rayleigh/NLOS abstraction at 20 MHz,
  limited to 1-6 m.
- `quadriga_raytraced`: external CSV/JSON trace replay.  Distance values are
  read from the trace; no CM8 distance limit is assumed.

## PHY/MAC

The base implementation uses ns-3 Wi-Fi helpers with `WIFI_STANDARD_80211ax`
and HE MCS mappings.  If the installed ns-3 version supports
`WIFI_STANDARD_80211be`, the simulator accepts `standard=80211be`; this is
reported as EHT-capable ns-3.  Otherwise use the documented HE-based
approximation in `configs/phy/ieee80211be_eht_like.yaml`.

## Build

The Debian ns-3 package exposes headers and shared libraries.  Build with:

```bash
cmake -S . -B build
cmake --build build -j
```

If CMake is unavailable, use the included Makefile:

```bash
make -j
```

## Run One Experiment

```bash
./build/industrial-wifi-sim \
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

## Run A Smoke Sweep

```bash
python3 scripts/run_sweep.py --smoke
python3 scripts/validate_trends.py --input results/sweep/results.csv --output results/sweep/trend_report.md
python3 scripts/plot_results.py --input results/sweep/results.csv --output-dir results/sweep/plots
python3 scripts/make_report.py --input results/sweep/results.csv --trend-report results/sweep/trend_report.md --output results/sweep/reproducibility_report.md
python3 scripts/run_tests.py
```

## Run The Full Sweep

```bash
python3 scripts/run_sweep.py --config configs/base.yaml
```

The default full sweep evaluates:

- channel model: `cm8_rayleigh`, `quadriga_raytraced`;
- scenario: `S4`, `S8`, `S9`;
- MCS: `0`, `1`, `3`;
- payload: `128`, `256`, `512` bit;
- CM8 distance: `1,2,3,4,5,6` m;
- QuaDRiGa distances: read from trace;
- jammer mode: `none`, `constant`, `reactive`;
- seeds: 10 by default.

## Import QuaDRiGa / Ray-Traced Traces

CSV columns:

```text
tx_id,rx_id,distance_m,time_s,path_loss_db,delay_s,power_db,doppler_hz,phase_rad
```

`doppler_hz` and `phase_rad` are optional.  If multiple taps are present, the
importer sums tap power per nearest time/distance interval to derive an
effective path-loss abstraction.  If only path loss is present, path-loss replay
is used directly.

JSON traces are also accepted as an array of flat objects with the same field
names.

The included `data/quadriga/example_trace.csv` is synthetic and only exercises
the importer.  It is not real QuaDRiGa output and must not support final
scientific claims.

## PLR/PER Interpretation

- `PDR = received_packets / transmitted_packets`
- `PLR = lost_packets / transmitted_packets`
- `PER = packet_errors / transmitted_packets`

In this first standalone binary, `PER` is an application-observed packet-error
proxy unless PHY/MAC drop traces are enabled in a future extension.  The output
includes `phy_per_available=false` to avoid confusing application-level PLR with
hidden PHY/MAC retransmission behavior.

See `docs/metrics.md` for details.
See `docs/journal_figures.md` for figure-generation guidance.

## Trend Validation

`scripts/validate_trends.py` checks that:

- PLR/PER generally increase with distance;
- more robust MCS generally has lower PLR/PER;
- jammer cases are not better than no-jammer baselines;
- anomalous results are flagged rather than removed.

Violations are written to Markdown and JSON reports with likely causes.

## Known Limitations

- EHT/802.11be support depends on the installed ns-3 version.
- `quadriga_raytraced` currently replays scalar path loss; full
  frequency-selective CIR/CFR replay should use `SpectrumWifiPhy`.
- Reactive jammer is modeled as bursty same-channel Wi-Fi interference, not a
  waveform-level adversary.
- PHY/MAC-level PER is marked unavailable until explicit ns-3 drop trace
  callbacks are added.
