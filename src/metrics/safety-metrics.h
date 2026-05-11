#ifndef SAFETY_METRICS_H
#define SAFETY_METRICS_H

#include <cstdint>
#include <map>
#include <set>
#include <vector>

namespace ns3
{
namespace industrial
{

struct SafetyMetricResult
{
    double deadlineMissRatio{0.0};
    double safetyCriticalPacketLossRatio{0.0};
    uint32_t maxLossBurstLength{0};
    double maxTimeWithoutSuccessfulUpdateS{0.0};
    double probabilityExceedingDeadline{0.0};
};

SafetyMetricResult ComputeSafetyMetrics(uint32_t transmittedPackets,
                                        const std::set<uint32_t>& receivedSeq,
                                        const std::map<uint32_t, double>& receiveDelayS,
                                        double intervalS,
                                        double deadlineS);

} // namespace industrial
} // namespace ns3

#endif // SAFETY_METRICS_H
