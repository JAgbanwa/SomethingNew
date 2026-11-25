"""Checkpointed projective-lattice campaigns for the integer-cube target.

The search sweeps integer coordinates in height/ratio regions. Displayed n
slices are never used as a claim of computational coverage. An unsuccessful
worker attempt cannot advance a saved coverage boundary.
"""
from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import csv
import hashlib
import json
import math
from pathlib import Path
import platform
import time

import ej_backend
import equation
import region as regions

ROOT = Path(__file__).resolve().parent
SCHEMA_VERSION = 1


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    """Replace one checkpoint atomically, preserving exact-number strings."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def source_hashes():
    names = ("ej_worker.cpp", "ej_backend.py", "equation.py", "region.py", "campaign.py")
    return {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in names}


def task_path(directory, task):
    digest = hashlib.sha256(task.id.encode("ascii")).hexdigest()
    return Path(directory)/"tasks"/(digest + ".json")


def _stored_integer(value, name, *, minimum=None):
    """Enforce the checkpoint's lossless decimal-string representation."""
    if not isinstance(value, str):
        raise ValueError(f"stored {name} must be a decimal integer string")
    number = equation.integer(value, name)
    if minimum is not None and number < minimum:
        raise ValueError(f"stored {name} is below its allowed minimum")
    return number


def _same_value(actual, expected):
    """JSON equality without treating a Boolean as the integer zero or one."""
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (actual.keys() == expected.keys() and
                all(_same_value(actual[key], value) for key, value in expected.items()))
    if isinstance(expected, list):
        return (len(actual) == len(expected) and
                all(_same_value(a, b) for a, b in zip(actual, expected)))
    return actual == expected


def _validate_manifest(manifest, region=None):
    """Reconstruct the exact plan and require the same mathematical sources."""
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int:
        raise ValueError("invalid campaign manifest schema")
    if manifest["schema_version"] != SCHEMA_VERSION or manifest.get("engine") != "elkies-ej-3d":
        raise ValueError("unsupported campaign manifest schema or engine")
    if manifest.get("target") not in ("primitive", "cubes"):
        raise ValueError("invalid campaign integer-cube target")
    n_min = _stored_integer(manifest.get("n_min"), "n_min", minimum=1)
    n_max = _stored_integer(manifest.get("n_max"), "n_max", minimum=n_min)
    width = _stored_integer(manifest.get("band_width"), "band_width", minimum=1)
    scale = equation.rational(manifest.get("tile_scale"), "tile_scale")
    if scale <= 0 or manifest.get("tile_scale") != str(scale):
        raise ValueError("invalid or noncanonical campaign tile scale")
    descriptor = manifest.get("region")
    if not isinstance(descriptor, dict):
        raise ValueError("campaign has no exact region descriptor")
    lo = _stored_integer(descriptor.get("height_min"), "height_min", minimum=0)
    hi = _stored_integer(descriptor.get("height_max"), "height_max", minimum=0)
    # The planner deliberately represents an empty physical intersection by
    # selected_min > proven_max. Its stored selected_max is then proven_max,
    # although an explicit user min/max pair in that order would be invalid.
    # Reconstruct that case through the original uncapped upper bound; the
    # complete descriptor equality below still rejects any changed endpoint.
    rebuilt = region_from_manifest(manifest)
    expected = regions.describe_region(rebuilt, width)
    if not _same_value(descriptor, expected):
        raise ValueError("campaign region descriptor disagrees with its exact bounds")
    if region is not None and region != rebuilt:
        raise ValueError("supplied region differs from the campaign manifest")
    if manifest.get("planned_task_count") != str(regions.task_count(rebuilt, width)):
        raise ValueError("campaign planned-task count disagrees with its exact region")
    if manifest.get("source_sha256") != source_hashes():
        raise ValueError("Campaign mathematical sources have changed; use a new --out directory.")
    return rebuilt


def load_manifest(directory):
    """Read an existing campaign with source, target and exact-region guards."""
    try:
        manifest = json.loads((Path(directory)/"manifest.json").read_text(encoding="utf-8"))
        _validate_manifest(manifest)
    except (KeyError, TypeError) as error:
        raise ValueError(f"malformed campaign manifest: {error}") from error
    return manifest


