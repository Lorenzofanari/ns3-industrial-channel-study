#include "safety-metrics.h"

#include <algorithm>

namespace ns3
{
namespace industrial
{

SafetyMetricResult
ComputeSafetyMetrics(uint32_t transmittedPackets,
                     const std::set<uint32_t>& receivedSeq,
                     const std::map<uint32_t, double>& receiveDelayS,
                     double intervalS,
                     double deadlineS)
{
    SafetyMetricResult out;
    if (transmittedPackets == 0)
    {
        return out;
    }

    uint32_t deadlineMisses = 0;
    uint32_t lost = 0;
    uint32_t currentBurst = 0;
    double lastSuccessTimeS = 0.0;

    for (uint32_t seq = 0; seq < transmittedPackets; ++seq)
    {
        const bool received = receivedSeq.find(seq) != receivedSeq.end();
        const auto delayIt = receiveDelayS.find(seq);
        const bool late = !received || delayIt == receiveDelayS.end() || delayIt->second > deadlineS;

        if (late)
        {
            ++deadlineMisses;
        }

        if (!received)
        {
            ++lost;
            ++currentBurst;
            out.maxLossBurstLength = std::max(out.maxLossBurstLength, currentBurst);
            const double gapS = (seq + 1) * intervalS - lastSuccessTimeS;
            out.maxTimeWithoutSuccessfulUpdateS = std::max(out.maxTimeWithoutSuccessfulUpdateS, gapS);
        }
        else
        {
            currentBurst = 0;
            lastSuccessTimeS = seq * intervalS + delayIt->second;
        }
    }

    out.deadlineMissRatio = static_cast<double>(deadlineMisses) / transmittedPackets;
    out.safetyCriticalPacketLossRatio = static_cast<double>(lost) / transmittedPackets;
    out.probabilityExceedingDeadline = out.deadlineMissRatio;
    return out;
}

} // namespace industrial
} // namespace ns3
