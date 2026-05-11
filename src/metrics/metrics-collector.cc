#include "metrics-collector.h"

#include <algorithm>
#include <cctype>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <numeric>
#include <sstream>

namespace ns3
{
namespace industrial
{

namespace
{

double
Percentile(std::vector<double> values, double p)
{
    if (values.empty())
    {
        return 0.0;
    }
    std::sort(values.begin(), values.end());
    const double idx = (values.size() - 1) * p;
    const auto lo = static_cast<std::size_t>(idx);
    const auto hi = std::min(lo + 1, values.size() - 1);
    const double frac = idx - lo;
    return values[lo] * (1.0 - frac) + values[hi] * frac;
}

std::string
ToString(double value)
{
    std::ostringstream ss;
    ss << std::setprecision(12) << value;
    return ss.str();
}

std::string
JsonEscape(const std::string& value)
{
    std::string out;
    for (char c : value)
    {
        if (c == '"')
        {
            out += "\\\"";
        }
        else if (c == '\\')
        {
            out += "\\\\";
        }
        else
        {
            out += c;
        }
    }
    return out;
}

} // namespace

void
MetricsCollector::RecordTx(uint32_t seq)
{
    m_transmittedSeq.insert(seq);
}

void
MetricsCollector::RecordRx(uint32_t seq, double delayS)
{
    m_receivedSeq.insert(seq);
    m_receiveDelayS[seq] = delayS;
}

RunMetrics
MetricsCollector::Compute(const RunContext& context,
                          double signalPowerDbm,
                          double noiseFloorDbm,
                          double jammerPowerAtReceiverDbm) const
{
    RunMetrics out;
    out.context = context;
    out.transmittedPackets = static_cast<uint32_t>(m_transmittedSeq.size());
    out.receivedPackets = static_cast<uint32_t>(m_receivedSeq.size());
    out.lostPackets = out.transmittedPackets >= out.receivedPackets
                          ? out.transmittedPackets - out.receivedPackets
                          : 0;
    out.corruptedPackets = out.lostPackets;

    if (out.transmittedPackets > 0)
    {
        out.pdr = static_cast<double>(out.receivedPackets) / out.transmittedPackets;
        out.plr = static_cast<double>(out.lostPackets) / out.transmittedPackets;
        out.per = static_cast<double>(out.corruptedPackets) / out.transmittedPackets;
        out.packetSuccessProbability = out.pdr;
    }

    std::vector<double> delays;
    for (const auto& item : m_receiveDelayS)
    {
        delays.push_back(item.second);
    }
    if (!delays.empty())
    {
        out.meanDelayS = std::accumulate(delays.begin(), delays.end(), 0.0) / delays.size();
        out.medianDelayS = Percentile(delays, 0.50);
        out.p95DelayS = Percentile(delays, 0.95);
        out.p99DelayS = Percentile(delays, 0.99);
        if (delays.size() > 1)
        {
            std::vector<double> diffs;
            for (std::size_t i = 1; i < delays.size(); ++i)
            {
                diffs.push_back(std::abs(delays[i] - delays[i - 1]));
            }
            out.jitterS = std::accumulate(diffs.begin(), diffs.end(), 0.0) / diffs.size();
        }
    }

    out.safety = ComputeSafetyMetrics(out.transmittedPackets,
                                      m_receivedSeq,
                                      m_receiveDelayS,
                                      context.trafficIntervalS,
                                      context.deadlineS);
    out.antiJamming = ComputeAntiJammingMetrics(signalPowerDbm,
                                                noiseFloorDbm,
                                                jammerPowerAtReceiverDbm,
                                                out.pdr,
                                                1.0,
                                                out.plr,
                                                0.0,
                                                out.per,
                                                0.0,
                                                context.jammerMode);
    return out;
}

std::vector<std::string>
CsvHeader()
{
    return {"git_commit",
            "ns3_version",
            "seed",
            "scenario",
            "channel_model",
            "channel_abstraction",
            "trace_path",
            "mcs",
            "payload_bits",
            "distance_m",
            "jammer_mode",
            "jammer_power_dbm",
            "standard",
            "data_mode",
            "retry_limit",
            "tx_power_dbm",
            "noise_figure_db",
            "bandwidth_mhz",
            "simulation_time_s",
            "traffic_interval_s",
            "deadline_s",
            "phy_per_available",
            "per_definition",
            "transmitted_packets",
            "received_packets",
            "lost_packets",
            "corrupted_packets",
            "pdr",
            "plr",
            "per",
            "packet_success_probability",
            "mean_delay_s",
            "median_delay_s",
            "p95_delay_s",
            "p99_delay_s",
            "jitter_s",
            "deadline_miss_ratio",
            "safety_critical_packet_loss_ratio",
            "max_loss_burst_length",
            "max_time_without_successful_update_s",
            "probability_exceeding_safety_deadline",
            "signal_power_dbm",
            "noise_floor_dbm",
            "jammer_power_at_receiver_dbm",
            "sinr_under_jamming_db",
            "robustness_ratio",
            "plr_increase_due_to_jammer",
            "per_increase_due_to_jammer",
            "recovery_time_s"};
}

std::vector<std::string>
CsvRow(const RunMetrics& m)
{
    return {m.context.gitCommit,
            m.context.ns3Version,
            std::to_string(m.context.seed),
            m.context.scenario,
            m.context.channelModel,
            m.context.channelAbstraction,
            m.context.tracePath,
            std::to_string(m.context.mcs),
            std::to_string(m.context.payloadBits),
            ToString(m.context.distanceM),
            m.context.jammerMode,
            ToString(m.context.jammerPowerDbm),
            m.context.standard,
            m.context.dataMode,
            std::to_string(m.context.retryLimit),
            ToString(m.context.txPowerDbm),
            ToString(m.context.noiseFigureDb),
            ToString(m.context.bandwidthMHz),
            ToString(m.context.simulationTimeS),
            ToString(m.context.trafficIntervalS),
            ToString(m.context.deadlineS),
            m.context.phyPerAvailable ? "true" : "false",
            m.context.perDefinition,
            std::to_string(m.transmittedPackets),
            std::to_string(m.receivedPackets),
            std::to_string(m.lostPackets),
            std::to_string(m.corruptedPackets),
            ToString(m.pdr),
            ToString(m.plr),
            ToString(m.per),
            ToString(m.packetSuccessProbability),
            ToString(m.meanDelayS),
            ToString(m.medianDelayS),
            ToString(m.p95DelayS),
            ToString(m.p99DelayS),
            ToString(m.jitterS),
            ToString(m.safety.deadlineMissRatio),
            ToString(m.safety.safetyCriticalPacketLossRatio),
            std::to_string(m.safety.maxLossBurstLength),
            ToString(m.safety.maxTimeWithoutSuccessfulUpdateS),
            ToString(m.safety.probabilityExceedingDeadline),
            ToString(m.antiJamming.signalPowerDbm),
            ToString(m.antiJamming.noiseFloorDbm),
            ToString(m.antiJamming.jammerPowerAtReceiverDbm),
            ToString(m.antiJamming.sinrDb),
            ToString(m.antiJamming.robustnessRatio),
            ToString(m.antiJamming.plrIncreaseDueToJammer),
            ToString(m.antiJamming.perIncreaseDueToJammer),
            ToString(m.antiJamming.recoveryTimeS)};
}

void
WriteCsv(const std::string& path, const RunMetrics& metrics)
{
    std::filesystem::create_directories(std::filesystem::path(path).parent_path());
    std::ofstream out(path);
    const auto header = CsvHeader();
    const auto row = CsvRow(metrics);
    for (std::size_t i = 0; i < header.size(); ++i)
    {
        out << (i ? "," : "") << header[i];
    }
    out << "\n";
    for (std::size_t i = 0; i < row.size(); ++i)
    {
        out << (i ? "," : "") << row[i];
    }
    out << "\n";
}

void
WriteJson(const std::string& path, const RunMetrics& metrics)
{
    std::filesystem::create_directories(std::filesystem::path(path).parent_path());
    std::ofstream out(path);
    const auto header = CsvHeader();
    const auto row = CsvRow(metrics);
    out << "{\n";
    for (std::size_t i = 0; i < header.size(); ++i)
    {
        const bool boolean = row[i] == "true" || row[i] == "false";
        const bool numeric = !row[i].empty() &&
                             std::all_of(row[i].begin(), row[i].end(), [](unsigned char c) {
                                 return std::isdigit(c) || c == '-' || c == '+' || c == '.' ||
                                        c == 'e' || c == 'E';
                             }) &&
                             std::any_of(row[i].begin(), row[i].end(), [](unsigned char c) {
                                 return std::isdigit(c);
                             });
        out << "  \"" << header[i] << "\": ";
        if (boolean || numeric)
        {
            out << row[i];
        }
        else
        {
            out << "\"" << JsonEscape(row[i]) << "\"";
        }
        out << (i + 1 == header.size() ? "\n" : ",\n");
    }
    out << "}\n";
}

} // namespace industrial
} // namespace ns3