def ensure_manifest(directory, region, *, band_width=1000, tile_scale="11/2", target="primitive"):
    if target not in ("primitive", "cubes"):
        raise ValueError("the integer lattice target must be primitive or cubes")
    band_width = equation.integer(band_width, "band_width")
    scale = equation.rational(tile_scale, "tile_scale")
    if scale <= 0 or band_width <= 0:
        raise ValueError("tile scale and band width must be positive")
    directory = Path(directory)
    descriptor = regions.describe_region(region, band_width)
    contract = {
        "schema_version": SCHEMA_VERSION, "engine": "elkies-ej-3d",
        "target": target, "n_min": str(region.n_min), "n_max": str(region.n_max),
        "region": descriptor, "band_width": str(band_width), "tile_scale": str(scale),
        "planned_task_count": str(regions.task_count(region, band_width)),
        "source_sha256": source_hashes(),
    }
    path = directory/"manifest.json"
    if path.exists():
        old = load_manifest(directory)
        if any(old.get(key) != value for key, value in contract.items()):
            raise ValueError("Existing campaign has a different region, target, tile scale, or mathematical source. Use a new --out directory.")
        return old
    value = {**contract, "created_utc": utc_now(),
             "python": platform.python_version(), "platform": platform.platform(),
             "equation": "y^2 = 1 + (36n^3+54n^2+27n-58)/(x*(6n+3+x)^2)",
             "coverage_note": "Native tasks cover height/ratio regions and all n values encountered there; unscheduled/unfinished regions remain unsearched. General rational-only points are outside this integer-cube lattice.",
             "point_count_note": "Each (n,x,+/-y) pair is counted once; one canonical cube triple can give several equation points."}
    write_json(path, value)
    return value


def region_from_manifest(manifest):
    r = manifest["region"]
    lo, hi = equation.integer(r["height_min"]), equation.integer(r["height_max"])
    return regions.make_region(equation.integer(manifest["n_min"]), equation.integer(manifest["n_max"]),
                               lo, None if hi < lo else hi)


def verify_points(points):
    """Deduplicate and independently recheck every stored exact equation point."""
    if not isinstance(points, list):
        raise ValueError("checkpoint points must be a list")
    unique = {}
    for point in points:
        if not isinstance(point, dict):
            raise ValueError("checkpoint contains an invalid point record")
        try:
            checked = equation.check_point(point["n"], point["x"], point["y"])
        except (KeyError, TypeError) as error:
            raise ValueError("checkpoint contains a malformed point") from error
        if not checked["exact"] or not checked["integral_lift"]:
            raise ValueError("lattice checkpoint contains a non-integral or non-exact point")
        for key, value in checked.items():
            if not _same_value(point.get(key), value):
                raise ValueError("stored point classification disagrees with exact arithmetic")
        if Fraction(point["y"]) < 0:
            raise ValueError("lattice checkpoint must count each +/-y pair once with nonnegative y")
        source = point.get("source_cube_triple")
        if (point.get("source") != "elkies-integer-cube-lift" or
                not isinstance(source, list) or len(source) != 3):
            raise ValueError("stored point has no valid cube provenance")
        xyz = tuple(_stored_integer(v, "source cube coordinate") for v in source)
        if sum(v**3 for v in xyz) != 375 or sorted(xyz) != sorted(map(int, checked["cube_triple"])):
            raise ValueError("stored source cube triple disagrees with the exact equation point")
        unique[(int(point["n"]), int(point["x"]), abs(Fraction(point["y"])))] = point
    return [unique[key] for key in sorted(unique)]


