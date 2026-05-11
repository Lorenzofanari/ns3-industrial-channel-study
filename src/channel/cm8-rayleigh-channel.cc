#include "cm8-rayleigh-channel.h"

#include "ns3/double.h"
#include "ns3/log.h"
#include "ns3/mobility-model.h"
#include "ns3/simulator.h"

#include <algorithm>
#include <cmath>

namespace ns3
{
namespace industrial
{

NS_LOG_COMPONENT_DEFINE("Cm8RayleighPropagationLossModel");
NS_OBJECT_ENSURE_REGISTERED(Cm8RayleighPropagationLossModel);

TypeId
Cm8RayleighPropagationLossModel::GetTypeId()
{
    static TypeId tid =
        TypeId("ns3::industrial::Cm8RayleighPropagationLossModel")
            .SetParent<PropagationLossModel>()
            .SetGroupName("Propagation")
            .AddConstructor<Cm8RayleighPropagationLossModel>();
    return tid;
}

Cm8RayleighPropagationLossModel::Cm8RayleighPropagationLossModel()
    : m_shadowing(CreateObject<NormalRandomVariable>()),
      m_rayleighPower(CreateObject<ExponentialRandomVariable>())
{
    m_shadowing->SetAttribute("Mean", DoubleValue(0.0));
    m_shadowing->SetAttribute("Variance", DoubleValue(m_config.shadowingStdDb * m_config.shadowingStdDb));
    m_rayleighPower->SetAttribute("Mean", DoubleValue(1.0));
}

void
Cm8RayleighPropagationLossModel::SetConfig(const Cm8RayleighConfig& config)
{
    m_config = config;
    m_shadowing->SetAttribute("Variance", DoubleValue(config.shadowingStdDb * config.shadowingStdDb));
}

const Cm8RayleighConfig&
Cm8RayleighPropagationLossModel::GetConfig() const
{
    return m_config;
}

double
CalculateCm8PathLossDb(double distanceM, const Cm8RayleighConfig& config)
{
    const double d = std::max(distanceM, config.referenceDistanceM);
    return config.referenceLossDb +
           10.0 * config.pathLossExponent * std::log10(d / config.referenceDistanceM) +
           config.industrialExcessLossDb;
}

double
CalculateNoiseFloorDbm(double bandwidthHz, double noiseFigureDb)
{
    return -174.0 + 10.0 * std::log10(bandwidthHz) + noiseFigureDb;
}

double
Cm8RayleighPropagationLossModel::DoCalcRxPower(double txPowerDbm,
                                               Ptr<MobilityModel> a,
                                               Ptr<MobilityModel> b) const
{
    const double distanceM = a->GetDistanceFrom(b);
    const double pathLossDb = CalculateCm8PathLossDb(distanceM, m_config);
    if (Simulator::Now() >= m_nextFadingSample)
    {
        double fadingDb = 0.0;
        if (m_config.shadowingStdDb > 0.0)
        {
            fadingDb += m_shadowing->GetValue();
        }
        if (m_config.rayleighFading)
        {
            const double powerGain = std::max(m_rayleighPower->GetValue(), 1e-12);
            fadingDb += 10.0 * std::log10(powerGain);
        }
        m_cachedFadingDb = fadingDb;
        m_nextFadingSample = Simulator::Now() + MilliSeconds(m_config.coherenceTimeMs);
    }
    return txPowerDbm - pathLossDb + m_cachedFadingDb;
}

int64_t
Cm8RayleighPropagationLossModel::DoAssignStreams(int64_t stream)
{
    m_shadowing->SetStream(stream);
    m_rayleighPower->SetStream(stream + 1);
    return 2;
}

} // namespace industrial
} // namespace ns3
