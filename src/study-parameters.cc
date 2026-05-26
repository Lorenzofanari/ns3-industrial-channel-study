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
    // Engineering/stochastic proxies. Both cm8_rayleigh and inf_nlos_dl share
    // the same log-distance + log-normal SF engine; they differ only in the
    // calibration values (Molisch et al. CM8 [Mol09] vs 3GPP InF-DL NLOS
    // [3GPP38901]). See BIBLIOGRAPHY.md and configs/channels/.
    if (channelModel == "cm8_rayleigh" || channelModel == "CM8" ||
        channelModel == "inf_nlos_dl" || channelModel == "INF_NLOS_DL" ||
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
        // trace, formatted to match QuaDRiGa output conventions [Jae14].
        // Stronger than proxy but not full frequency-selective CIR/CFR.
        // Full replay requires future SpectrumWifiPhy path. (TODO)
        return "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE";
    }
    if (channelModel == "inf_nlos_dl")
    {
        // Reviewer-readable label for 3GPP TR 38.901 InF-DL NLOS [3GPP38901].
        return "TR38901_INF_NLOS_DL";
    }
    return channelModel;
}

std::string
PolicyLabel(const std::string& scenario)
{
    // Archive-facing label. Kept stable so the historical CSV archive of the
    // paper [Fan26] keeps validating bit-for-bit. The paper-facing names
    // ("RTX-Assist", "Realloc") are exported in parallel through
    // PaperPolicyLabel() below. Both labels are written by the metrics
    // collector to separate columns.
    //   S0 NoPLS         : null policy, no PLS-specific behaviour.
    //   S4 Baseline-PF   : proportional-fair baseline [Fan26 §4.1].
    //   S8 PLS-RTX       : opportunistic retransmission. Theoretical backing
    //                      from secure HARQ [Tan09] / outage secrecy
    //                      framework [Blo08, Blo11]; in [Fan26] the policy is
    //                      renamed RTX-Assist because the present archive
    //                      validates reliability, not secrecy capacity.
    //   S9 PLS-Realloc   : AP-side SNIR-estimate-driven reallocation with a
    //                      76-symbol anti-oscillation cooldown [Fan26 §4.3,
    //                      Algorithm 1]. Renamed Realloc in [Fan26] for the
    //                      same reason as S8.
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

std::string
PaperPolicyLabel(const std::string& scenario)
{
    // Paper-facing label per [Fan26] §4.1-4.3. Use this in plots / tables that
    // are reproduced in the manuscript so the figure captions match the prose.
    //   S0 -> Null
    //   S4 -> Baseline-PF
    //   S8 -> RTX-Assist
    //   S9 -> Realloc
    if (scenario == "S0")
    {
        return "Null";
    }
    if (scenario == "S4")
    {
        return "Baseline-PF";
    }
    if (scenario == "S8")
    {
        return "RTX-Assist";
    }
    if (scenario == "S9")
    {
        return "Realloc";
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

void
ApplyS9EstimatorProfile(const std::string& profile, S9EstimatorConfig& out)
{
    // Profiles are taken from [Fan26] §4.5. Numerical values are documented in
    // BIBLIOGRAPHY.md and configs/s9_estimator_sensitivity.yaml; they are
    // chosen to bracket realistic AP-side HE-LTF estimator behaviour. Keep
    // these in sync with the YAML preset files.
    out.profile = profile;
    if (profile == "ideal")
    {
        out.snirNoiseStdDb = 0.0;
        out.snirBiasDb = 0.0;
        out.snirStalenessSlots = 0;
        out.jammerMissedDetProb = 0.0;
        out.jammerFalseAlarmProb = 0.0;
        return;
    }
    if (profile == "moderate")
    {
        out.snirNoiseStdDb = 1.0;
        out.snirBiasDb = 0.0;
        out.snirStalenessSlots = 1;
        out.jammerMissedDetProb = 0.05;
        out.jammerFalseAlarmProb = 0.05;
        return;
    }
    if (profile == "conservative")
    {
        out.snirNoiseStdDb = 3.0;
        out.snirBiasDb = 0.0;
        out.snirStalenessSlots = 4;
        out.jammerMissedDetProb = 0.20;
        out.jammerFalseAlarmProb = 0.10;
        return;
    }
    if (profile == "custom")
    {
        // Caller provides individual knobs; do not overwrite them here.
        return;
    }
    throw std::runtime_error("unknown S9 estimator profile (expected ideal/moderate/conservative/custom): " +
                             profile);
}

bool
S9AblationIdeal(const S9AblationConfig& cfg)
{
    return !cfg.disableJammerFlag && !cfg.disableCooldown && !cfg.disableSnirMargin &&
           !cfg.disablePerMargin;
}

S9Estimate
ComputeS9Estimate(double trueGammaDb, bool trueJammerActive, const S9EstimatorConfig& cfg,
                  std::mt19937& rng)
{
    S9Estimate estimate{trueGammaDb + cfg.snirBiasDb, trueJammerActive};
    if (cfg.snirNoiseStdDb > 0.0)
    {
        std::normal_distribution<double> noise(0.0, cfg.snirNoiseStdDb);
        estimate.gammaHatDb += noise(rng);
    }
    // jammerFlagHat is corrupted with two independent Bernoulli sources to
    // model missed detection (true=1 -> hat=0) and false alarm (true=0 ->
    // hat=1). When both probabilities are zero (ideal profile) the flag is
    // pass-through.
    if (cfg.jammerMissedDetProb > 0.0 || cfg.jammerFalseAlarmProb > 0.0)
    {
        std::uniform_real_distribution<double> uniform(0.0, 1.0);
        if (trueJammerActive)
        {
            if (uniform(rng) < cfg.jammerMissedDetProb)
            {
                estimate.jammerFlagHat = false;
            }
        }
        else
        {
            if (uniform(rng) < cfg.jammerFalseAlarmProb)
            {
                estimate.jammerFlagHat = true;
            }
        }
    }
    return estimate;
}

} // namespace industrial
} // namespace ns3
