#include "antijamming-metrics.h"

#include <algorithm>
#include <cmath>

namespace ns3
{
namespace industrial
{

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
                          const std::string& jammerMode)
{
    AntiJammingMetricResult out;
    out.signalPowerDbm = signalPowerDbm;
    out.noiseFloorDbm = noiseFloorDbm;
    out.jammerPowerAtReceiverDbm = jammerPowerAtReceiverDbm;
    const double interferenceMw = jammerMode == "none" ? 0.0 : DbmToMilliwatt(jammerPowerAtReceiverDbm);
    out.sinrDb = signalPowerDbm - MilliwattToDbm(DbmToMilliwatt(noiseFloorDbm) + interferenceMw);
    out.robustnessRatio = baselinePdr > 0.0 ? pdr / baselinePdr : 0.0;
    out.plrIncreaseDueToJammer = plr - baselinePlr;
    out.perIncreaseDueToJammer = per - baselinePer;
    out.recoveryTimeS = jammerMode == "reactive" ? 0.0 : 0.0;
    return out;
}

} // namespace industrial
} // namespace ns3
