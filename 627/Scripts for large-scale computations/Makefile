CXX ?= c++
CPPFLAGS ?=
CXXFLAGS ?= -O3 -std=c++17 -Wall -Wextra -Wpedantic
LDFLAGS ?=
LDLIBS ?= -lgmpxx -lgmp

.PHONY: all clean test
all: bin/thue627_worker

bin/thue627_worker: src/thue627_worker.cpp
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) $< $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -f bin/thue627_worker

test: all
	python3 -m unittest discover -s tests -v
