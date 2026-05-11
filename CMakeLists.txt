cmake_minimum_required(VERSION 3.16)
project(ns3_industrial_channel_study CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

include_directories(/usr/include)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/src)

add_executable(industrial-wifi-sim
  src/industrial-wifi-sim.cc
  src/channel/cm8-rayleigh-channel.cc
  src/channel/quadriga-channel-importer.cc
  src/channel/channel-abstraction.cc
  src/metrics/metrics-collector.cc
  src/metrics/safety-metrics.cc
  src/metrics/antijamming-metrics.cc
  src/traffic/periodic-control-app.cc
  src/jammer/constant-jammer.cc
  src/jammer/reactive-jammer.cc
)

target_link_libraries(industrial-wifi-sim
  ns3-applications
  ns3-wifi
  ns3-internet
  ns3-mobility
  ns3-network
  ns3-propagation
  ns3-spectrum
  ns3-core
)

