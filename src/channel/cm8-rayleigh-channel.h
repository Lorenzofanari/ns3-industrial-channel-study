#ifndef CM8_RAYLEIGH_CHANNEL_H
#define CM8_RAYLEIGH_CHANNEL_H

#include "ns3/propagation-loss-model.h"
#include "ns3/random-variable-stream.h"
#include "ns3/nstime.h"

namespace ns3
{
namespace industrial
{

struct Cm8RayleighConfig
{
    double carrierFrequencyHz{5.18e9};
    double bandwidthHz{20e6};
    double maxDistanceM{6.0};
    double txPowerDbm{18.0};
    double noiseFigureDb{7.0};
    double pathLossExponent{2.2};
    double referenceLossDb{43.0};
    double referenceDistanceM{1.0};
    double shadowingStdDb{2.0};
    bool rayleighFading{true};
    double coherenceTimeMs{5.0};
    double industrialExcessLossDb{3.0};
    double receiverSensitivityDbm{-95.0};
    double packetDetectionThresholdDbm{-90.0};
};

double CalculateCm8PathLossDb(double distanceM, const Cm8RayleighConfig& config);
double CalculateNoiseFloorDbm(double bandwidthHz, double noiseFigureDb);

class Cm8RayleighPropagationLossModel : public PropagationLossModel
{
  public:
    static TypeId GetTypeId();
    Cm8RayleighPropagationLossModel();

    void SetConfig(const Cm8RayleighConfig& config);
    const Cm8RayleighConfig& GetConfig() const;

  private:
    double DoCalcRxPower(double txPowerDbm,
                         Ptr<MobilityModel> a,
                         Ptr<MobilityModel> b) const override;
    int64_t DoAssignStreams(int64_t stream) override;

    Cm8RayleighConfig m_config;
    Ptr<NormalRandomVariable> m_shadowing;
    Ptr<ExponentialRandomVariable> m_rayleighPower;
    mutable Time m_nextFadingSample{Seconds(0)};
    mutable double m_cachedFadingDb{0.0};
};

} // namespace industrial
} // namespace ns3

#endif // CM8_RAYLEIGH_CHANNEL_H
