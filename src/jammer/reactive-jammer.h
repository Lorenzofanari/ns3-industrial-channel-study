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

// Reactive jammer model. References (see BIBLIOGRAPHY.md):
//   [Bay08] Bayraktaroglu et al., "On the Performance of IEEE 802.11 under
//           Jamming", IEEE INFOCOM 2008. Foundational analytical model for
//           reactive jammers on 802.11 (channel-aware, jams ongoing tx).
//   [Pel11] Pelechrinis et al., "Denial of Service Attacks in Wireless
//           Networks: The Case of Jammers", IEEE COMST 13(2), 2011.
//   [Gri21] Pirayesh & Zeng, "Jamming Attacks and Anti-Jamming Strategies in
//           Wireless Networks: A Comprehensive Survey", IEEE COMST 24(2),
//           2022 (arXiv:2101.00292). Notes the < 4 us detect-to-burst budget
//           of a real reactive PHY attacker; the Yans-path implementation here
//           is a co-station MAC-level proxy and is documented as such in the
//           README and in core-harness telemetry.
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
