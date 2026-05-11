# Methodology

The project runs factorial ns-3 Wi-Fi experiments while changing only explicit
configuration parameters.  The same traffic generator, metrics collector and
channel interface are used for S4, S8 and S9.

Important design rules:

- Do not tune results after the fact.
- Do not remove anomalies.
- Keep MAC retransmission effects visible by reporting application PLR/PDR and
  marking PHY/MAC PER availability.
- Run multiple seeds; the default full sweep uses ten seeds.
- Use short CM8 distances only: 1-6 m.
- Read QuaDRiGa/ray-traced distances from trace files.

## Current Scenario Mapping

S4 is the validated baseline.  S8 and S9 use the same Wi-Fi stack, traffic
generator and channel interface, but raise the configured MAC retry emphasis:

- S4: retry limit 7;
- S8: retry limit 9;
- S9: retry limit 11.

This is intentionally conservative.  The standalone project focuses on channel
evaluation first; richer S8/S9 scheduler logic can be added behind the same
scenario interface without changing metric definitions.

## Architecture

- `src/industrial-wifi-sim.cc`: ns-3 executable using `YansWifiPhy`,
  `StaWifiMac`, `ApWifiMac`, IPv4 and UDP control traffic.
- `src/channel/`: CM8-like Rayleigh/NLOS abstraction plus CSV/JSON
  QuaDRiGa/ray-traced trace importer.
- `src/traffic/`: timestamped periodic control application.
- `src/metrics/`: reliability, latency, safety and anti-jamming formulas.
- `src/jammer/`: constant and burst-style same-channel Wi-Fi interferers.
- `scripts/`: sweep runner, parser, trend validation, plotting and report
  generation.
