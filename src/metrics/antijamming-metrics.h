#ifndef ANTIJAMMING_METRICS_H
#define ANTIJAMMING_METRICS_H

#include <cstdint>
#include <string>

namespace ns3
{
namespace industrial
{

// Per-run telemetry produced by the core-harness during the simulation. The
// Yans path leaves all fields at default (no per-packet jammer state available
// without PHY traces).
struct AntiJammingTelemetry
{
    // Configured / nominal duty cycle of the jammer:
    //   none      -> 0.0
    //   constant  -> 1.0
    //   reactive  -> burstDuration / burstInterval
    double jammerDutyCycle{0.0};

    // Number of transmitted packets whose first attempt overlapped a moment
    // when the jammer was emitting energy (true ON state).
    uint32_t txDuringJammerOn{0};

    // Number of received packets whose first transmission attempt overlapped
    // a jammer-ON moment.
    uint32_t rxAmongTxDuringJammerOn{0};

    // Number of lost packets whose first transmission attempt overlapped a
    // jammer-ON moment. Used to derive burst_induced_loss_ratio.
    uint32_t lostDuringJammerOn{0};

    // Mean recovery time in seconds: averaged over reactive jammer bursts,
    // the elapsed time from each burst end to the next successfully received
    // packet. NaN for constant or none modes (no transitions). The harness
    // emits 0.0 when no burst end occurs during the simulation window.
    double meanRecoveryTimeS{0.0};

    // Number of recovery samples that fed `meanRecoveryTimeS`. Lets the
    // statistical post-processing decide whether the mean is well-defined.
    uint32_t recoverySampleCount{0};

    // True when the harness actually populated this telemetry; lets readers
    // distinguish a zero-but-measured value from a missing measurement.
    bool populated{false};
};

struct AntiJammingMetricResult
{
    // Link-budget at the receiver.
    double signalPowerDbm{0.0};
    double noiseFloorDbm{0.0};
    double jammerPowerAtReceiverDbm{-300.0};
    double sinrDb{0.0};
    // Auxiliary link budgets specific to anti-jamming analyses.
    double sjrDb{0.0};       // S - J in dB (NaN when jammer absent)
    double jnrDb{0.0};       // J - N in dB (NaN when jammer absent)
    // Jammer activity.
    double jammerDutyCycle{0.0};
    // PDR conditioned on the jammer state observed at first-attempt time.
    double pdrJammerOn{0.0};
    double pdrJammerOff{0.0};
    // Fraction of total losses incurred while jammer was active at the
    // first-attempt time. 0 when jammer absent.
    double burstInducedLossRatio{0.0};
    // Comparative metrics versus the matching no-jammer baseline; filled in
    // post-hoc by the sweep aggregator.
    double robustnessRatio{1.0};
    double plrIncreaseDueToJammer{0.0};
    double perIncreaseDueToJammer{0.0};
    // Mean recovery time after a reactive burst ends (see telemetry struct).
    double meanRecoveryTimeS{0.0};
    uint32_t recoverySampleCount{0};
    // Historical alias retained for CSV/JSON backwards compatibility.
    double recoveryTimeS{0.0};
};

double DbmToMilliwatt(double dbm);
double MilliwattToDbm(double mw);

AntiJammingMetricResult ComputeAntiJammingMetrics(double signalPowerDbm,
                                                  double noiseFloorDbm,
                                                  double jammerPowerAtReceiverDbm,
                                                  double pdr,
                                                  double baselinePdr,
                                                  double plr,
                                                  double baselinePlr,
                                                  double per,
                                                  double baselinePer,
                                                  const std::string& jammerMode,
                                                  const AntiJammingTelemetry& telemetry);

} // namespace industrial
} // namespace ns3

#endif // ANTIJAMMING_METRICS_H
