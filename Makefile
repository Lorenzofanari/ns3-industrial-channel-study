CXX ?= g++
CXXFLAGS ?= -std=c++20 -O2 -Wall -Wextra
CPPFLAGS += -I/usr/include -Isrc
LDFLAGS += -L/usr/lib/x86_64-linux-gnu
LDLIBS += -lns3-applications -lns3-wifi -lns3-internet -lns3-mobility -lns3-network -lns3-propagation -lns3-spectrum -lns3-core

SRC := \
  src/industrial-wifi-sim.cc \
  src/study-parameters.cc \
  src/channel/cm8-rayleigh-channel.cc \
  src/channel/quadriga-channel-importer.cc \
  src/channel/channel-abstraction.cc \
  src/core-harness/core-harness.cc \
  src/metrics/metrics-collector.cc \
  src/metrics/safety-metrics.cc \
  src/metrics/antijamming-metrics.cc \
  src/traffic/periodic-control-app.cc \
  src/jammer/constant-jammer.cc \
  src/jammer/reactive-jammer.cc

TARGET := build/industrial-wifi-sim
TEST_TARGET := build/study-parameter-tests

.PHONY: all clean test

all: $(TARGET) $(TEST_TARGET)

$(TARGET): $(SRC)
	mkdir -p $(dir $@)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $^ -o $@ $(LDFLAGS) $(LDLIBS)

TEST_SRC := \
  tests/study-parameter-tests.cc \
  src/study-parameters.cc \
  src/core-harness/core-harness.cc \
  src/channel/cm8-rayleigh-channel.cc \
  src/channel/quadriga-channel-importer.cc \
  src/metrics/metrics-collector.cc \
  src/metrics/safety-metrics.cc \
  src/metrics/antijamming-metrics.cc

$(TEST_TARGET): $(TEST_SRC)
	mkdir -p $(dir $@)
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $(TEST_SRC) -o $@ $(LDFLAGS) $(LDLIBS)

test: $(TEST_TARGET)
	./$(TEST_TARGET)

clean:
	rm -rf build
