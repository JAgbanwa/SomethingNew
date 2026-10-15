CXX ?= c++
CPPFLAGS ?=
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDFLAGS ?=
LDLIBS ?= -lgmpxx -lgmp

.PHONY: all clean test
all: bin/cf_worker bin/xy_cf_worker

bin/cf_worker: src/cf_worker.cpp src/q_sieve.hpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

bin/xy_cf_worker: src/xy_cf_worker.cpp src/q_sieve.hpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -f bin/cf_worker bin/xy_cf_worker

test: all
	python3 -m unittest discover -s tests -v
