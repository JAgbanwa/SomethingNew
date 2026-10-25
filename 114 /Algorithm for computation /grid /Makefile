# Build the grid programs and run their self tests.   make; make test; make validate
CC ?= cc
CFLAGS ?= -O3

all: dsweep dsmooth xscan xroots

dsweep: dsweep.c filter.h local.h
	$(CC) $(CFLAGS) -o $@ dsweep.c -lm
dsmooth: dsmooth.c filter.h local.h
	$(CC) $(CFLAGS) -o $@ dsmooth.c -lm -lquadmath
xscan: xscan.c
	$(CC) $(CFLAGS) -o $@ xscan.c -lm
xroots: xroots.c local.h
	$(CC) $(CFLAGS) -o $@ xroots.c -lm

test: all
	./selftest.sh

validate: all
	python3 validate.py

clean:
	rm -f dsweep dsmooth xscan xroots

.PHONY: all test validate clean
