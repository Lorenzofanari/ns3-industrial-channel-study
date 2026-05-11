# Journal Figure Guidelines

Use `scripts/plot_results.py` to create reproducible `.dat`, `.gp` and `.png`
files, then restyle the gnuplot scripts for the target journal.

Recommended figure set:

- PLR and PER versus distance: log-y when nonzero losses span orders of
  magnitude; linear-y when all values are zero.
- PDR versus distance: linear-y, because values near one are easier to compare
  directly.
- p95 and p99 latency versus distance: linear-y in seconds or milliseconds.
- deadline miss ratio versus distance: log-y when nonzero.
- PLR/PER versus MCS: show MCS 0, 1 and 3 with the exact channel and payload
  fixed in the caption.
- robustness versus jammer power: report `PDR_with_jammer / PDR_without_jammer`
  and include jammer mode.
- CM8 versus QuaDRiGa: keep the channel abstraction label in the caption.
- S4 versus S8 versus S9: state the MAC/scheduler parameter differences, such
  as retry limit, rather than implying hidden post-processing.

Captions should state:

- ns-3 version and Wi-Fi standard;
- packet count and seed set;
- payload size and MCS;
- channel model and whether the trace is synthetic or real;
- whether PER is PHY/MAC-level or the current application-loss proxy.
