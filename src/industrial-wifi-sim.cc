// industrial-wifi-sim.cc -- entry point for the IEEE 802.11ax (HE) industrial
// channel study. The validation addendum (ns3_wifi_yans simulationPath) is built
// on top of the ns-3 Wi-Fi stack [HLR08, LH06]; the statistical main campaign
// (ns3_core_harness simulationPath) bypasses MAC/PHY contention and consumes
// only the propagation-loss models and RNG infrastructure of ns-3. See
// BIBLIOGRAPHY.md for the full citation chain.
#include "channel/channel-abstraction.h"
#include "core-harness/core-harness.h"
#include "jammer/constant-jammer.h"
#include "jammer/reactive-jammer.h"
#include "metrics/metrics-collector.h"
#include "study-parameters.h"
#include "traffic/periodic-control-app.h"

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/propagation-delay-model.h"
#include "ns3/version.h"
#include "ns3/wifi-net-device.h"
#include "ns3/wifi-module.h"
#include "ns3/wifi-remote-station-manager.h"
#include "ns3/yans-wifi-channel.h"
#include "ns3/yans-wifi-helper.h"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <limits>
#include <iostream>
#include <random>
#include <sstream>
#include <stdexcept>
#include <string>

using namespace ns3;
using namespace ns3::industrial;

