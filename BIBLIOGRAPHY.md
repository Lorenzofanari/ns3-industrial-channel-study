# Bibliography

This file is the canonical reference list for the ns3-industrial-channel-study
project. Each entry is cited from the source/script that uses it, so a reviewer
can audit the calibration of every value without leaving the repository.

The companion file [`paper.bib`](paper.bib) provides BibTeX entries for direct
inclusion in an IEEE/Elsevier LaTeX manuscript.

> **Scientific honesty note.** Some calibrations in the source tree are
> intentionally lighter than what the corresponding literature recommends (in
> particular the legacy `cm8_rayleigh` profile is an engineering proxy, not a
> faithful CM8 implementation). The "Deviation" subsection below documents each
> known divergence with file, value and rationale.
>
> **PLS scoping.** The CSV labels `PLS-RTX` and `PLS-Realloc` are retained for
> archive continuity. The paper this simulator supports ([Fan26] below) does
> **not** export secrecy capacity or secrecy outage. The S8 and S9 policies
> are therefore presented in the manuscript as **RTX-Assist** and **Realloc**
> respectively, and the validation metrics are PDR/PLR/PER, p95 delay, recovery
> time, deadline miss, jammer-ON/OFF behaviour, and Jain's fairness index — not
> information-theoretic secrecy. The eavesdropper-SNIR scaffolding
> (`--eve-snir-*` flags) is preserved so a future PLS-oriented campaign can
> reuse it, but it is **not** part of the present paper's claim set.

## How to cite this repository

If you use this code or data in a paper, please cite the simulator together
with the dependencies it builds on:

> L. Fanari, *ns3-industrial-channel-study*, EUNEIZ / Università di Cagliari,
> 2026. https://github.com/<...>/ns3-industrial-channel-study

and the ns-3 simulator (key reference [HLR08] below).

### [Fan26] Paper this simulator supports

L. Fanari, *"Resilient OFDMA Scheduling under Reactive Jamming in Industrial
IEEE 802.11ax-like Networks: An ns-3 Scheduler-Harness Study"*, EUNEIZ
Universidad / submitted to Ad Hoc Networks, 2026.

Key sections backed by this codebase:

| Paper item | Section | Code asset |
|---|---|---|
| Scheduler harness, fidelity matrix, CM8 stochastic-proxy class | §3.1-3.3 / §5.1-5.2 | `src/core-harness/core-harness.cc`, `configs/channels/cm8_rayleigh_20mhz.yaml` |
| PER waterfall sigmoid (3.0 / 6.0 / 15.5 dB at slope 1.15) | §3.3 / Tab. waterfall | `src/core-harness/core-harness.cc::CalculatePerSigmoid` |
| Reactive jammer abstraction | §3.4 | `src/jammer/reactive-jammer.{h,cc}`, harness `interferenceMw` |
| S4 Baseline-PF | §4.1 | `src/study-parameters.cc::PaperPolicyLabel("S4")` |
| S8 RTX-Assist (1.35 SNR retry gain) | §4.2 | core-harness retry loop, `s8RtxSnirGainDb` |
| S9 Realloc: Algorithm 1 critical-mask defer + 76-symbol cooldown | §4.3-4.4 / Alg. 1 | core-harness `s9ProactiveDefer`, `S9EstimatorConfig`, `S9AblationConfig` |
| Estimator-impairment profiles (ideal / moderate / conservative) | §4.5 / Tab. 10 | `src/study-parameters.cc::ApplyS9EstimatorProfile`, `configs/s9_estimator_sensitivity.yaml` |
| Complexity bounds Tab. 1 | §4.6 | dimensional analysis only; no runtime overhead exported |
| Six-user fairness diagnostic + Jain index | §6.9 / Tab. 12 | `configs/fairness_minirun.yaml`, `MetricsCollector::Compute` |
| Component ablation (full / no-jammer-flag / no-cooldown / SNIR-only) | §6.8 / Tab. 11 | `configs/s9_ablation.yaml`, `scripts/aggregate_s9_ablation.py` |
| Robustness ratio Eq. (10) | §6.6 | `scripts/run_sweep.py::recompute_jammer_deltas`, `robustness_ratio` column |
| Diagnostic Yans gap Tab. 5 | §5.5 | `scripts/run_cross_validation.py` |
| Synthetic-trace guard | §3.3 / §5.2 / Tab. 3 | `traceProvenance`, `requireMeasuredTrace`, `data/quadriga/example_trace.csv` |

