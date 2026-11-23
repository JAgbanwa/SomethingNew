#!/usr/bin/env python3
"""Reproducible, bounded calibration of the public native Booker search.

This runs actual target-375 searches at low, medium and high D. The extended
low interval defaults to 100 million D values, with a 30-second native budget
and a 45-second process-group limit. Completed/partial scopes are recorded
exactly. These local timings are not a forecast for an entire campaign.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

import search375
from booker_native import build_worker

ROOT = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--width", type=search375.positive_int, default=1048576)
    parser.add_argument("--extended-count", type=search375.positive_int, default=100000000)
    parser.add_argument("--deadline-seconds", type=search375.positive_int, default=30)
    parser.add_argument("--wall-timeout", type=search375.positive_int, default=45)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output already exists")
    if args.width > 10**12:
        parser.error("width must be at most 10^12")
    worker = build_worker()
    samples = []
    intervals = [("low", 1, 1 + args.width),
                 ("middle", 10**9, 10**9 + args.width),
                 ("high", 10**12 - args.width + 1, 10**12 + 1),
                 ("extended_low", 1, 1 + args.extended_count)]
    for name, start, stop in intervals:
        argv = ["booker-gap", "--D-start", str(start), "--D-stop", str(stop),
                "--ratio-max", "1024", "--chunk", "65536", "--progress-every", "0",
                "--deadline-seconds", str(args.deadline_seconds)]
        print(f"calibrating {name}: D in [{start}, {stop})", file=sys.stderr, flush=True)
        began = time.perf_counter()
        process = subprocess.Popen([sys.executable, str(ROOT / "search375.py"), *argv],
                                   cwd=ROOT, text=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, start_new_session=True)
        timed_out = False
        try:
            stdout, stderr = process.communicate(timeout=args.wall_timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                stdout, stderr = process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                stdout, stderr = process.communicate()
        seconds = time.perf_counter() - began
        rows = [json.loads(line) for line in stdout.splitlines()]
        valid = (not timed_out and process.returncode in (0, 3) and len(rows) >= 2
                 and rows[0].get("type") == "start" and rows[-1].get("type") == "end"
                 and rows[-1].get("complete") is (process.returncode == 0))
        samples.append({"name": name, "argv": argv, "seconds_including_python_start": seconds,
                        "returncode": process.returncode, "timed_out": timed_out,
                        "accepted_coverage": valid, "records": rows, "stderr": stderr})
        print(f"  exit={process.returncode}; seconds={seconds:.6f}; coverage accepted={valid}",
              file=sys.stderr, flush=True)
    report = {"schema": "algorithm-ii-native-booker-calibration-v1", "target": "375",
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "python": platform.python_version(), "platform": platform.platform(),
              "source_sha256": search375.source_hashes(),
              "build": json.loads(worker.with_suffix(".build.json").read_text()),
              "notes": ["Single-run local samples, not stable throughput forecasts.",
                        "Low and extended-low intervals overlap; do not add their coverage.",
                        "Native deadlines are checked after completed chunks.",
                        "Each timed-out process group supplies no accepted coverage."],
              "samples": samples}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return 0 if all(sample["accepted_coverage"] for sample in samples) else 2


if __name__ == "__main__":
    sys.exit(main())
