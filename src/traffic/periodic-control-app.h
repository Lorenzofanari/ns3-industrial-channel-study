#ifndef PERIODIC_CONTROL_APP_H
#define PERIODIC_CONTROL_APP_H

#include "metrics/metrics-collector.h"

#include "ns3/application.h"
#include "ns3/event-id.h"
#include "ns3/ptr.h"
#include "ns3/socket.h"

namespace ns3
{
namespace industrial
{

class PeriodicControlApp : public Application
{
  public:
    static TypeId GetTypeId();
    PeriodicControlApp();

    void Configure(Address peer,
                   uint32_t payloadBytes,
                   Time interval,
                   uint32_t maxPackets,
                   Ptr<MetricsCollector> collector);

  private:
    void StartApplication() override;
    void StopApplication() override;
    void SendPacket();
    void ScheduleNext();

    Ptr<Socket> m_socket;
    Address m_peer;
    uint32_t m_payloadBytes{16};
    Time m_interval{MilliSeconds(10)};
    uint32_t m_maxPackets{1000};
    uint32_t m_sent{0};
    EventId m_sendEvent;
    Ptr<MetricsCollector> m_collector;
};

class ControlReceiverApp : public Application
{
  public:
    static TypeId GetTypeId();
    ControlReceiverApp();

    void Configure(uint16_t port, Ptr<MetricsCollector> collector);

  private:
    void StartApplication() override;
    void StopApplication() override;
    void HandleRead(Ptr<Socket> socket);

    Ptr<Socket> m_socket;
    uint16_t m_port{9000};
    Ptr<MetricsCollector> m_collector;
};

} // namespace industrial
} // namespace ns3

#endif // PERIODIC_CONTROL_APP_H
