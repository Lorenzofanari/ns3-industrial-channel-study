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
    std::string policy{"S4"};
    std::string policyLabel{"Baseline-PF"};
    std::string simulationPath{"ns3_wifi_yans"};
    std::string channelModel{"cm8_rayleigh"};
    std::string channelFidelity{"proxy"};
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
    double perThetaM{3.0};
    double perSlope{1.15};
    double s8RtxSnirGain{1.35};
    uint32_t s9CooldownSymbols{76};
    double eveSnirBiasDb{0.0};
    double eveSnirNoiseStdDb{0.0};
    uint32_t eveSnirDelaySlots{0};
    bool eveEstimationIdeal{true};

    // Trace provenance (channel fidelity gating). Filled by the simulator for
    // every CSV row so reviewers can immediately tell whether a result row
    // relies on measured propagation data or on the documented synthetic
    // placeholder shipped in `data/quadriga/`.
    //  - For CM8 runs both fields are populated with the stochastic-proxy
    //    semantics (`trace_provenance=cm8_stochastic_proxy`).
    //  - For QuaDRiGa trace replay this carries through whatever the YAML
    //    declares (`synthetic_placeholder` or `measured`).
    std::string traceProvenance{"cm8_stochastic_proxy"};
    // True only when the YAML / CLI explicitly enables the placeholder for
    // final paper claims. Default false to keep the safety gate ON.
    bool syntheticPlaceholderFinalClaimsAllowed{false};
    // Source of the small-scale fading variance used at run time. One of
    // `trace_column` (QuaDRiGa `fading_std_db`), `cm8_proxy` (CM8 log-normal +
    // Rayleigh draws), or `none` (deterministic path-loss only).
    std::string fadingVarianceSource{"cm8_proxy"};
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
                       double jammerPowerAtReceiverDbm,
                       const AntiJammingTelemetry& telemetry = {}) const;

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
