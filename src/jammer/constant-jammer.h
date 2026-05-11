#ifndef CONSTANT_JAMMER_H
#define CONSTANT_JAMMER_H

#include "ns3/application-container.h"
#include "ns3/ipv4-address.h"
#include "ns3/node-container.h"
#include "ns3/nstime.h"

namespace ns3
{
namespace industrial
{

struct ConstantJammerConfig
{
    bool enabled{false};
    double powerDbm{10.0};
    uint32_t packetBytes{1200};
    Time interval{MilliSeconds(1)};
};

ApplicationContainer InstallConstantJammer(NodeContainer jammerNodes,
                                           Ipv4Address destination,
                                           uint16_t port,
                                           const ConstantJammerConfig& config,
                                           Time start,
                                           Time stop);

} // namespace industrial
} // namespace ns3

#endif // CONSTANT_JAMMER_H