namespace
{

std::string
DataModeFor(uint32_t mcs, const std::string& standard)
{
    if (standard == "80211be")
    {
        return "EhtMcs" + std::to_string(mcs);
    }
    return "HeMcs" + std::to_string(mcs);
}

std::string
GetGitCommit()
{
    const char* env = std::getenv("GIT_COMMIT");
    if (env && std::string(env).size() > 0)
    {
        return env;
    }
    return "unknown";
}

double
NominalRxPowerDbm(double txPowerDbm, double pathLossDb)
{
    return txPowerDbm - pathLossDb;
}

void
SetScenarioDefaults(const std::string& scenario, uint32_t& retryLimit)
{
    if (scenario == "S8")
    {
        retryLimit = std::max(retryLimit, 9u);
    }
    else if (scenario == "S9")
    {
        retryLimit = std::max(retryLimit, 11u);
    }
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string scenario = "S4";
    std::string channelModel = "cm8_rayleigh";
    std::string standard = "80211ax";
    std::string jammerMode = "none";
    std::string simulationPath = "ns3_wifi_yans";
    std::string output = "results/one_run.csv";
    std::string jsonOutput = "results/one_run.json";
    std::string tracePath = "data/quadriga/example_trace.csv";
    uint32_t seed = 1;
    uint32_t mcs = 0;
    uint32_t payloadBits = 128;
    uint32_t packets = 1000;
    uint32_t users = 1;
    uint32_t retryLimit = 7;
    uint32_t s9CooldownSymbols = 76;
    bool enableNoplsBaseline = false;
    double distanceM = 1.0;
    double jammerPowerDbm = 10.0;
    double jammerDistanceM = 1.0;
    // Reactive-jammer duty cycle = reactiveBurstMs / reactiveIntervalMs.
    // Defaults reproduce the historical archive (4 ms ON every 20 ms).
    // Exposed as CLI flags so the duty-cycle / burst-length sensitivity
    // sweep of Tab. 13 ([Fan26] §X) can be reproduced without recompiling.
    double reactiveBurstMs = 4.0;
    double reactiveIntervalMs = 20.0;
    double txPowerDbm = 18.0;
    double noiseFigureDb = 7.0;
    double bandwidthMHz = 20.0;
    double simTimeS = 10.0;
    double warmupS = 1.0;
    double intervalMs = 10.0;
    double deadlineMs = 10.0;
    double pathLossExponent = 2.2;
    double referenceLossDb = 43.0;
    double shadowingStdDb = 2.0;
    double coherenceTimeMs = 5.0;
    double industrialExcessLossDb = 3.0;
    // Validity range of the loaded channel model. The C++ default mirrors the
    // legacy cm8_rayleigh preset (6 m); for inf_nlos_dl, cm8_strict_nlos and
    // the QuaDRiGa profile the operator (or run_sweep.py) overrides this from
    // the YAML's `max_distance_m`. The simulator enforces `distanceM <=
    // maxDistanceM` for stochastic models, refusing extrapolation beyond the
    // literature's validity envelope. -1 disables the check explicitly.
    double maxDistanceM = 6.0;
    double perThetaBpskDb = 3.0;
    double perThetaQpskDb = 6.0;
    double perTheta16QamDb = 15.5;
    double perSlope = 1.15;
    double s8RtxSnirGain = 1.35;
    double eveSnirBiasDb = 0.0;
    double eveSnirNoiseStdDb = 0.0;
    uint32_t eveSnirDelaySlots = 0;
    bool rayleighFading = true;

    // S9 estimator-impairment profile (paper §4.5). `ideal` reproduces the
    // historical archive bit-for-bit; the named profiles populate the
    // individual knobs from a literature-aligned preset. Each knob can also
    // be overridden via its own CLI flag; in that case `--s9-estimator-profile=custom`
    // keeps the operator's overrides intact.
    std::string s9EstimatorProfile = "ideal";
    double s9SnirNoiseStdDb = 0.0;
    double s9SnirBiasDb = 0.0;
    uint32_t s9SnirStalenessSlots = 0;
    double s9JammerMissedDetProb = 0.0;
    double s9JammerFalseAlarmProb = 0.0;
    double s9PerCrit = 0.10;
    double s9GammaOutDb = 0.0;

    // S9 component ablation (paper §6.8).
    bool s9DisableJammerFlag = false;
    bool s9DisableCooldown = false;
    bool s9DisableSnirMargin = false;
    bool s9DisablePerMargin = false;

    // Master switch: enable the paper Algorithm 1 critical-mask defer. Default
    // false to preserve the historical archive.
    bool s9ProactiveDeferEnabled = false;
    // Trace provenance gate (reviewer-grade channel-fidelity guard).
    //   - `traceProvenance` is exported verbatim into the CSV. Allowed
    //     values: synthetic_placeholder, measured, cm8_stochastic_proxy.
    //   - `syntheticPlaceholderFinalClaimsAllowed` is forwarded to the CSV
    //     so reviewers see the gate state per row.
    //   - When `requireMeasuredTrace` is true the binary refuses to start
    //     a QuaDRiGa run whose provenance is not `measured`. This is what a
    //     paper-submission pipeline should turn on.
    std::string traceProvenance = "";
    bool syntheticPlaceholderFinalClaimsAllowed = false;
    bool requireMeasuredTrace = false;

    CommandLine cmd(__FILE__);
    cmd.AddValue("scenario", "Scenario label: S4, S8 or S9; S0 is accepted only with --enable-nopls-baseline", scenario);
    cmd.AddValue("channelModel",
                 "Channel model: cm8_rayleigh (CM8 industrial NLOS proxy [Mol09]), "
                 "inf_nlos_dl (3GPP TR 38.901 InF-DL NLOS [3GPP38901]) or "
                 "quadriga_raytraced (scalar geometry trace [Jae14])",
                 channelModel);
    cmd.AddValue("standard", "Wi-Fi standard: 80211ax or 80211be", standard);
    cmd.AddValue("simulationPath",
                 "Simulation path: ns3_wifi_yans (packet-level addendum, YansWifiPhy stack) "
                 "or ns3_core_harness (statistical Monte-Carlo PER-waterfall campaign)",
                 simulationPath);
    cmd.AddValue("mcs", "MCS index, supported study values: 0, 1, 3", mcs);
    cmd.AddValue("payloadBits", "Application payload size in bits", payloadBits);
    cmd.AddValue("distanceM", "STA-AP distance in meters", distanceM);
    cmd.AddValue("jammerMode", "none, constant or reactive", jammerMode);
    cmd.AddValue("jammerPowerDbm", "Jammer transmit power in dBm", jammerPowerDbm);
    cmd.AddValue("jammerDistanceM", "Jammer-AP nominal distance in meters", jammerDistanceM);
    cmd.AddValue("reactive-burst-ms",
                 "Reactive jammer burst length in ms (default 4 ms)",
                 reactiveBurstMs);
    cmd.AddValue("reactive-interval-ms",
                 "Reactive jammer period (burst + silence) in ms (default 20 ms; "
                 "duty cycle = burst/interval)",
                 reactiveIntervalMs);
    cmd.AddValue("seed", "RNG seed", seed);
    cmd.AddValue("packets", "Number of control packets to transmit", packets);
    cmd.AddValue("users",
                 "Core-harness only: STAs sharing the PHY in round-robin (packet seq mod users). "
                 "Must be 1 for ns3_wifi_yans.",
                 users);
    cmd.AddValue("retryLimit", "Wi-Fi long/short retry limit metadata", retryLimit);
    cmd.AddValue("enable-nopls-baseline", "Enable S0/NoPLS baseline policy metadata", enableNoplsBaseline);
    cmd.AddValue("per-theta-bpsk", "BPSK-1/2 PER waterfall midpoint in dB", perThetaBpskDb);
    cmd.AddValue("per-theta-qpsk", "QPSK-1/2 PER waterfall midpoint in dB", perThetaQpskDb);
    cmd.AddValue("per-theta-16qam", "16QAM-3/4 PER waterfall midpoint in dB", perTheta16QamDb);
    cmd.AddValue("per-slope", "PER waterfall slope calibration parameter", perSlope);
    cmd.AddValue("s8-rtx-snir-gain", "S8 opportunistic retransmission SNIR gain factor", s8RtxSnirGain);
    // S9 cooldown: 76 OFDM symbols at T_sym=16us => ~1.216 ms.
    // Purpose: prevent repeated trigger oscillations across consecutive
    // short packets. Not derived from IEEE 802.11ax standard timing.
    // To sweep: use --s9-cooldown-symbols CLI argument.
    cmd.AddValue("s9-cooldown-symbols", "S9 harness cooldown in OFDM symbols", s9CooldownSymbols);
    cmd.AddValue("eve-snir-bias-db", "Additive bias on gamma_E estimate in dB", eveSnirBiasDb);
    cmd.AddValue("eve-snir-noise-std-db", "Zero-mean Gaussian gamma_E estimate noise std in dB", eveSnirNoiseStdDb);
    cmd.AddValue("eve-snir-delay-slots", "Scheduling slots by which gamma_E estimate is stale", eveSnirDelaySlots);
    // S9 estimator-impairment knobs (paper [Fan26] §4.5 / Tab. 10). Each
    // defaults to 0 (= ideal observability profile, no behaviour change).
    cmd.AddValue("s9-estimator-profile",
                 "S9 estimator preset: ideal|moderate|conservative|custom",
                 s9EstimatorProfile);
    cmd.AddValue("s9-snir-noise-std-db",
                 "Zero-mean Gaussian noise sigma on S9 AP-side SNIR estimate (dB)",
                 s9SnirNoiseStdDb);
    cmd.AddValue("s9-snir-bias-db",
                 "Systematic bias on S9 AP-side SNIR estimate (dB; positive = over-estimate)",
                 s9SnirBiasDb);
    cmd.AddValue("s9-snir-staleness-slots",
                 "Number of slots the S9 SNIR estimate lags the truth (0 = ideal)",
                 s9SnirStalenessSlots);
    cmd.AddValue("s9-jammer-md-prob",
                 "AP-side jammer-flag missed-detection probability P_md (paper §4.5)",
                 s9JammerMissedDetProb);
    cmd.AddValue("s9-jammer-fa-prob",
                 "AP-side jammer-flag false-alarm probability P_fa (paper §4.5)",
                 s9JammerFalseAlarmProb);
    cmd.AddValue("s9-per-crit",
                 "PER_crit threshold above which an RU opportunity is marked critical (Eq. 4)",
                 s9PerCrit);
    cmd.AddValue("s9-gamma-out-db",
                 "gamma_out threshold below which an RU is marked critical regardless of PER (Eq. 4)",
                 s9GammaOutDb);
    // S9 ablation switches (paper [Fan26] §6.8 / Tab. 11).
    cmd.AddValue("s9-ablation-disable-jammer-flag",
                 "Ablation: ignore the AP-side jammer-exposure flag in S9 critical mask",
                 s9DisableJammerFlag);
    cmd.AddValue("s9-ablation-disable-cooldown",
                 "Ablation: run S9 without the 76-symbol anti-oscillation cooldown",
                 s9DisableCooldown);
    cmd.AddValue("s9-ablation-disable-snir-margin",
                 "Ablation: skip the gamma_hat < gamma_out check in S9 critical mask",
                 s9DisableSnirMargin);
    cmd.AddValue("s9-ablation-disable-per-margin",
                 "Ablation: skip the PER_hat > PER_crit check in S9 critical mask",
                 s9DisablePerMargin);
    // Master switch for the paper Algorithm 1 critical-mask defer.
    cmd.AddValue("s9-proactive-defer",
                 "Enable the paper Algorithm 1 critical-mask defer (opt-in; default false "
                 "preserves the historical archive). Required to populate Tab. 10/11 campaigns.",
                 s9ProactiveDeferEnabled);
    cmd.AddValue("txPowerDbm", "STA/AP transmit power in dBm", txPowerDbm);
    cmd.AddValue("noiseFigureDb", "Receiver noise figure in dB", noiseFigureDb);
    cmd.AddValue("bandwidthMHz", "Channel bandwidth in MHz", bandwidthMHz);
    cmd.AddValue("simTimeS", "Maximum simulation time in seconds", simTimeS);
    cmd.AddValue("warmupS", "Application start time in seconds", warmupS);
    cmd.AddValue("intervalMs", "Periodic control interval in ms", intervalMs);
    cmd.AddValue("deadlineMs", "Safety deadline in ms", deadlineMs);
    cmd.AddValue("tracePath", "QuaDRiGa/ray-traced CSV path", tracePath);
    cmd.AddValue("pathLossExponent", "CM8-like path loss exponent", pathLossExponent);
    cmd.AddValue("referenceLossDb", "CM8-like reference loss in dB at 1 m", referenceLossDb);
    cmd.AddValue("shadowingStdDb", "CM8-like log-normal shadowing standard deviation", shadowingStdDb);
    cmd.AddValue("coherenceTimeMs", "CM8-like fading coherence time in ms", coherenceTimeMs);
    cmd.AddValue("industrialExcessLossDb", "CM8-like industrial excess loss in dB", industrialExcessLossDb);
    cmd.AddValue("rayleighFading", "Enable CM8-like Rayleigh fading", rayleighFading);
    cmd.AddValue("maxDistanceM",
                 "Maximum tx-rx distance allowed for stochastic channel models "
                 "(CM8: 10 m [Mol09]; InF-DL: 600 m [3GPP38901]). Use -1 to "
                 "disable the validity check explicitly.",
                 maxDistanceM);
    cmd.AddValue("traceProvenance",
                 "Trace provenance tag: synthetic_placeholder, measured or cm8_stochastic_proxy. "
                 "Leave empty to auto-detect (cm8_stochastic_proxy for CM8, synthetic_placeholder for "
                 "the QuaDRiGa example trace).",
                 traceProvenance);
    cmd.AddValue("syntheticPlaceholderFinalClaimsAllowed",
                 "Operator-acknowledged flag that the run can be used for final paper claims even with "
                 "a synthetic trace. Default false; final-paper pipelines should keep it false.",
                 syntheticPlaceholderFinalClaimsAllowed);
    cmd.AddValue("requireMeasuredTrace",
                 "Refuse to start QuaDRiGa runs whose trace_provenance is not 'measured'. Turn on in "
                 "the camera-ready pipeline so synthetic placeholders cannot accidentally feed the "
                 "paper figures.",
                 requireMeasuredTrace);
    cmd.AddValue("output", "CSV output path", output);
    cmd.AddValue("jsonOutput", "JSON output path", jsonOutput);
    cmd.Parse(argc, argv);

    SetScenarioDefaults(scenario, retryLimit);

    if (scenario == "S0" && !enableNoplsBaseline)
    {
        throw std::runtime_error("S0/NoPLS requires --enable-nopls-baseline=true");
    }
    if (scenario != "S0" && scenario != "S4" && scenario != "S8" && scenario != "S9")
    {
        throw std::runtime_error("scenario must be S4, S8, S9, or gated S0");
    }
    if (mcs != 0 && mcs != 1 && mcs != 3)
    {
        throw std::runtime_error("This study only supports MCS 0, 1 and 3");
    }
    if (payloadBits % 8 != 0)
    {
        throw std::runtime_error("payloadBits must be divisible by 8");
    }
    if (standard != "80211ax" && standard != "80211be")
    {
        throw std::runtime_error("standard must be 80211ax or 80211be");
    }
    if (simulationPath != "ns3_wifi_yans" && simulationPath != "ns3_core_harness")
    {
        throw std::runtime_error("simulationPath must be ns3_wifi_yans or ns3_core_harness");
    }
    if (simulationPath == "ns3_wifi_yans" && users != 1)
    {
        throw std::runtime_error("ns3_wifi_yans only supports users=1; use ns3_core_harness for multi-user fairness");
    }
    if (users < 1)
    {
        throw std::runtime_error("users must be >= 1");
    }

    // Channel-fidelity gate (reviewer-grade). For CM8 the run is stochastic
    // proxy by construction; for QuaDRiGa we default to synthetic_placeholder
    // unless the operator overrides --traceProvenance. The example_trace.csv
    // ships as documented placeholder; pointing --tracePath at a different
    // file is necessary (but not sufficient) for `--traceProvenance=measured`.
    if (traceProvenance.empty())
    {
        if (channelModel == "cm8_rayleigh")
        {
            traceProvenance = "cm8_stochastic_proxy";
        }
        else if (channelModel == "inf_nlos_dl")
        {
            // 3GPP TR 38.901 InF-DL NLOS [3GPP38901] is itself a stochastic
            // model (path-loss formula + log-normal SF), not a measured trace.
            traceProvenance = "tr38901_inf_stochastic";
        }
        else if (channelModel == "quadriga_raytraced")
        {
            // Default to the safe (synthetic_placeholder) provenance so a
            // missing CLI flag never accidentally tags rows as measured.
            traceProvenance = "synthetic_placeholder";
        }
        else
        {
            traceProvenance = "unknown";
        }
    }
    if (traceProvenance != "synthetic_placeholder" && traceProvenance != "measured" &&
        traceProvenance != "cm8_stochastic_proxy" &&
        traceProvenance != "tr38901_inf_stochastic" && traceProvenance != "unknown")
    {
        throw std::runtime_error(
            "traceProvenance must be one of: synthetic_placeholder, measured, "
            "cm8_stochastic_proxy, tr38901_inf_stochastic");
    }
    if (channelModel == "quadriga_raytraced" && requireMeasuredTrace &&
        traceProvenance != "measured")
    {
        throw std::runtime_error(
            "requireMeasuredTrace is set but traceProvenance=" + traceProvenance +
            "; refuse to feed final-paper figures with a non-measured trace. Run with "
            "--traceProvenance=measured only once data/quadriga/<your_trace>.csv has been "
            "replaced with measured QuaDRiGa data.");
    }

    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(seed);

    Cm8RayleighConfig cm8;
    cm8.txPowerDbm = txPowerDbm;
    cm8.noiseFigureDb = noiseFigureDb;
    cm8.bandwidthHz = bandwidthMHz * 1e6;
    cm8.pathLossExponent = pathLossExponent;
    cm8.referenceLossDb = referenceLossDb;
    cm8.shadowingStdDb = shadowingStdDb;
    cm8.coherenceTimeMs = coherenceTimeMs;
    cm8.industrialExcessLossDb = industrialExcessLossDb;
    cm8.rayleighFading = rayleighFading;
    // maxDistanceM < 0 -> disable the validity check (operator opt-in to
    // extrapolate beyond the channel-model envelope; rows are still tagged
    // with the original channel_model and can be filtered out downstream).
    cm8.maxDistanceM = maxDistanceM < 0.0 ? std::numeric_limits<double>::infinity()
                                          : maxDistanceM;

    const PerWaterfallConfig perConfig{perThetaBpskDb, perThetaQpskDb, perTheta16QamDb, perSlope, 1e-8};
    const EveEstimationConfig eveConfig{eveSnirBiasDb, eveSnirNoiseStdDb, eveSnirDelaySlots};

    // S9 estimator: apply the named profile first (no-op for "custom"), then
    // honour any individual knob overrides supplied on the command line. The
    // knob defaults are zero (ideal) so unspecified flags do not change the
    // preset values. To detect operator overrides we re-apply only knobs that
    // differ from the preset's defaults: a simpler convention is to require
    // `--s9-estimator-profile=custom` whenever per-knob overrides are mixed.
    S9EstimatorConfig s9EstimatorCfg;
    ApplyS9EstimatorProfile(s9EstimatorProfile, s9EstimatorCfg);
    if (s9EstimatorProfile == "custom")
    {
        s9EstimatorCfg.snirNoiseStdDb = s9SnirNoiseStdDb;
        s9EstimatorCfg.snirBiasDb = s9SnirBiasDb;
        s9EstimatorCfg.snirStalenessSlots = s9SnirStalenessSlots;
        s9EstimatorCfg.jammerMissedDetProb = s9JammerMissedDetProb;
        s9EstimatorCfg.jammerFalseAlarmProb = s9JammerFalseAlarmProb;
    }
    // PER_crit and gamma_out apply to every profile; they tune the critical-
    // mask thresholds rather than the estimation impairment itself.
    s9EstimatorCfg.perCrit = s9PerCrit;
    s9EstimatorCfg.gammaOutDb = s9GammaOutDb;

    S9AblationConfig s9AblationCfg;
    s9AblationCfg.disableJammerFlag = s9DisableJammerFlag;
    s9AblationCfg.disableCooldown = s9DisableCooldown;
    s9AblationCfg.disableSnirMargin = s9DisableSnirMargin;
    s9AblationCfg.disablePerMargin = s9DisablePerMargin;

    S9ProactiveDeferConfig s9ProactiveDeferCfg;
    s9ProactiveDeferCfg.enabled = s9ProactiveDeferEnabled;

    auto buildRunContext = [&](const std::string& abstraction,
                               const std::string& effectiveTracePath) {
        RunContext context;
        context.gitCommit = GetGitCommit();
        context.ns3Version = Version::ShortVersion();
        context.seed = seed;
        context.scenario = scenario;
        context.policy = scenario;
        context.policyLabel = PolicyLabel(scenario);
        context.policyPaperLabel = PaperPolicyLabel(scenario);
        context.simulationPath = simulationPath;
        context.channelModel = ChannelDisplayName(channelModel);
        context.channelFidelity = ToString(ChannelFidelityForModel(channelModel));
        context.channelAbstraction = abstraction;
        context.tracePath = effectiveTracePath;
        context.mcs = mcs;
        context.payloadBits = payloadBits;
        context.distanceM = distanceM;
        context.jammerMode = jammerMode;
        context.jammerPowerDbm = jammerMode != "none" ? jammerPowerDbm : 0.0;
        context.standard = standard;
        context.dataMode = DataModeFor(mcs, standard);
        context.retryLimit = retryLimit;
        context.txPowerDbm = txPowerDbm;
        context.noiseFigureDb = noiseFigureDb;
        context.bandwidthMHz = bandwidthMHz;
        context.simulationTimeS = simTimeS;
        context.trafficIntervalS = intervalMs / 1000.0;
        context.deadlineS = deadlineMs / 1000.0;
        context.phyPerAvailable = simulationPath == "ns3_core_harness";
        context.perDefinition = simulationPath == "ns3_core_harness"
                                    ? "per_waterfall_sigmoid_on_per_packet_snir"
                                    : "application_loss_proxy_until_phy_mac_traces_enabled";
        context.perThetaM = PerThetaForMcs(mcs, perConfig);
        context.perSlope = perSlope;
        context.s8RtxSnirGain = s8RtxSnirGain;
        context.s9CooldownSymbols = s9CooldownSymbols;
        context.eveSnirBiasDb = eveSnirBiasDb;
        context.eveSnirNoiseStdDb = eveSnirNoiseStdDb;
        context.eveSnirDelaySlots = eveSnirDelaySlots;
        context.eveEstimationIdeal = EveEstimationIdeal(eveConfig);
        // S9 estimator + ablation provenance per row (Data and Reproducibility
        // Statement, [Fan26] §9). Always exported, regardless of scenario.
        context.s9EstimatorProfile = s9EstimatorCfg.profile;
        context.s9SnirNoiseStdDb = s9EstimatorCfg.snirNoiseStdDb;
        context.s9SnirBiasDb = s9EstimatorCfg.snirBiasDb;
        context.s9SnirStalenessSlots = s9EstimatorCfg.snirStalenessSlots;
        context.s9JammerMissedDetProb = s9EstimatorCfg.jammerMissedDetProb;
        context.s9JammerFalseAlarmProb = s9EstimatorCfg.jammerFalseAlarmProb;
        context.s9PerCrit = s9EstimatorCfg.perCrit;
        context.s9GammaOutDb = s9EstimatorCfg.gammaOutDb;
        context.s9AblationDisableJammerFlag = s9AblationCfg.disableJammerFlag;
        context.s9AblationDisableCooldown = s9AblationCfg.disableCooldown;
        context.s9AblationDisableSnirMargin = s9AblationCfg.disableSnirMargin;
        context.s9AblationDisablePerMargin = s9AblationCfg.disablePerMargin;
        context.s9ProactiveDeferEnabled = s9ProactiveDeferCfg.enabled;
        context.traceProvenance = traceProvenance;
        context.syntheticPlaceholderFinalClaimsAllowed = syntheticPlaceholderFinalClaimsAllowed;
        context.numUsers = users;
        // Fading-variance source: drives reviewer-readable channel-fidelity
        // semantics. The harness path knows the actual source from its own
        // dispatch (trace-derived vs CM8 proxy vs deterministic) and overrides
        // this field below; the Yans path keeps the default below.
        if (channelModel == "cm8_rayleigh")
        {
            context.fadingVarianceSource = rayleighFading ? "cm8_proxy" : "none";
        }
        else if (channelModel == "inf_nlos_dl")
        {
            // 3GPP InF-DL stochastic SF; the YAML default is log-normal only,
            // but the operator can still toggle on the Rayleigh draw to obtain
            // a coarser proxy. Surface the actual choice in the CSV so the
            // channel-fidelity story is self-documenting.
            context.fadingVarianceSource = rayleighFading ? "cm8_proxy" : "log_normal_only";
        }
        else if (channelModel == "quadriga_raytraced")
        {
            // Conservative default. The harness path will refine this once it
            // confirms whether the trace actually provided fading_std_db.
            context.fadingVarianceSource = "trace_or_path_loss_only";
        }
        return context;
    };

    if (simulationPath == "ns3_core_harness")
    {
        if (jammerMode != "none" && jammerMode != "constant" && jammerMode != "reactive")
        {
            throw std::runtime_error("jammerMode must be none, constant or reactive");
        }

        CoreHarnessConfig harness;
        harness.channelModel = channelModel;
        harness.tracePath = tracePath;
        harness.cm8 = cm8;
        harness.distanceM = distanceM;
        harness.txPowerDbm = txPowerDbm;
        harness.noiseFigureDb = noiseFigureDb;
        harness.bandwidthMHz = bandwidthMHz;
        harness.mcs = mcs;
        harness.payloadBits = payloadBits;
        harness.packets = packets;
        harness.retryLimit = retryLimit;
        harness.trafficIntervalS = intervalMs / 1000.0;
        harness.deadlineS = deadlineMs / 1000.0;
        harness.jammerMode = jammerMode;
        harness.jammerPowerDbm = jammerPowerDbm;
        harness.jammerDistanceM = jammerDistanceM;
        harness.reactiveBurstS = reactiveBurstMs / 1000.0;
        harness.reactiveIntervalS = reactiveIntervalMs / 1000.0;
        harness.scenario = scenario;
        harness.per = perConfig;
        harness.s8RtxSnirGainDb = s8RtxSnirGain;
        harness.s9CooldownSymbols = s9CooldownSymbols;
        harness.seed = seed;
        harness.users = users;
        harness.s9Estimator = s9EstimatorCfg;
        harness.s9Ablation = s9AblationCfg;
        harness.s9ProactiveDefer = s9ProactiveDeferCfg;

        Ptr<MetricsCollector> collector = Create<MetricsCollector>();
        const CoreHarnessLinkBudget budget = RunCoreHarness(harness, *collector);

        RunContext context = buildRunContext(budget.channelAbstraction, budget.tracePath);
        // Refine fading variance source from the actual harness dispatch:
        // the buildRunContext default is conservative because it cannot see
        // whether the trace exposed fading_std_db.
        context.fadingVarianceSource = budget.fadingVarianceSource;
        RunMetrics metrics = collector->Compute(context,
                                                budget.signalPowerDbm,
                                                budget.noiseFloorDbm,
                                                budget.jammerPowerAtReceiverDbm,
                                                budget.telemetry);
        metrics.s9ProactiveDeferCount = budget.s9ProactiveDeferCount;
        WriteCsv(output, metrics);
        WriteJson(jsonOutput, metrics);
        Simulator::Destroy();
        return 0;
    }

    ChannelRuntimeConfig channelConfig;
    channelConfig.model = channelModel;
    channelConfig.distanceM = distanceM;
    channelConfig.tracePath = tracePath;
    channelConfig.cm8 = cm8;
    ChannelRuntimeSummary channelSummary;
    Ptr<PropagationLossModel> lossModel = CreateIndustrialPropagationLoss(channelConfig, channelSummary);
    lossModel->AssignStreams(seed * 1000);

    Ptr<YansWifiChannel> wifiChannel = CreateObject<YansWifiChannel>();
    wifiChannel->SetPropagationLossModel(lossModel);
    wifiChannel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());

