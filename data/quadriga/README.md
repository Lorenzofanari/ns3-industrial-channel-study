# QuaDRiGa / Ray-Traced Trace Input

The simulator accepts CSV traces with these columns:

```text
tx_id,rx_id,distance_m,time_s,path_loss_db,delay_s,power_db,doppler_hz,phase_rad,fading_std_db
```

`doppler_hz`, `phase_rad` and `fading_std_db` are optional.

When `fading_std_db` is present, the `ns3_core_harness` simulation path uses
that per-distance value as the standard deviation of a zero-mean Gaussian
small-scale fading draw, and disables the parametric CM8 Rayleigh draw, so the
trace is the only source of small-scale variability.  When `fading_std_db` is
absent, the importer falls back to the sample standard deviation of
`path_loss_db` across all taps that share the nearest distance bucket (useful
when the trace exports many time snapshots per distance).  Multiple rows with the same
`tx_id`, `rx_id`, `distance_m` and `time_s` are treated as taps.  The importer
uses `path_loss_db` directly when present.  If tap powers are present, scripts
can extend the abstraction to compute effective received power from the CIR.

JSON traces are accepted as an array of flat objects with the same field names.

`example_trace.csv` and `example_trace.json` are synthetic and exist only to
exercise the pipeline.  Replace them with exported QuaDRiGa/Quadriga-Lib or
ray-traced data for scientific claims.
