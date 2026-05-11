#include "quadriga-channel-importer.h"

#include "ns3/log.h"
#include "ns3/mobility-model.h"

#include <algorithm>
#include <cctype>
#include <cmath>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <unordered_map>

namespace ns3
{
namespace industrial
{

NS_LOG_COMPONENT_DEFINE("QuadrigaTraceImporter");
NS_OBJECT_ENSURE_REGISTERED(QuadrigaTracePropagationLossModel);

namespace
{

std::vector<std::string>
SplitCsvLine(const std::string& line)
{
    std::vector<std::string> cells;
    std::string cell;
    std::stringstream ss(line);
    while (std::getline(ss, cell, ','))
    {
        cells.push_back(cell);
    }
    return cells;
}

double
ParseDouble(const std::vector<std::string>& row,
            const std::unordered_map<std::string, std::size_t>& index,
            const std::string& name,
            double fallback = 0.0)
{
    auto it = index.find(name);
    if (it == index.end() || it->second >= row.size() || row[it->second].empty())
    {
        return fallback;
    }
    return std::stod(row[it->second]);
}

std::string
ParseString(const std::vector<std::string>& row,
            const std::unordered_map<std::string, std::size_t>& index,
            const std::string& name)
{
    auto it = index.find(name);
    if (it == index.end() || it->second >= row.size())
    {
        return "";
    }
    return row[it->second];
}

std::string
Trim(std::string value)
{
    value.erase(value.begin(),
                std::find_if(value.begin(), value.end(), [](unsigned char ch) {
                    return !std::isspace(ch);
                }));
    value.erase(std::find_if(value.rbegin(),
                             value.rend(),
                             [](unsigned char ch) { return !std::isspace(ch); })
                    .base(),
                value.end());
    if (value.size() >= 2 && value.front() == '"' && value.back() == '"')
    {
        value = value.substr(1, value.size() - 2);
    }
    return value;
}

std::unordered_map<std::string, std::string>
ParseFlatJsonObject(const std::string& objectText)
{
    std::unordered_map<std::string, std::string> out;
    std::string body = objectText;
    if (!body.empty() && body.front() == '{')
    {
        body.erase(body.begin());
    }
    if (!body.empty() && body.back() == '}')
    {
        body.pop_back();
    }
    std::stringstream ss(body);
    std::string pair;
    while (std::getline(ss, pair, ','))
    {
        const auto colon = pair.find(':');
        if (colon == std::string::npos)
        {
            continue;
        }
        out[Trim(pair.substr(0, colon))] = Trim(pair.substr(colon + 1));
    }
    return out;
}

} // namespace

void
QuadrigaTrace::Load(const std::string& path)
{
    if (path.size() >= 5 && path.substr(path.size() - 5) == ".json")
    {
        LoadJson(path);
    }
    else
    {
        LoadCsv(path);
    }
}

void
QuadrigaTrace::LoadCsv(const std::string& path)
{
    std::ifstream in(path);
    if (!in)
    {
        throw std::runtime_error("Cannot open QuaDRiGa trace: " + path);
    }
    m_taps.clear();
    m_sourcePath = path;

    std::string headerLine;
    if (!std::getline(in, headerLine))
    {
        throw std::runtime_error("Empty QuaDRiGa trace: " + path);
    }
    const auto header = SplitCsvLine(headerLine);
    std::unordered_map<std::string, std::size_t> index;
    for (std::size_t i = 0; i < header.size(); ++i)
    {
        index[header[i]] = i;
    }

    const std::vector<std::string> required = {
        "tx_id", "rx_id", "distance_m", "time_s", "path_loss_db", "delay_s", "power_db"};
    for (const auto& name : required)
    {
        if (index.find(name) == index.end())
        {
            throw std::runtime_error("Missing required QuaDRiGa column: " + name);
        }
    }

    std::string line;
    while (std::getline(in, line))
    {
        if (line.empty())
        {
            continue;
        }
        const auto row = SplitCsvLine(line);
        QuadrigaTap tap;
        tap.txId = ParseString(row, index, "tx_id");
        tap.rxId = ParseString(row, index, "rx_id");
        tap.distanceM = ParseDouble(row, index, "distance_m");
        tap.timeS = ParseDouble(row, index, "time_s");
        tap.pathLossDb = ParseDouble(row, index, "path_loss_db");
        tap.delayS = ParseDouble(row, index, "delay_s");
        tap.powerDb = ParseDouble(row, index, "power_db");
        tap.hasDoppler = index.find("doppler_hz") != index.end();
        tap.hasPhase = index.find("phase_rad") != index.end();
        tap.hasFadingStd = index.find("fading_std_db") != index.end();
        tap.dopplerHz = ParseDouble(row, index, "doppler_hz");
        tap.phaseRad = ParseDouble(row, index, "phase_rad");
        tap.fadingStdDb = ParseDouble(row, index, "fading_std_db");
        m_taps.push_back(tap);
    }
    if (m_taps.empty())
    {
        throw std::runtime_error("QuaDRiGa trace has header but no taps: " + path);
    }
}

void
QuadrigaTrace::LoadJson(const std::string& path)
{
    std::ifstream in(path);
    if (!in)
    {
        throw std::runtime_error("Cannot open QuaDRiGa JSON trace: " + path);
    }
    std::stringstream buffer;
    buffer << in.rdbuf();
    const std::string text = buffer.str();
    m_taps.clear();
    m_sourcePath = path;

    std::size_t pos = 0;
    while ((pos = text.find('{', pos)) != std::string::npos)
    {
        const std::size_t end = text.find('}', pos);
        if (end == std::string::npos)
        {
            break;
        }
        const auto fields = ParseFlatJsonObject(text.substr(pos, end - pos + 1));
        auto require = [&fields](const std::string& key) {
            auto it = fields.find(key);
            if (it == fields.end())
            {
                throw std::runtime_error("Missing required QuaDRiGa JSON field: " + key);
            }
            return it->second;
        };

        QuadrigaTap tap;
        tap.txId = require("tx_id");
        tap.rxId = require("rx_id");
        tap.distanceM = std::stod(require("distance_m"));
        tap.timeS = std::stod(require("time_s"));
        tap.pathLossDb = std::stod(require("path_loss_db"));
        tap.delayS = std::stod(require("delay_s"));
        tap.powerDb = std::stod(require("power_db"));
        if (fields.find("doppler_hz") != fields.end())
        {
            tap.hasDoppler = true;
            tap.dopplerHz = std::stod(fields.at("doppler_hz"));
        }
        if (fields.find("phase_rad") != fields.end())
        {
            tap.hasPhase = true;
            tap.phaseRad = std::stod(fields.at("phase_rad"));
        }
        if (fields.find("fading_std_db") != fields.end())
        {
            tap.hasFadingStd = true;
            tap.fadingStdDb = std::stod(fields.at("fading_std_db"));
        }
        m_taps.push_back(tap);
        pos = end + 1;
    }
    if (m_taps.empty())
    {
        throw std::runtime_error("QuaDRiGa JSON trace has no tap objects: " + path);
    }
}

bool
QuadrigaTrace::Empty() const
{
    return m_taps.empty();
}

const std::vector<QuadrigaTap>&
QuadrigaTrace::GetTaps() const
{
    return m_taps;
}

std::vector<double>
QuadrigaTrace::GetDistances() const
{
    std::vector<double> distances;
    for (const auto& tap : m_taps)
    {
        distances.push_back(tap.distanceM);
    }
    std::sort(distances.begin(), distances.end());
    distances.erase(std::unique(distances.begin(), distances.end()), distances.end());
    return distances;
}

double
QuadrigaTrace::GetPathLossDb(double distanceM) const
{
    if (m_taps.empty())
    {
        throw std::runtime_error("No QuaDRiGa taps loaded");
    }
    const auto best = std::min_element(m_taps.begin(),
                                       m_taps.end(),
                                       [distanceM](const QuadrigaTap& a, const QuadrigaTap& b) {
                                           return std::abs(a.distanceM - distanceM) <
                                                  std::abs(b.distanceM - distanceM);
                                       });
    return best->pathLossDb;
}

double
QuadrigaTrace::GetEffectiveDelayS(double distanceM) const
{
    if (m_taps.empty())
    {
        return 0.0;
    }
    const auto best = std::min_element(m_taps.begin(),
                                       m_taps.end(),
                                       [distanceM](const QuadrigaTap& a, const QuadrigaTap& b) {
                                           return std::abs(a.distanceM - distanceM) <
                                                  std::abs(b.distanceM - distanceM);
                                       });
    return best->delayS;
}

bool
QuadrigaTrace::HasFadingStdDb() const
{
    for (const auto& tap : m_taps)
    {
        if (tap.hasFadingStd)
        {
            return true;
        }
    }
    return false;
}

double
QuadrigaTrace::GetFadingStdDb(double distanceM) const
{
    if (m_taps.empty())
    {
        return 0.0;
    }
    const auto best = std::min_element(m_taps.begin(),
                                       m_taps.end(),
                                       [distanceM](const QuadrigaTap& a, const QuadrigaTap& b) {
                                           return std::abs(a.distanceM - distanceM) <
                                                  std::abs(b.distanceM - distanceM);
                                       });
    if (best->hasFadingStd)
    {
        return std::max(best->fadingStdDb, 0.0);
    }
    // Fallback: sample standard deviation of path_loss_db across all taps that
    // share the nearest distance bucket. Useful when the trace exports several
    // time-snapshot rows per (tx, rx, distance) and the trace itself is the
    // source of small-scale variability.
    const double targetDistance = best->distanceM;
    double sum = 0.0;
    double sumSq = 0.0;
    std::size_t n = 0;
    for (const auto& tap : m_taps)
    {
        if (std::abs(tap.distanceM - targetDistance) < 1e-9)
        {
            sum += tap.pathLossDb;
            sumSq += tap.pathLossDb * tap.pathLossDb;
            ++n;
        }
    }
    if (n < 2)
    {
        return 0.0;
    }
    const double mean = sum / static_cast<double>(n);
    const double var = std::max(0.0, sumSq / static_cast<double>(n) - mean * mean);
    return std::sqrt(var * static_cast<double>(n) / static_cast<double>(n - 1));
}

std::string
QuadrigaTrace::GetSourcePath() const
{
    return m_sourcePath;
}

TypeId
QuadrigaTracePropagationLossModel::GetTypeId()
{
    static TypeId tid =
        TypeId("ns3::industrial::QuadrigaTracePropagationLossModel")
            .SetParent<PropagationLossModel>()
            .SetGroupName("Propagation")
            .AddConstructor<QuadrigaTracePropagationLossModel>();
    return tid;
}

QuadrigaTracePropagationLossModel::QuadrigaTracePropagationLossModel() = default;

void
QuadrigaTracePropagationLossModel::SetTrace(const QuadrigaTrace& trace)
{
    m_trace = trace;
}

void
QuadrigaTracePropagationLossModel::SetDistanceM(double distanceM)
{
    m_distanceM = distanceM;
}

double
QuadrigaTracePropagationLossModel::GetConfiguredDistanceM() const
{
    return m_distanceM;
}

const QuadrigaTrace&
QuadrigaTracePropagationLossModel::GetTrace() const
{
    return m_trace;
}

double
QuadrigaTracePropagationLossModel::DoCalcRxPower(double txPowerDbm,
                                                 Ptr<MobilityModel> a,
                                                 Ptr<MobilityModel> b) const
{
    const double requestedDistance = m_distanceM > 0.0 ? m_distanceM : a->GetDistanceFrom(b);
    return txPowerDbm - m_trace.GetPathLossDb(requestedDistance);
}

int64_t
QuadrigaTracePropagationLossModel::DoAssignStreams(int64_t)
{
    return 0;
}

} // namespace industrial
} // namespace ns3
