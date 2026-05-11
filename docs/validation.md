# Validation And Anomaly Handling

The study treats trend checks as warnings, not filters.  A failed check must
not delete or smooth results.

## Automated Checks

`scripts/validate_trends.py` checks:

- PLR generally does not decrease with distance for a fixed channel, scenario,
  MCS, payload and jammer configuration.
- PER generally does not decrease with distance under the same conditions.
- MCS 0 should generally be more robust than MCS 1, and MCS 1 more robust than
  MCS 3.
- Jammed cases should generally not improve PLR/PER relative to the matching
  no-jammer baseline.

The script writes Markdown and JSON reports.  Warnings include the exact group
and values that violated the trend.

## Common Causes To Inspect

- too few seeds or packets;
- channel path-loss mapping too weak for the distance range;
- unrealistic TX power, receiver sensitivity or noise figure;
- wrong bandwidth or thermal noise calculation;
- MCS mode string not matching the selected Wi-Fi standard;
- MAC retransmissions hiding PHY errors;
- saturated traffic changing latency and deadline metrics before PLR/PER;
- too-short simulation duration for the requested packet count.

## Smoke Versus Paper Runs

Smoke runs are only pipeline tests.  They may show flat zero PLR/PER because
the default link budget is intentionally conservative at short industrial
distances.  Paper runs should document the full parameter set and explain any
flat regions rather than forcing a visible slope.
