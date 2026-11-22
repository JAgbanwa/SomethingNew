CXX ?= c++
CPPFLAGS ?= -I/usr/include/$(shell $(CXX) -dumpmachine)
CXXFLAGS ?= -O3 -std=gnu++17 -Wall -Wextra
LDFLAGS ?=
LDLIBS ?= -lpari -lgmpxx -lgmp

.PHONY: all clean test
all: bin/xy375_worker

bin/xy375_worker: src/xy375_worker.cpp src/fac128.h
	mkdir -p bin
	$(CXX) $(CPPFLAGS) $(CXXFLAGS) -Isrc $< $(LDFLAGS) $(LDLIBS) -o $@

clean:
	rm -f bin/xy375_worker

test: all
	python3 -m unittest discover -s tests -v
