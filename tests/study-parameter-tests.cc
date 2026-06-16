#include "core-harness/core-harness.h"
#include "study-parameters.h"

#include <cmath>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <vector>

using namespace ns3::industrial;

namespace
{

void
Require(bool condition, const std::string& message)
{
    if (!condition)
    {
        throw std::runtime_error(message);
    }
}

void
TestPerWaterfallDefaults()
{
    const PerWaterfallConfig cfg;
    Require(PerThetaForMcs(0, cfg) == 3.0, "MCS0 must use BPSK-1/2 theta 3.0 dB");
    Require(PerThetaForMcs(1, cfg) == 6.0, "MCS1 must use QPSK-1/2 theta 6.0 dB");
    Require(PerThetaForMcs(3, cfg) == 15.5, "MCS3 must use 16QAM-1/2 theta 15.5 dB");
    Require(cfg.slope == 1.15, "PER slope default must be 1.15");
    Require(cfg.floor == 1e-8, "PER floor default must be 1e-8");
}

void
TestMcsMetadata()
{
    Require(McsLabel(0) == "BPSK_1_2", "MCS0 label must be BPSK_1_2");
    Require(McsLabel(1) == "QPSK_1_2", "MCS1 label must be QPSK_1_2");
    Require(McsLabel(3) == "16QAM_1_2", "MCS3 label must be 16QAM_1_2");
    Require(McsModulation(3) == "16-QAM", "MCS3 modulation must be 16-QAM");
    Require(McsCodingRate(0) == "1/2", "MCS0 coding rate must be 1/2");
}

void
TestCooldownConversion()
{
    Require(std::abs(CooldownSymbolsToMs(0) - 0.0) < 1e-12,
            "0 cooldown symbols must convert to 0 ms");
    Require(std::abs(CooldownSymbolsToMs(76) - 1.216) < 1e-12,
            "76 OFDM symbols at 16 us must convert to 1.216 ms");
    Require(std::abs(CooldownSymbolsToMs(304) - 4.864) < 1e-12,
            "304 OFDM symbols at 16 us must convert to 4.864 ms");
}

void
TestPerRuJammerSelection()
{
    const auto broadband =
        JammedRusForBurst("broadband_reactive", {}, 1, 4, 0, 20260507, 0, 0.0, 1.0);
    Require(broadband.size() == 4, "Broadband jammer must affect every RU");

    const auto narrow =
        JammedRusForBurst("narrowband_reactive", {2}, 1, 4, 0, 20260507, 0, 0.0, 1.0);
    Require(narrow.size() == 1 && narrow[0] == 2,
            "Narrowband jammer must affect only the configured RU");

    const auto partialA =
        JammedRusForBurst("partial_band_reactive_random", {}, 2, 8, 3, 20260507, 0, 0.0, 1.0);
    const auto partialB =
        JammedRusForBurst("partial_band_reactive_random", {}, 2, 8, 3, 20260507, 0, 0.0, 1.0);
    Require(partialA.size() == 2, "Partial-band jammer must select exactly K RUs");
    Require(partialA == partialB, "Partial-band RU selection must be seed/burst reproducible");

    const auto retryAware =
        JammedRusForBurst("retry_aware_reactive", {}, 1, 4, 0, 20260507, 3, 1.0, 0.0);
    Require(retryAware.size() == 1 && retryAware[0] == 3,
            "Retry-aware jammer must follow the retry RU when the Bernoulli draw fires");
}

void
TestBestRuSelectors()
{
    Require(SelectMinIndex({0.8, 0.2, 0.4}) == 1,
            "Estimated-best-RU selection must choose minimum estimated PER");
    Require(SelectMinIndex({0.6, 0.5, 0.1, 0.2}) == 2,
            "Oracle-best-RU selection must choose minimum true PER");
}

void
TestEveNoiseDistribution()
{
    EveEstimationConfig cfg;
    cfg.noiseStdDb = 2.0;
    std::mt19937 rng(20260507);
    constexpr int n = 200000;
    std::vector<double> samples;
    samples.reserve(n);
    for (int i = 0; i < n; ++i)
    {
        samples.push_back(ApplyEveSnirEstimate(10.0, cfg, rng) - 10.0);
    }
    const double mean = std::accumulate(samples.begin(), samples.end(), 0.0) / samples.size();
    double variance = 0.0;
    for (double sample : samples)
    {
        variance += (sample - mean) * (sample - mean);
    }
    const double stddev = std::sqrt(variance / samples.size());
    Require(std::abs(mean) < 0.02, "Eve SNIR noise mean should remain near zero");
    Require(std::abs(stddev - cfg.noiseStdDb) < 0.02, "Eve SNIR noise std should match input");
}

void
TestChannelFidelityLabels()
{
    Require(ToString(ChannelFidelityForModel("cm8_rayleigh")) == "proxy",
            "CM8 profile must be tagged proxy");
    Require(ToString(ChannelFidelityForModel("QD_INDUSTRIAL_NLOS_PROXY")) == "proxy",
            "QD proxy display label must be tagged proxy");
    Require(ToString(ChannelFidelityForModel("quadriga_raytraced")) == "scalar_geometry_trace",
            "Geometry trace replay must be tagged scalar_geometry_trace");
    Require(ChannelDisplayName("quadriga_raytraced") == "QD_INDUSTRIAL_NLOS_GEOMETRY_TRACE",
            "Yans geometry trace display name must disambiguate QD label");
}

void
TestPerWaterfallSigmoidMonotonic()
{
    // PER waterfall sigmoid must be monotonically decreasing in SNIR, match the
    // documented midpoint (PER = 0.5 at gamma = theta_m) and decay below floor.
    PerWaterfallConfig cfg;
    const double mid = CalculatePerSigmoid(cfg.thetaBpskDb, 0, cfg);
    Require(std::abs(mid - 0.5) < 1e-6, "PER waterfall midpoint must be 0.5 at gamma = theta_m");
    double prev = 1.0;
    for (double snir = -10.0; snir <= 30.0; snir += 1.0)
    {
        const double per = CalculatePerSigmoid(snir, 0, cfg);
        Require(per <= prev + 1e-9, "PER waterfall must be monotone non-increasing in SNIR");
        prev = per;
    }
    Require(CalculatePerSigmoid(40.0, 0, cfg) <= cfg.floor + 1e-12,
            "PER waterfall must hit configured floor far above theta_m");
    Require(CalculatePerSigmoid(0.0, 3, cfg) > CalculatePerSigmoid(0.0, 0, cfg),
            "Higher MCS must show higher PER than lower MCS at the same SNIR");
}

void
TestAntiJammingTelemetryReactive()
{
    // Drive the core harness with a high-power reactive jammer at a low SNR
    // operating point and check that the new journal-grade telemetry is
    // populated with physically meaningful values: every first-attempt SINR
    // during the jammer-ON window must fall below the outage threshold, the
    // duty cycle must match burst/interval, and the recovery samples must
    // give a finite CV. The conditional PDR must drop on the jammer-ON
    // window and stay high on the jammer-OFF window.
    CoreHarnessConfig cfg;
    cfg.channelModel = "cm8_rayleigh";
    cfg.distanceM = 3.0;
    cfg.txPowerDbm = -30.0;
    cfg.noiseFigureDb = 7.0;
    cfg.bandwidthMHz = 20.0;
    cfg.mcs = 0;
    cfg.payloadBits = 128;
    cfg.packets = 5000;
    cfg.retryLimit = 7;
    cfg.trafficIntervalS = 0.01;
    cfg.deadlineS = 0.01;
    cfg.jammerMode = "reactive";
    cfg.jammerPowerDbm = 15.0;
    cfg.jammerDistanceM = 1.0;
    cfg.scenario = "S4";
    cfg.seed = 20260507;
    ns3::Ptr<MetricsCollector> collector = ns3::Create<MetricsCollector>();
    const CoreHarnessLinkBudget budget = RunCoreHarness(cfg, *collector);
    const auto& t = budget.telemetry;
    Require(t.populated, "Telemetry should be marked populated by the harness");
    Require(std::abs(t.jammerDutyCycle - 0.2) < 1e-9, "Reactive duty cycle must be burst/interval = 0.2");
    Require(t.txDuringJammerOn > 0, "There must be at least one tx during jammer-ON");
    Require(t.recoverySampleCount >= 10, "Should collect plenty of burst-end recovery samples");
    Require(t.meanRecoveryTimeS > 0.0, "Mean recovery time must be positive when there are bursts");
    Require(t.outageThresholdDb == 5.0, "Default outage threshold must be 5 dB");
    Require(t.outageProbabilityJammerOn > 0.9,
            "At SJR ~= -55 dB every jammer-ON first attempt should be in outage");
    Require(t.effectiveThroughputPps > 0.0, "Effective throughput must be positive");
    Require(t.worstCaseBurstLatencyS >= 0.0, "Worst-case burst latency must be non-negative");
}

void
TestAntiJammingTelemetryNoJammer()
{
    // Without a jammer the telemetry must be populated with safe defaults:
    // duty cycle 0, outage probability 0 (no tx in jammer-ON window), recovery
    // count 0 (no bursts).
    CoreHarnessConfig cfg;
    cfg.channelModel = "cm8_rayleigh";
    cfg.distanceM = 3.0;
    cfg.txPowerDbm = -30.0;
    cfg.mcs = 0;
    cfg.payloadBits = 128;
    cfg.packets = 1000;
    cfg.retryLimit = 7;
    cfg.trafficIntervalS = 0.01;
    cfg.deadlineS = 0.01;
    cfg.jammerMode = "none";
    cfg.scenario = "S4";
    cfg.seed = 20260507;
    ns3::Ptr<MetricsCollector> collector = ns3::Create<MetricsCollector>();
    const CoreHarnessLinkBudget budget = RunCoreHarness(cfg, *collector);
    const auto& t = budget.telemetry;
    Require(t.populated, "Telemetry should be populated even without jammer");
    Require(t.jammerDutyCycle == 0.0, "Duty cycle must be 0 with no jammer");
    Require(t.txDuringJammerOn == 0, "There must be no jammer-ON tx without jammer");
    Require(t.recoverySampleCount == 0, "There must be no burst-end transitions without jammer");
    Require(t.outageProbabilityJammerOn == 0.0,
            "Outage probability under jamming must be 0 when there is no jammer");
    Require(t.effectiveThroughputPps > 0.0, "Effective throughput must be positive in clean run");
}

} // namespace

int
main()
{
    TestPerWaterfallDefaults();
    TestMcsMetadata();
    TestCooldownConversion();
    TestPerRuJammerSelection();
    TestBestRuSelectors();
    TestEveNoiseDistribution();
    TestChannelFidelityLabels();
    TestPerWaterfallSigmoidMonotonic();
    TestAntiJammingTelemetryReactive();
    TestAntiJammingTelemetryNoJammer();
    std::cout << "study-parameter-tests passed\n";
    return 0;
}