#### Paper-cited references that are now in this bibliography

The paper bibliography cites the following items that are independently
relevant to the simulator. Their BibTeX entries are mirrored in `paper.bib`
so a reviewer can cross-reference any number in the manuscript to the
corresponding implementation.

| Bib key | Used in | Cited in [Fan26] as |
|---|---|---|
| [Kho19] | HE-MCS rate table, PER waterfall midpoints | [1] |
| [Lop19] | 802.11be context (introduction) | [2] |
| [Den20] | 802.11be / Wi-Fi 7 next-gen context | [3] |
| [Fan24] | smart-warehouse 802.11ax application | [4] |
| [Aij20] | high-performance industrial Wi-Fi | [5] |
| [Bel19] | OFDMA AP-triggered multi-user | [12] |
| [Ban18] | OFDMA uplink scheduling | [11] |
| [Tut21] | OFDMA RU allocation with frequency-selective fading | [13] |
| [Mag21] | ns-3 802.11ax OFDMA validation | [16] |
| [Mon24] | OFDMA uplink activation characterisation | [18] |
| [Ang22] | PLS for industrial wireless | [25] |
| [Bay08] | reactive jamming foundation | – (used in our model) |
| [Pel11] | jamming/anti-jamming metrics | – (used in our metric set) |
| [Jai84] | Jain fairness | – (used in `MetricsCollector`) |
| [HLR08] / [LH06] | ns-3 / YansWifiPhy | – (used in the diagnostic path) |

---

## 1. Industrial wireless channel models

### [Mol09] IEEE 802.15.4a CM8 industrial NLOS (foundational reference for the `cm8_rayleigh` channel name)

A. F. Molisch, K. Balakrishnan, D. Cassioli, C.-C. Chong, S. Emami, A. Fort,
J. Karedal, J. Kunisch, H. G. Schantz, U. Schuster, K. Siwiak, *"A
Comprehensive Standardized Model for Ultrawideband Propagation Channels"*,
IEEE Transactions on Antennas and Propagation, vol. 57, no. 11, pp.
3151–3166, Nov. 2009. DOI: `10.1109/TAP.2009.2009738`.

Companion TG document: A. F. Molisch et al., *"IEEE 802.15.4a Channel Model —
Final Report"*, IEEE 802.15-04/0662-04-004a, Nov. 2004.

Key NLOS industrial parameters (Channel Model 8 / "Industrial NLOS"):

| parameter | value | notes |
|---|---|---|
| path-loss exponent `n` | 2.15 | from [13]/[14] of the TG report |
| shadowing std `σ_S` | 6 dB | from [14], [15] |
| reference loss `PL_0` | 56.7 dB | at d0 = 1 m |
| validity range | 1 m to 10 m | measurements covered 2–8 m |
| small-scale fading | modified Saleh–Valenzuela, dense single-cluster | NLOS PDP is monocluster |

Used in: `src/channel/cm8-rayleigh-channel.{h,cc}`, `configs/channels/cm8_rayleigh_20mhz.yaml`.

**Deviation**: the shipped `cm8_rayleigh` profile uses `n=2.2, σ_S=2 dB,
PL_0=43 dB, max_distance=6 m`, which is **not** strictly CM8 — it is a
lightweight industrial-NLOS-like proxy intended for 20 MHz IEEE 802.11ax PHY
studies, not UWB. To run with the strict CM8 NLOS calibration use the
companion profile `configs/channels/cm8_strict_nlos.yaml` (added together
with this bibliography) or override the parameters on the CLI:
`--pathLossExponent=2.15 --referenceLossDb=56.7 --shadowingStdDb=6 --industrialExcessLossDb=0`.

### [3GPP38901] 3GPP TR 38.901 Indoor Factory channel (modern, recommended)

3GPP TR 38.901 v17.0.0, *"Study on channel model for frequencies from 0.5 to
100 GHz"*, Release 17, March 2022 (also v16.1.0 Release 16 introduced the
Indoor Factory scenarios). §7.2-4 and §7.4.1.

Indoor Factory (InF) NLOS path-loss formula:

```
PL_NLOS(d, fc) = α + β · log10(d_3D [m]) + 20 · log10(fc [GHz])
```

