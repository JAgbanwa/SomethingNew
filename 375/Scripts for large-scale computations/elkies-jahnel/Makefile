CXX ?= c++
CPPFLAGS ?=
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDFLAGS ?=
LDLIBS ?= -lgmpxx -lgmp

.PHONY: all test clean
all: bin/elkies375_worker

bin/elkies375_worker: src/elkies375_worker.cpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

test: all
	python3 -m unittest discover -s tests -v

clean:
	rm -f bin/elkies375_worker
