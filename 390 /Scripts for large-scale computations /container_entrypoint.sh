#!/bin/sh
# The current target is the d-first half-integer search. Explicit legacy
# commands remain available for reproducing their historical task definitions.
set -eu
if [ "$#" -eq 0 ]; then
    exec python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output
fi
case "$1" in
    --*) exec python3 /app/run_d_task.py --task /local/input/task.json --output-dir /local/output "$@" ;;
    *) exec "$@" ;;
esac
