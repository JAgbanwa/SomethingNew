#!/bin/sh
# Accept Docker argument-only use and CE's explicit in-container command.
set -eu
if [ "$#" -eq 0 ]; then
    exec /app/run_task.sh
fi
case "$1" in
    --*) exec /app/run_task.sh "$@" ;;
    *) exec "$@" ;;
esac
