#include "channel/channel-abstraction.h"
#include "jammer/constant-jammer.h"
#include "jammer/reactive-jammer.h"
#include "metrics/metrics-collector.h"
#include "traffic/periodic-control-app.h"

#include "ns3/applications-module.h"
#include "ns3/core-module.h"
#include "ns3/internet-module.h"
#include "ns3/mobility-module.h"
#include "ns3/network-module.h"
#include "ns3/propagation-delay-model.h"
#include "ns3/version.h"
#include "ns3/wifi-net-device.h"
#include "ns3/wifi-module.h"
#include "ns3/wifi-remote-station-manager.h"
#include "ns3/yans-wifi-channel.h"
#include "ns3/yans-wifi-helper.h"

#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>

using namespace ns3;
using namespace ns3::industrial;

namespace
{

std::string
DataModeFor(uint32_t mcs, const std::string& standard)
{
    if (standard == "80211be")
    {
        return "EhtMcs" + std::to_string(mcs);
    }
    return "HeMcs" + std::to_string(mcs);
}

std::string
GetGitCommit()
{
    const char* env = std::getenv("GIT_COMMIT");
    if (env && std::string(env).size() > 0)
    {
        return env;
    }
    return "unknown";
}

double
NominalRxPowerDbm(double txPowerDbm, double pathLossDb)
{
    return txPowerDbm - pathLossDb;
}

void
SetScenarioDefaults(const std::string& scenario, uint32_t& retryLimit)
{
    if (scenario == "S8")
    {
        retryLimit = std::max(retryLimit, 9u);
    }
    else if (scenario == "S9")
    {
        retryLimit = std::max(retryLimit, 11u);
    }
}

} // namespace

