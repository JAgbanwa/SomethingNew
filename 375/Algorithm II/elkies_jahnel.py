"""Validated interface to Algorithm II's exact Elkies--Elsenhans--Jahnel worker.

``iter_shell`` streams native start/hit/progress/end records. A hit is an
integer cube triple, not yet an accepted point of the original equation;
the common verifier must impose its odd, coprime X,Y conditions. A terminal
record is mandatory. No exception, interrupted output, or missing record is
converted into a claim of completed coverage.

Only Python's standard library and a C++17 compiler with GMP are required.
See EJ_METHOD.md for the finite region, enclosure proof, and provenance.
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
from math import gcd
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from typing import Iterator


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "ej_worker.cpp"
DEFAULT_WORKER = ROOT / "build" / "ej_worker"
BUILD_FLAGS = ("-O3", "-std=c++17")
WORKER_VERSION = "1.0.0-algorithm-ii"


class EJWorkerError(RuntimeError):
    """Compilation, worker execution, or the exact output contract failed."""


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", str(value)):
        raise ValueError(f"{name} must be an exact decimal integer")
    return int(str(value))


def _icbrt(value: int) -> int:
    if value < 0:
        raise ValueError("cube-root argument must be nonnegative")
    if value == 0:
        return 0
    result = 1 << ((value.bit_length() + 2) // 3)
    while True:
        candidate = (2 * result + value // (result * result)) // 3
        if candidate >= result:
            return result
        result = candidate


def minimum_index(height: int, target: int = 375) -> int:
    """Return the inclusive lower ratio-grid index for a valid height shell.

    The shell is H <= max(|a|,|b|,|c|) < 2H. For target 375, H=25
    is already valid. Smaller coordinate heights need separate finite work.
    """
    height = _integer(height, "height")
    target = _integer(target, "target")
    if height < 25 or target <= 0 or _icbrt(target) ** 3 == target:
        raise ValueError("need height >= 25 and a positive noncube target")
    radicand = 3 * height * height - 3 * height + 1 - target
    if radicand <= 0 or 125 * target > 3 * height ** 3:
        raise ValueError("height does not satisfy the proved shell inequalities")
    lower = _icbrt(radicand)
    if lower ** 3 < radicand:
        lower += 1
    return 5 * lower // 2


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_worker(*, force: bool = False) -> Path:
    """Build/reuse the local GMP worker, with source/binary fingerprints.

    Set CXX to a compiler command, for example ``c++`` or ``ccache g++``.
    Compilation uses an argument list, never a shell. The finished binary
    replaces the previous one atomically only after successful compilation.
    """
    compiler = shlex.split(os.environ.get("CXX", "c++"))
    if not compiler:
        raise EJWorkerError("CXX must specify a C++17 compiler")
    fingerprint = {"source_sha256": _sha256(SOURCE), "compiler": compiler,
                   "flags": list(BUILD_FLAGS)}
    output = DEFAULT_WORKER
    stamp = output.with_suffix(".build.json")
    if not force and output.is_file() and stamp.is_file():
        try:
            previous = json.loads(stamp.read_text(encoding="utf-8"))
            if (all(previous.get(key) == value for key, value in fingerprint.items())
                    and previous.get("binary_sha256") == _sha256(output)):
                return output
        except (OSError, ValueError, TypeError):
            pass
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ej-build-", dir=output.parent) as directory:
        temporary = Path(directory) / "ej_worker"
        command = [*compiler, *BUILD_FLAGS, str(SOURCE), "-lgmpxx", "-lgmp",
                   "-o", str(temporary)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise EJWorkerError(f"cannot run the C++ compiler: {exc}") from exc
        if result.returncode:
            raise EJWorkerError("GMP worker compilation failed:\n" + result.stderr.strip())
        if fingerprint["source_sha256"] != _sha256(SOURCE):
            raise EJWorkerError("worker source changed during compilation; rerun the build")
        fingerprint["binary_sha256"] = _sha256(temporary)
        temporary.replace(output)
        temporary_stamp = Path(directory) / "build.json"
        temporary_stamp.write_text(json.dumps(fingerprint, sort_keys=True, indent=2) + "\n",
                                   encoding="utf-8")
        temporary_stamp.replace(stamp)
    return output


def _verify_hit(record: dict, *, height: int, target: int, start: int,
                stop: int, primitive: bool) -> tuple[int, int, int]:
    if _integer(record.get("k"), "hit target") != target:
        raise EJWorkerError("native hit has the wrong target")
    xyz = tuple(_integer(record.get(key), f"hit {key}") for key in ("x", "y", "z"))
    if sum(value ** 3 for value in xyz) != target:
        raise EJWorkerError("native hit fails the exact cube identity")
    a, b, c = sorted(abs(value) for value in xyz)
    if not (0 < a <= b < c and height <= c < 2 * height):
        raise EJWorkerError("native hit lies outside the canonical height shell")
    if xyz not in ((a, b, -c), (-a, -b, c)):
        raise EJWorkerError("native hit is not in canonical signed order")
    scaled = 5 * height * a
    if not (start * c <= scaled and (scaled < stop * c or
                                     stop == 4 * height and scaled == stop * c)):
        raise EJWorkerError("native hit lies outside the requested ratio band")
    actual_primitive = gcd(gcd(a, b), c) == 1
    if record.get("primitive") is not actual_primitive or primitive and not actual_primitive:
        raise EJWorkerError("native hit has an invalid primitive flag")
    if _integer(record.get("height"), "hit height") != c:
        raise EJWorkerError("native hit reports an incorrect coordinate height")
    return xyz


def iter_shell(height: int, *, target: int = 375, index_start: int | None = None,
               index_stop: int | None = None, primitive: bool = True,
               tile_scale: str | Fraction = "11/2", max_tiles: int = 0,
               progress_every: int = 100, worker: str | Path | None = None
               ) -> Iterator[dict]:
    """Stream one finite shell/band, checking every native record exactly.

    ``index_start <= (5H)*a/c < index_stop`` is the assigned ratio band;
    the global right endpoint ``index_stop=4H`` is included. Omitting both
    indices searches the full proved shell. ``max_tiles=0`` means no tile
    limit. A positive tile limit or a signal can yield ``complete=False``
    with a resumable ``next_index``; the uncovered interval is
    ``[index_start, next_index)`` under the same endpoint convention.

    The default primitive filter is safe for the user's stricter point
    conditions, but does not replace them. General noncube targets are
    available for independent nonempty controls. A supplied worker path
    is used as given; otherwise build_worker() prepares the local binary.
    """
    height = _integer(height, "height")
    target = _integer(target, "target")
    low = minimum_index(height, target)
    start = low if index_start is None else _integer(index_start, "index_start")
    stop = 4 * height if index_stop is None else _integer(index_stop, "index_stop")
    if not low <= start <= stop <= 4 * height:
        raise ValueError("ratio band lies outside the proved shell domain")
    if not isinstance(primitive, bool):
        raise ValueError("primitive must be a boolean")
    if isinstance(tile_scale, (bool, float)):
        raise ValueError("tile_scale must be an exact positive rational")
    scale = Fraction(tile_scale)
    if scale <= 0:
        raise ValueError("tile_scale must be positive")
    max_tiles = _integer(max_tiles, "max_tiles")
    progress_every = _integer(progress_every, "progress_every")
    if max_tiles < 0 or progress_every < 0:
        raise ValueError("max_tiles and progress_every must be nonnegative")
    executable = build_worker() if worker is None else Path(worker).resolve()
    command = [str(executable), "--height", str(height), "--target", str(target),
               "--index-start", str(start), "--index-stop", str(stop),
               "--tile-scale", str(scale), "--max-tiles", str(max_tiles),
               "--progress-every", str(progress_every)]
    if not primitive:
        command.append("--include-nonprimitive")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, encoding="utf-8")
    except OSError as exc:
        raise EJWorkerError(f"cannot start the lattice worker: {exc}") from exc
    started = ended = False
    next_index, tiles, points = stop, 0, 0
    seen: set[tuple[int, int, int]] = set()
    terminal: dict | None = None
    try:
        assert process.stdout is not None and process.stderr is not None
        for line in process.stdout:
            try:
                record = json.loads(line)
            except (ValueError, TypeError) as exc:
                raise EJWorkerError("native worker produced malformed JSON") from exc
            if not isinstance(record, dict) or ended:
                raise EJWorkerError("invalid native record or output after terminal record")
            kind = record.get("type")
            if kind == "start":
                if started:
                    raise EJWorkerError("duplicate native start record")
                expected = {"engine": "elkies-jahnel", "version": WORKER_VERSION,
                            "primitive": primitive}
                if any(record.get(key) != value for key, value in expected.items()):
                    raise EJWorkerError("native start record has unexpected engine/options")
                if not isinstance(record.get("primitive"), bool):
                    raise EJWorkerError("native primitive option must be boolean")
                scope = {"k": target, "height": height,
                         "index_start": start, "index_stop": stop}
                if any(_integer(record.get(key), key) != value for key, value in scope.items()):
                    raise EJWorkerError("native start record has the wrong requested region")
                started = True
            elif not started:
                raise EJWorkerError("native worker omitted its start record")
            elif kind == "hit":
                xyz = _verify_hit(record, height=height, target=target, start=start,
                                  stop=stop, primitive=primitive)
                if xyz in seen:
                    raise EJWorkerError("native worker emitted a duplicate canonical hit")
                seen.add(xyz)
            elif kind in ("progress", "end"):
                new_next = _integer(record.get("next_index"), "next_index")
                new_tiles = _integer(record.get("tiles"), "tiles")
                new_points = _integer(record.get("lattice_points"), "lattice_points")
                if not (start <= new_next <= next_index and new_tiles >= tiles
                        and new_points >= points):
                    raise EJWorkerError("native progress is outside its region or regresses")
                if (new_tiles == tiles and (new_next != next_index or new_points != points)
                        or new_tiles > tiles and new_next >= next_index):
                    raise EJWorkerError("native progress changes coverage without completed tiles")
                if new_tiles < 0 or new_points < 0 or max_tiles and new_tiles > max_tiles:
                    raise EJWorkerError("native progress violates its work budget")
                next_index, tiles, points = new_next, new_tiles, new_points
                if kind == "end":
                    complete = next_index == start
                    if record.get("complete") is not complete:
                        raise EJWorkerError("native completion flag disagrees with its region")
                    reason = record.get("reason")
                    if complete and reason != "complete" or not complete and reason not in (
                            "tile_budget", "signal"):
                        raise EJWorkerError("native terminal reason is inconsistent")
                    if reason == "tile_budget" and (not max_tiles or tiles != max_tiles):
                        raise EJWorkerError("native terminal tile budget is inconsistent")
                    ended, terminal = True, record
            else:
                raise EJWorkerError(f"unknown native record type: {kind!r}")
            # Do not expose completion before the worker exits successfully and
            # EOF establishes that no trailing/malformed record followed it.
            if kind != "end":
                yield record
        return_code = process.wait()
        error = process.stderr.read().strip()
        if return_code:
            raise EJWorkerError(f"native worker exited {return_code}: {error}")
        if not started or not ended or terminal is None:
            raise EJWorkerError("native worker ended without a complete terminal record")
        yield terminal
    except (ValueError, TypeError, KeyError) as exc:
        raise EJWorkerError(f"invalid native output: {exc}") from exc
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        if process.stdout is not None:
            process.stdout.close()
        if process.stderr is not None:
            process.stderr.close()
