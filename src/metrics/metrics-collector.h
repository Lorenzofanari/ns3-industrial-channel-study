#ifndef METRICS_COLLECTOR_H
#define METRICS_COLLECTOR_H

#include "antijamming-metrics.h"
#include "safety-metrics.h"

#include "ns3/simple-ref-count.h"

#include <cstdint>
#include <map>
#include <set>
#include <string>
#include <vector>

namespace ns3
{
namespace industrial
{

struct RunContext
{
    std::string gitCommit{"unknown"};
    std::string ns3Version{"unknown"};
    uint32_t seed{1};
    std::string scenario{"S4"};
    std::string channelModel{"cm8_rayleigh"};
    std::string channelAbstraction;
    std::string tracePath;
    uint32_t mcs{0};
    uint32_t payloadBits{128};
    double distanceM{1.0};
    std::string jammerMode{"none"};
    double jammerPowerDbm{0.0};
    std::string standard{"80211ax"};
    std::string dataMode{"HeMcs0"};
    uint32_t retryLimit{7};
    double txPowerDbm{18.0};
    double noiseFigureDb{7.0};
    double bandwidthMHz{20.0};
    double simulationTimeS{10.0};
    double trafficIntervalS{0.01};
    double deadlineS{0.01};
    bool phyPerAvailable{false};
    std::string perDefinition{"application_loss_proxy_until_phy_mac_traces_enabled"};
};

struct RunMetrics
{
    RunContext context;
    uint32_t transmittedPackets{0};
    uint32_t receivedPackets{0};
    uint32_t lostPackets{0};
    uint32_t corruptedPackets{0};
    double pdr{0.0};
    double plr{0.0};
    double per{0.0};
    double packetSuccessProbability{0.0};
    double meanDelayS{0.0};
    double medianDelayS{0.0};
    double p95DelayS{0.0};
    double p99DelayS{0.0};
    double jitterS{0.0};
    SafetyMetricResult safety;
    AntiJammingMetricResult antiJamming;
};

class MetricsCollector : public SimpleRefCount<MetricsCollector>
{
  public:
    void RecordTx(uint32_t seq);
    void RecordRx(uint32_t seq, double delayS);
    RunMetrics Compute(const RunContext& context,
                       double signalPowerDbm,
                       double noiseFloorDbm,
                       double jammerPowerAtReceiverDbm) const;

  private:
    std::set<uint32_t> m_transmittedSeq;
    std::set<uint32_t> m_receivedSeq;
    std::map<uint32_t, double> m_receiveDelayS;
};

std::vector<std::string> CsvHeader();
std::vector<std::string> CsvRow(const RunMetrics& metrics);
void WriteCsv(const std::string& path, const RunMetrics& metrics);
void WriteJson(const std::string& path, const RunMetrics& metrics);

} // namespace industrial
} // namespace ns3

#endif // METRICS_COLLECTOR_H
