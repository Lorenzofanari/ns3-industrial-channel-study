#ifndef REACTIVE_JAMMER_H
#define REACTIVE_JAMMER_H

#include "ns3/application-container.h"
#include "ns3/ipv4-address.h"
#include "ns3/node-container.h"
#include "ns3/nstime.h"

namespace ns3
{
namespace industrial
{

struct ReactiveJammerConfig
{
    bool enabled{false};
    double powerDbm{10.0};
    uint32_t packetBytes{1200};
    Time burstInterval{MilliSeconds(20)};
    Time burstDuration{MilliSeconds(4)};
};

ApplicationContainer InstallReactiveJammer(NodeContainer jammerNodes,
                                           Ipv4Address destination,
                                           uint16_t port,
                                           const ReactiveJammerConfig& config,
                                           Time start,
                                           Time stop);

} // namespace industrial
} // namespace ns3

#endif // REACTIVE_JAMMER_H
