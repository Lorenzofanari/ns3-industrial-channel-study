#include "periodic-control-app.h"

#include "ns3/inet-socket-address.h"
#include "ns3/log.h"
#include "ns3/packet.h"
#include "ns3/seq-ts-size-header.h"
#include "ns3/simulator.h"
#include "ns3/udp-socket-factory.h"

namespace ns3
{
namespace industrial
{

NS_LOG_COMPONENT_DEFINE("PeriodicControlApp");
NS_OBJECT_ENSURE_REGISTERED(PeriodicControlApp);
NS_OBJECT_ENSURE_REGISTERED(ControlReceiverApp);

TypeId
PeriodicControlApp::GetTypeId()
{
    static TypeId tid = TypeId("ns3::industrial::PeriodicControlApp")
                            .SetParent<Application>()
                            .SetGroupName("Applications")
                            .AddConstructor<PeriodicControlApp>();
    return tid;
}

PeriodicControlApp::PeriodicControlApp() = default;

void
PeriodicControlApp::Configure(Address peer,
                              uint32_t payloadBytes,
                              Time interval,
                              uint32_t maxPackets,
                              Ptr<MetricsCollector> collector)
{
    m_peer = peer;
    m_payloadBytes = payloadBytes;
    m_interval = interval;
    m_maxPackets = maxPackets;
    m_collector = collector;
}

void
PeriodicControlApp::StartApplication()
{
    m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
    m_socket->Connect(m_peer);
    SendPacket();
}

void
PeriodicControlApp::StopApplication()
{
    if (m_sendEvent.IsPending())
    {
        Simulator::Cancel(m_sendEvent);
    }
    if (m_socket)
    {
        m_socket->Close();
    }
}

void
PeriodicControlApp::SendPacket()
{
    SeqTsSizeHeader header;
    header.SetSeq(m_sent);
    header.SetSize(m_payloadBytes);
    const uint32_t headerSize = header.GetSerializedSize();
    const uint32_t bodyBytes = m_payloadBytes > headerSize ? m_payloadBytes - headerSize : 0;
    Ptr<Packet> packet = Create<Packet>(bodyBytes);
    packet->AddHeader(header);
    m_socket->Send(packet);
    if (m_collector)
    {
        m_collector->RecordTx(m_sent);
    }
    ++m_sent;
    ScheduleNext();
}

void
PeriodicControlApp::ScheduleNext()
{
    if (m_sent < m_maxPackets)
    {
        m_sendEvent = Simulator::Schedule(m_interval, &PeriodicControlApp::SendPacket, this);
    }
}

TypeId
ControlReceiverApp::GetTypeId()
{
    static TypeId tid = TypeId("ns3::industrial::ControlReceiverApp")
                            .SetParent<Application>()
                            .SetGroupName("Applications")
                            .AddConstructor<ControlReceiverApp>();
    return tid;
}

ControlReceiverApp::ControlReceiverApp() = default;

void
ControlReceiverApp::Configure(uint16_t port, Ptr<MetricsCollector> collector)
{
    m_port = port;
    m_collector = collector;
}

void
ControlReceiverApp::StartApplication()
{
    m_socket = Socket::CreateSocket(GetNode(), UdpSocketFactory::GetTypeId());
    m_socket->Bind(InetSocketAddress(Ipv4Address::GetAny(), m_port));
    m_socket->SetRecvCallback(MakeCallback(&ControlReceiverApp::HandleRead, this));
}

void
ControlReceiverApp::StopApplication()
{
    if (m_socket)
    {
        m_socket->Close();
    }
}

void
ControlReceiverApp::HandleRead(Ptr<Socket> socket)
{
    Address from;
    Ptr<Packet> packet;
    while ((packet = socket->RecvFrom(from)))
    {
        SeqTsSizeHeader header;
        if (packet->GetSize() >= header.GetSerializedSize())
        {
            packet->RemoveHeader(header);
            const double delayS = (Simulator::Now() - header.GetTs()).GetSeconds();
            if (m_collector)
            {
                m_collector->RecordRx(header.GetSeq(), delayS);
            }
        }
    }
}

} // namespace industrial
} // namespace ns3
