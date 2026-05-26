#include "metrics-collector.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <limits>
#include <numeric>
#include <stdexcept>
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
    if (std::isnan(value))
    {
        // CSV consumers treat empty as "missing"; the JSON writer rewrites
        // empties to `null` so JSON stays parseable for journal pipelines.
        return "";
    }
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

std::string
JoinSemicolon(const std::vector<std::string>& parts)
{
    std::ostringstream ss;
    for (std::size_t i = 0; i < parts.size(); ++i)
    {
        if (i > 0)
        {
            ss << ';';
        }
        ss << parts[i];
    }
    return ss.str();
}

} // namespace

void
MetricsCollector::RecordTx(uint32_t seq, uint32_t userId)
{
    m_transmittedSeq.insert(seq);
    ++m_txCountByUser[userId];
}

void
MetricsCollector::RecordRx(uint32_t seq, double delayS, uint32_t userId)
{
    m_receivedSeq.insert(seq);
    m_receiveDelayS[seq] = delayS;
    ++m_rxCountByUser[userId];
    m_delaysByUser[userId].push_back(delayS);
}

RunMetrics
MetricsCollector::Compute(const RunContext& context,
                          double signalPowerDbm,
                          double noiseFloorDbm,
                          double jammerPowerAtReceiverDbm,
                          const AntiJammingTelemetry& telemetry) const
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
                                                context.jammerMode,
                                                telemetry);

    if (telemetry.populated && context.jammerMode != "none")
    {
        const uint32_t txOn = telemetry.txDuringJammerOn;
        const uint32_t txOff = out.transmittedPackets >= txOn ? out.transmittedPackets - txOn : 0;
        const uint32_t rxOn = telemetry.rxAmongTxDuringJammerOn;
        const uint32_t rxOff = out.receivedPackets >= rxOn ? out.receivedPackets - rxOn : 0;
        out.antiJamming.pdrJammerOff = txOff > 0
                                           ? static_cast<double>(rxOff) / static_cast<double>(txOff)
                                           : std::numeric_limits<double>::quiet_NaN();
        if (out.lostPackets > 0)
        {
            out.antiJamming.burstInducedLossRatio =
                static_cast<double>(telemetry.lostDuringJammerOn) /
                static_cast<double>(out.lostPackets);
        }
        else
        {
            out.antiJamming.burstInducedLossRatio = 0.0;
        }
    }

    const uint32_t nUsers = std::max(1u, context.numUsers);
    const double windowS =
        out.transmittedPackets > 0 && context.trafficIntervalS > 0.0
            ? static_cast<double>(out.transmittedPackets) * context.trafficIntervalS
            : 0.0;
    std::vector<std::string> pdrParts;
    std::vector<std::string> tputParts;
    std::vector<std::string> p95Parts;
    pdrParts.reserve(nUsers);
    tputParts.reserve(nUsers);
    p95Parts.reserve(nUsers);
    double jainSum = 0.0;
    double jainSumSq = 0.0;
    for (uint32_t u = 0; u < nUsers; ++u)
    {
        const auto txIt = m_txCountByUser.find(u);
        const auto rxIt = m_rxCountByUser.find(u);
        const uint32_t txU = txIt != m_txCountByUser.end() ? txIt->second : 0u;
        const uint32_t rxU = rxIt != m_rxCountByUser.end() ? rxIt->second : 0u;
        const double pdrU = txU > 0 ? static_cast<double>(rxU) / static_cast<double>(txU) : 0.0;
        pdrParts.push_back(ToString(pdrU));
        const double tputU =
            windowS > 0.0 ? static_cast<double>(rxU) / windowS : 0.0;
        tputParts.push_back(ToString(tputU));
        const auto delayIt = m_delaysByUser.find(u);
        const double p95U = (delayIt != m_delaysByUser.end() && !delayIt->second.empty())
                                ? Percentile(delayIt->second, 0.95)
                                : std::numeric_limits<double>::quiet_NaN();
        p95Parts.push_back(ToString(p95U));
        jainSum += pdrU;
        jainSumSq += pdrU * pdrU;
    }
    out.perUserPdr = JoinSemicolon(pdrParts);
    out.perUserThroughputPps = JoinSemicolon(tputParts);
    out.perUserP95DelayS = JoinSemicolon(p95Parts);
    // Jain's fairness index over per-user PDR [Jai84]:
    //   J(x_1, ..., x_n) = (sum x_i)^2 / (n * sum x_i^2)
    // 1 = perfectly fair, 1/n = fully unfair (single user gets everything).
    // n=1 is reported as 1.0 by convention (no multi-user contention).
    if (nUsers > 1 && jainSumSq > 0.0)
    {
        out.jainFairnessIndex = (jainSum * jainSum) /
                                (static_cast<double>(nUsers) * jainSumSq);
    }
    else
    {
        out.jainFairnessIndex = 1.0;
    }
    return out;
}

