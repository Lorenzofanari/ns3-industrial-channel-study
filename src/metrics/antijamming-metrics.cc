#include "antijamming-metrics.h"

#include <algorithm>
#include <cmath>
#include <limits>

namespace ns3
{
namespace industrial
{

namespace
{
constexpr double NaN = std::numeric_limits<double>::quiet_NaN();
} // namespace

double
DbmToMilliwatt(double dbm)
{
    return std::pow(10.0, dbm / 10.0);
}

double
MilliwattToDbm(double mw)
{
    return 10.0 * std::log10(std::max(mw, 1e-30));
}

AntiJammingMetricResult
ComputeAntiJammingMetrics(double signalPowerDbm,
                          double noiseFloorDbm,
                          double jammerPowerAtReceiverDbm,
                          double pdr,
                          double baselinePdr,
                          double plr,
                          double baselinePlr,
                          double per,
                          double baselinePer,
                          const std::string& jammerMode,
                          const AntiJammingTelemetry& telemetry)
{
    AntiJammingMetricResult out;
    out.signalPowerDbm = signalPowerDbm;
    out.noiseFloorDbm = noiseFloorDbm;
    out.jammerPowerAtReceiverDbm = jammerPowerAtReceiverDbm;

    const bool jammerOn = jammerMode != "none";
    const double interferenceMw = jammerOn ? DbmToMilliwatt(jammerPowerAtReceiverDbm) : 0.0;
    out.sinrDb = signalPowerDbm - MilliwattToDbm(DbmToMilliwatt(noiseFloorDbm) + interferenceMw);

    if (jammerOn)
    {
        out.sjrDb = signalPowerDbm - jammerPowerAtReceiverDbm;
        out.jnrDb = jammerPowerAtReceiverDbm - noiseFloorDbm;
    }
    else
    {
        out.sjrDb = NaN;
        out.jnrDb = NaN;
    }

    out.robustnessRatio = baselinePdr > 0.0 ? pdr / baselinePdr : 0.0;
    out.plrIncreaseDueToJammer = plr - baselinePlr;
    out.perIncreaseDueToJammer = per - baselinePer;

    out.jammerDutyCycle = telemetry.jammerDutyCycle;
    out.meanRecoveryTimeS = telemetry.meanRecoveryTimeS;
    out.recoverySampleCount = telemetry.recoverySampleCount;
    out.stdRecoveryTimeS = telemetry.stdRecoveryTimeS;
    out.p95RecoveryTimeS = telemetry.p95RecoveryTimeS;
    out.outageProbabilityJammerOn = telemetry.outageProbabilityJammerOn;
    out.outageThresholdDb = telemetry.outageThresholdDb;
    out.worstCaseBurstLatencyS = telemetry.worstCaseBurstLatencyS;
    out.maxConsecutiveDeadlineMisses = telemetry.maxConsecutiveDeadlineMisses;
    out.effectiveThroughputPps = telemetry.effectiveThroughputPps;
    out.recoveryTimeS = telemetry.meanRecoveryTimeS;
    // Coefficient of variation of the recovery time distribution. Useful for
    // claims like "the recovery time is consistent across bursts". NaN when
    // the mean is non-positive or the distribution has fewer than 2 samples.
    if (telemetry.recoverySampleCount >= 2 && telemetry.meanRecoveryTimeS > 0.0)
    {
        out.cvRecoveryTime = telemetry.stdRecoveryTimeS / telemetry.meanRecoveryTimeS;
    }
    else
    {
        out.cvRecoveryTime = NaN;
    }

    // Conditional PDR: only meaningful when the harness actually tracked
    // per-packet jammer state and the jammer was active for part of the run.
    if (telemetry.populated && jammerOn)
    {
        if (telemetry.txDuringJammerOn > 0)
        {
            out.pdrJammerOn = static_cast<double>(telemetry.rxAmongTxDuringJammerOn) /
                              static_cast<double>(telemetry.txDuringJammerOn);
        }
        // Total losses across the run, derived from the PLR scalar to avoid
        // requiring the caller to pass the integer counters again.
        const double totalLosses = plr; // ratio relative to transmitted packets
        if (totalLosses > 0.0 && telemetry.txDuringJammerOn > 0)
        {
            const double burstLossRatioOfTx =
                static_cast<double>(telemetry.lostDuringJammerOn) /
                static_cast<double>(telemetry.txDuringJammerOn);
            // burst_induced_loss_ratio = lost_during_ON / total_lost; reuse the
            // ratio definition by normalising against PLR rather than against
            // total tx count.
            out.burstInducedLossRatio = std::min(1.0, burstLossRatioOfTx * telemetry.jammerDutyCycle / totalLosses);
        }
    }
    else
    {
        out.pdrJammerOn = NaN;
        out.burstInducedLossRatio = NaN;
    }

    if (telemetry.populated)
    {
        // pdr_jammer_off is computed by the collector via the public
        // RunMetrics view; the formula is symmetric to pdr_jammer_on so the
        // collector fills it in. For safety leave NaN here.
        out.pdrJammerOff = NaN;
    }
    else
    {
        out.pdrJammerOff = NaN;
    }
    return out;
}

} // namespace industrial
} // namespace ns3
