PYTHON ?= python3

.PHONY: build test help

build:
	$(PYTHON) -c 'from elkies_jahnel import build_worker; print(build_worker())'

test: build
	$(PYTHON) -m unittest discover -s tests -v

help:
	$(PYTHON) search375.py --help
