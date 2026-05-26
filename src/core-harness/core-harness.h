#ifndef CORE_HARNESS_H
#define CORE_HARNESS_H

#include "channel/cm8-rayleigh-channel.h"
#include "channel/quadriga-channel-importer.h"
#include "metrics/antijamming-metrics.h"
#include "metrics/metrics-collector.h"
#include "study-parameters.h"

#include <cstdint>
#include <string>

namespace ns3
{
namespace industrial
{

// Pure ns3::Simulator/RNG Monte-Carlo configuration: no YansWifiPhy, no MAC
// contention, no trigger frames, no BlockAck, no A-MPDU. The harness draws a
// per-packet SINR from the configured channel + jammer, applies the PER
// waterfall sigmoid for the active MCS, and resolves S4/S8/S9 retransmission
// policy on the resulting Bernoulli outcome. This is the simulation path used
// by the paper's statistical campaign (channel_fidelity=proxy).
//
// Multi-user fairness (`users` > 1): packet index `seq` belongs to user `seq %
// users`. All users share the same PHY channel draw (common AP/STA geometry
// and jammer); scheduling is idealised round-robin in time with one transmit
// opportunity every `trafficIntervalS` (no MAC contention model).
struct CoreHarnessConfig
{
    std::string channelModel{"cm8_rayleigh"};
    std::string tracePath{"data/quadriga/example_trace.csv"};
    Cm8RayleighConfig cm8;

    double distanceM{3.0};
    double txPowerDbm{18.0};
    double noiseFigureDb{7.0};
    double bandwidthMHz{20.0};
    uint32_t mcs{0};
    uint32_t payloadBits{128};
    uint32_t packets{1000};
    uint32_t retryLimit{7};
    double trafficIntervalS{0.01};
    double deadlineS{0.01};

    std::string jammerMode{"none"};
    double jammerPowerDbm{0.0};
    double jammerDistanceM{1.0};
    double reactiveBurstS{0.004};
    double reactiveIntervalS{0.020};

    std::string scenario{"S4"};
    PerWaterfallConfig per;
    double s8RtxSnirGainDb{1.35};
    uint32_t s9CooldownSymbols{76};
    double ofdmSymbolUs{16.0};

    uint32_t seed{1};
    // Number of users sharing the PHY in strict time-domain round-robin. Each
    // user transmits on sequential global slots; default 1 preserves legacy
    // single-link study behaviour.
    uint32_t users{1};

    // S9 estimator-impairment configuration ([Fan26] §4.5). Default is the
    // ideal profile, which keeps the historical archive bit-reproducible.
    S9EstimatorConfig s9Estimator;
    // S9 component ablation switches ([Fan26] §6.8). Default all-false.
    S9AblationConfig s9Ablation;
    // Master switch for the paper Algorithm 1 critical-mask defer. When
    // disabled (default) S9 retains its legacy cooldown-on-failure behaviour.
    S9ProactiveDeferConfig s9ProactiveDefer;
};

struct CoreHarnessLinkBudget
{
    double signalPowerDbm{0.0};
    double noiseFloorDbm{0.0};
    double jammerPowerAtReceiverDbm{-300.0};
    double nominalPathLossDb{0.0};
    double nominalDelayS{0.0};
    std::string channelAbstraction;
    std::string tracePath;
    // What was actually used at run time to model small-scale fading. One of
    //   "cm8_proxy"          (CM8 log-normal shadowing + Rayleigh draws)
    //   "trace_column"       (QuaDRiGa fading_std_db read from the trace)
    //   "none"               (deterministic path-loss only)
    // Reported in the CSV so the channel-fidelity story is self-documenting.
    std::string fadingVarianceSource{"cm8_proxy"};
    AntiJammingTelemetry telemetry;
    // Number of S9 proactive defer events that were triggered during the run.
    // Always zero unless `S9ProactiveDeferConfig.enabled` is true and the
    // scenario is S9. Exported as CSV column `s9_proactive_defer_count`.
    uint64_t s9ProactiveDeferCount{0};
};

// HE-MCS data-rate table used by the harness; 20 MHz, 1 SS, GI 3.2 us.
double HeDataRateMbps(uint32_t mcs);

// Logistic / sigmoid PER waterfall:
//   PER(gamma) = max(floor, 1 / (1 + exp(slope * (gamma_dB - theta_m_dB))))
// theta_m is the per-MCS midpoint exported as `per_theta_m` and slope is the
// shared waterfall steepness. The same calibration is used by both CM8 and
// QuaDRiGa runs so that channel differences are observable in PER vs SNR.
double CalculatePerSigmoid(double snirDb, uint32_t mcs, const PerWaterfallConfig& cfg);

CoreHarnessLinkBudget RunCoreHarness(const CoreHarnessConfig& cfg, MetricsCollector& collector);

} // namespace industrial
} // namespace ns3

#endif // CORE_HARNESS_H
