#ifndef QUADRIGA_CHANNEL_IMPORTER_H
#define QUADRIGA_CHANNEL_IMPORTER_H

#include "ns3/propagation-loss-model.h"

#include <map>
#include <string>
#include <vector>

namespace ns3
{
namespace industrial
{

struct QuadrigaTap
{
    std::string txId;
    std::string rxId;
    double distanceM{0.0};
    double timeS{0.0};
    double pathLossDb{0.0};
    double delayS{0.0};
    double powerDb{0.0};
    double dopplerHz{0.0};
    double phaseRad{0.0};
    bool hasDoppler{false};
    bool hasPhase{false};
};

class QuadrigaTrace
{
  public:
    void Load(const std::string& path);
    void LoadCsv(const std::string& path);
    void LoadJson(const std::string& path);
    bool Empty() const;
    const std::vector<QuadrigaTap>& GetTaps() const;
    std::vector<double> GetDistances() const;
    double GetPathLossDb(double distanceM) const;
    double GetEffectiveDelayS(double distanceM) const;
    std::string GetSourcePath() const;

  private:
    std::vector<QuadrigaTap> m_taps;
    std::string m_sourcePath;
};

class QuadrigaTracePropagationLossModel : public PropagationLossModel
{
  public:
    static TypeId GetTypeId();
    QuadrigaTracePropagationLossModel();

    void SetTrace(const QuadrigaTrace& trace);
    void SetDistanceM(double distanceM);
    double GetConfiguredDistanceM() const;
    const QuadrigaTrace& GetTrace() const;

  private:
    double DoCalcRxPower(double txPowerDbm,
                         Ptr<MobilityModel> a,
                         Ptr<MobilityModel> b) const override;
    int64_t DoAssignStreams(int64_t stream) override;

    QuadrigaTrace m_trace;
    double m_distanceM{0.0};
};

} // namespace industrial
} // namespace ns3

#endif // QUADRIGA_CHANNEL_IMPORTER_H
