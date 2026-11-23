"""Validated native Booker--Sutherland gap/ratio search for Algorithm II.

The finite region is D in [d_start,d_stop), floor(3847D/1000) <= |z| <= R*D,
x >= y, (x+y)*z < 0, and D=|x+y|.  This is not a whole coordinate box.
The worker streams start/hit/chunk/end records.  Only a validated terminal
record followed by successful process exit certifies its completed prefix.
See BS_NATIVE_METHOD.md for arithmetic bounds, exclusions, and provenance.
"""
from __future__ import annotations

import hashlib
import json
from math import gcd, isfinite, isqrt
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
from typing import Iterator


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "bs_worker.cpp"
DEFAULT_WORKER = ROOT / "build" / "bs_worker"
BUILD_FLAGS = ("-O3", "-std=c++17")
WORKER_VERSION = "1.0.0-algorithm-ii-bs"
METHOD = "booker-sutherland-native-gap-v1"
D_STOP_MAX = 2 ** 63 // 27
RATIO_MAX = 2 ** 40
COUNTER_LIMIT = 2 ** 128
UINT64_MAX = 2 ** 64 - 1
COUNTERS = ("d_total", "d_skipped_mod3", "d_skipped_prim", "d_no_roots", "d_live",
            "roots", "candidates", "pass_2adic", "pass_residue", "exact_checks",
            "hits", "hits_primitive")


class BSWorkerError(RuntimeError):
    """Compilation, native execution, or the exact record contract failed."""


def _integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"-?(0|[1-9][0-9]*)", str(value)):
        raise ValueError(f"{name} must be an exact decimal integer")
    return int(str(value))


def validate_gap(d_start: int, d_stop: int, ratio_max: int = 1024) -> dict[str, int]:
    """Validate exact half-open gap bounds and the native arithmetic envelope.

    Arithmetic validity is not a memory or runtime estimate.  Initialization
    still sieves primes through isqrt(d_stop-1), even for a narrow interval.
    """
    start = _integer(d_start, "d_start")
    stop = _integer(d_stop, "d_stop")
    ratio = _integer(ratio_max, "ratio_max")
    if not 1 <= start < stop <= D_STOP_MAX:
        raise ValueError(f"need 1 <= d_start < d_stop <= {D_STOP_MAX}")
    if not 4 <= ratio <= RATIO_MAX:
        raise ValueError(f"need 4 <= ratio_max <= {RATIO_MAX}")
    if ratio * (stop - 1) + 18 * stop >= 2 ** 126:
        raise ValueError("ratio/gap region exceeds the native z arithmetic limit")
    if (ratio + 1) * stop * (stop - start) >= COUNTER_LIMIT:
        raise ValueError("region exceeds the 128-bit counter bound; split it into smaller tasks")
    return {"d_start": start, "d_stop": stop, "ratio_max": ratio}


def _validate_target(target: int, primitive: bool) -> int:
    target = _integer(target, "target")
    if target == 0 or abs(target) > 1_000_000 or target % 9 not in (3, 6):
        raise ValueError("target must be nonzero, |target| <= 1000000 and target == +/-3 mod 9")
    if primitive:
        remaining, prime = abs(target), 2
        while prime ** 3 <= remaining:
            valuation = 0
            while remaining % prime == 0:
                remaining //= prime
                valuation += 1
            if valuation >= 3 and prime % 3 != 2:
                raise ValueError("native primitive mode requires cube-factor primes == 2 mod 3")
            prime += 1
    return target


