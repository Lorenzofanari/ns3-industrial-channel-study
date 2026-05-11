# QuaDRiGa / Ray-Traced Trace Input

The simulator accepts CSV traces with these columns:

```text
tx_id,rx_id,distance_m,time_s,path_loss_db,delay_s,power_db,doppler_hz,phase_rad
```

`doppler_hz` and `phase_rad` are optional.  Multiple rows with the same
`tx_id`, `rx_id`, `distance_m` and `time_s` are treated as taps.  The importer
uses `path_loss_db` directly when present.  If tap powers are present, scripts
can extend the abstraction to compute effective received power from the CIR.

JSON traces are accepted as an array of flat objects with the same field names.

`example_trace.csv` and `example_trace.json` are synthetic and exist only to
exercise the pipeline.  Replace them with exported QuaDRiGa/Quadriga-Lib or
ray-traced data for scientific claims.