| sub-scenario | α [dB] | β | σ_SF [dB] | typical clutter |
|---|---|---|---|---|
| InF-SL (sparse, low BS) | 33    | 25.5 | 5.7 | <40%, 10 m clutter |
| **InF-DL (dense, low BS)** | **18.6** | **35.7** | **7.2** | **≥40%, 2 m clutter** |
| InF-SH (sparse, high BS) | 32.4 | 23.0 | 5.9 | <40%, 10 m clutter, BS above clutter |
| InF-DH (dense, high BS) | 33.63 | 21.9 | 4.0 | ≥40%, 2 m clutter, BS above clutter |

Validity: `1 m ≤ d ≤ 600 m`, `0.5 GHz ≤ fc ≤ 100 GHz`.

Used in: new channel model `inf_nlos_dl` (added by this revision), see
`configs/channels/inf_nlos_dl_5ghz.yaml`. At fc=5.18 GHz the formula reduces
to `PL = 32.87 + 35.7·log10(d)` (i.e. PL_0 = 32.87 dB at 1 m).

### [Tan08] Industrial indoor channel at 900 / 2400 / 5200 MHz

E. Tanghe, W. Joseph, L. Verloock, L. Martens, H. Capoen, K. Van Herwegen,
W. Vantomme, *"The industrial indoor channel: large-scale and temporal
fading at 900, 2400, and 5200 MHz"*, IEEE Trans. Wireless Commun., vol. 7,
no. 7, pp. 2740–2751, July 2008. DOI: `10.1109/TWC.2008.070143`.

One-slope log-distance path-loss + log-normal shadowing model at 5.2 GHz
(matches the carrier used in this study). Reports `n ≈ 1.5–2.5` and `σ_S ≈
4–7 dB` depending on factory topography. Used as cross-check for the InF
parameters above and as the closest peer-reviewed reference for the
`cm8_rayleigh` proxy at 5.18 GHz.

### [Tra18] 5 GHz ISM industrial indoor empirical channel model

A. Trassl et al., *"Deriving an empirical channel model for wireless
industrial indoor communications"*, IEEE PIMRC 2018 (and Vodafone Chair
technical report). Reports Rician K-factor distributions and Doppler in
industrial halls; used to motivate `coherence_time_ms = 5` in CM8 config.

### [Wil19] Industrial indoor measurements for 3GPP-NR and QuaDRiGa parameters

A. Wille et al., *"Industrial Indoor Measurements from 2–6 GHz for the
3GPP-NR and QuaDRiGa Channel Model"*, arXiv:1906.12145, 2019. Provides the
empirical basis for InF parameter selection at 5.4 GHz; supports our choice
of σ_SF and the InF-DL band for clutter-dense factory halls.

---

## 2. QuaDRiGa channel generator

### [Jae14] QuaDRiGa primary reference

S. Jaeckel, L. Raschkowski, K. Börner, L. Thiele, *"QuaDRiGa: A 3-D Multicell
Channel Model with Time Evolution for Enabling Virtual Field Trials"*, IEEE
Trans. Antennas Propag., vol. 62, no. 6, pp. 3242–3256, June 2014.
DOI: `10.1109/TAP.2014.2310220`.

Documentation: S. Jaeckel et al., *"QuaDRiGa: Quasi Deterministic Radio
Channel Generator, User Manual and Documentation"*, Fraunhofer HHI Tech.
Rep. v2.x, 2014–2024. Code: https://github.com/fraunhoferhhi/QuaDRiGa.

Used in: `src/channel/quadriga-channel-importer.{h,cc}`,
`configs/channels/quadriga_raytraced.yaml`, importer for CSV/JSON trace
replay. The repository **does not** redistribute QuaDRiGa traces; only a
synthetic placeholder for pipeline tests.

---

## 3. IEEE 802.11ax PHY, PER waterfall and link abstraction

### [Kho19] IEEE 802.11ax tutorial (used as reference for HE-MCS table and PHY behavior)

E. Khorov, A. Kiryanov, A. Lyakhov, G. Bianchi, *"A Tutorial on IEEE 802.11ax
High-Efficiency WLANs"*, IEEE Communications Surveys & Tutorials, vol. 21,
no. 1, pp. 197–216, 2019. DOI: `10.1109/COMST.2018.2871099`.

Used in: `src/core-harness/core-harness.cc::HeDataRateMbps()` (20 MHz, 1 SS,
GI=3.2 µs data-rate table for HE-MCS 0/1/3), and in the README data-rate
discussion. The 44 µs HE-SU preamble figure used as `preambleS` is also
consistent with this reference (see §IV.A on HE-SIG-A/B fields).