def _verify_cube_records(data, *, n_min, n_max, primitive, task=None,
                         height_min=None, height_max=None):
    """Require exact provenance, physical scope and all parity-pair images."""
    points = verify_points(data.get("points"))
    if len(points) != len(data["points"]):
        raise ValueError("checkpoint contains duplicate equation points")
    triples = data.get("cube_triples")
    if not isinstance(triples, list):
        raise ValueError("checkpoint cube triples must be a list")
    expected, seen = [], set()
    for triple in triples:
        if not isinstance(triple, list) or len(triple) != 3:
            raise ValueError("invalid stored cube triple")
        xyz = tuple(_stored_integer(v, "cube coordinate") for v in triple)
        if xyz in seen or sum(v**3 for v in xyz) != 375:
            raise ValueError("duplicate or inexact stored cube triple")
        seen.add(xyz)
        height = max(abs(v) for v in xyz)
        if task is not None:
            a, b, c = sorted(abs(v) for v in xyz)
            if (not 0 < a <= b < c or xyz != (a, b, -c) or
                    not task.c_min <= c <= task.c_max or
                    not task.height <= c < 2*task.height or
                    not task.sum_min <= sum(xyz) <= task.sum_max):
                raise ValueError("stored native cube is outside the task's height or sum region")
            next_index = _stored_integer(data["next_index"], "next_index")
            scaled = 5*task.height*a
            upper_ok = (scaled < task.index_stop*c or
                        task.include_right_endpoint and scaled == task.index_stop*c)
            if not next_index*c <= scaled or not upper_ok:
                raise ValueError("stored native cube is outside the completed ratio interval")
        else:
            if xyz != tuple(sorted(xyz)) or not height_min <= height <= height_max:
                raise ValueError("stored small-height cube is outside its sign/order/height scope")
        mapped = equation.points_from_cube(xyz, n_min=n_min, n_max=n_max)
        if not mapped or primitive and not all(point["primitive"] for point in mapped):
            raise ValueError("stored cube violates the campaign n interval or primitive target")
        expected.extend(mapped)
    if points != verify_points(expected):
        raise ValueError("stored points do not contain exactly all same-parity images of the saved cubes")
    return points


def _verify_coverage(data, task):
    """Check the contiguous tile/attempt witness behind a completion claim.

    This is a corruption/consistency check of recorded native work, not a
    replacement for rerunning the lattice enumeration as a formal proof.
    Every native progress record is retained because progress_every is one.
    """
    next_index = _stored_integer(data.get("next_index"), "next_index")
    if not task.index_start <= next_index <= task.index_stop:
        raise ValueError("saved coverage endpoint is outside its assigned task")
    status = data.get("status")
    if status not in ("complete", "partial", "error"):
        raise ValueError("invalid saved task status")
    if (status == "complete") != (next_index == task.index_start):
        raise ValueError("saved completion status disagrees with its exact endpoint")
    tile_count = _stored_integer(data.get("tiles_count"), "tiles_count", minimum=0)
    lattice_count = _stored_integer(data.get("lattice_points"), "lattice_points", minimum=0)
    tiles, attempts = data.get("tiles"), data.get("attempts")
    if not isinstance(tiles, list) or not isinstance(attempts, list) or len(tiles) != tile_count:
        raise ValueError("saved tile witness disagrees with the coverage counters")
    boundary, count = task.index_stop, 0
    deltas = []
    for tile in tiles:
        if not isinstance(tile, dict):
            raise ValueError("invalid stored tile")
        left = _stored_integer(tile.get("left"), "tile left")
        right = _stored_integer(tile.get("right"), "tile right")
        height = _stored_integer(tile.get("height"), "tile height")
        delta = _stored_integer(tile.get("lattice_points_delta"), "tile lattice count", minimum=0)
        if not task.index_start <= left < right == boundary or height != task.height:
            raise ValueError("saved tiles have a gap, overlap, or wrong height")
        boundary, count = left, count+delta
        deltas.append(delta)
    if boundary != next_index or count != lattice_count:
        raise ValueError("saved tiles do not certify the claimed coverage endpoint/counter")
    boundary, consumed, count = task.index_stop, 0, 0
    for attempt in attempts:
        if not isinstance(attempt, dict):
            raise ValueError("invalid stored attempt")
        if _stored_integer(attempt.get("index_stop"), "attempt index_stop") != boundary:
            raise ValueError("attempts do not resume at the preceding certified boundary")
        budget = equation.integer(attempt.get("max_tiles"), "attempt max_tiles")
        elapsed = attempt.get("elapsed_seconds")
        if (budget < 0 or isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or
                not math.isfinite(elapsed) or elapsed < 0):
            raise ValueError("invalid stored attempt budget or elapsed time")
        if attempt.get("status") == "failed":
            if "terminal" in attempt or not isinstance(attempt.get("error"), str):
                raise ValueError("failed attempt cannot certify new native coverage")
            continue
        terminal = attempt.get("terminal")
        if attempt.get("status") != "validated" or not isinstance(terminal, dict) or terminal.get("type") != "end":
            raise ValueError("attempt lacks a validated native terminal record")
        new_boundary = equation.integer(terminal.get("next_index"), "terminal next_index")
        new_tiles = equation.integer(terminal.get("tiles"), "terminal tiles")
        new_count = equation.integer(terminal.get("lattice_points"), "terminal lattice_points")
        if (new_tiles < 0 or new_count < 0 or consumed+new_tiles > tile_count or
                budget and new_tiles > budget):
            raise ValueError("native terminal counters violate the recorded attempt")
        expected_boundary = int(tiles[consumed+new_tiles-1]["left"]) if new_tiles else boundary
        if new_boundary != expected_boundary or new_count != sum(deltas[consumed:consumed+new_tiles]):
            raise ValueError("native terminal disagrees with the contiguous saved tile witness")
        is_complete = new_boundary == task.index_start
        reason = terminal.get("reason")
        if terminal.get("complete") is not is_complete:
            raise ValueError("native terminal completion flag disagrees with exact coverage")
        if ((is_complete and reason != "complete") or
                (not is_complete and reason not in ("tile_budget", "signal")) or
                (reason == "tile_budget" and (not budget or new_tiles != budget))):
            raise ValueError("native terminal reason disagrees with the attempt budget")
        if boundary == task.index_start:
            raise ValueError("saved attempt runs after the task was already complete")
        boundary, consumed, count = new_boundary, consumed+new_tiles, count+new_count
    if boundary != next_index or consumed != tile_count or count != lattice_count:
        raise ValueError("saved attempt history does not establish the claimed coverage")
    last_failed = bool(attempts and attempts[-1].get("status") == "failed")
    if (status == "error") != last_failed:
        raise ValueError("saved error state disagrees with the most recent attempt")


