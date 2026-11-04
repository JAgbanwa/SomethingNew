CXX ?= c++
CPPFLAGS ?=
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDFLAGS ?=
LDLIBS ?= -lgmpxx -lgmp

.PHONY: all clean test
all: bin/thue192_worker

bin/thue192_worker: src/thue192_worker.cpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -f bin/thue192_worker

test: all
	python3 -m unittest discover -s tests -v
