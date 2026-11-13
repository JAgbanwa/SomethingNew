CC ?= cc
CFLAGS ?= -O3 -Wall -Wextra -Wno-unused-function
LDLIBS ?= -lecm -lgmp -lm

.PHONY: all test clean
all: bin/rd_worker bin/brute

bin/rd_worker: src/rd_worker.c src/fac128.h
	mkdir -p bin
	$(CC) $(CFLAGS) $< -o $@ $(LDLIBS)

bin/brute: tests/brute.c
	mkdir -p bin
	$(CC) $(CFLAGS) $< -o $@ -lm

test: all
	sh tests/run_tests.sh

clean:
	rm -rf bin