def _task_in_manifest(task, manifest, region=None):
    region = region or region_from_manifest(manifest)
    expected = next(regions.iter_tasks(region, int(manifest["band_width"]),
                                      start=task.logical_index, limit=1), None)
    if expected != task:
        raise ValueError("task is not part of the exact campaign plan")


def _validate_task(data, task, manifest):
    if (not isinstance(data, dict) or type(data.get("schema_version")) is not int or
            data.get("schema_version") != SCHEMA_VERSION or
            not _same_value(data.get("task"), task.to_dict())):
        raise ValueError("task checkpoint belongs to a different region")
    _verify_coverage(data, task)
    _verify_cube_records(data, n_min=int(manifest["n_min"]), n_max=int(manifest["n_max"]),
                         primitive=manifest["target"] == "primitive", task=task)
    return data


def read_task(directory, task, *, manifest=None):
    path = task_path(directory, task)
    if not path.exists():
        return None
    manifest = load_manifest(directory) if manifest is None else manifest
    _task_in_manifest(task, manifest)
    try:
        return _validate_task(json.loads(path.read_text()), task, manifest)
    except (KeyError, TypeError) as error:
        raise ValueError(f"malformed task checkpoint: {error}") from error


def empty_task(task):
    return {"schema_version": SCHEMA_VERSION, "task": task.to_dict(),
            "status": "partial", "next_index": str(task.index_stop),
            "tiles_count": "0", "lattice_points": "0", "points": [],
            "cube_triples": [], "tiles": [], "attempts": [], "updated_utc": utc_now()}


