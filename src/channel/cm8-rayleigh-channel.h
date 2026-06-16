#ifndef CM8_RAYLEIGH_CHANNEL_H
#define CM8_RAYLEIGH_CHANNEL_H

#include "ns3/propagation-loss-model.h"
#include "ns3/random-variable-stream.h"
#include "ns3/nstime.h"

namespace ns3
{
namespace industrial
{

// References (see BIBLIOGRAPHY.md / paper.bib for the full entries):
//   [Mol09] Molisch et al., "A Comprehensive Standardized Model for UWB
//           Propagation Channels", IEEE TAP 57(11):3151-3166, 2009.
//   [Mol04] Molisch et al., IEEE 802.15-04/0662-04-004a "Channel Model Final
//           Report", 2004. CM8 = industrial NLOS, n=2.15, sigma_S=6 dB,
//           PL0=56.7 dB at d0=1 m, validity 1-10 m.
//   [Tan08] Tanghe et al., "The industrial indoor channel at 900, 2400 and
//           5200 MHz", IEEE TWC 7(7):2740-2751, 2008. Source for the
//           one-slope + log-normal SF model used at 5.18 GHz.
//   [3GPP38901] 3GPP TR 38.901 §7.4.1 Indoor Factory NLOS. Modern alternative
//           to CM8; this same C++ engine drives `inf_nlos_dl` via the
//           InF-DL parameter set documented in
//           configs/channels/inf_nlos_dl_5ghz.yaml.
//
// The struct below is a generic *log-distance + log-normal shadowing + optional
// Rayleigh* configuration. Calling it "Cm8RayleighConfig" is a historical name;
// at 5.18 GHz with the InF-DL parameter set this same engine implements the
// 3GPP InF NLOS model exactly. See `inf_nlos_dl_5ghz.yaml` and `cm8_strict_nlos.yaml`
// for two literature-faithful presets, and `cm8_rayleigh_20mhz.yaml` for the
// lighter engineering proxy shipped historically with this repository.
struct Cm8RayleighConfig
{
    double carrierFrequencyHz{5.18e9};
    double bandwidthHz{20e6};
    double maxDistanceM{6.0};
    double txPowerDbm{18.0};
    double noiseFigureDb{7.0};
    double pathLossExponent{2.2};
    double referenceLossDb{43.0};
    double referenceDistanceM{1.0};
    double shadowingStdDb{2.0};
    bool rayleighFading{true};
    double coherenceTimeMs{5.0};
    // Temporal-correlation model for the small-scale fading process.
    //   "block" : historical piecewise-constant block fading. The fading
    //             sample is held for `coherenceTimeMs` then redrawn independent.
    //             Default, so all pre-existing archives stay bit-reproducible.
    //   "ar1"   : first-order auto-regressive / Ornstein-Uhlenbeck process
    //             sampled at the actual access instants:
    //               x(t2) = rho*x(t1) + sqrt(1-rho^2)*eps,  rho = exp(-dt/Tc).
    //             Shadowing (Gaussian in dB) and the Rayleigh complex envelope
    //             are each evolved as OU processes so that the *temporal*
    //             autocorrelation is monotone in `coherenceTimeMs` (larger Tc
    //             -> slower decorrelation). This is a documented engineering
    //             correlation model, NOT a calibrated 802.11ax PHY.
    std::string correlationModel{"block"};
    // Uniform sampling period (us) used by the standalone channel-trace probe
    // (EmitChannelTrace) when estimating the autocorrelation R_gamma(tau).
    double channelUpdatePeriodUs{50.0};
    // Dedicated RNG seed for the fading process. 0 -> derive from the run seed.
    uint32_t fadingSeed{0};
    double industrialExcessLossDb{3.0};
    double receiverSensitivityDbm{-95.0};
    double packetDetectionThresholdDbm{-90.0};
};

double CalculateCm8PathLossDb(double distanceM, const Cm8RayleighConfig& config);
double CalculateNoiseFloorDbm(double bandwidthHz, double noiseFigureDb);

class Cm8RayleighPropagationLossModel : public PropagationLossModel
{
  public:
    static TypeId GetTypeId();
    Cm8RayleighPropagationLossModel();

    void SetConfig(const Cm8RayleighConfig& config);
    const Cm8RayleighConfig& GetConfig() const;

  private:
    double DoCalcRxPower(double txPowerDbm,
                         Ptr<MobilityModel> a,
                         Ptr<MobilityModel> b) const override;
    int64_t DoAssignStreams(int64_t stream) override;

    Cm8RayleighConfig m_config;
    Ptr<NormalRandomVariable> m_shadowing;
    Ptr<ExponentialRandomVariable> m_rayleighPower;
    mutable Time m_nextFadingSample{Seconds(0)};
    mutable double m_cachedFadingDb{0.0};
};

} // namespace industrial
} // namespace ns3

#endif // CM8_RAYLEIGH_CHANNEL_H