    NodeContainer staNode;
    staNode.Create(1);
    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer jammerNode;
    const bool jammerEnabled = jammerMode != "none";
    if (jammerEnabled)
    {
        jammerNode.Create(1);
    }

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> positionAlloc = CreateObject<ListPositionAllocator>();
    positionAlloc->Add(Vector(distanceM, 0.0, 1.5));
    positionAlloc->Add(Vector(0.0, 0.0, 1.5));
    if (jammerEnabled)
    {
        positionAlloc->Add(Vector(jammerDistanceM, 1.0, 1.5));
    }
    NodeContainer allNodes;
    allNodes.Add(staNode);
    allNodes.Add(apNode);
    if (jammerEnabled)
    {
        allNodes.Add(jammerNode);
    }
    mobility.SetPositionAllocator(positionAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(allNodes);

    WifiHelper wifi;
    if (standard == "80211be")
    {
        wifi.SetStandard(WIFI_STANDARD_80211be);
    }
    else
    {
        wifi.SetStandard(WIFI_STANDARD_80211ax);
    }

    const std::string dataMode = DataModeFor(mcs, standard);
    const std::string controlMode = DataModeFor(0, standard);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue(dataMode),
                                 "ControlMode",
                                 StringValue(controlMode));

    YansWifiPhyHelper phy;
    phy.SetChannel(wifiChannel);
    phy.Set("ChannelSettings", StringValue("{36, 20, BAND_5GHZ, 0}"));
    phy.Set("TxPowerStart", DoubleValue(txPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(txPowerDbm));
    phy.Set("RxNoiseFigure", DoubleValue(noiseFigureDb));
    phy.Set("RxSensitivity", DoubleValue(cm8.receiverSensitivityDbm));
    phy.SetErrorRateModel("ns3::TableBasedErrorRateModel");

    WifiMacHelper mac;
    Ssid ssid = Ssid("industrial-channel-study");

    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer staDevice = wifi.Install(phy, mac, staNode);

    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDevice = wifi.Install(phy, mac, apNode);

    NetDeviceContainer jammerDevice;
    if (jammerEnabled)
    {
        phy.Set("TxPowerStart", DoubleValue(jammerPowerDbm));
        phy.Set("TxPowerEnd", DoubleValue(jammerPowerDbm));
        mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
        jammerDevice = wifi.Install(phy, mac, jammerNode);
    }

    InternetStackHelper stack;
    stack.Install(allNodes);

    NetDeviceContainer allDevices;
    allDevices.Add(staDevice);
    allDevices.Add(apDevice);
    if (jammerEnabled)
    {
        allDevices.Add(jammerDevice);
    }
    for (uint32_t i = 0; i < allDevices.GetN(); ++i)
    {
        Ptr<WifiNetDevice> wifiDevice = DynamicCast<WifiNetDevice>(allDevices.Get(i));
        if (wifiDevice && wifiDevice->GetRemoteStationManager())
        {
            wifiDevice->GetRemoteStationManager()->SetMaxSlrc(retryLimit);
            wifiDevice->GetRemoteStationManager()->SetMaxSsrc(retryLimit);
        }
    }
    Ipv4AddressHelper address;
    address.SetBase("10.40.0.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(allDevices);
    const Ipv4Address apAddress = interfaces.GetAddress(1);

    Ptr<MetricsCollector> collector = Create<MetricsCollector>();
    const uint16_t port = 9000;
    Ptr<ControlReceiverApp> receiver = CreateObject<ControlReceiverApp>();
    receiver->Configure(port, collector);
    apNode.Get(0)->AddApplication(receiver);
    receiver->SetStartTime(Seconds(0.0));
    receiver->SetStopTime(Seconds(simTimeS + warmupS + 1.0));

    Ptr<PeriodicControlApp> sender = CreateObject<PeriodicControlApp>();
    sender->Configure(InetSocketAddress(apAddress, port),
                      payloadBits / 8,
                      MilliSeconds(intervalMs),
                      packets,
                      collector);
    staNode.Get(0)->AddApplication(sender);
    sender->SetStartTime(Seconds(warmupS));
    sender->SetStopTime(Seconds(simTimeS + warmupS));

    const uint16_t jammerPort = 9001;
    Ptr<ControlReceiverApp> jammerSink = CreateObject<ControlReceiverApp>();
    jammerSink->Configure(jammerPort, Create<MetricsCollector>());
    apNode.Get(0)->AddApplication(jammerSink);
    jammerSink->SetStartTime(Seconds(0.0));
    jammerSink->SetStopTime(Seconds(simTimeS + warmupS + 1.0));

    if (jammerMode == "constant")
    {
        ConstantJammerConfig cfg;
        cfg.enabled = true;
        cfg.powerDbm = jammerPowerDbm;
        InstallConstantJammer(jammerNode,
                              apAddress,
                              jammerPort,
                              cfg,
                              Seconds(warmupS),
                              Seconds(simTimeS + warmupS));
    }
    else if (jammerMode == "reactive")
    {
        ReactiveJammerConfig cfg;
        cfg.enabled = true;
        cfg.powerDbm = jammerPowerDbm;
        InstallReactiveJammer(jammerNode,
                              apAddress,
                              jammerPort,
                              cfg,
                              Seconds(warmupS),
                              Seconds(simTimeS + warmupS));
    }
    else if (jammerMode != "none")
    {
        throw std::runtime_error("jammerMode must be none, constant or reactive");
    }

    Simulator::Stop(Seconds(simTimeS + warmupS + 1.0));
    Simulator::Run();

    RunContext context = buildRunContext(channelSummary.abstraction, channelSummary.tracePath);

    const double signalPowerDbm = NominalRxPowerDbm(txPowerDbm, channelSummary.nominalPathLossDb);
    const double noiseFloorDbm = CalculateNoiseFloorDbm(bandwidthMHz * 1e6, noiseFigureDb);
    const double jammerPathLossDb =
        (channelModel == "cm8_rayleigh" || channelModel == "inf_nlos_dl")
            ? CalculateCm8PathLossDb(jammerDistanceM, cm8)
            : channelSummary.nominalPathLossDb;
    const double jammerRxDbm = jammerEnabled ? jammerPowerDbm - jammerPathLossDb : -300.0;

    RunMetrics metrics = collector->Compute(context, signalPowerDbm, noiseFloorDbm, jammerRxDbm);
    WriteCsv(output, metrics);
    WriteJson(jsonOutput, metrics);

    Simulator::Destroy();
    return 0;
}