### [TGax571] TGax PHY abstraction evaluation methodology

IEEE 802.11-14/0571, *"TGax Evaluation Methodology"*, IEEE 802.11
Wireless LANs Working Group, 2015. Companion to 11-14-0882 (TGax Channel
Models), 11-14-0980 (Simulation Scenarios) and 11-14-1009 (Functional
Requirements). Defines the AWGN PER look-up + RBIR PHY abstraction used as
the baseline for the sigmoid waterfall in this repo.

### [Iyy22] RBIR-based PHY abstraction calibration (used to motivate the sigmoid waterfall fit)

R. Iyyappan, A. Karthik, P. Singh, *"Performance Analysis of Channel-Dependent
Rate Adaptation for OFDMA transmission in IEEE 802.11ax WLANs"*, IISc, 2022.
Shows that the AWGN PER vs SNR for each MCS, after RBIR mapping, is well
approximated by a logistic / sigmoid centred at the per-MCS waterfall
midpoint, with packet-length extrapolation `PER_PL = 1 - (1 - PER_PL0)^(PL/PL0)`.

Used in: `src/core-harness/core-harness.cc::CalculatePerSigmoid()`, midpoints
`per_theta_bpsk = 3 dB`, `per_theta_qpsk = 6 dB`, `per_theta_16qam = 15.5 dB`,
slope = 1.15 (calibrated to match AWGN PER@10%-target at the corresponding
HE-MCS in the TGax evaluation tables, for the default payload of this study;
the exact target packet length is documented in `RESULTS_FOR_PAPER.md`).

**Deviation**: the per-MCS midpoints are engineering estimates calibrated to
the TGax curves and are exposed as CLI flags (`--per-theta-bpsk` etc.) so the
operator can rerun the campaign with a different fit. They should not be
treated as canonical 802.11ax PHY values without re-derivation from a
reference link-level simulator (e.g. NIST/Aerospace ALL-PHY, MathWorks WLAN
toolbox, or matlab-based TGax curves).

---

## 4. Reactive jamming and anti-jamming evaluation

### [Bay08] Reactive and omniscient jamming on IEEE 802.11

E. Bayraktaroglu, C. King, X. Liu, G. Noubir, R. Rajaraman, B. Thapa,
*"On the Performance of IEEE 802.11 under Jamming"*, IEEE INFOCOM 2008,
pp. 1265–1273. DOI: `10.1109/INFOCOM.2008.180`.

Extended journal version: idem, *Mobile Networks and Applications* 2013,
DOI: `10.1007/s11036-011-0340-4`.

Defines the reactive jammer model (channel-aware, jams only ongoing
transmissions), provides saturation-throughput analysis, and the testbed
implementation with GNU Radio + USRP. Used as the canonical reference for
the harness reactive jammer model and the `outage_threshold_db = 5 dB`
default (their conservative "successful detection" SINR threshold).

Used in: `src/core-harness/core-harness.cc` (reactive `interferenceMw` and
`outageProbabilityJammerOn` telemetry), `src/jammer/reactive-jammer.{h,cc}`.

### [Pel11] Survey on jamming and anti-jamming in wireless networks

K. Pelechrinis, M. Iliofotou, S. V. Krishnamurthy, *"Denial of Service Attacks
in Wireless Networks: The Case of Jammers"*, IEEE Communications Surveys &
Tutorials, vol. 13, no. 2, pp. 245–257, 2011.
DOI: `10.1109/SURV.2011.041110.00022`.

Used to justify the choice of metrics exported by `MetricsCollector`:
packet delivery ratio (PDR), packet send ratio (PSR), bad-packet ratio, and
the explicit conditional decomposition `pdr_jammer_on` / `pdr_jammer_off`.

### [Gri21] Anti-jamming strategies survey (modern)

H. Pirayesh, H. Zeng, *"Jamming Attacks and Anti-Jamming Strategies in
Wireless Networks: A Comprehensive Survey"*, IEEE Communications Surveys &
Tutorials, vol. 24, no. 2, pp. 767–809, 2022. arXiv:2101.00292.
DOI: `10.1109/COMST.2022.3159185`.

Used as supporting reference for the timing constraints of a real reactive
jammer (< 4 µs detection-to-burst at OFDM symbol granularity), which
motivates the **explicit honest caveat** in the README and in
`src/jammer/reactive-jammer.cc` that the Yans-path jammer is a co-station
proxy, not a true PHY-overlay reactive attacker.

