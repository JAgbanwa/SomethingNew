CXX ?= c++
CPPFLAGS ?=
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDFLAGS ?=
LDLIBS ?= -lgmpxx -lgmp

.PHONY: all clean test
all: bin/cf_worker bin/rational_cf_worker

bin/cf_worker: src/cf_worker.cpp src/q_sieve.hpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

bin/rational_cf_worker: src/rational_cf_worker.cpp src/q_sieve.hpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -f bin/cf_worker bin/rational_cf_worker

test: all
	python3 -m unittest discover -s tests -v
