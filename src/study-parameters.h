#ifndef STUDY_PARAMETERS_H
#define STUDY_PARAMETERS_H

#include <cstdint>
#include <random>
#include <string>

namespace ns3
{
namespace industrial
{

enum class ChannelFidelity
{
    Proxy,
    ScalarGeometryTrace,
    CirCfrTrace,
};

struct PerWaterfallConfig
{
    double thetaBpskDb{3.0};
    double thetaQpskDb{6.0};
    double theta16QamDb{15.5};
    double slope{1.15};
    double floor{1e-8};
};

struct EveEstimationConfig
{
    double biasDb{0.0};
    double noiseStdDb{0.0};
    uint32_t delaySlots{0};
};

std::string ToString(ChannelFidelity fidelity);
ChannelFidelity ChannelFidelityForModel(const std::string& channelModel);
std::string ChannelDisplayName(const std::string& channelModel);
std::string PolicyLabel(const std::string& scenario);
double PerThetaForMcs(uint32_t mcs, const PerWaterfallConfig& config);
bool EveEstimationIdeal(const EveEstimationConfig& config);
double ApplyEveSnirEstimate(double gammaEDb, const EveEstimationConfig& config, std::mt19937& rng);

} // namespace industrial
} // namespace ns3

#endif // STUDY_PARAMETERS_H