def attempt_task(directory, task, manifest, *, max_tiles=64, worker=None):
    """Run one bounded attempt; commit coverage only after validated exit and EOF."""
    _validate_manifest(manifest)
    _task_in_manifest(task, manifest)
    max_tiles = equation.integer(max_tiles, "max_tiles")
    if max_tiles < 0:
        raise ValueError("max_tiles must be nonnegative")
    old = read_task(directory, task, manifest=manifest) or empty_task(task)
    if old["status"] == "complete":
        return old
    stop = int(old["next_index"])
    points, cubes, tiles = list(old["points"]), list(old["cube_triples"]), list(old["tiles"])
    terminal = None
    last_index, last_count = stop, 0
    started = time.monotonic()
    try:
        for record in ej_backend.iter_shell(
                task.height, target=375, index_start=task.index_start, index_stop=stop,
                primitive=manifest["target"] == "primitive", tile_scale=manifest["tile_scale"],
                max_tiles=max_tiles, progress_every=1, worker=worker):
            kind = record["type"]
            if kind == "hit":
                xyz = tuple(int(record[k]) for k in ("x", "y", "z"))
                height = max(abs(v) for v in xyz)
                if not task.c_min <= height <= task.c_max:
                    continue
                mapped = equation.points_from_cube(xyz, n_min=int(manifest["n_min"]),
                                                   n_max=int(manifest["n_max"]))
                if mapped:
                    points.extend(mapped)
                    cubes.append([str(v) for v in xyz])
            elif kind in ("progress", "end"):
                next_index, count = int(record["next_index"]), int(record["lattice_points"])
                if next_index < last_index:
                    tiles.append({"left": str(next_index), "right": str(last_index),
                                  "height": str(task.height),
                                  "lattice_points_delta": str(count-last_count)})
                last_index, last_count = next_index, count
                if kind == "end":
                    terminal = record
        if terminal is None:
            raise ej_backend.EJWorkerError("no verified native terminal record")
        result = dict(old)
        result.update(status="complete" if int(terminal["next_index"]) == task.index_start else "partial",
                      next_index=str(terminal["next_index"]),
                      tiles_count=str(int(old["tiles_count"])+int(terminal["tiles"])),
                      lattice_points=str(int(old["lattice_points"])+int(terminal["lattice_points"])),
                      points=verify_points(points), cube_triples=[list(v) for v in sorted({tuple(v) for v in cubes})],
                      tiles=tiles, updated_utc=utc_now())
        result.pop("error", None)
        result["attempts"] = old["attempts"] + [{"index_stop": str(stop), "max_tiles": max_tiles,
            "elapsed_seconds": time.monotonic()-started, "terminal": terminal, "status": "validated"}]
        _validate_task(result, task, manifest)
        write_json(task_path(directory, task), result)
        return result
    except (Exception, KeyboardInterrupt) as error:
        # Retain only the previously certified boundary. In particular, no
        # native progress line or unvalidated terminal can complete a task.
        failed = dict(old)
        failed.update(status="error", error=f"{type(error).__name__}: {error}", updated_utc=utc_now())
        failed["attempts"] = old["attempts"] + [{"index_stop": str(stop), "max_tiles": max_tiles,
            "elapsed_seconds": time.monotonic()-started, "status": "failed", "error": failed["error"]}]
        write_json(task_path(directory, task), failed)
        raise


def _small_height_result(region, primitive):
    """Tiny independent enumeration also used to validate its stored witness."""
    if not isinstance(primitive, bool):
        raise ValueError("primitive must be a Boolean")
    scope = {"height_min": str(region.small_height_min), "height_max": str(region.small_height_max),
             "n_min": str(region.n_min), "n_max": str(region.n_max), "primitive_only": primitive}
    points, triples = [], set()
    count = 0
    if region.small_height_required:
        high, low = region.small_height_max, region.small_height_min
        cubes = {v**3: v for v in range(-high, high+1)}
        for A in range(-high, high+1):
            for B in range(A, high+1):
                count += 1
                C = cubes.get(375-A**3-B**3)
                if C is None or C < B or max(abs(A), abs(B), abs(C)) < low:
                    continue
                mapped = equation.points_from_cube((A,B,C), n_min=region.n_min, n_max=region.n_max)
                if primitive:
                    mapped = [p for p in mapped if p["primitive"]]
                if mapped:
                    points.extend(mapped)
                    triples.add((str(A),str(B),str(C)))
    return {"schema_version": SCHEMA_VERSION, "scope": scope, "complete": True,
              "required": region.small_height_required, "pairs_checked": count,
              "points": verify_points(points), "cube_triples": [list(t) for t in sorted(triples)],
              "source_sha256": source_hashes()}


