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

// Constant (channel-oblivious) jammer model. References (see BIBLIOGRAPHY.md):
//   [Bay08] Bayraktaroglu et al., IEEE INFOCOM 2008. Channel-oblivious
//           jammer (periodic / memoryless) baseline used to bound the
//           saturation throughput of 802.11 under jamming.
//   [Pel11] Pelechrinis et al., IEEE COMST 13(2), 2011.
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
