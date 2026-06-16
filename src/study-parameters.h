#ifndef STUDY_PARAMETERS_H
#define STUDY_PARAMETERS_H

#include <cstdint>
#include <random>
#include <string>

namespace ns3
{
namespace industrial
{

enum class ChannelFidelity
{
    Proxy,
    ScalarGeometryTrace,
    CirCfrTrace,
};

// AP-side SNIR-estimate impairment configuration for S9/Realloc. Backed by
// section 4.5 ("Estimator-Impairment Profiles") of Fanari, "Resilient OFDMA
// Scheduling under Reactive Jamming..." 2026 [Fan26]. The ideal profile
// (default) corresponds to the upper-bound observability case in which the
// AP-side estimate coincides with the simulated per-packet SNIR; moderate and
// conservative profiles inject Gaussian SNIR noise, staleness, bias, and
// jammer-detection errors (missed detection, false alarm).
//
// All values default to zero so that:
//   - existing archives are bit-reproducible (no behaviour change unless the
//     operator explicitly enables a non-zero profile);
//   - rows always carry the impairment metadata in CSV (per the paper's Data
//     and Reproducibility Statement, section 9).
struct S9EstimatorConfig
{
    // Symbolic profile label exported to the CSV (`ideal`, `moderate`,
    // `conservative`, or `custom` when the operator overrides individual knobs
    // without naming a profile).
    std::string profile{"ideal"};
    // sigma of the zero-mean Gaussian SNIR-estimation noise eta_gamma(t), dB.
    double snirNoiseStdDb{0.0};
    // systematic SNIR estimation bias b_gamma, dB. Positive values mean the AP
    // over-estimates the channel quality (more critical-mask false negatives).
    double snirBiasDb{0.0};
    // staleness Delta t expressed in OFDM symbols. The AP uses the SNIR from
    // `Delta_t` symbols in the past as the observation feeding the critical
    // mask. 0 disables staleness (ideal).
    uint32_t snirStalenessSlots{0};
    // Probability that the AP-side jammer-exposure detector misses an active
    // jammer slot (P_md). 0 = perfect jammer indication (ideal).
    double jammerMissedDetProb{0.0};
    // Probability that the AP-side detector raises a false jammer alarm on a
    // clean slot (P_fa). 0 = perfect indication (ideal).
    double jammerFalseAlarmProb{0.0};
    // Critical-mask thresholds used by S9 once the AP's estimate is in hand.
    // These follow Algorithm 1 in [Fan26]; the defaults are conservative but
    // not aggressive: PER_crit = 10% mirrors the standard reliability target;
    // gamma_out = 0 dB is below the BPSK saturation knee and serves as a hard
    // floor independently of the per-MCS waterfall sigmoid.
    double perCrit{0.10};
    double gammaOutDb{0.0};
};

// S9 ablation switches: section 6.8 of [Fan26] enumerates four variants used
// to attribute the gain of full S9 to its individual components. Each `true`
// disables that contribution to the critical mask / cooldown logic.
struct S9AblationConfig
{
    bool disableJammerFlag{false};   // ignore the AP-side jammer-exposure flag
    bool disableCooldown{false};     // run S9 without the 76-symbol anti-oscillation guard
    bool disableSnirMargin{false};   // skip the gamma_hat < gamma_out check
    bool disablePerMargin{false};    // skip the PER_hat > PER_crit check
};

// Master switch for the paper's Algorithm 1 critical-mask defer. Default false
// preserves the historical archive behaviour (cooldown-on-failure only). When
// true, S9 evaluates the AP-side estimate before each transmission attempt and
// proactively defers (= inserts a cooldown delay before attempt 0) if the
// critical mask fires. This is required to populate the estimator-sensitivity
// (Tab. 10) and ablation (Tab. 11) campaigns of the paper.
struct S9ProactiveDeferConfig
{
    bool enabled{false};
};

// Per-MCS waterfall midpoint and shared slope of the logistic PHY abstraction
// PER(gamma) = max(floor, 1 / (1 + exp(slope * (gamma - theta_m)))).
// Calibration source: AWGN PER curves from the TGax evaluation methodology
// [TGax571] cross-checked against the RBIR PHY abstraction in [Iyy22] and the
// HE-MCS rate table in [Kho19]. Values are exposed as CLI flags so reviewers
// can rerun the campaign with a different fit. See BIBLIOGRAPHY.md.
struct PerWaterfallConfig
{
    double thetaBpskDb{3.0};
    double thetaQpskDb{6.0};
    double theta16QamDb{15.5};
    double slope{1.15};
    double floor{1e-8};
};

struct EveEstimationConfig
{
    double biasDb{0.0};
    double noiseStdDb{0.0};
    uint32_t delaySlots{0};
};

std::string ToString(ChannelFidelity fidelity);
ChannelFidelity ChannelFidelityForModel(const std::string& channelModel);
std::string ChannelDisplayName(const std::string& channelModel);

// Legacy (archive-facing) policy label. Kept stable for backwards
// compatibility with the published CSV archive of the paper [Fan26]: S0=NoPLS,
// S4=Baseline-PF, S8=PLS-RTX, S9=PLS-Realloc.
std::string PolicyLabel(const std::string& scenario);

// Paper-facing policy label. [Fan26] §4.2-4.3 explicitly renames PLS-RTX ->
// RTX-Assist and PLS-Realloc -> Realloc because the new evaluation validates
// reliability/resilience rather than information-theoretic secrecy capacity.
// Exported as a second CSV column `policy_paper_label` to keep both views
// available without breaking historical scripts.
std::string PaperPolicyLabel(const std::string& scenario);

std::string McsLabel(uint32_t mcs);
std::string McsModulation(uint32_t mcs);
std::string McsCodingRate(uint32_t mcs);
std::string ScenarioDefaultPolicy(const std::string& scenario);
std::string PolicyDisplayLabel(const std::string& policyOrScenario);
double CooldownSymbolsToMs(uint32_t symbols, double ofdmSymbolUs = 16.0);

double PerThetaForMcs(uint32_t mcs, const PerWaterfallConfig& config);
bool EveEstimationIdeal(const EveEstimationConfig& config);
double ApplyEveSnirEstimate(double gammaEDb, const EveEstimationConfig& config, std::mt19937& rng);

// Populate `out` from a named profile {ideal, moderate, conservative}; matches
// the impairment profiles in [Fan26] §4.5. Unknown names throw. The CLI also
// accepts `custom`, in which case the operator is expected to set the
// individual knobs and this helper is not used.
//   - ideal       : zero noise / bias / staleness / P_md / P_fa.
//   - moderate    : sigma_eta = 1.0 dB, 1-slot staleness, P_md = P_fa = 0.05.
//   - conservative: sigma_eta = 3.0 dB, 4-slot staleness, P_md = 0.20,
//                   P_fa = 0.10.
// Bias is left at 0 unless overridden, since the paper Eq. (6) treats bias as
// an independent dimension.
void ApplyS9EstimatorProfile(const std::string& profile, S9EstimatorConfig& out);

// True if no S9-component is disabled. Convenience for telemetry / CSV
// serialisation.
bool S9AblationIdeal(const S9AblationConfig& cfg);

// One-shot helper that converts the inputs of Algorithm 1 (true SNIR observed
// `staleness` symbols ago, true jammer-active flag) into the AP-side estimate
// pair (gamma_hat, J_hat). The function intentionally has no side effects on
// the harness flow: it draws the noise/Bernoulli samples and returns the
// estimate, so the caller can decide whether to act on it.
struct S9Estimate
{
    double gammaHatDb;
    bool jammerFlagHat;
};
S9Estimate
ComputeS9Estimate(double trueGammaDb, bool trueJammerActive, const S9EstimatorConfig& cfg,
                  std::mt19937& rng);

} // namespace industrial
} // namespace ns3

#endif // STUDY_PARAMETERS_H
