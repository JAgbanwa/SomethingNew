#!/bin/sh
# Default: run the task staged at /local/input/task.json into /local/output.
# Any arguments are passed to run_task.py instead (e.g. --task ... --output-dir ...).
set -eu
if [ "$#" -eq 0 ]; then
    exec python3 /app/run_task.py --task /local/input/task.json --output-dir /local/output
fi
case "$1" in
    --*) exec python3 /app/run_task.py "$@" ;;
    *)   exec "$@" ;;
esac
