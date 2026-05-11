CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra
CPPFLAGS += -I/usr/include -Isrc
LDFLAGS += -L/usr/lib/x86_64-linux-gnu
LDLIBS += -lns3-applications -lns3-wifi -lns3-internet -lns3-mobility -lns3-network -lns3-propagation -lns3-spectrum -lns3-core

SRC := \
  src/industrial-wifi-sim.cc \
  src/channel/cm8-rayleigh-channel.cc \
  src/channel/quadriga-channel-importer.cc \
  src/channel/channel-abstraction.cc \
  src/metrics/metrics-collector.cc \
  src/metrics/safety-metrics.cc \
  src/metrics/antijamming-metrics.cc \
  src/traffic/periodic-control-app.cc \
  src/jammer/constant-jammer.cc \
  src/jammer/reactive-jammer.cc

TARGET := build/industrial-wifi-sim

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	mkdir -p $(dir $@)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@ $(LDFLAGS) $(LDLIBS)

clean:
	rm -rf build