---

## 5. Physical-layer security and secure retransmission

### [Blo08] Wireless information-theoretic security (foundation)

M. Bloch, J. Barros, M. R. D. Rodrigues, S. W. McLaughlin, *"Wireless
Information-Theoretic Security"*, IEEE Trans. Inform. Theory, vol. 54,
no. 6, pp. 2515–2534, June 2008. DOI: `10.1109/TIT.2008.921908`.

Introduces secrecy outage and outage secrecy capacity over wireless fading
channels. Conceptual basis for the `S8 (PLS-RTX)` and `S9 (PLS-Realloc)`
policy labels and for the gamma_E (eavesdropper SNIR) estimation
scaffolding exposed via `--eve-snir-bias-db / --eve-snir-noise-std-db /
--eve-snir-delay-slots`.

### [Blo11] Physical-Layer Security textbook

M. Bloch, J. Barros, *Physical-Layer Security: From Information Theory to
Security Engineering*, Cambridge University Press, 2011. ISBN
978-0-521-51650-1.

Reference textbook used for the secrecy framework definitions in
`docs/methodology.md` and for the policy semantics encoded by
`PolicyLabel()` in `src/study-parameters.cc`.

### [Tan09] Secure HARQ throughput over block-fading wiretap channels

X. Tang, R. Liu, P. Spasojević, H. V. Poor, *"On the Throughput of Secure
Hybrid-ARQ Protocols for Gaussian Block-Fading Channels"*, IEEE Trans.
Inform. Theory, vol. 55, no. 4, pp. 1575–1591, April 2009.
DOI: `10.1109/TIT.2009.2013040`. (Preprint: arXiv:0712.4135.)

Provides the connection-vs-secrecy outage trade-off framework and the
notion of incremental redundancy versus repetition time diversity used as
inspiration for `S8 (PLS-RTX, opportunistic retransmission)` and
`S9 (PLS-Realloc, cooldown reallocation)`. Used in
`src/core-harness/core-harness.cc` (retry-attempt loop with optional SNIR
gain on S8 retries).

---

## 6. Fairness measure

### [Jai84] Jain's fairness index

R. Jain, D.-M. Chiu, W. R. Hawe, *"A Quantitative Measure of Fairness and
Discrimination for Resource Allocation in Shared Computer Systems"*,
Digital Equipment Corporation Tech. Report DEC-TR-301, Sept. 1984.

Formula:

```
J(x_1, ..., x_n) = (Σ x_i)^2 / (n · Σ x_i^2)
```

with `J = 1` for a perfectly fair allocation and `J = 1/n` for the worst
case. Used in: `src/metrics/metrics-collector.cc::Compute()` over per-user
PDRs to populate the `jain_fairness_index` CSV column.

---

## 7. Network simulator

### [HLR08] ns-3 simulator

T. R. Henderson, M. Lacage, G. F. Riley, *"Network Simulations with the ns-3
Simulator"*, ACM SIGCOMM 2008 Demo. https://www.nsnam.org

The discrete-event core (`ns3::Simulator`, RNG manager, `Time`,
`SimpleRefCount`, `Ptr<T>`) and the WiFi module that powers the
`ns3_wifi_yans` validation addendum.

### [LH06] YansWifiPhy and the ns-3 Wi-Fi stack

M. Lacage, T. R. Henderson, *"Yet Another Network Simulator"*, ACM WNS2
Workshop on ns-2: the IP Network Simulator, 2006.
DOI: `10.1145/1190455.1190467`.

Reference for `ns3::YansWifiPhy`, `YansWifiChannel`, `WifiHelper`,
`WifiMacHelper` and the table-based error-rate model
(`ns3::TableBasedErrorRateModel`) used by the validation addendum in
`src/industrial-wifi-sim.cc`.

---

## 8. Wireless industrial control and TSN context (paper framing)

### [3GPP22.104] Service requirements for cyber-physical control applications

3GPP TS 22.104 (Release 16+), *"Service requirements for cyber-physical
control applications in vertical domains"*, Stage 1. Defines the
deterministic latency / cycle-time / availability targets used to size the
default `deadlineMs = 10 ms` and `intervalMs = 10 ms` of the simulator.

### [IEEE802.1Qbv] Time-Aware Shaper

