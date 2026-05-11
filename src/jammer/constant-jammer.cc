#include "constant-jammer.h"

#include "ns3/udp-client-server-helper.h"
#include "ns3/uinteger.h"

namespace ns3
{
namespace industrial
{

ApplicationContainer
InstallConstantJammer(NodeContainer jammerNodes,
                      Ipv4Address destination,
                      uint16_t port,
                      const ConstantJammerConfig& config,
                      Time start,
                      Time stop)
{
    if (!config.enabled || jammerNodes.GetN() == 0)
    {
        return ApplicationContainer();
    }
    UdpClientHelper jammer(destination, port);
    jammer.SetAttribute("MaxPackets", UintegerValue(0xffffffff));
    jammer.SetAttribute("Interval", TimeValue(config.interval));
    jammer.SetAttribute("PacketSize", UintegerValue(config.packetBytes));
    auto apps = jammer.Install(jammerNodes);
    apps.Start(start);
    apps.Stop(stop);
    return apps;
}

} // namespace industrial
} // namespace ns3
