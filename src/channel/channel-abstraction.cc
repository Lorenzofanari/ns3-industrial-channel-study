#include "channel-abstraction.h"

#include <stdexcept>

namespace ns3
{
namespace industrial
{

void
ValidateChannelConfig(const ChannelRuntimeConfig& config)
{
    if (config.model == "cm8_rayleigh" && config.distanceM > config.cm8.maxDistanceM)
    {
        throw std::runtime_error("CM8 distance exceeds configured max_distance_m=6 m");
    }
}

Ptr<PropagationLossModel>
CreateIndustrialPropagationLoss(const ChannelRuntimeConfig& config, ChannelRuntimeSummary& summary)
{
    ValidateChannelConfig(config);
    summary.model = config.model;
    summary.configuredDistanceM = config.distanceM;

    if (config.model == "cm8_rayleigh")
    {
        auto model = CreateObject<Cm8RayleighPropagationLossModel>();
        model->SetConfig(config.cm8);
        summary.abstraction = "controlled_rayleigh_path_loss_with_shadowing";
        summary.nominalPathLossDb = CalculateCm8PathLossDb(config.distanceM, config.cm8);
        summary.nominalDelayS = config.distanceM / 299792458.0;
        return model;
    }

    if (config.model == "quadriga_raytraced")
    {
        QuadrigaTrace trace;
        trace.Load(config.tracePath);
        auto model = CreateObject<QuadrigaTracePropagationLossModel>();
        model->SetTrace(trace);
        model->SetDistanceM(config.distanceM);
        summary.abstraction = "external_geometry_trace_scalar_path_loss_replay";
        summary.tracePath = config.tracePath;
        summary.traceDistancesM = trace.GetDistances();
        summary.nominalPathLossDb = trace.GetPathLossDb(config.distanceM);
        summary.nominalDelayS = trace.GetEffectiveDelayS(config.distanceM);
        return model;
    }

    throw std::runtime_error("Unsupported channel model: " + config.model);
}

} // namespace industrial
} // namespace ns3