IEEE Std 802.1Qbv-2015 (now part of IEEE 802.1Q), *"Enhancements for
Scheduled Traffic"*. Reference for time-sensitive networking shapers used
in wired-side of a 5G-TSN bridge. Cited in `docs/methodology.md` as
context for why deadline / availability metrics are reported.

### [IEEE802.1CB] Frame Replication and Elimination for Reliability (FRER)

IEEE Std 802.1CB-2017, *"Frame Replication and Elimination for Reliability"*.
Same context as above; useful background when the paper discusses
redundancy as a complementary anti-jamming mechanism.

### [TSN5G25] 5G-TSN deterministic communication

M. Berisha et al., *"5G-TSN Integrated Prototype for Reliable Industrial
Communication Using FRER"*, MDPI Electronics 14(4):758, 2025.
DOI: `10.3390/electronics14040758`.

### [TSN5G2025] Indoor factory 5G-TSN scalability

A. Cano-Salazar et al., *"Scalability Analysis of 5G-TSN Applications in
Indoor Factory Settings"*, arXiv:2501.13138, 2025.

Both used as supporting references in the introduction/related-work to
frame the *why* of the deadline / recovery-time / safety-burst metrics
already exported by `MetricsCollector` and `AntiJammingMetricResult`.

---

## 9. Reproducibility-related software and tools

- **gnuplot** — T. Williams, C. Kelley et al., *gnuplot 5.x*,
  http://gnuplot.info. Used by `scripts/plot_results.py` to render every
  figure committed in the paper repository.
- **CMake** — Kitware Inc., *CMake build system*, https://cmake.org.
  Primary build orchestrator in `CMakeLists.txt`.
- **GNU make** — Free Software Foundation, *GNU make 4.x*. Fallback build
  path in `Makefile`.
- **Linux RFCs** for `/dev/urandom`: not directly used (the C++ harness
  takes its seeds from CLI / config), but cited for the seed-management
  contract in `scripts/check_seed_independence.py`.

---

## 10. Where each citation lands in the source tree

| File / function | Cited references |
|---|---|
| `src/channel/cm8-rayleigh-channel.{h,cc}` | [Mol09], [Tan08], [Tra18] |
| `src/channel/quadriga-channel-importer.{h,cc}` | [Jae14], [Wil19] |
| `src/channel/channel-abstraction.{h,cc}` | [3GPP38901] (new `inf_nlos_dl` dispatch), [Mol09], [Jae14] |
| `src/core-harness/core-harness.cc::HeDataRateMbps` | [Kho19] |
| `src/core-harness/core-harness.cc::CalculatePerSigmoid` | [TGax571], [Iyy22], [Kho19] |
| `src/core-harness/core-harness.cc` retry-loop / `s8RtxSnirGainDb` / `s9CooldownSymbols` | [Tan09], [Blo08] |
| `src/core-harness/core-harness.cc` reactive jamming, outage, recovery | [Bay08], [Pel11], [Gri21] |
| `src/metrics/metrics-collector.cc::Compute` (Jain) | [Jai84] |
| `src/metrics/antijamming-metrics.cc` | [Bay08], [Pel11] |
| `src/study-parameters.cc::PolicyLabel` | [Blo08], [Blo11], [Tan09] |
| `src/study-parameters.cc::PaperPolicyLabel` | [Fan26] §4.1-4.3 |
| `src/study-parameters.cc::ApplyS9EstimatorProfile` | [Fan26] §4.5 |
| `src/core-harness/core-harness.cc` S9 proactive defer (Algorithm 1) | [Fan26] §4.3 |
| `configs/s9_estimator_sensitivity.yaml` | [Fan26] Tab. 10 |
| `configs/s9_ablation.yaml` | [Fan26] Tab. 11 |
| `scripts/aggregate_s9_sensitivity.py`, `scripts/aggregate_s9_ablation.py` | [Fan26] §6.7-6.8 |
| `src/industrial-wifi-sim.cc` (Yans path) | [HLR08], [LH06] |
| `src/jammer/{constant,reactive}-jammer.cc` | [Bay08], [Gri21] |
| `configs/channels/cm8_rayleigh_20mhz.yaml` | [Mol09], [Tan08] |
| `configs/channels/inf_nlos_dl_5ghz.yaml` (new) | [3GPP38901] |
| `configs/channels/quadriga_raytraced.yaml` | [Jae14] |
| Paper deadline / interval defaults | [3GPP22.104], [TSN5G25] |
