# Metrics

## Reliability

- `transmitted_packets`: packets emitted by the periodic control sender.
- `received_packets`: packets received by the control receiver.
- `lost_packets = transmitted_packets - received_packets`.
- `PDR = received_packets / transmitted_packets`.
- `PLR = lost_packets / transmitted_packets`.
- `packet_success_probability = PDR`.

## PER

The selected definition in the current standalone binary is:

```text
PER = packet_errors / transmitted_packets
```

where packet errors are currently application-observed losses.  This is marked
in CSV/JSON as:

```text
phy_per_available = false
per_definition = application_loss_proxy_until_phy_mac_traces_enabled
```

This distinction is intentional.  MAC retransmissions can hide PHY errors, so
future extensions should attach ns-3 PHY/MAC drop trace callbacks and report a
separate PHY/MAC PER.

## Latency

Each transmitted packet carries a timestamp header.  The receiver records:

- mean delay;
- median delay;
- p95 delay;
- p99 delay;
- jitter, defined as mean absolute difference between consecutive received
  packet delays.

## Safety

For a deadline `D`:

```text
deadline_miss_ratio =
  packets received after D or not received before D
  / transmitted safety-critical packets
```

The collector also reports consecutive loss burst count, maximum loss burst
length, and maximum time without successful update.

## Anti-Jamming

- `sinr_under_jamming_db`: link-budget estimate based on received signal,
  thermal noise and configured jammer power.
- `plr_increase_due_to_jammer`: computed by post-processing against the
  matching no-jammer baseline.
- `per_increase_due_to_jammer`: same for PER.
- `robustness = PDR_with_jammer / PDR_without_jammer`.

