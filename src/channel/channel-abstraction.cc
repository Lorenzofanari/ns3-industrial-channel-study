#include "channel-abstraction.h"

#include <stdexcept>

namespace ns3
{
namespace industrial
{

void
ValidateChannelConfig(const ChannelRuntimeConfig& config)
{
    // The validity range comes from the channel-model literature itself, not
    // from a hard-coded number: CM8 NLOS is 1-10 m [Mol09]; 3GPP InF-DL NLOS
    // is 1-600 m [3GPP38901]. The actual ceiling lives in the YAML config
    // (`max_distance_m`) which the run loads into `config.cm8.maxDistanceM`.
    if ((config.model == "cm8_rayleigh" || config.model == "inf_nlos_dl") &&
        config.distanceM > config.cm8.maxDistanceM)
    {
        throw std::runtime_error(
            "channel-abstraction: configured distance " + std::to_string(config.distanceM) +
            " m exceeds max_distance_m=" + std::to_string(config.cm8.maxDistanceM) +
            " m declared for channel '" + config.model + "'");
    }
}

Ptr<PropagationLossModel>
CreateIndustrialPropagationLoss(const ChannelRuntimeConfig& config, ChannelRuntimeSummary& summary)
{
    ValidateChannelConfig(config);
    summary.model = config.model;
    summary.configuredDistanceM = config.distanceM;

    // cm8_rayleigh    -> historical industrial-NLOS proxy + Rayleigh;
    //                    see configs/channels/cm8_rayleigh_20mhz.yaml.
    // cm8_strict_nlos -> same engine, calibrated to [Mol09] CM8 NLOS;
    //                    selected via `--channelModel=cm8_rayleigh` and the
    //                    configs/channels/cm8_strict_nlos.yaml preset.
    // inf_nlos_dl     -> 3GPP TR 38.901 InF-DL NLOS [3GPP38901];
    //                    see configs/channels/inf_nlos_dl_5ghz.yaml.
    if (config.model == "cm8_rayleigh" || config.model == "inf_nlos_dl")
    {
        auto model = CreateObject<Cm8RayleighPropagationLossModel>();
        model->SetConfig(config.cm8);
        summary.abstraction = config.model == "inf_nlos_dl"
                                  ? "stochastic_3gpp_inf_nlos_dl_log_distance_with_shadowing"
                                  : "controlled_rayleigh_path_loss_with_shadowing";
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