int
main(int argc, char* argv[])
{
    std::string scenario = "S4";
    std::string channelModel = "cm8_rayleigh";
    std::string standard = "80211ax";
    std::string jammerMode = "none";
    std::string output = "results/one_run.csv";
    std::string jsonOutput = "results/one_run.json";
    std::string tracePath = "data/quadriga/example_trace.csv";
    uint32_t seed = 1;
    uint32_t mcs = 0;
    uint32_t payloadBits = 128;
    uint32_t packets = 1000;
    uint32_t retryLimit = 7;
    double distanceM = 1.0;
    double jammerPowerDbm = 10.0;
    double jammerDistanceM = 1.0;
    double txPowerDbm = 18.0;
    double noiseFigureDb = 7.0;
    double bandwidthMHz = 20.0;
    double simTimeS = 10.0;
    double warmupS = 1.0;
    double intervalMs = 10.0;
    double deadlineMs = 10.0;
    double pathLossExponent = 2.2;
    double referenceLossDb = 43.0;
    double shadowingStdDb = 2.0;
    double coherenceTimeMs = 5.0;
    double industrialExcessLossDb = 3.0;
    bool rayleighFading = true;

    CommandLine cmd(__FILE__);
    cmd.AddValue("scenario", "Scenario label: S4, S8 or S9", scenario);
    cmd.AddValue("channelModel", "Channel model: cm8_rayleigh or quadriga_raytraced", channelModel);
    cmd.AddValue("standard", "Wi-Fi standard: 80211ax or 80211be", standard);
    cmd.AddValue("mcs", "MCS index, supported study values: 0, 1, 3", mcs);
    cmd.AddValue("payloadBits", "Application payload size in bits", payloadBits);
    cmd.AddValue("distanceM", "STA-AP distance in meters", distanceM);
    cmd.AddValue("jammerMode", "none, constant or reactive", jammerMode);
    cmd.AddValue("jammerPowerDbm", "Jammer transmit power in dBm", jammerPowerDbm);
    cmd.AddValue("jammerDistanceM", "Jammer-AP nominal distance in meters", jammerDistanceM);
    cmd.AddValue("seed", "RNG seed", seed);
    cmd.AddValue("packets", "Number of control packets to transmit", packets);
    cmd.AddValue("retryLimit", "Wi-Fi long/short retry limit metadata", retryLimit);
    cmd.AddValue("txPowerDbm", "STA/AP transmit power in dBm", txPowerDbm);
    cmd.AddValue("noiseFigureDb", "Receiver noise figure in dB", noiseFigureDb);
    cmd.AddValue("bandwidthMHz", "Channel bandwidth in MHz", bandwidthMHz);
    cmd.AddValue("simTimeS", "Maximum simulation time in seconds", simTimeS);
    cmd.AddValue("warmupS", "Application start time in seconds", warmupS);
    cmd.AddValue("intervalMs", "Periodic control interval in ms", intervalMs);
    cmd.AddValue("deadlineMs", "Safety deadline in ms", deadlineMs);
    cmd.AddValue("tracePath", "QuaDRiGa/ray-traced CSV path", tracePath);
    cmd.AddValue("pathLossExponent", "CM8-like path loss exponent", pathLossExponent);
    cmd.AddValue("referenceLossDb", "CM8-like reference loss in dB at 1 m", referenceLossDb);
    cmd.AddValue("shadowingStdDb", "CM8-like log-normal shadowing standard deviation", shadowingStdDb);
    cmd.AddValue("coherenceTimeMs", "CM8-like fading coherence time in ms", coherenceTimeMs);
    cmd.AddValue("industrialExcessLossDb", "CM8-like industrial excess loss in dB", industrialExcessLossDb);
    cmd.AddValue("rayleighFading", "Enable CM8-like Rayleigh fading", rayleighFading);
    cmd.AddValue("output", "CSV output path", output);
    cmd.AddValue("jsonOutput", "JSON output path", jsonOutput);
    cmd.Parse(argc, argv);

    SetScenarioDefaults(scenario, retryLimit);

    if (mcs != 0 && mcs != 1 && mcs != 3)
    {
        throw std::runtime_error("This study only supports MCS 0, 1 and 3");
    }
    if (payloadBits % 8 != 0)
    {
        throw std::runtime_error("payloadBits must be divisible by 8");
    }
    if (standard != "80211ax" && standard != "80211be")
    {
        throw std::runtime_error("standard must be 80211ax or 80211be");
    }

    RngSeedManager::SetSeed(seed);
    RngSeedManager::SetRun(seed);

    Cm8RayleighConfig cm8;
    cm8.txPowerDbm = txPowerDbm;
    cm8.noiseFigureDb = noiseFigureDb;
    cm8.bandwidthHz = bandwidthMHz * 1e6;
    cm8.pathLossExponent = pathLossExponent;
    cm8.referenceLossDb = referenceLossDb;
    cm8.shadowingStdDb = shadowingStdDb;
    cm8.coherenceTimeMs = coherenceTimeMs;
    cm8.industrialExcessLossDb = industrialExcessLossDb;
    cm8.rayleighFading = rayleighFading;

    ChannelRuntimeConfig channelConfig;
    channelConfig.model = channelModel;
    channelConfig.distanceM = distanceM;
    channelConfig.tracePath = tracePath;
    channelConfig.cm8 = cm8;
    ChannelRuntimeSummary channelSummary;
    Ptr<PropagationLossModel> lossModel = CreateIndustrialPropagationLoss(channelConfig, channelSummary);
    lossModel->AssignStreams(seed * 1000);

    Ptr<YansWifiChannel> wifiChannel = CreateObject<YansWifiChannel>();
    wifiChannel->SetPropagationLossModel(lossModel);
    wifiChannel->SetPropagationDelayModel(CreateObject<ConstantSpeedPropagationDelayModel>());

    NodeContainer staNode;
    staNode.Create(1);
    NodeContainer apNode;
    apNode.Create(1);
    NodeContainer jammerNode;
    const bool jammerEnabled = jammerMode != "none";
    if (jammerEnabled)
    {
        jammerNode.Create(1);
    }

    MobilityHelper mobility;
    Ptr<ListPositionAllocator> positionAlloc = CreateObject<ListPositionAllocator>();
    positionAlloc->Add(Vector(distanceM, 0.0, 1.5));
    positionAlloc->Add(Vector(0.0, 0.0, 1.5));
    if (jammerEnabled)
    {
        positionAlloc->Add(Vector(jammerDistanceM, 1.0, 1.5));
    }
    NodeContainer allNodes;
    allNodes.Add(staNode);
    allNodes.Add(apNode);
    if (jammerEnabled)
    {
        allNodes.Add(jammerNode);
    }
    mobility.SetPositionAllocator(positionAlloc);
    mobility.SetMobilityModel("ns3::ConstantPositionMobilityModel");
    mobility.Install(allNodes);

    WifiHelper wifi;
    if (standard == "80211be")
    {
        wifi.SetStandard(WIFI_STANDARD_80211be);
    }
    else
    {
        wifi.SetStandard(WIFI_STANDARD_80211ax);
    }

    const std::string dataMode = DataModeFor(mcs, standard);
    const std::string controlMode = DataModeFor(0, standard);
    wifi.SetRemoteStationManager("ns3::ConstantRateWifiManager",
                                 "DataMode",
                                 StringValue(dataMode),
                                 "ControlMode",
                                 StringValue(controlMode));

    YansWifiPhyHelper phy;
    phy.SetChannel(wifiChannel);
    phy.Set("ChannelSettings", StringValue("{36, 20, BAND_5GHZ, 0}"));
    phy.Set("TxPowerStart", DoubleValue(txPowerDbm));
    phy.Set("TxPowerEnd", DoubleValue(txPowerDbm));
    phy.Set("RxNoiseFigure", DoubleValue(noiseFigureDb));
    phy.Set("RxSensitivity", DoubleValue(cm8.receiverSensitivityDbm));
    phy.SetErrorRateModel("ns3::TableBasedErrorRateModel");

    WifiMacHelper mac;
    Ssid ssid = Ssid("industrial-channel-study");

    mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
    NetDeviceContainer staDevice = wifi.Install(phy, mac, staNode);

    mac.SetType("ns3::ApWifiMac", "Ssid", SsidValue(ssid));
    NetDeviceContainer apDevice = wifi.Install(phy, mac, apNode);

    NetDeviceContainer jammerDevice;
    if (jammerEnabled)
    {
        phy.Set("TxPowerStart", DoubleValue(jammerPowerDbm));
        phy.Set("TxPowerEnd", DoubleValue(jammerPowerDbm));
        mac.SetType("ns3::StaWifiMac", "Ssid", SsidValue(ssid), "ActiveProbing", BooleanValue(false));
        jammerDevice = wifi.Install(phy, mac, jammerNode);
    }

    InternetStackHelper stack;
    stack.Install(allNodes);

    NetDeviceContainer allDevices;
    allDevices.Add(staDevice);
    allDevices.Add(apDevice);
    if (jammerEnabled)
    {
        allDevices.Add(jammerDevice);
    }
    for (uint32_t i = 0; i < allDevices.GetN(); ++i)
    {
        Ptr<WifiNetDevice> wifiDevice = DynamicCast<WifiNetDevice>(allDevices.Get(i));
        if (wifiDevice && wifiDevice->GetRemoteStationManager())
        {
            wifiDevice->GetRemoteStationManager()->SetMaxSlrc(retryLimit);
            wifiDevice->GetRemoteStationManager()->SetMaxSsrc(retryLimit);
        }
    }
    Ipv4AddressHelper address;
    address.SetBase("10.40.0.0", "255.255.255.0");
    Ipv4InterfaceContainer interfaces = address.Assign(allDevices);
    const Ipv4Address apAddress = interfaces.GetAddress(1);

    Ptr<MetricsCollector> collector = Create<MetricsCollector>();
    const uint16_t port = 9000;
    Ptr<ControlReceiverApp> receiver = CreateObject<ControlReceiverApp>();
    receiver->Configure(port, collector);
    apNode.Get(0)->AddApplication(receiver);
    receiver->SetStartTime(Seconds(0.0));
    receiver->SetStopTime(Seconds(simTimeS + warmupS + 1.0));

    Ptr<PeriodicControlApp> sender = CreateObject<PeriodicControlApp>();
    sender->Configure(InetSocketAddress(apAddress, port),
                      payloadBits / 8,
                      MilliSeconds(intervalMs),
                      packets,
                      collector);
    staNode.Get(0)->AddApplication(sender);
    sender->SetStartTime(Seconds(warmupS));
    sender->SetStopTime(Seconds(simTimeS + warmupS));

    const uint16_t jammerPort = 9001;
    Ptr<ControlReceiverApp> jammerSink = CreateObject<ControlReceiverApp>();
    jammerSink->Configure(jammerPort, Create<MetricsCollector>());
    apNode.Get(0)->AddApplication(jammerSink);
    jammerSink->SetStartTime(Seconds(0.0));
    jammerSink->SetStopTime(Seconds(simTimeS + warmupS + 1.0));

    if (jammerMode == "constant")
    {
        ConstantJammerConfig cfg;
        cfg.enabled = true;
        cfg.powerDbm = jammerPowerDbm;
        InstallConstantJammer(jammerNode,
                              apAddress,
                              jammerPort,
                              cfg,
                              Seconds(warmupS),
                              Seconds(simTimeS + warmupS));
    }
    else if (jammerMode == "reactive")
    {
        ReactiveJammerConfig cfg;
        cfg.enabled = true;
        cfg.powerDbm = jammerPowerDbm;
        InstallReactiveJammer(jammerNode,
                              apAddress,
                              jammerPort,
                              cfg,
                              Seconds(warmupS),
                              Seconds(simTimeS + warmupS));
    }
    else if (jammerMode != "none")
    {
        throw std::runtime_error("jammerMode must be none, constant or reactive");
    }

    Simulator::Stop(Seconds(simTimeS + warmupS + 1.0));
    Simulator::Run();

    RunContext context;
    context.gitCommit = GetGitCommit();
    context.ns3Version = Version::ShortVersion();
    context.seed = seed;
    context.scenario = scenario;
    context.channelModel = channelModel;
    context.channelAbstraction = channelSummary.abstraction;
    context.tracePath = channelSummary.tracePath;
    context.mcs = mcs;
    context.payloadBits = payloadBits;
    context.distanceM = distanceM;
    context.jammerMode = jammerMode;
    context.jammerPowerDbm = jammerEnabled ? jammerPowerDbm : 0.0;
    context.standard = standard;
    context.dataMode = dataMode;
    context.retryLimit = retryLimit;
    context.txPowerDbm = txPowerDbm;
    context.noiseFigureDb = noiseFigureDb;
    context.bandwidthMHz = bandwidthMHz;
    context.simulationTimeS = simTimeS;
    context.trafficIntervalS = intervalMs / 1000.0;
    context.deadlineS = deadlineMs / 1000.0;
    context.phyPerAvailable = false;
    context.perDefinition = "application_loss_proxy_until_phy_mac_traces_enabled";

    const double signalPowerDbm = NominalRxPowerDbm(txPowerDbm, channelSummary.nominalPathLossDb);
    const double noiseFloorDbm = CalculateNoiseFloorDbm(bandwidthMHz * 1e6, noiseFigureDb);
    const double jammerPathLossDb = channelModel == "cm8_rayleigh"
                                        ? CalculateCm8PathLossDb(jammerDistanceM, cm8)
                                        : channelSummary.nominalPathLossDb;
    const double jammerRxDbm = jammerEnabled ? jammerPowerDbm - jammerPathLossDb : -300.0;

    RunMetrics metrics = collector->Compute(context, signalPowerDbm, noiseFloorDbm, jammerRxDbm);
    WriteCsv(output, metrics);
    WriteJson(jsonOutput, metrics);

    Simulator::Destroy();
    return 0;
}
