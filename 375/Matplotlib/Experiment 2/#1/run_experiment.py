#!/usr/bin/env python3
"""Run Experiment 2/#1: the bounded primitive-cube search for 10^17 <= n <= 10^20.

Examples (the script works from any current directory):
  python3 run_experiment.py
  python3 run_experiment.py --no-window
  python3 run_experiment.py --out ./fresh-run --save-prefix ./figures/experiment
  python3 run_experiment.py --plan-only --show-command
  python3 run_experiment.py --view-recorded
  python3 run_experiment.py --plot-only ./fresh-run

The search uses the unchanged sibling elkies375 package. An existing output
directory resumes its campaign; use a new empty --out directory to reproduce
the initial 43-task assignment. Those 43 tasks are a bounded pilot, not a
complete search of every integer n in the interval. The 64 displayed n slices
show real geometry and do not establish search coverage.

Viewing a recorded campaign performs no search and does not rewrite its
checkpoints or summaries. --save-prefix exports figures separately and
suppresses windows. Compiler/GMP settings are inherited by the shared backend.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import shlex
import sys


HERE = Path(__file__).resolve().parent
PACKAGE = (HERE.parent / "elkies375").resolve()
ENGINE = PACKAGE / "elkies375_lab.py"
N_MIN, N_MAX = 10**17, 10**20
TARGET = "primitive"
BAND_WIDTH, TILE_SCALE = 1000, "11/2"
MAX_TASKS, MAX_TILES = 43, 64
SCHEDULE, TASK_OFFSET = "spread", 0
GEOMETRY_SLICES = 64


def parser():
    result = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    result.add_argument("--out", type=Path,
                        help="Search output directory; default: run-output beside this script")
    result.add_argument("--no-window", action="store_true", help="Do not open Matplotlib windows")
    result.add_argument("--save-prefix", type=Path,
                        help="Export 2D, 3D and coverage figures; suppresses windows")
    result.add_argument("--plan-only", action="store_true", help="Write the plan without running native tasks")
    result.add_argument("--show-command", action="store_true",
                        help="Print the exact search/plan command and exit without writing files")
    views = result.add_mutually_exclusive_group()
    views.add_argument("--view-recorded", action="store_true",
                       help="Open the shared examples/large-pilot campaign without changing it")
    views.add_argument("--plot-only", type=Path, metavar="DIRECTORY",
                       help="Open a saved campaign without running or rewriting it")
    return result


def resolved(path):
    return path.expanduser().resolve()


def outside(path, protected, description):
    if path == protected or protected in path.parents:
        raise ValueError(f"{description} must be outside the protected directory: {protected}")


def search_arguments(args, output, prefix):
    command = ["--engine", "elkies", "--n-min", str(N_MIN), "--n-max", str(N_MAX),
               "--target", TARGET, "--band-width", str(BAND_WIDTH), "--tile-scale", TILE_SCALE,
               "--max-tasks", str(MAX_TASKS), "--max-tiles", str(MAX_TILES),
               "--schedule", SCHEDULE, "--task-offset", str(TASK_OFFSET),
               "--geometry-slices", str(GEOMETRY_SLICES), "--out", str(output)]
    if args.no_window:
        command.append("--no-window")
    if args.plan_only:
        command.append("--plan-only")
    if prefix is not None:
        command.extend(("--save-prefix", str(prefix)))
    return command


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    viewing = args.view_recorded or args.plot_only is not None
    if viewing and (args.out is not None or args.plan_only or args.show_command):
        argument_parser.error("viewing options cannot be combined with --out, --plan-only or --show-command")
    output = resolved(args.out) if args.out is not None else HERE / "run-output"
    prefix = resolved(args.save_prefix) if args.save_prefix is not None else None
    if prefix is not None:
        outside(prefix, PACKAGE, "Figure export prefix")
    if not viewing:
        outside(output, PACKAGE, "Search output")
        command = search_arguments(args, output, prefix)
        if args.show_command:
            print(shlex.join([sys.executable, str(ENGINE), *command]))
            return 0
    if not ENGINE.is_file():
        raise FileNotFoundError(f"Shared engine missing: {ENGINE}. Keep #1 beside the complete elkies375 folder.")
    # Importing a read-only viewer should not create __pycache__ in its package.
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(PACKAGE))
    if viewing:
        directory = PACKAGE / "examples" / "large-pilot" if args.view_recorded else resolved(args.plot_only)
        if prefix is not None:
            outside(prefix, directory, "Read-only figure export prefix")
        print(f"Viewing saved campaign without changing its records: {directory}", flush=True)
        if args.no_window or prefix is not None:
            import matplotlib
            matplotlib.use("Agg")
        from plotting import plot_campaign
        paths = plot_campaign(directory, geometry_slices=GEOMETRY_SLICES,
                              save_prefix=prefix, show=not args.no_window and prefix is None)
        for label, path in paths.items():
            print(f"Saved {label}: {path}")
        return 0
    if (output / "manifest.json").exists():
        # The engine normally inherits a saved campaign's optional height
        # restriction. This fixed experiment must retain its full planned scope.
        import campaign
        manifest = campaign.load_manifest(output)
        if manifest["region"]["complete_height_scope"] is not True:
            raise ValueError("This experiment requires the full planned height scope. Use a new empty --out directory.")
    print(f"Experiment 2/#1: {N_MIN} <= n <= {N_MAX}; target={TARGET}.", flush=True)
    print(f"Up to {MAX_TASKS} tasks, {MAX_TILES} tiles per attempt; {GEOMETRY_SLICES} displayed geometry slices.", flush=True)
    print(f"Output: {output}\nExisting checkpoints resume. Use a new empty --out directory to repeat the initial 43-task assignment.", flush=True)
    from elkies375_lab import entry as engine_entry
    return engine_entry(command)


def entry(argv=None):
    try:
        return main(argv)
    except KeyboardInterrupt:
        print("\nStopped; previously completed campaign work remains saved.", file=sys.stderr)
        return 130
    except (ValueError, OSError, ArithmeticError, ImportError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(entry())