std::vector<std::string>
CsvHeader()
{
    return {"git_commit",
            "ns3_version",
            "seed",
            "scenario",
            "policy",
            "policy_label",
            "policy_paper_label",
            "simulation_path",
            "channel_model",
            "channel_fidelity",
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
            "per_theta_m",
            "per_slope",
            "s8_rtx_snir_gain",
            "s9_cooldown_symbols",
            "eve_snir_bias_db",
            "eve_snir_noise_std_db",
            "eve_snir_delay_slots",
            "eve_estimation_ideal",
            "s9_estimator_profile",
            "s9_snir_noise_std_db",
            "s9_snir_bias_db",
            "s9_snir_staleness_slots",
            "s9_jammer_missed_detection_prob",
            "s9_jammer_false_alarm_prob",
            "s9_per_crit",
            "s9_gamma_out_db",
            "s9_ablation_disable_jammer_flag",
            "s9_ablation_disable_cooldown",
            "s9_ablation_disable_snir_margin",
            "s9_ablation_disable_per_margin",
            "s9_proactive_defer_enabled",
            "s9_proactive_defer_count",
            "trace_provenance",
            "synthetic_placeholder_final_claims_allowed",
            "fading_variance_source",
            "num_users",
            "per_user_pdr",
            "per_user_throughput_pps",
            "per_user_p95_delay_s",
            "jain_fairness_index",
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
            "sjr_db",
            "jnr_db",
            "jammer_duty_cycle",
            "pdr_jammer_on",
            "pdr_jammer_off",
            "burst_induced_loss_ratio",
            "mean_recovery_time_s",
            "recovery_sample_count",
            "std_recovery_time_s",
            "cv_recovery_time",
            "p95_recovery_time_s",
            "outage_probability_jammer_on",
            "outage_threshold_db",
            "worst_case_burst_latency_s",
            "max_consecutive_deadline_misses",
            "effective_throughput_pps",
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
            m.context.policy,
            m.context.policyLabel,
            m.context.policyPaperLabel,
            m.context.simulationPath,
            m.context.channelModel,
            m.context.channelFidelity,
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
            ToString(m.context.perThetaM),
            ToString(m.context.perSlope),
            ToString(m.context.s8RtxSnirGain),
            std::to_string(m.context.s9CooldownSymbols),
            ToString(m.context.eveSnirBiasDb),
            ToString(m.context.eveSnirNoiseStdDb),
            std::to_string(m.context.eveSnirDelaySlots),
            m.context.eveEstimationIdeal ? "true" : "false",
            m.context.s9EstimatorProfile,
            ToString(m.context.s9SnirNoiseStdDb),
            ToString(m.context.s9SnirBiasDb),
            std::to_string(m.context.s9SnirStalenessSlots),
            ToString(m.context.s9JammerMissedDetProb),
            ToString(m.context.s9JammerFalseAlarmProb),
            ToString(m.context.s9PerCrit),
            ToString(m.context.s9GammaOutDb),
            m.context.s9AblationDisableJammerFlag ? "true" : "false",
            m.context.s9AblationDisableCooldown ? "true" : "false",
            m.context.s9AblationDisableSnirMargin ? "true" : "false",
            m.context.s9AblationDisablePerMargin ? "true" : "false",
            m.context.s9ProactiveDeferEnabled ? "true" : "false",
            std::to_string(m.s9ProactiveDeferCount),
            m.context.traceProvenance,
            m.context.syntheticPlaceholderFinalClaimsAllowed ? "true" : "false",
            m.context.fadingVarianceSource,
            std::to_string(m.context.numUsers),
            m.perUserPdr,
            m.perUserThroughputPps,
            m.perUserP95DelayS,
            ToString(m.jainFairnessIndex),
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
            ToString(m.antiJamming.sjrDb),
            ToString(m.antiJamming.jnrDb),
            ToString(m.antiJamming.jammerDutyCycle),
            ToString(m.antiJamming.pdrJammerOn),
            ToString(m.antiJamming.pdrJammerOff),
            ToString(m.antiJamming.burstInducedLossRatio),
            ToString(m.antiJamming.meanRecoveryTimeS),
            std::to_string(m.antiJamming.recoverySampleCount),
            ToString(m.antiJamming.stdRecoveryTimeS),
            ToString(m.antiJamming.cvRecoveryTime),
            ToString(m.antiJamming.p95RecoveryTimeS),
            ToString(m.antiJamming.outageProbabilityJammerOn),
            ToString(m.antiJamming.outageThresholdDb),
            ToString(m.antiJamming.worstCaseBurstLatencyS),
            std::to_string(m.antiJamming.maxConsecutiveDeadlineMisses),
            ToString(m.antiJamming.effectiveThroughputPps),
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
    out << "# simulation_path: " << metrics.context.simulationPath << "\n";
    out << "# channel_fidelity: " << metrics.context.channelFidelity << "\n";
    if (metrics.context.simulationPath == "ns3_core_harness")
    {
        out << "# purpose: main paper statistical campaign (PER waterfall sigmoid on per-packet SNIR)\n";
        out << "# stack: pure ns3::Simulator/RNG; no YansWifiPhy, no MAC contention, no BlockAck, no A-MPDU\n";
        out << "# note: rows produced by this path are the primary evidence base. Do not aggregate\n";
        out << "#   with rows whose simulation_path differs.\n";
    }
    else
    {
        out << "# purpose: packet-level behavioral validation addendum\n";
        out << "# main_campaign_path: ns3_core_harness\n";
        out << "# note: main campaign remains primary evidence base for statistical\n";
        out << "#   sweep. This addendum provides packet-level contention/BlockAck\n";
        out << "#   validation for a subset of configurations. Results should not be\n";
        out << "#   aggregated with main CSV.\n";
    }
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
        if (row[i].empty())
        {
            // Missing measurements (e.g. NaN telemetry on a no-jammer run)
            // serialise to JSON null so consumers can branch cleanly.
            out << "null";
        }
        else if (boolean || numeric)
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
