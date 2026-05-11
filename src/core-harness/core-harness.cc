#include "core-harness.h"

#include "channel/cm8-rayleigh-channel.h"
#include "channel/quadriga-channel-importer.h"

#include <algorithm>
#include <cmath>
#include <random>
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
    // useful symbol duration 12.8 us + 3.2 us GI = 16 us).
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
    const double theta = PerThetaForMcs(mcs, cfg);
    const double per = 1.0 / (1.0 + std::exp(cfg.slope * (snirDb - theta)));
    return std::max(per, cfg.floor);
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

} // namespace

CoreHarnessLinkBudget
RunCoreHarness(const CoreHarnessConfig& cfg, MetricsCollector& collector)
{
    if (cfg.channelModel == "cm8_rayleigh" && cfg.distanceM > cfg.cm8.maxDistanceM)
    {
        throw std::runtime_error("CM8 distance exceeds configured max_distance_m=6 m");
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
    if (cfg.channelModel == "cm8_rayleigh")
    {
        pathLossDb = CalculateCm8PathLossDb(cfg.distanceM, cfg.cm8);
        budget.channelAbstraction = "controlled_rayleigh_path_loss_with_shadowing";
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
        }
        else
        {
            useRayleigh = cfg.cm8.rayleighFading;
            budget.channelAbstraction = "external_geometry_trace_scalar_path_loss_replay";
        }
    }
    else
    {
        throw std::runtime_error("core-harness: unsupported channel model " + cfg.channelModel);
    }
    std::normal_distribution<double> shadow(0.0, effectiveShadowStdDb);

    const double noiseFloorDbm = CalculateNoiseFloorDbm(cfg.bandwidthMHz * 1e6, cfg.noiseFigureDb);
    const double noiseMw = DbmToMw(noiseFloorDbm);

    double jammerPathLossDb = 0.0;
    double jammerRxDbm = -300.0;
    double jammerMw = 0.0;
    if (cfg.jammerMode != "none")
    {
        if (cfg.channelModel == "cm8_rayleigh")
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
            if (effectiveShadowStdDb > 0.0)
            {
                fadingDb += shadow(rng);
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

    // Per-packet bookkeeping for conditional PDR and recovery time.
    std::vector<bool> txDuringJammerOnFlag(cfg.packets, false);
    std::vector<bool> rxFlag(cfg.packets, false);
    std::vector<double> rxTimeS(cfg.packets, 0.0);
    uint32_t txDuringJammerOn = 0;
    uint32_t rxDuringJammerOn = 0;
    uint32_t lostDuringJammerOn = 0;

    for (uint32_t seq = 0; seq < cfg.packets; ++seq)
    {
        const double launchTimeS = seq * cfg.trafficIntervalS;
        collector.RecordTx(seq);
        const bool jammerOnAtTx = jammerActiveAt(launchTimeS);
        txDuringJammerOnFlag[seq] = jammerOnAtTx;
        if (jammerOnAtTx)
        {
            ++txDuringJammerOn;
        }

        double currentTimeS = launchTimeS;
        bool success = false;
        double finalDelayS = 0.0;

        for (uint32_t attempt = 0; attempt <= cfg.retryLimit; ++attempt)
        {
            double extraGainDb = 0.0;
            // S8 (PLS-RTX): each retransmission is opportunistic, picking a
            // moment where the AP estimates a stronger channel state; modelled
            // as a fixed effective-SINR gain on the retry attempt.
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
            // slot units.
            if (cfg.scenario == "S9")
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
            collector.RecordRx(seq, finalDelayS);
            rxFlag[seq] = true;
            rxTimeS[seq] = launchTimeS + finalDelayS;
            if (jammerOnAtTx)
            {
                ++rxDuringJammerOn;
            }
        }
        else if (jammerOnAtTx)
        {
            ++lostDuringJammerOn;
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
        }
    }

    budget.telemetry = telemetry;
    return budget;
}

} // namespace industrial
} // namespace ns3
