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
    Require(PerThetaForMcs(3, cfg) == 15.5, "MCS3 must use 16QAM-3/4 theta 15.5 dB");
    Require(cfg.slope == 1.15, "PER slope default must be 1.15");
    Require(cfg.floor == 1e-8, "PER floor default must be 1e-8");
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

} // namespace

int
main()
{
    TestPerWaterfallDefaults();
    TestEveNoiseDistribution();
    TestChannelFidelityLabels();
    TestPerWaterfallSigmoidMonotonic();
    std::cout << "study-parameter-tests passed\n";
    return 0;
}