def read_low_height(directory, region, *, primitive, manifest=None):
    """Validate an existing small-height result without creating search work.

    This check independently repeats at most 1,225 pairs (height below 25),
    so missing solutions, altered counters and false completion flags cannot
    silently convert that finite control region into a completed search.
    """
    path = Path(directory)/"low_height.json"
    if not path.exists():
        return None
    if manifest is not None:
        _validate_manifest(manifest, region)
        if primitive is not (manifest["target"] == "primitive"):
            raise ValueError("small-height target differs from the campaign")
    saved = json.loads(path.read_text())
    expected = _small_height_result(region, primitive)
    if (not isinstance(saved, dict) or
            any(not _same_value(saved.get(key), value) for key, value in expected.items())):
        raise ValueError("small-height checkpoint fails exact scope, source, counter or solution validation")
    _verify_cube_records(saved, n_min=region.n_min, n_max=region.n_max, primitive=primitive,
                         height_min=region.small_height_min, height_max=region.small_height_max)
    return saved


def search_small_heights(directory, region, *, primitive):
    """Exhaust all sign/order possibilities below the native height threshold."""
    saved = read_low_height(directory, region, primitive=primitive)
    if saved is not None:
        return saved
    result = _small_height_result(region, primitive)
    result["updated_utc"] = utc_now()
    path = Path(directory)/"low_height.json"
    write_json(path, result)
    return result


def saved_tasks(directory, region, band_width, *, manifest=None):
    manifest = load_manifest(directory) if manifest is None else manifest
    _validate_manifest(manifest, region)
    if equation.integer(band_width, "band_width") != int(manifest["band_width"]):
        raise ValueError("supplied band width differs from the campaign manifest")
    records = []
    for path in sorted((Path(directory)/"tasks").glob("*.json")):
        raw = json.loads(path.read_text())
        index = equation.integer(raw["task"]["logical_index"], "logical_index")
        task = next(regions.iter_tasks(region, band_width, start=index, limit=1), None)
        if task is None or task_path(directory, task) != path:
            raise ValueError("saved task is outside the campaign plan")
        records.append(read_task(directory, task, manifest=manifest))
    return sorted(records, key=lambda r: int(r["task"]["logical_index"]))


