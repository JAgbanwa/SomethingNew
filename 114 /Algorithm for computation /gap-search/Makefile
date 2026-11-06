CXX ?= c++
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDLIBS ?= -lgmp

.PHONY: all clean test
all: bin/gap_worker

bin/gap_worker: src/gap_worker.cpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -f bin/gap_worker

test: all
	python3 -m unittest discover -s tests -v
