#!/usr/bin/env python3
"""Bounded, exact searches of the original radical equation for target 375.

Every public search enforces integer n, odd coprime X,Y and Y>0. See README.md
for mathematical scope, required compiler/GMP, rational-d bounds and examples.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Iterator, TextIO

import booker_sutherland as bs
from equation375 import (TARGET, Point, RationalDFilter, points_from_cubes,
                         validate_point)
import rational_d

ROOT = Path(__file__).resolve().parent
VERSION = "1.0.0"


def exact_fraction(text: str) -> Fraction:
    try:
        return Fraction(text)
    except (ValueError, ZeroDivisionError) as exc:
        raise argparse.ArgumentTypeError("use an exact rational such as -4/11") from exc


def positive_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use a positive decimal integer") from exc
    if value < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return value


def nonnegative_int(text: str) -> int:
    try:
        value = int(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("use a nonnegative decimal integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be nonnegative")
    return value


def source_hashes() -> dict[str, str]:
    names = ("search375.py", "equation375.py", "booker_sutherland.py",
             "rational_d.py", "elkies_jahnel.py", "ej_worker.cpp")
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
            for name in names}


def small_cube_box(bound: int, target: int = TARGET) -> Iterator[tuple[int, int, int]]:
    """Independent finite closure for the low heights outside the EJ theorem.

    Used only below 25 by the public Elkies search. This is deliberately not
    presented as the lattice algorithm or used as a substitute at large height.
    """
    if bound < 0:
        raise ValueError("box bound must be nonnegative")
    cubes = {v ** 3: v for v in range(-bound, bound + 1)}
    for a in range(-bound, bound + 1):
        for b in range(a, bound + 1):
            c = cubes.get(target - a ** 3 - b ** 3)
            if c is not None and b <= c:
                yield a, b, c


class Run:
    def __init__(self, args: argparse.Namespace, stream: TextIO) -> None:
        self.args, self.stream = args, stream
        self.started = time.monotonic()
        self.d_filter = RationalDFilter(
            values=None if not getattr(args, "d", None) else frozenset(args.d),
            minimum=getattr(args, "d_min", None),
            maximum=getattr(args, "d_max", None),
            height=getattr(args, "d_height", None))
        self.n_min, self.n_max = getattr(args, "n_min", None), getattr(args, "n_max", None)
        if self.n_min is not None and self.n_max is not None and self.n_min > self.n_max:
            raise ValueError("n-min must be at most n-max")
        self.seen_cubes: set[tuple[int, int, int]] = set()
        self.seen_points: set[tuple[int, int, int]] = set()
        self.cube_candidates = 0
        self.chart_points = 0
        self.progress: dict = {}
        self.scope: dict = {}

    def emit(self, record: dict) -> None:
        print(json.dumps(record, sort_keys=True, separators=(",", ":")),
              file=self.stream, flush=True)

    def begin(self, scope: dict) -> None:
        self.scope = scope
        self.emit({"type": "start", "schema": "algorithm-ii-375-v1",
                   "version": VERSION, "command": self.args.command, "target": TARGET,
                   "scope": scope, "rational_d_filter": self.d_filter.as_dict(),
                   "n_filter": {"minimum": None if self.n_min is None else str(self.n_min),
                                "maximum": None if self.n_max is None else str(self.n_max)},
                   "required": {"integer_n": True, "odd_X_Y": True,
                                "gcd_X_Y": 1, "positive_Y": True},
                   "source_sha256": source_hashes()})

    def accept_point(self, point: Point) -> None:
        # Revalidate at the public output boundary, even for direct-d results.
        point = validate_point(point.n, point.X, point.Y, point.d)
        if ((self.n_min is not None and point.n < self.n_min)
                or (self.n_max is not None and point.n > self.n_max)
                or not self.d_filter.accepts(point.d)):
            return
        key = point.n, point.X, point.Y
        if key not in self.seen_points:
            self.seen_points.add(key)
            self.emit({"type": "solution", "engine": self.args.command,
                       "verified_original_equation": True, **point.as_dict()})

    def accept_cubes(self, triple: tuple[int, int, int], *, height_max: int | None = None) -> None:
        if len(triple) != 3 or any(type(v) is not int for v in triple):
            raise ValueError("backend did not return an integer cube triple")
        if sum(v ** 3 for v in triple) != TARGET:
            raise ValueError("backend cube identity fails")
        self.cube_candidates += 1
        if height_max is not None and max(abs(v) for v in triple) > height_max:
            return
        key = tuple(sorted(triple))
        if key in self.seen_cubes:
            return
        self.seen_cubes.add(key)
        for point in points_from_cubes(key):
            self.chart_points += 1
            self.accept_point(point)

    def show_progress(self, record: dict, *, force: bool = False) -> None:
        self.progress = record
        if force:
            print(json.dumps({"type": "progress", "command": self.args.command,
                              **record}, sort_keys=True), file=sys.stderr, flush=True)

    def end(self, *, complete: bool, details: dict | None = None,
            status: str | None = None) -> None:
        self.emit({"type": "end", "status": status or ("complete" if complete else "partial"),
                   "complete": complete, "scope": self.scope,
                   "solutions": len(self.seen_points),
                   "cube_candidates": self.cube_candidates,
                   "unique_cube_triples": len(self.seen_cubes),
                   "chart_points_before_optional_filters": self.chart_points,
                   "elapsed_seconds": round(time.monotonic() - self.started, 6),
                   "progress": self.progress, **(details or {})})


def run_booker(run: Run) -> int:
    args = run.args
    box = args.height_max if args.command == "booker-box" else None
    D_min, D_max = (1, 2 * box) if box is not None else (args.D_min, args.D_max)
    z_min, z_max = (-box, box) if box is not None else (
        -args.z_max if args.z_min is None else args.z_min, args.z_max)
    if D_min > D_max or z_min > z_max:
        raise ValueError("search lower bounds must not exceed upper bounds")
    scope = {"kind": "cube_box" if box is not None else "integer_gap_rectangle",
             "D_min": str(D_min), "D_max": str(D_max),
             "z_min": str(z_min), "z_max": str(z_max), "endpoints": "inclusive",
             "cube_height_max": None if box is None else str(box),
             "D_definition": "abs(u+v), integer; distinct from signed rational d",
             "permutations": "all original-equation charts of each cube triple"}
    run.begin(scope)
    stats = bs.SearchStats()
    run.progress = {"next_D": D_min}

    def progress(record: dict) -> None:
        count = record["counters"]["D_processed"]
        run.show_progress(record, force=bool(args.progress_every and count % args.progress_every == 0))

    for triple in bs.search(TARGET, D_min, D_max, z_min, z_max,
                            primitive_only=True, stats=stats, on_progress=progress):
        run.accept_cubes(triple, height_max=box)
    run.end(complete=True, details={"backend_counters": stats.as_dict()})
    return 0


def run_ej_shell(run: Run, height: int, *, start: int | None = None,
                 stop: int | None = None, height_max: int | None = None) -> dict:
    from elkies_jahnel import iter_shell
    terminal = None
    for record in iter_shell(height, target=TARGET, index_start=start, index_stop=stop,
                             primitive=True, tile_scale=run.args.tile_scale,
                             max_tiles=run.args.max_tiles,
                             progress_every=run.args.progress_every):
        if record["type"] == "hit":
            run.accept_cubes(tuple(int(record[key]) for key in ("x", "y", "z")),
                             height_max=height_max)
        elif record["type"] == "start":
            run.show_progress({"height": str(height),
                               "index_start": record["index_start"],
                               "next_index": record["index_stop"]})
        elif record["type"] in ("progress", "end"):
            run.show_progress({"height": str(height),
                               **{key: value for key, value in record.items() if key != "type"}},
                              force=record["type"] == "progress")
            if record["type"] == "end":
                terminal = record
    if terminal is None:
        raise RuntimeError("lattice worker omitted a validated terminal record")
    return terminal


def run_elkies(run: Run) -> int:
    from elkies_jahnel import minimum_index
    args = run.args
    if args.command == "elkies-shell":
        lo = minimum_index(args.height) if args.index_start is None else args.index_start
        hi = 4 * args.height if args.index_stop is None else args.index_stop
        minimum_index(args.height)
        if not minimum_index(args.height) <= lo <= hi <= 4 * args.height:
            raise ValueError("ratio indices are outside the proved shell domain")
        run.begin({"kind": "cube_height_shell_and_ratio_band", "height_min": str(args.height),
                   "height_stop_exclusive": str(2 * args.height), "index_start": str(lo),
                   "index_stop": str(hi), "grid_denominator": str(5 * args.height),
                   "cube_height_max": None if args.cube_height_max is None else str(args.cube_height_max),
                   "global_right_endpoint_included": hi == 4 * args.height})
        terminal = run_ej_shell(run, args.height, start=lo, stop=hi,
                                height_max=args.cube_height_max)
        run.end(complete=terminal["complete"], details={"backend_terminal": terminal})
        return 0 if terminal["complete"] else 3

    bound = args.height_max
    run.begin({"kind": "cube_box", "cube_height_max": str(bound),
               "endpoints": "inclusive", "low_height_closure": "exact enumeration below 25",
               "remaining_region": "complete lattice shells H=25,50,100,...; final shell filtered"})
    for triple in small_cube_box(min(24, bound)):
        run.accept_cubes(triple, height_max=bound)
    run.progress = {"low_height_complete_through": str(min(24, bound))}
    height = 25
    shells = 0
    while height <= bound:
        terminal = run_ej_shell(run, height, height_max=bound)
        if not terminal["complete"]:
            continuation = ["elkies-shell", "--height", str(height),
                            "--index-start", str(minimum_index(height)),
                            "--index-stop", terminal["next_index"],
                            "--cube-height-max", str(bound),
                            "--tile-scale", str(args.tile_scale),
                            "--progress-every", str(args.progress_every)]
            for d in args.d or []:
                continuation.append("--d=" + str(d))
            for name in ("d_min", "d_max", "d_height", "n_min", "n_max"):
                value = getattr(args, name)
                if value is not None:
                    continuation.append("--" + name.replace("_", "-") + "=" + str(value))
            run.end(complete=False, details={"completed_shells": shells,
                                            "backend_terminal": terminal,
                                            "resume": {"script": "search375.py",
                                                       "argv": continuation,
                                                       "covers": "unfinished part of this shell only"},
                                            "remaining_larger_shells_begin": str(2 * height)})
            return 3
        shells += 1
        height *= 2
    run.end(complete=True, details={"completed_shells": shells})
    return 0


def run_rational(run: Run) -> int:
    args = run.args
    if args.height_min > args.height_max:
        raise ValueError("height-min must not exceed height-max")
    run.begin({"kind": "rational_d_height_and_integer_n", "height_min": str(args.height_min),
               "height_max": str(args.height_max), "n_min": str(args.n_min),
               "n_max": str(args.n_max), "endpoints": "inclusive",
               "height_definition": "max(abs(p),q), d=p/q reduced, q>0",
               "integer_scale_m": "all integer roots; no +/-1 restriction or fixed m cutoff"})
    stats = rational_d.SearchStats()

    def progress(record: dict) -> None:
        run.show_progress(record, force=bool(args.progress_every
                                           and record["parameters"] % args.progress_every == 0))

    for point in rational_d.search(args.height_min, args.height_max, args.n_min, args.n_max,
                                   d_filter=run.d_filter, stats=stats, on_progress=progress):
        run.chart_points += 1
        run.accept_point(point)
    run.end(complete=True, details={"backend_counters": asdict(stats)})
    return 0


def add_output(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--output", type=Path, help="new JSONL file; existing files are never overwritten")


def add_filters(parser: argparse.ArgumentParser, *, require_n: bool = False) -> None:
    parser.add_argument("--d", action="append", type=exact_fraction,
                        help="only this signed rational d; repeatable, use --d=-4/11 for negatives")
    parser.add_argument("--d-min", type=exact_fraction)
    parser.add_argument("--d-max", type=exact_fraction)
    parser.add_argument("--d-height", type=positive_int,
                        help="optional max(abs(numerator),denominator) bound")
    parser.add_argument("--n-min", type=int, required=require_n)
    parser.add_argument("--n-max", type=int, required=require_n)
    parser.add_argument("--progress-every", type=nonnegative_int, default=100,
                        help="progress interval on stderr; 0 disables it")
    add_output(parser)


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser("booker", help="Booker-Sutherland integer-D/signed-z rectangle")
    command.add_argument("--D-min", type=positive_int, default=1)
    command.add_argument("--D-max", type=positive_int, required=True)
    command.add_argument("--z-min", type=int)
    command.add_argument("--z-max", type=int, required=True)
    add_filters(command)
    command = commands.add_parser("booker-box", help="complete cube-height box using Booker-Sutherland")
    command.add_argument("--height-max", type=positive_int, required=True)
    add_filters(command)
    for name, help_text in (("elkies", "complete cube-height box using exact lattice shells"),
                             ("elkies-shell", "one exact lattice shell or ratio subband")):
        command = commands.add_parser(name, help=help_text)
        if name == "elkies":
            command.add_argument("--height-max", type=positive_int, required=True)
        else:
            command.add_argument("--height", type=positive_int, required=True)
            command.add_argument("--index-start", type=nonnegative_int)
            command.add_argument("--index-stop", type=nonnegative_int)
            command.add_argument("--cube-height-max", type=positive_int,
                                 help="optional original box cap when continuing its last shell")
        command.add_argument("--max-tiles", type=nonnegative_int, default=0,
                             help="per-shell tile budget; 0 means no budget; incomplete runs exit 3")
        command.add_argument("--tile-scale", type=exact_fraction, default=Fraction(11, 2))
        add_filters(command)
    command = commands.add_parser("rational-d", help="separate d-first binary-cubic search, with all scales")
    command.add_argument("--height-min", type=positive_int, default=1)
    command.add_argument("--height-max", type=positive_int, required=True)
    add_filters(command, require_n=True)
    command = commands.add_parser("verify-point", help="strictly verify a proposed original-equation point")
    command.add_argument("--n", type=int, required=True)
    command.add_argument("--X", type=int, required=True)
    command.add_argument("--Y", type=int, required=True)
    command.add_argument("--signed-d", type=exact_fraction)
    add_output(command)
    command = commands.add_parser("verify-cubes", help="verify a triple and return every admissible chart")
    command.add_argument("cubes", nargs=3, type=int)
    add_output(command)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    stream: TextIO = sys.stdout
    run: Run | None = None
    try:
        if args.output is not None:
            stream = args.output.open("x", encoding="utf-8")
        run = Run(args, stream)
        if args.command in ("booker", "booker-box"):
            return run_booker(run)
        if args.command in ("elkies", "elkies-shell"):
            return run_elkies(run)
        if args.command == "rational-d":
            return run_rational(run)
        run.begin({"kind": "verification_only"})
        if args.command == "verify-point":
            run.accept_point(validate_point(args.n, args.X, args.Y, args.signed_d))
        else:
            run.accept_cubes(tuple(args.cubes))
        run.end(complete=True)
        return 0
    except KeyboardInterrupt:
        if run is not None:
            run.end(complete=False, status="interrupted")
        return 130
    except (ValueError, ArithmeticError, RuntimeError, OSError) as exc:
        if run is not None:
            run.end(complete=False, status="error", details={"error": str(exc)})
        print(f"search375: {exc}", file=sys.stderr)
        return 2
    finally:
        if stream is not sys.stdout:
            stream.close()


if __name__ == "__main__":
    sys.exit(main())
