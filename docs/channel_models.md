# Channel Models

## CM8-Like Industrial Rayleigh

`cm8_rayleigh` is a controlled industrial NLOS abstraction at 20 MHz.  It is
not a literal IEEE 802.15.4a CM8 waveform replay.  The maximum distance is 6 m;
the sweep should use 1-6 m only.

Configurable parameters:

- carrier frequency;
- bandwidth;
- TX power;
- noise figure;
- path-loss exponent;
- shadowing standard deviation;
- Rayleigh fading toggle;
- coherence time;
- industrial excess loss;
- receiver sensitivity;
- packet detection threshold;
- SNR-to-PER method.

## QuaDRiGa / Ray-Traced

`quadriga_raytraced` imports path-loss or tap rows from CSV or JSON.  Distance
is read from the trace and is not constrained by the CM8 6 m limit.

If only path loss is present, the simulator uses scalar path-loss replay.  If
full CIR taps are available, future extensions should compute effective
received power or subcarrier gain from tap delay and power, then move to
`SpectrumWifiPhy` for frequency-selective replay.

## Scientific Labeling

Synthetic placeholder traces are acceptable only for pipeline validation.  They
must be labelled synthetic and excluded from final scientific conclusions.
