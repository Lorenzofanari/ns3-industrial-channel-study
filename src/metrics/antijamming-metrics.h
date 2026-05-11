#ifndef ANTIJAMMING_METRICS_H
#define ANTIJAMMING_METRICS_H

#include <string>

namespace ns3
{
namespace industrial
{

struct AntiJammingMetricResult
{
    double signalPowerDbm{0.0};
    double noiseFloorDbm{0.0};
    double jammerPowerAtReceiverDbm{-300.0};
    double sinrDb{0.0};
    double robustnessRatio{1.0};
    double plrIncreaseDueToJammer{0.0};
    double perIncreaseDueToJammer{0.0};
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
                                                  const std::string& jammerMode);

} // namespace industrial
} // namespace ns3

#endif // ANTIJAMMING_METRICS_H
