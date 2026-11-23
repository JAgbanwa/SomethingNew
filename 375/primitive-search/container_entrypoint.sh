#!/bin/sh
# A CE bundle uses both provisioned cores; a single task remains available for pilots.
set -eu
if [ "$#" -eq 0 ]; then
    if [ -f /local/input/bundle.json ]; then
        exec python3 /app/run_ce_bundle.py --manifest /local/input/bundle.json --output-dir /local/output
    fi
    exec python3 /app/run_gap_task.py --task /local/input/task.json --output-dir /local/output
fi
case "$1" in
    --*) exec python3 /app/run_gap_task.py --task /local/input/task.json --output-dir /local/output "$@" ;;
    *) exec "$@" ;;
esac
