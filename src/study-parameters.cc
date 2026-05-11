#include "study-parameters.h"

#include <cmath>
#include <stdexcept>

namespace ns3
{
namespace industrial
{

std::string
ToString(ChannelFidelity fidelity)
{
    switch (fidelity)
    {
    case ChannelFidelity::Proxy:
        return "proxy";
    case ChannelFidelity::ScalarGeometryTrace:
        return "scalar_geometry_trace";
    case ChannelFidelity::CirCfrTrace:
        return "cir_cfr_trace";
    }
    throw std::runtime_error("unknown channel fidelity");
}

ChannelFidelity
ChannelFidelityForModel(const std::string& channelModel)
{
    if (channelModel == "cm8_rayleigh" || channelModel == "CM8" ||
        channelModel == "QD_INDUSTRIAL_NLOS_PROXY" || channelModel == "TGAX_MODEL_D" ||
        channelModel == "TGAX_MODEL_E")
    {
        return ChannelFidelity::Proxy;
    }
    if (channelModel == "quadriga_raytraced" ||
        channelModel == "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE")
    {
        return ChannelFidelity::ScalarGeometryTrace;
    }
    throw std::runtime_error("unsupported channel model for channel_fidelity: " + channelModel);
}

std::string
ChannelDisplayName(const std::string& channelModel)
{
    if (channelModel == "quadriga_raytraced")
    {
        // Scalar path-loss replay from an externally generated geometry
        // trace, formatted to match QuaDRiGa output conventions.
        // Stronger than proxy but not full frequency-selective CIR/CFR.
        // Full replay requires future SpectrumWifiPhy path. (TODO)
        return "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE";
    }
    return channelModel;
}

std::string
PolicyLabel(const std::string& scenario)
{
    if (scenario == "S0")
    {
        return "NoPLS";
    }
    if (scenario == "S4")
    {
        return "Baseline-PF";
    }
    if (scenario == "S8")
    {
        return "PLS-RTX";
    }
    if (scenario == "S9")
    {
        return "PLS-Realloc";
    }
    throw std::runtime_error("unsupported policy/scenario: " + scenario);
}

double
PerThetaForMcs(uint32_t mcs, const PerWaterfallConfig& config)
{
    if (mcs == 0)
    {
        return config.thetaBpskDb;
    }
    if (mcs == 1)
    {
        return config.thetaQpskDb;
    }
    if (mcs == 3)
    {
        return config.theta16QamDb;
    }
    throw std::runtime_error("PER waterfall threshold is only defined for MCS 0, 1 and 3");
}

bool
EveEstimationIdeal(const EveEstimationConfig& config)
{
    return config.biasDb == 0.0 && config.noiseStdDb == 0.0 && config.delaySlots == 0;
}

double
ApplyEveSnirEstimate(double gammaEDb, const EveEstimationConfig& config, std::mt19937& rng)
{
    double estimate = gammaEDb + config.biasDb;
    if (config.noiseStdDb > 0.0)
    {
        std::normal_distribution<double> noise(0.0, config.noiseStdDb);
        estimate += noise(rng);
    }
    return estimate;
}

} // namespace industrial
} // namespace ns3