def _sha256(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            result.update(block)
    return result.hexdigest()


def build_worker(*, force: bool = False) -> Path:
    """Build/reuse a fingerprinted C++17/GMP worker, replacing files atomically."""
    compiler = shlex.split(os.environ.get("CXX", "c++"))
    if not compiler:
        raise BSWorkerError("CXX must specify a C++17 compiler")
    fingerprint = {"schema": "algorithm-ii-bs-build-v1", "source_sha256": _sha256(SOURCE),
                   "compiler": compiler, "flags": list(BUILD_FLAGS),
                   "worker_version": WORKER_VERSION}
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
    with tempfile.TemporaryDirectory(prefix="bs-build-", dir=output.parent) as directory:
        temporary = Path(directory) / "bs_worker"
        command = [*compiler, *BUILD_FLAGS, str(SOURCE), "-lgmp", "-o", str(temporary)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise BSWorkerError(f"cannot run the C++ compiler: {exc}") from exc
        if result.returncode:
            raise BSWorkerError("GMP worker compilation failed:\n" + result.stderr.strip())
        if fingerprint["source_sha256"] != _sha256(SOURCE):
            raise BSWorkerError("worker source changed during compilation; rerun the build")
        fingerprint["binary_sha256"] = _sha256(temporary)
        temporary.replace(output)
        temporary_stamp = Path(directory) / "build.json"
        temporary_stamp.write_text(json.dumps(fingerprint, sort_keys=True, indent=2) + "\n",
                                   encoding="utf-8")
        temporary_stamp.replace(stamp)
    return output


def _seconds(record: dict, name: str) -> float:
    value = record.get(name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise BSWorkerError(f"native {name} must be a nonnegative finite number")
    if not isfinite(value) or value < 0:
        raise BSWorkerError(f"native {name} must be a nonnegative finite number")
    return float(value)


def _verify_hit(record: dict, *, target: int, start: int, stop: int,
                ratio: int, primitive: bool) -> tuple[int, int, int]:
    if record.get("method") != METHOD or _integer(record.get("k"), "hit target") != target:
        raise BSWorkerError("native hit has the wrong method or target")
    xyz = tuple(_integer(record.get(name), f"hit {name}") for name in ("x", "y", "z"))
    x, y, z = xyz
    gap = _integer(record.get("d"), "hit gap")
    if sum(v ** 3 for v in xyz) != target:
        raise BSWorkerError("native hit fails the exact cube identity")
    if not (x >= y and gap == abs(x + y) and start <= gap < stop and (x + y) * z < 0):
        raise BSWorkerError("native hit lies outside the requested gap/sign region")
    if not (3847 * gap // 1000 <= abs(z) <= ratio * gap):
        raise BSWorkerError("native hit lies outside the requested ratio interval")
    actual_primitive = gcd(gcd(x, y), z) == 1
    if record.get("primitive") is not actual_primitive or primitive and not actual_primitive:
        raise BSWorkerError("native hit has an invalid primitive flag")
    return xyz


def _validate_counters(record: dict, start: int, stop: int, *, primitive: bool,
                       emitted_hits: int, emitted_primitive: int) -> dict[str, int]:
    raw = record.get("counters")
    if not isinstance(raw, dict) or set(raw) != set(COUNTERS):
        raise BSWorkerError("native chunk has an invalid counter schema")
    counters = {key: _integer(raw[key], f"counter {key}") for key in COUNTERS}
    if any(value < 0 or value >= COUNTER_LIMIT for value in counters.values()):
        raise BSWorkerError("native counter is negative or exceeds the 128-bit envelope")
    if counters["d_total"] != stop - start:
        raise BSWorkerError("native chunk counter does not equal its covered gap count")
    skipped_three = (stop - 1) // 3 - (start - 1) // 3
    if counters["d_skipped_mod3"] != skipped_three:
        raise BSWorkerError("native count of gaps divisible by three is incorrect")
    if sum(counters[key] for key in ("d_skipped_mod3", "d_skipped_prim", "d_no_roots", "d_live")) != counters["d_total"]:
        raise BSWorkerError("native gap accounting does not partition its chunk")
    if not primitive and counters["d_skipped_prim"]:
        raise BSWorkerError("native worker used the primitive gap filter without authorization")
    if (counters["roots"] < counters["d_live"]
            or counters["candidates"] != counters["pass_2adic"]
            or counters["pass_2adic"] < counters["pass_residue"]
            or counters["pass_residue"] != counters["exact_checks"]
            or counters["exact_checks"] < counters["hits"]
            or counters["hits"] < counters["hits_primitive"]):
        raise BSWorkerError("native arithmetic counters are inconsistent")
    if counters["hits"] != emitted_hits or counters["hits_primitive"] != emitted_primitive:
        raise BSWorkerError("native hit counters disagree with emitted records")
    if primitive and counters["hits"] != counters["hits_primitive"]:
        raise BSWorkerError("native primitive search reports nonprimitive hits")
    return counters


def iter_gap(d_start: int, d_stop: int, ratio_max: int = 1024, *,
             primitive: bool = True, deadline_seconds: int = 0, chunk: int = 65536,
             worker: str | Path | None = None, target: int = 375) -> Iterator[dict]:
    """Stream one native gap/ratio task with exact record validation.

    The default target is 375. Other supported targets exist for independent
    positive controls. A soft deadline includes worker initialization; SIGINT
    and SIGTERM request a safe partial return. The terminal d_next is the first
    uncovered gap. A start record, hit, or interrupted stream is not completion.
    Chunk requests are normally rounded up to a completed 65536-gap factor
    block; a deadline/signal can flush a shorter, exactly completed prefix.
    """
    region = validate_gap(d_start, d_stop, ratio_max)
    start, stop, ratio = (region[key] for key in ("d_start", "d_stop", "ratio_max"))
    if not isinstance(primitive, bool):
        raise ValueError("primitive must be a boolean")
    target = _validate_target(target, primitive)
    deadline = _integer(deadline_seconds, "deadline_seconds")
    chunk = _integer(chunk, "chunk")
    if not 0 <= deadline <= UINT64_MAX or not 1 <= chunk <= UINT64_MAX:
        raise ValueError("need 0 <= deadline_seconds <= 2^64-1 and 1 <= chunk <= 2^64-1")
    executable = build_worker() if worker is None else Path(worker).resolve()
    command = [str(executable), "--d-start", str(start), "--d-stop", str(stop),
               "--ratio-max", str(ratio), "--k", str(target), "--chunk", str(chunk),
               "--deadline-seconds", str(deadline)]
    if primitive:
        command.append("--primitive")
    # A temporary stderr file cannot fill a pipe and deadlock a worker while
    # the caller is consuming its stdout stream.
    with tempfile.TemporaryFile(mode="w+t", encoding="utf-8") as errors:
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                       text=True, encoding="utf-8")
        except OSError as exc:
            raise BSWorkerError(f"cannot start the gap worker: {exc}") from exc
        started = ended = False
        next_gap = start
        last_hit_gap = start - 1
        pending_hits = pending_primitive = 0
        seen: set[tuple[int, int, int]] = set()
        terminal: dict | None = None
        try:
            assert process.stdout is not None
            for line in process.stdout:
                try:
                    record = json.loads(line)
                except (ValueError, TypeError) as exc:
                    raise BSWorkerError("native worker produced malformed JSON") from exc
                if not isinstance(record, dict) or ended:
                    raise BSWorkerError("invalid native record or output after terminal record")
                kind = record.get("type")
                if kind == "start":
                    if started:
                        raise BSWorkerError("duplicate native start record")
                    expected = {"engine": "booker-sutherland", "version": WORKER_VERSION,
                                "method": METHOD, "z_lo": "floor(3847*d/1000)",
                                "pair_sum_sign": "opposite_z"}
                    if any(record.get(key) != value for key, value in expected.items()):
                        raise BSWorkerError("native start record has unexpected method/options")
                    if record.get("primitive") is not primitive or record.get("square_sieve") is not True:
                        raise BSWorkerError("native start record has unexpected filter options")
                    scope = {"k": target, "d_start": start, "d_stop": stop, "ratio_max": ratio,
                             "chunk": chunk, "deadline_seconds": deadline,
                             "sieve_limit": isqrt(stop - 1)}
                    if any(_integer(record.get(key), key) != value for key, value in scope.items()):
                        raise BSWorkerError("native start record has the wrong requested region")
                    _seconds(record, "setup_seconds")
                    started = True
                elif not started:
                    raise BSWorkerError("native worker omitted its start record")
                elif kind == "hit":
                    xyz = _verify_hit(record, target=target, start=start, stop=stop,
                                      ratio=ratio, primitive=primitive)
                    gap = abs(xyz[0] + xyz[1])
                    if gap < next_gap or gap < last_hit_gap:
                        raise BSWorkerError("native hit regresses behind completed coverage")
                    if xyz in seen:
                        raise BSWorkerError("native worker emitted a duplicate hit")
                    seen.add(xyz)
                    last_hit_gap = gap
                    pending_hits += 1
                    pending_primitive += int(record["primitive"])
                elif kind == "chunk":
                    begin = _integer(record.get("d_start"), "chunk d_start")
                    end = _integer(record.get("d_stop"), "chunk d_stop")
                    if not (begin == next_gap < end <= stop):
                        raise BSWorkerError("native chunks are not a contiguous completed prefix")
                    if pending_hits and last_hit_gap >= end:
                        raise BSWorkerError("native chunk does not cover its preceding hit records")
                    _seconds(record, "seconds")
                    _validate_counters(record, begin, end, primitive=primitive,
                                       emitted_hits=pending_hits, emitted_primitive=pending_primitive)
                    next_gap = end
                    pending_hits = pending_primitive = 0
                elif kind == "end":
                    next_value = _integer(record.get("d_next"), "terminal d_next")
                    if next_value != next_gap or pending_hits:
                        raise BSWorkerError("native terminal coverage disagrees with completed chunks")
                    state, reason = record.get("state"), record.get("reason")
                    if next_gap == stop:
                        if state != "complete" or reason != "complete":
                            raise BSWorkerError("native complete region has contradictory terminal state")
                    elif state != "partial" or reason not in ("deadline", "signal"):
                        raise BSWorkerError("native partial region has contradictory terminal state")
                    if reason == "deadline" and deadline == 0:
                        raise BSWorkerError("native worker claims an unrequested deadline")
                    ended, terminal = True, record
                else:
                    raise BSWorkerError(f"unknown native record type: {kind!r}")
                if kind != "end":
                    yield record
            return_code = process.wait()
            errors.seek(0)
            error = errors.read().strip()
            if return_code:
                raise BSWorkerError(f"native worker exited {return_code}: {error}")
            if not started or not ended or terminal is None:
                raise BSWorkerError("native worker ended without a validated terminal record")
            # A terminal record is withheld until both EOF and exit status are
            # known, so later malformed output cannot coexist with completion.
            yield terminal
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            raise BSWorkerError(f"invalid native output: {exc}") from exc
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
