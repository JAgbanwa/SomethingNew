#!/usr/bin/env python3
"""Actual rank-three Elkies/EJ search and Matplotlib views for the 375 equation.

Examples:
  python3 elkies375_lab.py --preset demo
  python3 elkies375_lab.py --n-min 100000000000000000 --n-max 100000000000000000000
  python3 elkies375_lab.py --plot-only elkies375-results
  python3 elkies375_lab.py --engine rational --n 13 --search-only

The native engine searches all integer cube-coordinate points within assigned
height/ratio regions, then maps them exactly to n,x,y. It does not sample n to
perform its search. Displayed n slices are continuous real geometry only.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys

import campaign
import equation
import region


@contextmanager
def campaign_lock(directory):
    """Prevent independent processes from overwriting each other's checkpoints."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory/"run.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as error:
        raise ValueError("This output directory has a run.lock. Another search may be active. Use another --out directory, or remove a stale lock only after checking the previous search has stopped.") from error
    try:
        with os.fdopen(descriptor, "w") as handle:
            handle.write(json.dumps({"pid": os.getpid(), "created_utc": campaign.utc_now()}))
        yield
    finally:
        lock.unlink(missing_ok=True)


def parser():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--engine", choices=("elkies", "rational"), default="elkies",
                   help="elkies: 3D integer-cube lattice; rational: separate fixed-n factor-pair engine")
    p.add_argument("--preset", choices=("large", "demo"), default="large")
    p.add_argument("--n-min", type=int, help="Inclusive integer n lower bound; default 10^17 (demo:1)")
    p.add_argument("--n-max", type=int, help="Inclusive integer n upper bound; default 10^20 (demo:5)")
    p.add_argument("--n", type=int, help="Set both n endpoints to one exact integer")
    p.add_argument("--target", choices=("primitive", "cubes"),
                   help="primitive filters gcd>1; cubes retains all integer lifts (demo default)")
    p.add_argument("--height-min", type=int, help="Optional inclusive coordinate magnitude restriction")
    p.add_argument("--height-max", type=int, help="Optional inclusive coordinate magnitude restriction")
    p.add_argument("--band-width", type=int, help="Logical ratio-index width; default 1000, not an x window")
    p.add_argument("--tile-scale", help="Exact positive rational controlling tile subdivision; default 11/2")
    p.add_argument("--max-tasks", type=int, default=12, help="Maximum actual native tasks attempted in this invocation")
    p.add_argument("--max-tiles", type=int, default=64, help="Tiles per task attempt; 0 removes this limit")
    p.add_argument("--schedule", choices=("spread", "sequential"), default="spread",
                   help="Spread across height shells or page through logical task indices")
    p.add_argument("--task-offset", type=int, default=0,
                   help="Sequential starting task index; in spread mode shifts each selected band")
    p.add_argument("--out", type=Path, help="Checkpoint directory; default elkies375-results (demo:elkies375-demo)")
    p.add_argument("--plan-only", action="store_true", help="Write the exact finite plan without running any native task")
    p.add_argument("--plot-only", type=Path, metavar="DIRECTORY", help="Open an existing campaign without compiling or searching")
    p.add_argument("--geometry-slices", type=int, default=64,
                   help="Number of real-geometry n slices drawn; does not change search coverage")
    p.add_argument("--save-prefix", type=Path, help="Save 2D,3D and coverage figures without opening windows")
    p.add_argument("--no-window", "--search-only", action="store_true", help="Run/checkpoint without opening Matplotlib windows")
    p.add_argument("--check", nargs=2, type=int, metavar=("N", "X"),
                   help="Exactly test one integer (n,x) for rational y, without a search")
    return p


