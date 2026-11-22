#!/bin/sh
# Default: run the gap-search task staged at /local/input/task.json into /local/output.
set -eu
if [ "$#" -eq 0 ]; then
    exec python3 /app/run_gap_task.py --task /local/input/task.json --output-dir /local/output
fi
case "$1" in
    --*) exec python3 /app/run_gap_task.py --task /local/input/task.json --output-dir /local/output "$@" ;;
    *) exec "$@" ;;
esac
