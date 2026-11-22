#!/bin/sh
# Charity Engine entry point: the task is staged at /local/input/task.json and
# everything under /local/output is returned.
set -eu
exec python3 /app/run_task.py --task "${CE375_TASK:-/local/input/task.json}" --output-dir "${CE375_OUTPUT:-/local/output}" "$@"