def summarize(directory, manifest, region):
    _validate_manifest(manifest, region)
    records = saved_tasks(directory, region, int(manifest["band_width"]), manifest=manifest)
    points = [p for r in records for p in r["points"]]
    low = read_low_height(directory, region, primitive=manifest["target"] == "primitive", manifest=manifest)
    if low:
        points.extend(low.get("points", []))
    points = verify_points(points)
    complete = sum(r["status"] == "complete" for r in records)
    planned = int(manifest["planned_task_count"])
    small_complete = (not region.small_height_required) or bool(low is not None and low["complete"] is True)
    all_bands = complete == planned and small_complete
    cube_keys = {tuple(sorted((Fraction(v) for v in p["cube_triple"]))) for p in points}
    result = {
        "schema_version": SCHEMA_VERSION, "engine": manifest["engine"], "target": manifest["target"],
        "n_min": manifest["n_min"], "n_max": manifest["n_max"],
        "planned_tasks": str(planned), "materialized_tasks": len(records),
        "complete_tasks": complete, "partial_tasks": sum(r["status"] == "partial" for r in records),
        "error_tasks": sum(r["status"] == "error" for r in records),
        "unstarted_tasks": str(planned-len(records)),
        "completed_ratio_index_units": str(sum(int(r["task"]["index_stop"])-int(r["next_index"]) for r in records)),
        "completed_tiles": str(sum(int(r["tiles_count"]) for r in records)),
        "covered_lattice_points": str(sum(int(r["lattice_points"]) for r in records)),
        "small_height_complete": small_complete, "all_planned_regions_complete": all_bands,
        "full_height_scope": region.complete_height_scope,
        "complete_target_search_in_n_interval": all_bands and region.complete_height_scope,
        "general_rational_y_search_complete": False,
        "canonical_cube_hits": len(cube_keys), "equation_points": len(points),
        "primitive_equation_points": sum(p["primitive"] for p in points),
        "nonprimitive_equation_points": sum(not p["primitive"] for p in points),
        "coverage_note": manifest["coverage_note"], "updated_utc": utc_now(),
    }
    write_json(Path(directory)/"summary.json", result)
    write_json(Path(directory)/"points.json", points)
    with (Path(directory)/"points.csv").open("w", newline="") as handle:
        fields = ["n","x","y","t","residual","status","cube_gcd","cube_A","cube_B","cube_C"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for p in points:
            writer.writerow({**{k:p[k] for k in fields if k in p},
                             **dict(zip(("cube_A","cube_B","cube_C"),p["cube_triple"]))})
    with (Path(directory)/"coverage.csv").open("w", newline="") as handle:
        fields = ["task_id","logical_index","height","c_min","c_max","index_start","index_stop",
                  "next_index","status","tiles_count","lattice_points","equation_points"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for r in records:
            row = {k:r["task"][k] for k in fields if k in r["task"]}
            row.update({k:r[k] for k in fields if k in r})
            row["equation_points"] = len(r["points"])
            writer.writerow(row)
    return result


def select_tasks(directory, region, *, band_width, maximum=12, schedule="spread", offset=0):
    """Select a finite actual work page without materializing its enormous plan.

    Previously partial tasks come first. Spread chooses representative bands
    across shell/ratio positions. Sequential paging is explicit and resumable.
    Selection describes assigned regions, never sample n-values.
    """
    if maximum < 1 or offset < 0:
        raise ValueError("max_tasks must be positive and task offset nonnegative")
    if schedule not in ("spread", "sequential"):
        raise ValueError("schedule must be spread or sequential")
    old = saved_tasks(directory, region, band_width)
    chosen, seen = [], set()
    done = {int(r["task"]["logical_index"]) for r in old if r["status"] == "complete"}
    for r in old:
        if r["status"] != "complete":
            i = int(r["task"]["logical_index"])
            chosen.append(next(regions.iter_tasks(region, band_width, start=i, limit=1)))
            seen.add(i)
            if len(chosen) == maximum:
                return chosen
    shells = list(regions.iter_shells(region))
    total = regions.task_count(region, band_width)
    if schedule == "spread" and shells:
        starts, cumulative = [], 0
        for shell in shells:
            starts.append(cumulative)
            cumulative += shell.band_count(band_width)
        # Each round visits different shell/ratio positions. Exact integer
        # indexing keeps a large starting n or task index fully intact.
        slots = maximum-len(chosen)
        for j in range(slots):
            shell_index = (j*(len(shells)-1)//max(1,slots-1)) if slots>1 else len(shells)//2
            count = shells[shell_index].band_count(band_width)
            band = min(count-1, count//2 + offset)
            index = starts[shell_index]+band
            while index in done or index in seen:
                index += 1
                if index >= starts[shell_index]+count:
                    break
            if index >= starts[shell_index]+count:
                continue
            chosen.append(next(regions.iter_tasks(region, band_width, start=index, limit=1)))
            seen.add(index)
    index = offset
    while len(chosen) < maximum and index < total:
        if index not in done and index not in seen:
            chosen.append(next(regions.iter_tasks(region, band_width, start=index, limit=1)))
            seen.add(index)
        index += 1
    return chosen


def run(directory, manifest, region, *, max_tasks=12, max_tiles=64, schedule="spread", offset=0,
        progress=print):
    if max_tiles < 0:
        raise ValueError("max_tiles must be nonnegative (0 means no tile limit)")
    search_small_heights(directory, region, primitive=manifest["target"] == "primitive")
    tasks = select_tasks(directory, region, band_width=int(manifest["band_width"]),
                         maximum=max_tasks, schedule=schedule, offset=offset)
    worker = ej_backend.build_worker() if tasks else None
    progress(f"Assigned {len(tasks)} native height/ratio tasks from a plan of {manifest['planned_task_count']} tasks.")
    progress("The n interval is swept collectively inside those regions; displayed n slices are geometry only.")
    try:
        for i, task in enumerate(tasks, 1):
            result = attempt_task(directory, task, manifest, max_tiles=max_tiles, worker=worker)
            progress(f"[{i}/{len(tasks)}] H={task.height}; {result['status']}; tiles={result['tiles_count']}; exact equation points={len(result['points'])}")
            summarize(directory, manifest, region)
    finally:
        summary = summarize(directory, manifest, region)
    return summary
