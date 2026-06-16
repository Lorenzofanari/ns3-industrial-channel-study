#include "core-harness.h"

#include "channel/cm8-rayleigh-channel.h"
#include "channel/quadriga-channel-importer.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <limits>
#include <optional>
#include <random>
#include <set>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace ns3
{
namespace industrial
{

double
HeDataRateMbps(uint32_t mcs)
{
    // IEEE 802.11ax 20 MHz, 1 spatial stream, GI = 3.2 us (data subcarriers = 234,
    // useful symbol duration 12.8 us + 3.2 us GI = 16 us). Values reproduced
    // from the HE-MCS rate table in [Kho19] §III (see BIBLIOGRAPHY.md).
    switch (mcs)
    {
    case 0:
        return 8.6;
    case 1:
        return 17.2;
    case 3:
        return 51.6;
    }
    throw std::runtime_error("HeDataRateMbps: unsupported MCS (only 0, 1, 3 are part of this study)");
}

double
CalculatePerSigmoid(double snirDb, uint32_t mcs, const PerWaterfallConfig& cfg)
{
    // PHY abstraction (PER vs SINR after RBIR mapping) is well approximated
    // by a logistic centred at the per-MCS waterfall midpoint theta_m.
    //   PER(gamma) = max(floor, 1 / (1 + exp(slope * (gamma_dB - theta_m_dB))))
    // theta_m is calibrated per HE-MCS against the AWGN PER@10%-target curves
    // from the TGax evaluation methodology [TGax571] and the RBIR-based PHY
    // abstraction validation in [Iyy22]. Packet-length extrapolation
    // (PER_PL = 1 - (1 - PER_PL0)^(PL/PL0)) is documented separately in
    // `RESULTS_FOR_PAPER.md`.
    const double theta = PerThetaForMcs(mcs, cfg);
    const double per = 1.0 / (1.0 + std::exp(cfg.slope * (snirDb - theta)));
    return std::max(per, cfg.floor);
}

std::vector<uint32_t>
ParseRuList(const std::string& text, uint32_t numRus)
{
    std::vector<uint32_t> out;
    std::string normalised = text;
    for (char& c : normalised)
    {
        if (c == ';' || c == ':' || c == '|')
        {
            c = ',';
        }
    }
    std::stringstream ss(normalised);
    std::string part;
    while (std::getline(ss, part, ','))
    {
        if (part.empty())
        {
            continue;
        }
        const auto value = static_cast<uint32_t>(std::stoul(part));
        if (value >= numRus)
        {
            throw std::runtime_error("jammed RU id " + std::to_string(value) +
                                     " exceeds numRus=" + std::to_string(numRus));
        }
        if (std::find(out.begin(), out.end(), value) == out.end())
        {
            out.push_back(value);
        }
    }
    return out;
}

uint32_t
SelectMinIndex(const std::vector<double>& values)
{
    if (values.empty())
    {
        throw std::runtime_error("SelectMinIndex requires at least one value");
    }
    return static_cast<uint32_t>(std::distance(values.begin(),
                                               std::min_element(values.begin(), values.end())));
}

std::vector<uint32_t>
JammedRusForBurst(const std::string& jammerRuMode,
                  const std::vector<uint32_t>& configuredRus,
                  uint32_t jammedRuCount,
                  uint32_t numRus,
                  uint32_t burstIndex,
                  uint32_t seed,
                  uint32_t retryRu,
                  double followRetryProb,
                  double followDraw)
{
    if (jammerRuMode == "none" || numRus == 0)
    {
        return {};
    }
    if (jammerRuMode == "broadband_constant" || jammerRuMode == "broadband_reactive")
    {
        std::vector<uint32_t> all;
        all.reserve(numRus);
        for (uint32_t r = 0; r < numRus; ++r)
        {
            all.push_back(r);
        }
        return all;
    }
    if (jammerRuMode == "retry_aware_reactive" && retryRu < numRus &&
        followRetryProb > 0.0 && followDraw < followRetryProb)
    {
        return {retryRu};
    }
    if (!configuredRus.empty() &&
        (jammerRuMode == "narrowband_constant" || jammerRuMode == "narrowband_reactive" ||
         jammerRuMode == "retry_aware_reactive"))
    {
        return configuredRus;
    }
    const uint32_t count = std::min(std::max(1u, jammedRuCount), numRus);
    if (jammerRuMode == "narrowband_constant" || jammerRuMode == "narrowband_reactive" ||
        jammerRuMode == "retry_aware_reactive")
    {
        std::vector<uint32_t> out;
        out.reserve(count);
        for (uint32_t r = 0; r < count; ++r)
        {
            out.push_back(r);
        }
        return out;
    }
    if (jammerRuMode == "partial_band_reactive_random")
    {
        std::vector<uint32_t> all;
        all.reserve(numRus);
        for (uint32_t r = 0; r < numRus; ++r)
        {
            all.push_back(r);
        }
        std::mt19937 local(seed ^ (0x9e3779b9u + burstIndex * 2654435761u));
        std::shuffle(all.begin(), all.end(), local);
        all.resize(count);
        std::sort(all.begin(), all.end());
        return all;
    }
    throw std::runtime_error("unsupported jammer RU mode: " + jammerRuMode);
}

namespace
{

double
DbmToMw(double dbm)
{
    return std::pow(10.0, dbm / 10.0);
}

double
MwToDbm(double mw)
{
    return 10.0 * std::log10(std::max(mw, 1e-30));
}

std::string
NormaliseOfdmaPolicy(const CoreHarnessConfig& cfg)
{
    if (!cfg.policy.empty())
    {
        return cfg.policy;
    }
    return ScenarioDefaultPolicy(cfg.scenario);
}

std::string
NormaliseJammerRuMode(const CoreHarnessConfig& cfg)
{
    if (!cfg.jammerRuMode.empty())
    {
        return cfg.jammerRuMode;
    }
    if (cfg.jammerMode == "none")
    {
        return "none";
    }
    if (cfg.jammerMode == "constant")
    {
        return "broadband_constant";
    }
    if (cfg.jammerMode == "reactive")
    {
        return "broadband_reactive";
    }
    return cfg.jammerMode;
}

bool
JammerModeIsReactive(const std::string& mode)
{
    return mode == "broadband_reactive" || mode == "narrowband_reactive" ||
           mode == "partial_band_reactive_random" || mode == "retry_aware_reactive";
}

bool
JammerModeIsConstant(const std::string& mode)
{
    return mode == "broadband_constant" || mode == "narrowband_constant";
}

bool
ContainsRu(const std::vector<uint32_t>& rus, uint32_t ru)
{
    return std::find(rus.begin(), rus.end(), ru) != rus.end();
}

bool
TimeInReactiveBurst(double timeS, double phaseS, double intervalS, double burstS)
{
    if (intervalS <= 0.0 || burstS <= 0.0)
    {
        return false;
    }
    const double shifted = timeS - phaseS;
    double phase = std::fmod(shifted, intervalS);
    if (phase < 0.0)
    {
        phase += intervalS;
    }
    return phase < burstS;
}

uint32_t
BurstIndexAt(double timeS, double phaseS, double intervalS)
{
    if (intervalS <= 0.0)
    {
        return 0;
    }
    const double shifted = timeS - phaseS;
    if (shifted <= 0.0)
    {
        return 0;
    }
    return static_cast<uint32_t>(std::floor(shifted / intervalS));
}

CoreHarnessLinkBudget
RunCoreHarnessPerRu(const CoreHarnessConfig& cfg, MetricsCollector& collector)
{
    if (cfg.numRus < 1)
    {
        throw std::runtime_error("core-harness per-RU: numRus must be >= 1");
    }
    if (cfg.ruCorrelationRho < 0.0 || cfg.ruCorrelationRho > 1.0)
    {
        throw std::runtime_error("core-harness per-RU: ruCorrelationRho must be in [0,1]");
    }

    std::mt19937 rng(cfg.seed);
    std::uniform_real_distribution<double> uniform(0.0, 1.0);
    std::exponential_distribution<double> rayleighPower(1.0);
    // Dedicated fading RNG: only used by the AR(1) correlation model so that
    // the small-scale channel realisation is identical across policies sharing
    // the same fadingSeed (clean Delta-PDR isolation), and so legacy block-mode
    // draws (which keep using `rng`) stay bit-reproducible.
    const bool useAr1 = (cfg.cm8.correlationModel == "ar1");
    std::mt19937 fadingRng(cfg.cm8.fadingSeed != 0 ? cfg.cm8.fadingSeed : cfg.seed);
    std::normal_distribution<double> gauss(0.0, 1.0);

    CoreHarnessLinkBudget budget;
    double pathLossDb = 0.0;
    double effectiveShadowStdDb = cfg.cm8.shadowingStdDb;
    bool useRayleigh = cfg.cm8.rayleighFading;
    QuadrigaTrace trace;
    if (cfg.channelModel == "cm8_rayleigh" || cfg.channelModel == "inf_nlos_dl")
    {
        pathLossDb = CalculateCm8PathLossDb(cfg.distanceM, cfg.cm8);
        if (cfg.channelModel == "inf_nlos_dl")
        {
            budget.channelAbstraction =
                "per_ru_stochastic_3gpp_inf_nlos_dl_log_distance_with_shadowing";
            budget.fadingVarianceSource = useRayleigh ? "cm8_proxy" : "log_normal_only";
        }
        else
        {
            budget.channelAbstraction = "per_ru_controlled_rayleigh_path_loss_with_shadowing";
            budget.fadingVarianceSource = useRayleigh ? "cm8_proxy" : "none";
        }
    }
    else if (cfg.channelModel == "quadriga_raytraced")
    {
        trace.Load(cfg.tracePath);
        pathLossDb = trace.GetPathLossDb(cfg.distanceM);
        budget.tracePath = cfg.tracePath;
        budget.nominalDelayS = trace.GetEffectiveDelayS(cfg.distanceM);
        const double traceFadingStd = trace.GetFadingStdDb(cfg.distanceM);
        if (traceFadingStd > 0.0)
        {
            effectiveShadowStdDb = std::max(cfg.cm8.shadowingStdDb, traceFadingStd);
            useRayleigh = false;
            budget.channelAbstraction =
                "per_ru_external_geometry_trace_scalar_path_loss_replay_with_trace_fading_std";
            budget.fadingVarianceSource = "trace_column";
        }
        else
        {
            useRayleigh = cfg.cm8.rayleighFading;
            budget.channelAbstraction = "per_ru_external_geometry_trace_scalar_path_loss_replay";
            budget.fadingVarianceSource =
                (useRayleigh || effectiveShadowStdDb > 0.0) ? "cm8_proxy" : "none";
        }
    }
    else
    {
        throw std::runtime_error("core-harness per-RU: unsupported channel model " + cfg.channelModel);
    }

    const double noiseFloorDbm = CalculateNoiseFloorDbm(cfg.bandwidthMHz * 1e6, cfg.noiseFigureDb);
    const double noiseMw = DbmToMw(noiseFloorDbm);
    double jammerPathLossDb = 0.0;
    double jammerRxDbm = -300.0;
    double jammerMw = 0.0;
    const std::string jammerRuMode = NormaliseJammerRuMode(cfg);
    const bool jammerEnabled = jammerRuMode != "none";
    if (jammerEnabled)
    {
        if (cfg.channelModel == "cm8_rayleigh" || cfg.channelModel == "inf_nlos_dl")
        {
            jammerPathLossDb = CalculateCm8PathLossDb(cfg.jammerDistanceM, cfg.cm8);
        }
        else
        {
            jammerPathLossDb = trace.GetPathLossDb(cfg.jammerDistanceM);
        }
        jammerRxDbm = cfg.jammerPowerDbm - jammerPathLossDb;
        jammerMw = DbmToMw(jammerRxDbm);
    }

    budget.nominalPathLossDb = pathLossDb;
    budget.signalPowerDbm = cfg.txPowerDbm - pathLossDb;
    budget.noiseFloorDbm = noiseFloorDbm;
    budget.jammerPowerAtReceiverDbm = jammerRxDbm;
    if (budget.nominalDelayS == 0.0)
    {
        budget.nominalDelayS = cfg.distanceM / 299792458.0;
    }

    const double dataRateBps = HeDataRateMbps(cfg.mcs) * 1e6;
    constexpr double preambleS = 44e-6;
    constexpr double headerBits = 416.0;
    const double txTimeS = preambleS + (cfg.payloadBits + headerBits) / dataRateBps;
    const double propDelayS = budget.nominalDelayS;
    const double slotS = 9e-6;
    const double cooldownS =
        cfg.s9CooldownMs >= 0.0 ? cfg.s9CooldownMs / 1000.0
                                : cfg.s9CooldownSymbols * cfg.ofdmSymbolUs * 1e-6;
    const double cooldownMs = cooldownS * 1000.0;
    const std::string policy = NormaliseOfdmaPolicy(cfg);
    const std::vector<uint32_t> configuredJammedRus = ParseRuList(cfg.jammedRuList, cfg.numRus);

    std::optional<std::normal_distribution<double>> shadowDist;
    if (effectiveShadowStdDb > 0.0)
    {
        shadowDist.emplace(0.0, effectiveShadowStdDb);
    }
    std::optional<std::normal_distribution<double>> unitNormal;
    if (effectiveShadowStdDb > 0.0)
    {
        unitNormal.emplace(0.0, 1.0);
    }

    const double coherenceTimeS = cfg.cm8.coherenceTimeMs * 1e-3;
    const double spatialRho = std::clamp(cfg.ruCorrelationRho, 0.0, 1.0);
    double lastFadingTimeS = -1.0e9;
    std::vector<double> cachedRuFadingDb(cfg.numRus, 0.0);
    // AR(1)/OU state per RU (used only when correlationModel == "ar1").
    std::vector<double> ouShadow(cfg.numRus, 0.0);
    std::vector<double> ouRe(cfg.numRus, 0.0);
    std::vector<double> ouIm(cfg.numRus, 0.0);
    bool ouInit = false;
    auto composeRuFading = [&]() {
        for (uint32_t r = 0; r < cfg.numRus; ++r)
        {
            double fadingDb = 0.0;
            if (effectiveShadowStdDb > 0.0)
            {
                fadingDb += ouShadow[r];
            }
            if (useRayleigh)
            {
                const double powerGain = std::max(ouRe[r] * ouRe[r] + ouIm[r] * ouIm[r], 1e-12);
                fadingDb += 10.0 * std::log10(powerGain);
            }
            cachedRuFadingDb[r] = fadingDb;
        }
    };
    auto ruFadingAt = [&](double timeS) -> const std::vector<double>& {
        if (useAr1)
        {
            // Multiple accesses at the same instant share one realisation and
            // do not advance the process (avoids double-sampling within an
            // attempt, e.g. estimatedBestRuAt scanning every RU).
            if (ouInit && timeS <= lastFadingTimeS)
            {
                return cachedRuFadingDb;
            }
            const double TcS = std::max(coherenceTimeS, 1e-9);
            if (!ouInit)
            {
                // Stationary initial draw.
                const double common = gauss(fadingRng);
                for (uint32_t r = 0; r < cfg.numRus; ++r)
                {
                    if (effectiveShadowStdDb > 0.0)
                    {
                        const double indep = gauss(fadingRng);
                        ouShadow[r] = effectiveShadowStdDb *
                                      (std::sqrt(spatialRho) * common +
                                       std::sqrt(1.0 - spatialRho) * indep);
                    }
                    if (useRayleigh)
                    {
                        ouRe[r] = std::sqrt(0.5) * gauss(fadingRng);
                        ouIm[r] = std::sqrt(0.5) * gauss(fadingRng);
                    }
                }
                ouInit = true;
            }
            else
            {
                const double dt = std::max(0.0, timeS - lastFadingTimeS);
                const double rhoT = std::exp(-dt / TcS);
                const double sT = std::sqrt(std::max(0.0, 1.0 - rhoT * rhoT));
                const double commonInnov = gauss(fadingRng);
                for (uint32_t r = 0; r < cfg.numRus; ++r)
                {
                    if (effectiveShadowStdDb > 0.0)
                    {
                        const double indepInnov = gauss(fadingRng);
                        const double shadowInnov =
                            effectiveShadowStdDb * (std::sqrt(spatialRho) * commonInnov +
                                                    std::sqrt(1.0 - spatialRho) * indepInnov);
                        ouShadow[r] = rhoT * ouShadow[r] + sT * shadowInnov;
                    }
                    if (useRayleigh)
                    {
                        ouRe[r] = rhoT * ouRe[r] + sT * std::sqrt(0.5) * gauss(fadingRng);
                        ouIm[r] = rhoT * ouIm[r] + sT * std::sqrt(0.5) * gauss(fadingRng);
                    }
                }
            }
            lastFadingTimeS = timeS;
            composeRuFading();
            return cachedRuFadingDb;
        }
        // Legacy block fading (default): hold the draw for one coherence window.
        if (timeS - lastFadingTimeS >= coherenceTimeS)
        {
            const double common = unitNormal ? (*unitNormal)(rng) : 0.0;
            for (uint32_t r = 0; r < cfg.numRus; ++r)
            {
                double fadingDb = 0.0;
                if (unitNormal)
                {
                    const double independent = (*unitNormal)(rng);
                    fadingDb += effectiveShadowStdDb *
                                (std::sqrt(spatialRho) * common +
                                 std::sqrt(1.0 - spatialRho) * independent);
                }
                if (useRayleigh)
                {
                    const double powerGain = std::max(rayleighPower(rng), 1e-12);
                    fadingDb += 10.0 * std::log10(powerGain);
                }
                cachedRuFadingDb[r] = fadingDb;
            }
            lastFadingTimeS = timeS;
        }
        return cachedRuFadingDb;
    };

    auto activeJammedRus = [&](double timeS, uint32_t retryRu) {
        if (!jammerEnabled)
        {
            return std::vector<uint32_t>{};
        }
        if (JammerModeIsConstant(jammerRuMode))
        {
            return JammedRusForBurst(jammerRuMode,
                                     configuredJammedRus,
                                     cfg.jammedRuCount,
                                     cfg.numRus,
                                     0,
                                     cfg.seed,
                                     retryRu,
                                     cfg.jammerFollowRetryProb,
                                     uniform(rng));
        }
        if (JammerModeIsReactive(jammerRuMode) &&
            TimeInReactiveBurst(timeS, cfg.jammerPhaseS, cfg.reactiveIntervalS, cfg.reactiveBurstS))
        {
            const uint32_t burstIndex = BurstIndexAt(timeS, cfg.jammerPhaseS, cfg.reactiveIntervalS);
            return JammedRusForBurst(jammerRuMode,
                                     configuredJammedRus,
                                     cfg.jammedRuCount,
                                     cfg.numRus,
                                     burstIndex,
                                     cfg.seed,
                                     retryRu,
                                     cfg.jammerFollowRetryProb,
                                     uniform(rng));
        }
        return std::vector<uint32_t>{};
    };

    auto ruJammedAt = [&](double timeS, uint32_t ru, uint32_t retryRu) {
        return ContainsRu(activeJammedRus(timeS, retryRu), ru);
    };

    auto interferenceMw = [&](double timeS, uint32_t ru, uint32_t retryRu) {
        const bool jammed = ruJammedAt(timeS, ru, retryRu);
        return noiseMw + (jammed ? jammerMw : 0.0);
    };

    auto sinrAt = [&](double timeS, uint32_t ru, double extraGainDb, uint32_t retryRu) {
        const auto& fading = ruFadingAt(timeS);
        const double sigDbm = cfg.txPowerDbm - pathLossDb + fading[ru] + extraGainDb;
        const double iPlusNDbm = MwToDbm(interferenceMw(timeS, ru, retryRu));
        return sigDbm - iPlusNDbm;
    };

    auto estimatedSinrAt = [&](double timeS, uint32_t ru, uint32_t retryRu) {
        const double trueSinr = sinrAt(timeS, ru, 0.0, retryRu);
        const bool trueJammed = ruJammedAt(timeS, ru, retryRu);
        const auto estimate = ComputeS9Estimate(trueSinr, trueJammed, cfg.s9Estimator, rng);
        return estimate.gammaHatDb;
    };

    auto estimatedJammerAt = [&](double timeS, uint32_t ru, uint32_t retryRu) {
        const double trueSinr = sinrAt(timeS, ru, 0.0, retryRu);
        const bool trueJammed = ruJammedAt(timeS, ru, retryRu);
        const auto estimate = ComputeS9Estimate(trueSinr, trueJammed, cfg.s9Estimator, rng);
        return estimate.jammerFlagHat;
    };

    auto estimatedBestRuAt = [&](double timeS) {
        std::vector<double> estimatedPer;
        estimatedPer.reserve(cfg.numRus);
        for (uint32_t r = 0; r < cfg.numRus; ++r)
        {
            const double gammaHat = estimatedSinrAt(timeS, r, r);
            estimatedPer.push_back(CalculatePerSigmoid(gammaHat, cfg.mcs, cfg.per));
        }
        return SelectMinIndex(estimatedPer);
    };

    auto oracleBestRuAt = [&](double timeS) {
        std::vector<double> per;
        per.reserve(cfg.numRus);
        for (uint32_t r = 0; r < cfg.numRus; ++r)
        {
            per.push_back(CalculatePerSigmoid(sinrAt(timeS, r, 0.0, r), cfg.mcs, cfg.per));
        }
        return SelectMinIndex(per);
    };

    std::vector<bool> txDuringJammerOnFlag(cfg.packets, false);
    std::vector<bool> rxFlag(cfg.packets, false);
    std::vector<double> rxTimeS(cfg.packets, 0.0);
    uint32_t txDuringJammerOn = 0;
    uint32_t rxDuringJammerOn = 0;
    uint32_t lostDuringJammerOn = 0;
    constexpr double kOutageThresholdDb = 5.0;
    uint32_t outageJammerOnEvents = 0;
    double worstCaseBurstLatencyS = 0.0;
    uint32_t maxConsecutiveDeadlineMisses = 0;
    uint32_t currentMissStreak = 0;
    uint32_t deadlineMissCooldownCount = 0;
    uint32_t deadlineMissQueueingCount = 0;
    uint32_t deadlineMissRetryCount = 0;
    uint32_t retryAttempts = 0;
    uint32_t retryAfterBurst = 0;
    uint32_t retrySameBurst = 0;
    uint32_t retryOnJammed = 0;
    uint32_t retargetAttempts = 0;
    uint32_t retargetSuccess = 0;
    uint64_t s9ProactiveDeferCount = 0;

    struct AggregateAttemptTelemetry
    {
        bool haveInitial{false};
        bool haveRetry{false};
        uint32_t ruInitial{0};
        uint32_t ruRetry{0};
        uint32_t estimatedBestRu{0};
        uint32_t oracleBestRu{0};
        bool initialJammed{false};
        bool retryJammed{false};
        double sinrInitialSum{0.0};
        double sinrRetrySum{0.0};
        double estSinrInitialSum{0.0};
        double estSinrRetrySum{0.0};
        double perInitialSum{0.0};
        double perRetrySum{0.0};
        double estPerInitialSum{0.0};
        double estPerRetrySum{0.0};
        uint32_t initialCount{0};
        uint32_t retryCount{0};
    } agg;

    // Per-attempt instrumentation (coherence-time experiment). Disabled unless
    // an output path is supplied, so legacy campaigns pay nothing.
    std::ofstream attemptLog;
    const bool writeAttemptLog = !cfg.attemptLogPath.empty();
    const double cooldownUs = cooldownS * 1e6;
    if (writeAttemptLog)
    {
        attemptLog.open(cfg.attemptLogPath);
        attemptLog << "run_id,seed,packet_id,attempt_id,user_id,ru_id,ru_initial,ru_retry,"
                      "ru_changed,timestamp_us,first_tx_timestamp_us,retry_timestamp_us,"
                      "cooldown_symbols,cooldown_us,coherence_time_ms,channel_correlation_model,"
                      "jammer_mode,jammer_state_first_tx,jammer_state_retry,same_jammer_burst,"
                      "retry_after_burst,mcs,payload_bits,distance_m,policy,sinr_db,sinr_first_db,"
                      "sinr_retry_db,channel_gain_db,channel_gain_first_db,channel_gain_retry_db,"
                      "per_attempt,per_first,per_retry,tx_success,retry_success,packet_success,"
                      "latency_us,deadline_us,deadline_miss\n";
    }
    struct AttemptRow
    {
        uint32_t attempt{0};
        double timeS{0.0};
        uint32_t ru{0};
        double sinrDb{0.0};
        double gainDb{0.0};
        double per{0.0};
        bool jammed{false};
        bool isRetry{false};
        bool sameBurst{false};
        bool afterBurst{false};
        bool attemptSuccess{false};
    };

    for (uint32_t seq = 0; seq < cfg.packets; ++seq)
    {
        const uint32_t userId = seq % cfg.users;
        const uint32_t initialRu = userId % cfg.numRus;
        uint32_t currentRu = initialRu;
        const double launchTimeS = seq * cfg.trafficIntervalS;
        std::vector<AttemptRow> attemptRows;
        bool jammerStateFirstTx = false;
        collector.RecordTx(seq, userId);
        const bool jammerOnAtTx = !activeJammedRus(launchTimeS, initialRu).empty();
        jammerStateFirstTx = jammerOnAtTx;
        txDuringJammerOnFlag[seq] = jammerOnAtTx;
        if (jammerOnAtTx)
        {
            ++txDuringJammerOn;
            if (sinrAt(launchTimeS, initialRu, 0.0, initialRu) < kOutageThresholdDb)
            {
                ++outageJammerOnEvents;
            }
        }

        double currentTimeS = launchTimeS;
        bool success = false;
        bool cooldownUsed = false;
        uint32_t failedAttempts = 0;
        double finalDelayS = 0.0;

        if (policy == "full_cdr_s9" && cfg.s9ProactiveDefer.enabled)
        {
            const double gammaHat = estimatedSinrAt(currentTimeS, currentRu, currentRu);
            const bool jammerHat = estimatedJammerAt(currentTimeS, currentRu, currentRu);
            const double perHat = CalculatePerSigmoid(gammaHat, cfg.mcs, cfg.per);
            const bool critSnir =
                !cfg.s9Ablation.disableSnirMargin && gammaHat < cfg.s9Estimator.gammaOutDb;
            const bool critPer =
                !cfg.s9Ablation.disablePerMargin && perHat > cfg.s9Estimator.perCrit;
            const bool critJam = !cfg.s9Ablation.disableJammerFlag && jammerHat;
            if (critSnir || critPer || critJam)
            {
                ++s9ProactiveDeferCount;
                if (!cfg.s9Ablation.disableCooldown)
                {
                    currentTimeS += cooldownS;
                    cooldownUsed = true;
                }
                currentRu = estimatedBestRuAt(currentTimeS);
            }
        }

        for (uint32_t attempt = 0; attempt <= cfg.retryLimit; ++attempt)
        {
            const bool isRetry = attempt > 0;
            const double attemptTimeS = currentTimeS;
            double extraGainDb = 0.0;
            if (policy == "rtx_assist" && isRetry)
            {
                extraGainDb = cfg.s8RtxSnirGainDb;
            }
            const double snirDb = sinrAt(currentTimeS, currentRu, extraGainDb, currentRu);
            const double per = CalculatePerSigmoid(snirDb, cfg.mcs, cfg.per);
            const double gammaHat = estimatedSinrAt(currentTimeS, currentRu, currentRu);
            const double perHat = CalculatePerSigmoid(gammaHat, cfg.mcs, cfg.per);
            const bool ruJammed = ruJammedAt(currentTimeS, currentRu, currentRu);
            const uint32_t bestHat = estimatedBestRuAt(currentTimeS);
            const uint32_t bestOracle = oracleBestRuAt(currentTimeS);
            // Per-attempt channel gain (cached realisation at this instant).
            const double attemptGainDb = ruFadingAt(currentTimeS)[currentRu];
            const bool attemptFirstBurst = TimeInReactiveBurst(
                launchTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS, cfg.reactiveBurstS);
            const bool attemptThisBurst = TimeInReactiveBurst(
                attemptTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS, cfg.reactiveBurstS);
            const bool attemptSameBurst =
                isRetry && attemptFirstBurst && attemptThisBurst &&
                BurstIndexAt(launchTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS) ==
                    BurstIndexAt(attemptTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS);
            const bool attemptAfterBurst =
                isRetry && attemptFirstBurst && !attemptThisBurst;

            if (!isRetry)
            {
                agg.haveInitial = true;
                agg.ruInitial = currentRu;
                agg.initialJammed = ruJammed;
                agg.estimatedBestRu = bestHat;
                agg.oracleBestRu = bestOracle;
                agg.sinrInitialSum += snirDb;
                agg.estSinrInitialSum += gammaHat;
                agg.perInitialSum += per;
                agg.estPerInitialSum += perHat;
                ++agg.initialCount;
            }
            else
            {
                ++retryAttempts;
                agg.haveRetry = true;
                agg.ruRetry = currentRu;
                agg.retryJammed = ruJammed;
                agg.estimatedBestRu = bestHat;
                agg.oracleBestRu = bestOracle;
                agg.sinrRetrySum += snirDb;
                agg.estSinrRetrySum += gammaHat;
                agg.perRetrySum += per;
                agg.estPerRetrySum += perHat;
                ++agg.retryCount;
                if (ruJammed)
                {
                    ++retryOnJammed;
                }
                const bool firstBurst =
                    TimeInReactiveBurst(launchTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS, cfg.reactiveBurstS);
                const bool retryBurst =
                    TimeInReactiveBurst(currentTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS, cfg.reactiveBurstS);
                if (firstBurst && !retryBurst)
                {
                    ++retryAfterBurst;
                }
                if (firstBurst && retryBurst &&
                    BurstIndexAt(launchTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS) ==
                        BurstIndexAt(currentTimeS, cfg.jammerPhaseS, cfg.reactiveIntervalS))
                {
                    ++retrySameBurst;
                }
                if (currentRu != initialRu)
                {
                    ++retargetAttempts;
                }
            }

            currentTimeS += txTimeS + propDelayS;
            const bool attemptSuccess = uniform(rng) >= per;
            if (writeAttemptLog)
            {
                AttemptRow row;
                row.attempt = attempt;
                row.timeS = attemptTimeS;
                row.ru = currentRu;
                row.sinrDb = snirDb;
                row.gainDb = attemptGainDb;
                row.per = per;
                row.jammed = ruJammed;
                row.isRetry = isRetry;
                row.sameBurst = attemptSameBurst;
                row.afterBurst = attemptAfterBurst;
                row.attemptSuccess = attemptSuccess;
                attemptRows.push_back(row);
            }
            if (attemptSuccess)
            {
                success = true;
                finalDelayS = currentTimeS - launchTimeS;
                if (isRetry && currentRu != initialRu && !ruJammed)
                {
                    ++retargetSuccess;
                }
                break;
            }

            ++failedAttempts;
            if (attempt == cfg.retryLimit)
            {
                break;
            }

            double retryDelayS = slotS * static_cast<double>(1u << std::min<uint32_t>(attempt, 6u));
            uint32_t nextRu = currentRu;
            if (policy == "cooldown_only")
            {
                retryDelayS = cooldownS;
                cooldownUsed = true;
            }
            else if (policy == "ru_retarget_only")
            {
                retryDelayS = slotS;
                nextRu = estimatedBestRuAt(currentTimeS);
            }
            else if (policy == "cooldown_plus_retarget" || policy == "full_cdr_s9")
            {
                retryDelayS = cfg.s9Ablation.disableCooldown ? slotS : cooldownS;
                cooldownUsed = retryDelayS >= cooldownS && cooldownS > 0.0;
                nextRu = estimatedBestRuAt(currentTimeS + retryDelayS);
            }
            else if (policy == "random_ru_hop")
            {
                retryDelayS = slotS;
                std::uniform_int_distribution<uint32_t> ruPick(0, cfg.numRus - 1);
                nextRu = ruPick(rng);
            }
            else if (policy == "oracle_best_ru")
            {
                retryDelayS = slotS;
                nextRu = oracleBestRuAt(currentTimeS + retryDelayS);
            }
            else if (policy == "rtx_assist" || policy == "baseline_pf")
            {
                retryDelayS = slotS * static_cast<double>(1u << std::min<uint32_t>(attempt, 6u));
            }
            else
            {
                throw std::runtime_error("unsupported OFDMA policy: " + policy);
            }
            currentTimeS += retryDelayS;
            currentRu = nextRu;
        }

        if (success)
        {
            collector.RecordRx(seq, finalDelayS, userId);
            rxFlag[seq] = true;
            rxTimeS[seq] = launchTimeS + finalDelayS;
            if (jammerOnAtTx)
            {
                ++rxDuringJammerOn;
                if (finalDelayS > worstCaseBurstLatencyS)
                {
                    worstCaseBurstLatencyS = finalDelayS;
                }
            }
        }
        else if (jammerOnAtTx)
        {
            ++lostDuringJammerOn;
        }

        const bool late = success && finalDelayS > cfg.deadlineS;
        const bool missed = !success || late;
        if (!success)
        {
            // Loss is tracked as its own deadline-miss cause for safety analysis.
        }
        else if (late && cooldownUsed)
        {
            ++deadlineMissCooldownCount;
        }
        else if (late && failedAttempts > 0)
        {
            ++deadlineMissRetryCount;
        }
        else if (late)
        {
            ++deadlineMissQueueingCount;
        }
        if (missed)
        {
            ++currentMissStreak;
            if (currentMissStreak > maxConsecutiveDeadlineMisses)
            {
                maxConsecutiveDeadlineMisses = currentMissStreak;
            }
        }
        else
        {
            currentMissStreak = 0;
        }

        if (writeAttemptLog && !attemptRows.empty())
        {
            const double firstSinr = attemptRows.front().sinrDb;
            const double firstGain = attemptRows.front().gainDb;
            const double firstPer = attemptRows.front().per;
            bool ruChangedAny = false;
            for (const auto& r : attemptRows)
            {
                if (r.ru != initialRu)
                {
                    ruChangedAny = true;
                }
            }
            const std::string na = "NA";
            auto d2s = [](double v) {
                std::ostringstream o;
                o.precision(10);
                o << v;
                return o.str();
            };
            for (const auto& r : attemptRows)
            {
                attemptLog << cfg.runId << ',' << cfg.seed << ',' << seq << ',' << r.attempt << ','
                           << userId << ',' << r.ru << ',' << initialRu << ','
                           << (r.isRetry ? std::to_string(r.ru) : na) << ','
                           << (ruChangedAny ? 1 : 0) << ',' << d2s(r.timeS * 1e6) << ','
                           << d2s(launchTimeS * 1e6) << ','
                           << (r.isRetry ? d2s(r.timeS * 1e6) : na) << ',' << cfg.s9CooldownSymbols
                           << ',' << d2s(cooldownUs) << ',' << d2s(cfg.cm8.coherenceTimeMs) << ','
                           << cfg.cm8.correlationModel << ',' << jammerRuMode << ','
                           << (jammerStateFirstTx ? 1 : 0) << ','
                           << (r.isRetry ? std::to_string(r.jammed ? 1 : 0) : na) << ','
                           << (r.sameBurst ? 1 : 0) << ',' << (r.afterBurst ? 1 : 0) << ','
                           << cfg.mcs << ',' << cfg.payloadBits << ',' << d2s(cfg.distanceM) << ','
                           << policy << ',' << d2s(r.sinrDb) << ',' << d2s(firstSinr) << ','
                           << (r.isRetry ? d2s(r.sinrDb) : na) << ',' << d2s(r.gainDb) << ','
                           << d2s(firstGain) << ',' << (r.isRetry ? d2s(r.gainDb) : na) << ','
                           << d2s(r.per) << ',' << d2s(firstPer) << ','
                           << (r.isRetry ? d2s(r.per) : na) << ',' << (r.attemptSuccess ? 1 : 0)
                           << ',' << (r.isRetry ? std::to_string(r.attemptSuccess ? 1 : 0) : na)
                           << ',' << (success ? 1 : 0) << ','
                           << (success ? d2s(finalDelayS * 1e6) : na) << ','
                           << d2s(cfg.deadlineS * 1e6) << ',' << (missed ? 1 : 0) << '\n';
            }
        }
    }
    if (writeAttemptLog)
    {
        attemptLog.close();
    }

    AntiJammingTelemetry telemetry;
    telemetry.populated = true;
    telemetry.txDuringJammerOn = txDuringJammerOn;
    telemetry.rxAmongTxDuringJammerOn = rxDuringJammerOn;
    telemetry.lostDuringJammerOn = lostDuringJammerOn;
    if (JammerModeIsConstant(jammerRuMode))
    {
        const uint32_t jammedCount =
            static_cast<uint32_t>(activeJammedRus(0.0, 0).size());
        telemetry.jammerDutyCycle =
            cfg.numRus > 0 ? static_cast<double>(jammedCount) / static_cast<double>(cfg.numRus) : 0.0;
    }
    else if (JammerModeIsReactive(jammerRuMode) && cfg.reactiveIntervalS > 0.0)
    {
        telemetry.jammerDutyCycle = std::min(1.0, cfg.reactiveBurstS / cfg.reactiveIntervalS);
    }
    else
    {
        telemetry.jammerDutyCycle = 0.0;
    }

    if (JammerModeIsReactive(jammerRuMode) && cfg.reactiveIntervalS > 0.0 && cfg.packets > 0)
    {
        const double horizonS = (cfg.packets - 1) * cfg.trafficIntervalS + txTimeS + propDelayS;
        std::vector<double> recoverySamples;
        for (uint32_t k = 0;; ++k)
        {
            const double burstEnd = cfg.jammerPhaseS + k * cfg.reactiveIntervalS + cfg.reactiveBurstS;
            if (burstEnd > horizonS)
            {
                break;
            }
            const uint32_t firstSeq =
                static_cast<uint32_t>(std::ceil(std::max(0.0, burstEnd) / cfg.trafficIntervalS));
            for (uint32_t s = firstSeq; s < cfg.packets; ++s)
            {
                if (rxFlag[s])
                {
                    recoverySamples.push_back(rxTimeS[s] - burstEnd);
                    break;
                }
            }
        }
        if (!recoverySamples.empty())
        {
            double sum = 0.0;
            for (double v : recoverySamples)
            {
                sum += v;
            }
            telemetry.meanRecoveryTimeS = sum / static_cast<double>(recoverySamples.size());
            telemetry.recoverySampleCount = static_cast<uint32_t>(recoverySamples.size());
            double sqSum = 0.0;
            for (double v : recoverySamples)
            {
                const double d = v - telemetry.meanRecoveryTimeS;
                sqSum += d * d;
            }
            telemetry.stdRecoveryTimeS =
                std::sqrt(sqSum / static_cast<double>(recoverySamples.size()));
            std::sort(recoverySamples.begin(), recoverySamples.end());
            const std::size_t idx = static_cast<std::size_t>(
                std::min(recoverySamples.size() - 1,
                         static_cast<std::size_t>(std::round(0.95 * (recoverySamples.size() - 1)))));
            telemetry.p95RecoveryTimeS = recoverySamples[idx];
        }
    }

    telemetry.outageThresholdDb = kOutageThresholdDb;
    telemetry.outageProbabilityJammerOn =
        txDuringJammerOn > 0
            ? static_cast<double>(outageJammerOnEvents) / static_cast<double>(txDuringJammerOn)
            : 0.0;
    telemetry.worstCaseBurstLatencyS = worstCaseBurstLatencyS;
    telemetry.maxConsecutiveDeadlineMisses = maxConsecutiveDeadlineMisses;
    if (cfg.packets > 0 && cfg.trafficIntervalS > 0.0)
    {
        const double windowS = cfg.packets * cfg.trafficIntervalS;
        uint32_t rxCount = 0;
        for (bool rx : rxFlag)
        {
            if (rx)
            {
                ++rxCount;
            }
        }
        telemetry.effectiveThroughputPps = rxCount / windowS;
    }

    OfdmaRunTelemetry ofdma;
    ofdma.populated = true;
    ofdma.numRus = cfg.numRus;
    ofdma.ruWidthTones = cfg.ruWidthTones;
    ofdma.perRuChannelEnabled = true;
    ofdma.ruCorrelationRho = cfg.ruCorrelationRho;
    ofdma.policy = policy;
    ofdma.jammerRuMode = jammerRuMode;
    ofdma.jammedRuCount = static_cast<uint32_t>(activeJammedRus(0.0, 0).size());
    ofdma.fractionRusJammed =
        cfg.numRus > 0 ? static_cast<double>(ofdma.jammedRuCount) / static_cast<double>(cfg.numRus) : 0.0;
    ofdma.cooldownSymbols = cfg.s9CooldownSymbols;
    ofdma.cooldownMs = cooldownMs;
    ofdma.deadlineMs = cfg.deadlineS * 1000.0;
    ofdma.ruIdInitial = agg.ruInitial;
    ofdma.ruIdRetry = agg.haveRetry ? agg.ruRetry : agg.ruInitial;
    ofdma.ruChanged = agg.haveRetry && agg.ruRetry != agg.ruInitial;
    const uint32_t ruDiff = ofdma.ruIdRetry > ofdma.ruIdInitial
                                ? ofdma.ruIdRetry - ofdma.ruIdInitial
                                : ofdma.ruIdInitial - ofdma.ruIdRetry;
    ofdma.ruDistanceTones = ruDiff * cfg.ruWidthTones;
    ofdma.ruWasJammedInitial = agg.initialJammed;
    ofdma.ruWasJammedRetry = agg.retryJammed;
    ofdma.sinrInitialDb =
        agg.initialCount > 0 ? agg.sinrInitialSum / static_cast<double>(agg.initialCount) : 0.0;
    ofdma.sinrRetryDb =
        agg.retryCount > 0 ? agg.sinrRetrySum / static_cast<double>(agg.retryCount)
                           : std::numeric_limits<double>::quiet_NaN();
    ofdma.estimatedSinrInitialDb =
        agg.initialCount > 0 ? agg.estSinrInitialSum / static_cast<double>(agg.initialCount) : 0.0;
    ofdma.estimatedSinrRetryDb =
        agg.retryCount > 0 ? agg.estSinrRetrySum / static_cast<double>(agg.retryCount)
                           : std::numeric_limits<double>::quiet_NaN();
    ofdma.perInitial =
        agg.initialCount > 0 ? agg.perInitialSum / static_cast<double>(agg.initialCount) : 0.0;
    ofdma.perRetry =
        agg.retryCount > 0 ? agg.perRetrySum / static_cast<double>(agg.retryCount)
                           : std::numeric_limits<double>::quiet_NaN();
    ofdma.estimatedPerInitial =
        agg.initialCount > 0 ? agg.estPerInitialSum / static_cast<double>(agg.initialCount) : 0.0;
    ofdma.estimatedPerRetry =
        agg.retryCount > 0 ? agg.estPerRetrySum / static_cast<double>(agg.retryCount)
                           : std::numeric_limits<double>::quiet_NaN();
    ofdma.estimatedBestRu = agg.estimatedBestRu;
    ofdma.oracleBestRu = agg.oracleBestRu;
    ofdma.ruRetargetSuccess =
        retargetAttempts > 0 ? static_cast<double>(retargetSuccess) / static_cast<double>(retargetAttempts)
                             : std::numeric_limits<double>::quiet_NaN();
    ofdma.retryLandedAfterBurst =
        retryAttempts > 0 ? static_cast<double>(retryAfterBurst) / static_cast<double>(retryAttempts)
                          : std::numeric_limits<double>::quiet_NaN();
    ofdma.retryLandedSameBurst =
        retryAttempts > 0 ? static_cast<double>(retrySameBurst) / static_cast<double>(retryAttempts)
                          : std::numeric_limits<double>::quiet_NaN();
    ofdma.retryLandedOnJammedRu =
        retryAttempts > 0 ? static_cast<double>(retryOnJammed) / static_cast<double>(retryAttempts)
                          : std::numeric_limits<double>::quiet_NaN();
    ofdma.deadlineMissDueToCooldown =
        cfg.packets > 0 ? static_cast<double>(deadlineMissCooldownCount) / static_cast<double>(cfg.packets) : 0.0;
    ofdma.deadlineMissDueToLoss =
        cfg.packets > 0 ? static_cast<double>(cfg.packets - std::count(rxFlag.begin(), rxFlag.end(), true)) /
                              static_cast<double>(cfg.packets)
                        : 0.0;
    ofdma.deadlineMissDueToQueueing =
        cfg.packets > 0 ? static_cast<double>(deadlineMissQueueingCount) / static_cast<double>(cfg.packets) : 0.0;
    ofdma.deadlineMissDueToRepeatedRetry =
        cfg.packets > 0 ? static_cast<double>(deadlineMissRetryCount) / static_cast<double>(cfg.packets) : 0.0;

    budget.telemetry = telemetry;
    budget.ofdmaTelemetry = ofdma;
    budget.s9ProactiveDeferCount = s9ProactiveDeferCount;
    return budget;
}

} // namespace

CoreHarnessLinkBudget
RunCoreHarness(const CoreHarnessConfig& cfg, MetricsCollector& collector)
{
    if (cfg.users < 1)
    {
        throw std::runtime_error("core-harness: users must be >= 1");
    }
    // Validity range from the channel-model literature (loaded into
    // `cfg.cm8.maxDistanceM` by the corresponding YAML preset):
    //   cm8_rayleigh  -> 1-10 m [Mol09] (lighter proxy YAML may shrink this).
    //   inf_nlos_dl   -> 1-600 m [3GPP38901] (paper subset stops earlier).
    if ((cfg.channelModel == "cm8_rayleigh" || cfg.channelModel == "inf_nlos_dl") &&
        cfg.distanceM > cfg.cm8.maxDistanceM)
    {
        throw std::runtime_error(
            "core-harness: configured distance " + std::to_string(cfg.distanceM) +
            " m exceeds max_distance_m=" + std::to_string(cfg.cm8.maxDistanceM) +
            " m declared for channel '" + cfg.channelModel + "'");
    }
    if (cfg.perRuChannelEnabled)
    {
        return RunCoreHarnessPerRu(cfg, collector);
    }

    std::mt19937 rng(cfg.seed);
    std::uniform_real_distribution<double> uniform(0.0, 1.0);
    std::exponential_distribution<double> rayleighPower(1.0);

    CoreHarnessLinkBudget budget;
    double pathLossDb = 0.0;
    // Active small-scale fading model for this run. CM8 keeps the parametric
    // log-normal shadowing + Rayleigh from cfg.cm8; QuaDRiGa uses the
    // trace-derived per-distance fading std (Gaussian only, no extra Rayleigh)
    // when the trace provides it.
    double effectiveShadowStdDb = cfg.cm8.shadowingStdDb;
    bool useRayleigh = cfg.cm8.rayleighFading;
    QuadrigaTrace trace;
    if (cfg.channelModel == "cm8_rayleigh" || cfg.channelModel == "inf_nlos_dl")
    {
        // Same log-distance + log-normal SF engine, different parameter set
        // loaded via `cfg.cm8`. inf_nlos_dl is [3GPP38901] InF-DL NLOS.
        pathLossDb = CalculateCm8PathLossDb(cfg.distanceM, cfg.cm8);
        if (cfg.channelModel == "inf_nlos_dl")
        {
            budget.channelAbstraction =
                "stochastic_3gpp_inf_nlos_dl_log_distance_with_shadowing";
            budget.fadingVarianceSource = useRayleigh ? "cm8_proxy" : "log_normal_only";
        }
        else
        {
            budget.channelAbstraction = "controlled_rayleigh_path_loss_with_shadowing";
            budget.fadingVarianceSource = useRayleigh ? "cm8_proxy" : "none";
        }
    }
    else if (cfg.channelModel == "quadriga_raytraced")
    {
        trace.Load(cfg.tracePath);
        pathLossDb = trace.GetPathLossDb(cfg.distanceM);
        budget.tracePath = cfg.tracePath;
        budget.nominalDelayS = trace.GetEffectiveDelayS(cfg.distanceM);
        const double traceFadingStd = trace.GetFadingStdDb(cfg.distanceM);
        if (traceFadingStd > 0.0)
        {
            // Honour an explicit user override on cm8.shadowingStdDb if larger
            // than the trace-derived value (rare; lets a user widen the
            // distribution for sensitivity analysis without dropping the trace).
            effectiveShadowStdDb = std::max(cfg.cm8.shadowingStdDb, traceFadingStd);
            useRayleigh = false;
            budget.channelAbstraction =
                "external_geometry_trace_scalar_path_loss_replay_with_trace_fading_std";
            budget.fadingVarianceSource = "trace_column";
        }
        else
        {
            useRayleigh = cfg.cm8.rayleighFading;
            budget.channelAbstraction = "external_geometry_trace_scalar_path_loss_replay";
            // No trace-derived fading variance: either the run is purely
            // deterministic (path-loss only) or the operator forced CM8 proxy
            // fading on the trace. Surface this honestly so reviewers can spot
            // when the QuaDRiGa run inherits CM8 stochastic behaviour.
            budget.fadingVarianceSource =
                (useRayleigh || effectiveShadowStdDb > 0.0) ? "cm8_proxy" : "none";
        }
    }
    else
    {
        throw std::runtime_error("core-harness: unsupported channel model " + cfg.channelModel);
    }
    // std::normal_distribution constructed with sigma == 0 is undefined per
    // the standard (libstdc++ happens to return the mean reliably, but we do
    // not rely on it). Build the distribution lazily: callers that disabled
    // shadowing skip the draw entirely, so the run becomes deterministic on
    // that dimension without any UB.
    std::optional<std::normal_distribution<double>> shadowDist;
    if (effectiveShadowStdDb > 0.0)
    {
        shadowDist.emplace(0.0, effectiveShadowStdDb);
    }

    const double noiseFloorDbm = CalculateNoiseFloorDbm(cfg.bandwidthMHz * 1e6, cfg.noiseFigureDb);
    const double noiseMw = DbmToMw(noiseFloorDbm);

    double jammerPathLossDb = 0.0;
    double jammerRxDbm = -300.0;
    double jammerMw = 0.0;
    if (cfg.jammerMode != "none")
    {
        if (cfg.channelModel == "cm8_rayleigh" || cfg.channelModel == "inf_nlos_dl")
        {
            jammerPathLossDb = CalculateCm8PathLossDb(cfg.jammerDistanceM, cfg.cm8);
        }
        else
        {
            jammerPathLossDb = trace.GetPathLossDb(cfg.jammerDistanceM);
        }
        jammerRxDbm = cfg.jammerPowerDbm - jammerPathLossDb;
        jammerMw = DbmToMw(jammerRxDbm);
    }

    budget.nominalPathLossDb = pathLossDb;
    budget.signalPowerDbm = cfg.txPowerDbm - pathLossDb;
    budget.noiseFloorDbm = noiseFloorDbm;
    budget.jammerPowerAtReceiverDbm = jammerRxDbm;
    if (budget.nominalDelayS == 0.0)
    {
        budget.nominalDelayS = cfg.distanceM / 299792458.0;
    }

    const double dataRateBps = HeDataRateMbps(cfg.mcs) * 1e6;
    // PHY preamble: HE-SU PPDU ~ 44 us (L-STF/L-LTF/L-SIG/RL-SIG/HE-SIG-A/HE-STF/HE-LTF).
    constexpr double preambleS = 44e-6;
    // MAC + IP + UDP + SeqTsSize ~ 8 + 20 + 8 + 16 = 52 bytes ~ 416 bits.
    constexpr double headerBits = 416.0;
    const double txTimeS = preambleS + (cfg.payloadBits + headerBits) / dataRateBps;
    const double propDelayS = budget.nominalDelayS;
    const double slotS = 9e-6;
    const double cooldownS = cfg.s9CooldownSymbols * cfg.ofdmSymbolUs * 1e-6;

    // Coherence-time cache: redraw shadowing + Rayleigh only after the coherence
    // window has elapsed since the previous draw. This makes retries within the
    // same coherence interval correlated (realistic worst case for S4) while
    // S8/S9 retries which add cooldown can escape into a fresh fade.
    double lastFadingTimeS = -1.0e9;
    double cachedFadingDb = 0.0;
    auto fadingAt = [&](double timeS) {
        if (timeS - lastFadingTimeS >= cfg.cm8.coherenceTimeMs * 1e-3)
        {
            double fadingDb = 0.0;
            if (shadowDist)
            {
                fadingDb += (*shadowDist)(rng);
            }
            if (useRayleigh)
            {
                const double powerGain = std::max(rayleighPower(rng), 1e-12);
                fadingDb += 10.0 * std::log10(powerGain);
            }
            cachedFadingDb = fadingDb;
            lastFadingTimeS = timeS;
        }
        return cachedFadingDb;
    };

    auto interferenceMw = [&](double timeS) {
        if (cfg.jammerMode == "constant")
        {
            return noiseMw + jammerMw;
        }
        if (cfg.jammerMode == "reactive" && cfg.reactiveIntervalS > 0.0)
        {
            const double phase = std::fmod(timeS, cfg.reactiveIntervalS);
            if (phase < cfg.reactiveBurstS)
            {
                return noiseMw + jammerMw;
            }
        }
        return noiseMw;
    };

    auto snirAt = [&](double timeS, double extraGainDb) {
        const double fadingDb = fadingAt(timeS);
        const double sigDbm = cfg.txPowerDbm - pathLossDb + fadingDb + extraGainDb;
        const double iPlusNDbm = MwToDbm(interferenceMw(timeS));
        return sigDbm - iPlusNDbm;
    };

    // Jammer-state predicate at a given moment. Reused for the conditional PDR
    // and recovery-time telemetry.
    auto jammerActiveAt = [&](double timeS) -> bool {
        if (cfg.jammerMode == "constant")
        {
            return true;
        }
        if (cfg.jammerMode == "reactive" && cfg.reactiveIntervalS > 0.0)
        {
            const double phase = std::fmod(timeS, cfg.reactiveIntervalS);
            return phase < cfg.reactiveBurstS;
        }
        return false;
    };

    // Per-packet bookkeeping for conditional PDR, recovery time, outage
    // probability, worst-case burst latency, and deadline-streak telemetry.
    std::vector<bool> txDuringJammerOnFlag(cfg.packets, false);
    std::vector<bool> rxFlag(cfg.packets, false);
    std::vector<double> rxTimeS(cfg.packets, 0.0);
    uint32_t txDuringJammerOn = 0;
    uint32_t rxDuringJammerOn = 0;
    uint32_t lostDuringJammerOn = 0;
    // Outage = SINR at first transmission attempt below the configured
    // operating-point threshold (5 dB by default; cf. the BPSK saturation
    // throughput analysis in [Bay08]/[Bay13] and the anti-jamming metrics
    // survey [Pel11]). Tracked only for jammer-ON transmissions.
    constexpr double kOutageThresholdDb = 5.0;
    uint32_t outageJammerOnEvents = 0;
    double worstCaseBurstLatencyS = 0.0;
    uint32_t maxConsecutiveDeadlineMisses = 0;
    uint32_t currentMissStreak = 0;

    // S9 proactive critical-mask defer ([Fan26] Algorithm 1). Opt-in via
    // `cfg.s9ProactiveDefer.enabled`. The default-disabled path keeps the
    // historical archive bit-reproducible.
    //
    // Per-user observation cache: each entry stores the SNIR and jammer-active
    // state seen at the previous packet for that user, plus a cooldown
    // timestamp. With our 10 ms scheduling step and sub-millisecond CM8
    // coherence, "1 slot of staleness" (paper §4.5) is captured as
    // "previous-packet observation"; that is qualitatively beyond coherence
    // and matches the moderate/conservative profiles' intent. The exact
    // requested staleness is preserved in the CSV for reproducibility.
    struct UserApState
    {
        double lastSnirDb{0.0};
        bool lastJammerActive{false};
        bool hasHistory{false};
        double cooldownExpiresAtS{0.0};
    };
    std::vector<UserApState> userState(cfg.users);
    const bool s9ProactiveDefer = (cfg.scenario == "S9") && cfg.s9ProactiveDefer.enabled;
    uint64_t s9ProactiveDeferCount = 0;

    for (uint32_t seq = 0; seq < cfg.packets; ++seq)
    {
        const uint32_t userId = seq % cfg.users;
        const double launchTimeS = seq * cfg.trafficIntervalS;
        collector.RecordTx(seq, userId);
        const bool jammerOnAtTx = jammerActiveAt(launchTimeS);
        txDuringJammerOnFlag[seq] = jammerOnAtTx;
        if (jammerOnAtTx)
        {
            ++txDuringJammerOn;
            // First-attempt SINR (no policy gain yet) drives the outage flag.
            // Use snirAt with zero extra gain to mirror a reviewer's
            // outage-probability convention.
            if (snirAt(launchTimeS, 0.0) < kOutageThresholdDb)
            {
                ++outageJammerOnEvents;
            }
        }

        double currentTimeS = launchTimeS;
        bool success = false;
        double finalDelayS = 0.0;

        // Algorithm 1 critical-mask defer (S9 only, opt-in). Evaluated BEFORE
        // attempt 0 so that S9 protects packets *before* they enter a poor
        // opportunity. The defer cost is one cooldown period inserted into
        // `currentTimeS`, mirroring the paper's "reassign u to a better r*"
        // operation in a single-link harness where the "better RU" collapses
        // to "the same RU later, after the channel has decorrelated".
        if (s9ProactiveDefer)
        {
            auto& us = userState[userId];
            if (currentTimeS >= us.cooldownExpiresAtS)
            {
                // True channel observation feeding the estimator. The bias and
                // Gaussian noise are added inside ComputeS9Estimate(); the
                // staleness path is handled here by falling back to the
                // previous packet's observation when the operator requests
                // any non-zero `snirStalenessSlots`.
                const double currentTrueSnirDb = snirAt(currentTimeS, 0.0);
                const bool currentTrueJammer = jammerActiveAt(currentTimeS);
                const bool useStale =
                    cfg.s9Estimator.snirStalenessSlots > 0 && us.hasHistory;
                const double obsSnirDb = useStale ? us.lastSnirDb : currentTrueSnirDb;
                const bool obsJammer = useStale ? us.lastJammerActive : currentTrueJammer;
                const auto est = ComputeS9Estimate(obsSnirDb, obsJammer, cfg.s9Estimator, rng);
                const double perHat = CalculatePerSigmoid(est.gammaHatDb, cfg.mcs, cfg.per);
                const bool critSnir = !cfg.s9Ablation.disableSnirMargin &&
                                      est.gammaHatDb < cfg.s9Estimator.gammaOutDb;
                const bool critPer = !cfg.s9Ablation.disablePerMargin &&
                                     perHat > cfg.s9Estimator.perCrit;
                const bool critJam =
                    !cfg.s9Ablation.disableJammerFlag && est.jammerFlagHat;
                if (critSnir || critPer || critJam)
                {
                    ++s9ProactiveDeferCount;
                    if (!cfg.s9Ablation.disableCooldown)
                    {
                        currentTimeS += cooldownS;
                        us.cooldownExpiresAtS = currentTimeS + cooldownS;
                    }
                }
                // Always refresh the per-user observation cache (the AP has
                // an HE-LTF / ACK / CCA sample at every scheduling step).
                us.lastSnirDb = currentTrueSnirDb;
                us.lastJammerActive = currentTrueJammer;
                us.hasHistory = true;
            }
        }

        for (uint32_t attempt = 0; attempt <= cfg.retryLimit; ++attempt)
        {
            double extraGainDb = 0.0;
            // S8 (PLS-RTX): each retransmission is opportunistic, picking a
            // moment where the AP estimates a stronger channel state; modelled
            // as a fixed effective-SINR gain on the retry attempt. Information-
            // theoretic background: secure HARQ throughput over block-fading
            // wiretap channels [Tan09] (preprint arXiv:0712.4135) and the
            // outage secrecy framework of [Blo08]/[Blo11]. See PolicyLabel()
            // and BIBLIOGRAPHY.md for the full citation chain.
            if (cfg.scenario == "S8" && attempt > 0)
            {
                extraGainDb = cfg.s8RtxSnirGainDb;
            }
            const double snirDb = snirAt(currentTimeS, extraGainDb);
            const double per = CalculatePerSigmoid(snirDb, cfg.mcs, cfg.per);
            currentTimeS += txTimeS + propDelayS;

            if (uniform(rng) >= per)
            {
                success = true;
                finalDelayS = currentTimeS - launchTimeS;
                break;
            }
            // Retransmission spacing. S9 (PLS-Realloc) inserts the configured
            // cooldown so the next attempt usually falls in a new coherence
            // window; S4/S8 follow plain binary-exponential-style backoff in
            // slot units. The `s9AblationDisableCooldown` switch (Tab. 11 of
            // [Fan26]) collapses S9 to plain backoff for ablation rows.
            if (cfg.scenario == "S9" && !cfg.s9Ablation.disableCooldown)
            {
                currentTimeS += cooldownS;
            }
            else
            {
                const uint32_t shift = std::min<uint32_t>(attempt, 6u);
                currentTimeS += slotS * static_cast<double>(1u << shift);
            }
        }

        if (success)
        {
            collector.RecordRx(seq, finalDelayS, userId);
            rxFlag[seq] = true;
            rxTimeS[seq] = launchTimeS + finalDelayS;
            if (jammerOnAtTx)
            {
                ++rxDuringJammerOn;
                if (finalDelayS > worstCaseBurstLatencyS)
                {
                    worstCaseBurstLatencyS = finalDelayS;
                }
            }
        }
        else if (jammerOnAtTx)
        {
            ++lostDuringJammerOn;
        }
        // Deadline-miss streak: a packet is "missed" when it was lost OR
        // delivered past the configured deadline. The longest run is exposed
        // to the safety/availability discussion.
        const bool missed = !success || finalDelayS > cfg.deadlineS;
        if (missed)
        {
            ++currentMissStreak;
            if (currentMissStreak > maxConsecutiveDeadlineMisses)
            {
                maxConsecutiveDeadlineMisses = currentMissStreak;
            }
        }
        else
        {
            currentMissStreak = 0;
        }
    }

    // Anti-jamming telemetry: duty cycle, conditional counts, mean recovery
    // time after each reactive burst end. For a constant jammer the duty
    // cycle is 1 and there are no burst boundaries, so recovery is NaN.
    AntiJammingTelemetry telemetry;
    telemetry.populated = true;
    telemetry.txDuringJammerOn = txDuringJammerOn;
    telemetry.rxAmongTxDuringJammerOn = rxDuringJammerOn;
    telemetry.lostDuringJammerOn = lostDuringJammerOn;
    if (cfg.jammerMode == "constant")
    {
        telemetry.jammerDutyCycle = 1.0;
    }
    else if (cfg.jammerMode == "reactive" && cfg.reactiveIntervalS > 0.0)
    {
        telemetry.jammerDutyCycle = std::min(1.0, cfg.reactiveBurstS / cfg.reactiveIntervalS);
    }
    else
    {
        telemetry.jammerDutyCycle = 0.0;
    }

    if (cfg.jammerMode == "reactive" && cfg.reactiveIntervalS > 0.0 && cfg.packets > 0)
    {
        const double horizonS = (cfg.packets - 1) * cfg.trafficIntervalS + txTimeS + propDelayS;
        std::vector<double> recoverySamples;
        // Burst k ends at: k * reactiveInterval + reactiveBurstS.
        for (uint32_t k = 0;; ++k)
        {
            const double burstEnd = k * cfg.reactiveIntervalS + cfg.reactiveBurstS;
            if (burstEnd > horizonS)
            {
                break;
            }
            // Find the smallest seq with rxFlag and rxTime >= burstEnd.
            // Packets are sequential in time, so we scan forward from the
            // tx index whose launchTime first exceeds burstEnd.
            uint32_t firstSeq = static_cast<uint32_t>(
                std::ceil(burstEnd / cfg.trafficIntervalS));
            for (uint32_t s = firstSeq; s < cfg.packets; ++s)
            {
                if (rxFlag[s])
                {
                    recoverySamples.push_back(rxTimeS[s] - burstEnd);
                    break;
                }
            }
        }
        if (!recoverySamples.empty())
        {
            double sum = 0.0;
            for (double v : recoverySamples)
            {
                sum += v;
            }
            telemetry.meanRecoveryTimeS = sum / static_cast<double>(recoverySamples.size());
            telemetry.recoverySampleCount = static_cast<uint32_t>(recoverySamples.size());
            // Standard deviation: needed for the coefficient of variation
            // exposed in AntiJammingMetricResult.
            double sqSum = 0.0;
            for (double v : recoverySamples)
            {
                const double d = v - telemetry.meanRecoveryTimeS;
                sqSum += d * d;
            }
            telemetry.stdRecoveryTimeS =
                std::sqrt(sqSum / static_cast<double>(recoverySamples.size()));
            // p95: deterministic percentile over the sample set.
            std::vector<double> sorted = recoverySamples;
            std::sort(sorted.begin(), sorted.end());
            const std::size_t idx = static_cast<std::size_t>(
                std::min(sorted.size() - 1,
                         static_cast<std::size_t>(std::round(0.95 * (sorted.size() - 1)))));
            telemetry.p95RecoveryTimeS = sorted[idx];
        }
    }

    // Outage probability under jamming and worst-case burst latency.
    telemetry.outageThresholdDb = kOutageThresholdDb;
    telemetry.outageProbabilityJammerOn =
        txDuringJammerOn > 0
            ? static_cast<double>(outageJammerOnEvents) / static_cast<double>(txDuringJammerOn)
            : 0.0;
    telemetry.worstCaseBurstLatencyS = worstCaseBurstLatencyS;
    telemetry.maxConsecutiveDeadlineMisses = maxConsecutiveDeadlineMisses;

    // Effective throughput in packets/s over the offered-traffic window.
    if (cfg.packets > 0 && cfg.trafficIntervalS > 0.0)
    {
        const double windowS = cfg.packets * cfg.trafficIntervalS;
        uint32_t rxCount = 0;
        for (uint32_t s = 0; s < cfg.packets; ++s)
        {
            if (rxFlag[s])
            {
                ++rxCount;
            }
        }
        telemetry.effectiveThroughputPps = rxCount / windowS;
    }

    budget.telemetry = telemetry;
    budget.s9ProactiveDeferCount = s9ProactiveDeferCount;
    return budget;
}

void
EmitChannelTrace(const CoreHarnessConfig& cfg)
{
    if (cfg.channelTraceLogPath.empty())
    {
        return;
    }
    const bool useAr1 = (cfg.cm8.correlationModel == "ar1");
    std::mt19937 fadingRng(cfg.cm8.fadingSeed != 0 ? cfg.cm8.fadingSeed : cfg.seed);
    std::normal_distribution<double> gauss(0.0, 1.0);
    std::exponential_distribution<double> rayleighPower(1.0);
    const double shadowStd = cfg.cm8.shadowingStdDb;
    const bool useShadow = shadowStd > 0.0;
    const bool useRayleigh = cfg.cm8.rayleighFading;
    const double TcS = std::max(cfg.cm8.coherenceTimeMs * 1e-3, 1e-9);
    const double periodS = std::max(cfg.cm8.channelUpdatePeriodUs * 1e-6, 1e-9);
    const double horizonS = cfg.packets * cfg.trafficIntervalS;
    constexpr uint32_t kMaxSamples = 20000u;
    uint32_t nSamples =
        static_cast<uint32_t>(std::min<double>(kMaxSamples, std::floor(horizonS / periodS) + 1.0));
    if (nSamples < 2)
    {
        nSamples = 2;
    }

    std::ofstream out(cfg.channelTraceLogPath);
    out << "run_id,seed,coherence_time_ms,channel_correlation_model,channel_update_period_us,"
           "sample_index,time_us,channel_gain_db\n";
    out.precision(10);

    double ouShadow = 0.0;
    double ouRe = 0.0;
    double ouIm = 0.0;
    double blockFading = 0.0;
    double lastBlockTimeS = -1.0e9;
    for (uint32_t i = 0; i < nSamples; ++i)
    {
        const double t = i * periodS;
        double gainDb = 0.0;
        if (useAr1)
        {
            if (i == 0)
            {
                if (useShadow)
                {
                    ouShadow = shadowStd * gauss(fadingRng);
                }
                if (useRayleigh)
                {
                    ouRe = std::sqrt(0.5) * gauss(fadingRng);
                    ouIm = std::sqrt(0.5) * gauss(fadingRng);
                }
            }
            else
            {
                const double rhoT = std::exp(-periodS / TcS);
                const double sT = std::sqrt(std::max(0.0, 1.0 - rhoT * rhoT));
                if (useShadow)
                {
                    ouShadow = rhoT * ouShadow + sT * shadowStd * gauss(fadingRng);
                }
                if (useRayleigh)
                {
                    ouRe = rhoT * ouRe + sT * std::sqrt(0.5) * gauss(fadingRng);
                    ouIm = rhoT * ouIm + sT * std::sqrt(0.5) * gauss(fadingRng);
                }
            }
            if (useShadow)
            {
                gainDb += ouShadow;
            }
            if (useRayleigh)
            {
                const double p = std::max(ouRe * ouRe + ouIm * ouIm, 1e-12);
                gainDb += 10.0 * std::log10(p);
            }
        }
        else
        {
            if (t - lastBlockTimeS >= TcS)
            {
                double f = 0.0;
                if (useShadow)
                {
                    f += shadowStd * gauss(fadingRng);
                }
                if (useRayleigh)
                {
                    const double pw = std::max(rayleighPower(fadingRng), 1e-12);
                    f += 10.0 * std::log10(pw);
                }
                blockFading = f;
                lastBlockTimeS = t;
            }
            gainDb = blockFading;
        }
        out << cfg.runId << ',' << cfg.seed << ',' << cfg.cm8.coherenceTimeMs << ','
            << cfg.cm8.correlationModel << ',' << cfg.cm8.channelUpdatePeriodUs << ',' << i << ','
            << (t * 1e6) << ',' << gainDb << '\n';
    }
    out.close();
}

} // namespace industrial
} // namespace ns3