def print_summary(value):
    print(json.dumps(value, indent=2))
    if value["complete_target_search_in_n_interval"]:
        print("The complete finite region for the requested integer-cube target was searched.")
    else:
        print("Only the recorded completed height/ratio regions were searched; the full n-interval search is unfinished.")
    print("General rational-only points require --engine rational or an exact individual --check.")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    # Preserve the full established rational engine CLI rather than pretending
    # that an integer-t lattice enumerates every rational-only point.
    first = argparse.ArgumentParser(add_help=False)
    first.add_argument("--engine", choices=("elkies", "rational"), default="elkies")
    mode, rest = first.parse_known_args(argv)
    if mode.engine == "rational":
        import rational_core
        print("Engine: fixed-n exact rational factor pairs (separate from the 3D Elkies integer-cube lattice).")
        return rational_core.main(rest)
    args = parser().parse_args(argv)
    if args.geometry_slices < 1 or args.max_tasks < 1 or args.max_tiles < 0 or args.task_offset < 0:
        raise ValueError("geometry-slices/max-tasks must be positive; max-tiles/task-offset must be nonnegative")
    if args.check:
        point = equation.rational_point_at(*args.check)
        if point is None:
            print("No rational y exists at this exact integer (n,x).")
        else:
            print(json.dumps(point, indent=2))
            print("Both signs of y satisfy the equation; y=0 is counted once.")
        return 0
    if args.plot_only:
        directory = args.plot_only
        manifest = campaign.load_manifest(directory)
        area = campaign.region_from_manifest(manifest)
        summary = campaign.summarize(directory, manifest, area)
        print_summary(summary)
    else:
        directory = args.out or Path("elkies375-demo" if args.preset == "demo" else "elkies375-results")
        path = directory/"manifest.json"
        old = campaign.load_manifest(directory) if path.exists() else None
        default_min, default_max = (1,5) if args.preset == "demo" else (10**17,10**20)
        n_min = args.n_min if args.n_min is not None else int(old["n_min"]) if old else default_min
        n_max = args.n_max if args.n_max is not None else int(old["n_max"]) if old else default_max
        if args.n is not None:
            if args.n_min is not None or args.n_max is not None:
                raise ValueError("use --n or --n-min/--n-max, not both")
            n_min = n_max = args.n
        h_min = args.height_min if args.height_min is not None else int(old["region"]["height_min"]) if old else None
        h_max = args.height_max if args.height_max is not None else int(old["region"]["height_max"]) if old else None
        target = args.target or (old["target"] if old else "cubes" if args.preset == "demo" else "primitive")
        width = args.band_width if args.band_width is not None else int(old["band_width"]) if old else 1000
        scale = args.tile_scale or (old["tile_scale"] if old else "11/2")
        area = region.make_region(n_min, n_max, h_min, h_max)
        with campaign_lock(directory):
            manifest = campaign.ensure_manifest(directory, area, band_width=width, tile_scale=scale, target=target)
            print(f"Requested integer n interval: {n_min} .. {n_max}")
            print(f"Derived canonical coordinate height bound: {area.canonical_height_max}")
            print(f"Logical height/ratio tasks in the plan: {manifest['planned_task_count']}")
            if args.plan_only:
                summary = campaign.summarize(directory, manifest, area)
            else:
                summary = campaign.run(directory, manifest, area, max_tasks=args.max_tasks,
                                       max_tiles=args.max_tiles, schedule=args.schedule, offset=args.task_offset)
            print_summary(summary)
    if args.save_prefix or (not args.no_window and not args.plan_only):
        if args.save_prefix or args.no_window:
            import matplotlib
            matplotlib.use("Agg")
        from plotting import plot_campaign
        paths = plot_campaign(directory, geometry_slices=args.geometry_slices,
                              save_prefix=args.save_prefix,
                              show=not args.no_window and not args.save_prefix)
        if paths:
            print("Saved figures:")
            for label, path in paths.items():
                print(f"  {label}: {path}")
    return 0


def entry(argv=None):
    """Consistent terminal errors for the direct and historical entry points."""
    try:
        return main(argv)
    except KeyboardInterrupt:
        print("\nStopped. An interrupted native attempt cannot advance certified coverage; completed earlier attempts remain saved.", file=sys.stderr)
        return 130
    except (ValueError, OSError, ArithmeticError, campaign.ej_backend.EJWorkerError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(entry())
