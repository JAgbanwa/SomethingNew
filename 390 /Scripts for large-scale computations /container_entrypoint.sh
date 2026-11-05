#!/bin/sh
# Default: run the task staged at /local/input/task.json into /local/output.
# The runner is chosen by the task's schema: gap-search tasks (GAP_SEARCH.md,
# the current production search) or d-first tasks (D_FIRST.md, historical).
# Explicit commands remain available for every historical engine.
set -eu
TASK=/local/input/task.json
runner() {
    if grep -q '"ce390-gap-task-v1"' "$TASK" 2>/dev/null; then echo /app/run_gap_task.py; else echo /app/run_d_task.py; fi
}
if [ "$#" -eq 0 ]; then
    exec python3 "$(runner)" --task "$TASK" --output-dir /local/output
fi
case "$1" in
    --*) exec python3 "$(runner)" --task "$TASK" --output-dir /local/output "$@" ;;
    *) exec "$@" ;;
esac
