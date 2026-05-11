#ifndef CHANNEL_ABSTRACTION_H
#define CHANNEL_ABSTRACTION_H

#include "cm8-rayleigh-channel.h"
#include "quadriga-channel-importer.h"

#include "ns3/propagation-loss-model.h"

#include <memory>
#include <string>
#include <vector>

namespace ns3
{
namespace industrial
{

struct ChannelRuntimeConfig
{
    std::string model{"cm8_rayleigh"};
    double distanceM{1.0};
    std::string tracePath{"data/quadriga/example_trace.csv"};
    Cm8RayleighConfig cm8;
};

struct ChannelRuntimeSummary
{
    std::string model;
    std::string abstraction;
    std::string tracePath;
    double configuredDistanceM{0.0};
    double nominalPathLossDb{0.0};
    double nominalDelayS{0.0};
    std::vector<double> traceDistancesM;
};

Ptr<PropagationLossModel> CreateIndustrialPropagationLoss(const ChannelRuntimeConfig& config,
                                                          ChannelRuntimeSummary& summary);

void ValidateChannelConfig(const ChannelRuntimeConfig& config);

} // namespace industrial
} // namespace ns3

#endif // CHANNEL_ABSTRACTION_H
