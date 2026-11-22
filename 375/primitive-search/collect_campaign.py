#!/usr/bin/env python3
"""Collect a disjoint band campaign while preserving each band's exact search region.

  python3 collect_campaign.py --campaign tasks/campaign.json --results returned-results \
      --output-dir collected --require-complete

Each band is processed by collect_gap.py. Its summary and hits are then checked
again against the campaign manifest. Completion refers only to the listed bands,
each with its own ratio bound and the common strict maximum-coordinate height floor.
This command does not perform a hardware audit or establish any global height exclusion.
Exit 1 indicates invalid results/errors; exit 2 with --require-complete indicates gaps.
"""
from __future__ import annotations

import argparse
import json
from math import isfinite
from pathlib import Path
import subprocess
import sys
from typing import Any

from gap_common import (D_LIMIT, METHOD, PAGE_SCHEMA, atomic_json, check_k,
                        expected_solutions, load_json, ratio_ok, registered_tasks,
                        search_options, verify_hit)

ROOT = Path(__file__).resolve().parent
CAMPAIGN_SCHEMA = "ce375-primitive-bands-v1"
SUMMARY_SCHEMA = "ce375-primitive-campaign-summary-v1"


def read_manifest(path: Path) -> tuple[dict[str, Any], list[tuple[dict, Path]]]:
    campaign = load_json(path)
    if campaign.get("schema") != CAMPAIGN_SCHEMA or campaign.get("method") != METHOD:
        raise ValueError("campaign schema or method does not match this search")
    if not isinstance(campaign.get("campaign_id"), str) or not campaign["campaign_id"]:
        raise ValueError("campaign_id must be a nonempty string")
    k = int(campaign["k"])
    check_k(k)
    options = search_options(campaign)
    lo, hi = int(campaign["d_start"]), int(campaign["d_stop"])
    if not 1 <= lo < hi <= D_LIMIT:
        raise ValueError("invalid campaign pair-sum interval")
    bands = campaign.get("bands")
    if not isinstance(bands, list) or not bands:
        raise ValueError("campaign must contain at least one band")
    root = path.resolve().parent
    checked, ids, paths = [], set(), set()
    cursor = lo
    for band in bands:
        start, stop, ratio = int(band["d_start"]), int(band["d_stop"]), int(band["ratio_max"])
        if start != cursor or not start < stop <= hi or not ratio_ok(ratio, stop):
            raise ValueError("bands must form a disjoint, contiguous partition of the campaign interval")
        bid = band.get("campaign_id")
        if not isinstance(bid, str) or not bid or bid in ids:
            raise ValueError("band campaign identifiers must be nonempty and unique")
        relative = Path(band["page"])
        page_path = (root / relative).resolve()
        if relative.is_absolute() or not page_path.is_relative_to(root) or page_path in paths:
            raise ValueError("each band must refer to a distinct page within the campaign directory")
        page = load_json(page_path)
        if page.get("schema") != PAGE_SCHEMA or page.get("method") != METHOD \
                or page.get("campaign_id") != bid or int(page["k"]) != k \
                or int(page["d_start"]) != start or int(page["d_stop"]) != stop \
                or int(page["ratio_max"]) != ratio or search_options(page) != options:
            raise ValueError(f"band {bid} page disagrees with the campaign manifest")
        registered_tasks(page)
        checked.append((band, page_path))
        ids.add(bid)
        paths.add(page_path)
        cursor = stop
    if cursor != hi:
        raise ValueError("bands do not reach the campaign's declared endpoint")
    return campaign, checked


def validate_summary(summary: dict, band: dict, campaign: dict) -> list[tuple[int, int]]:
    if summary.get("campaign_id") != band["campaign_id"] or int(summary["k"]) != int(campaign["k"]) \
            or int(summary["ratio_max"]) != int(band["ratio_max"]) \
            or search_options(summary) != search_options(campaign):
        raise ValueError("band summary identity or constraints disagree with the manifest")
    lo, hi = int(band["d_start"]), int(band["d_stop"])
    covered, gaps, cursor = [], [], lo
    for interval in summary["covered_d"]:
        start, stop = map(int, interval)
        if not cursor <= start < stop <= hi:
            raise ValueError("invalid or overlapping covered intervals in band summary")
        if start > cursor:
            gaps.append([str(cursor), str(start)])
        covered.append((start, stop))
        cursor = stop
    if cursor < hi:
        gaps.append([str(cursor), str(hi)])
    if summary["gaps"] != gaps or int(summary["d_values_covered"]) != sum(b - a for a, b in covered):
        raise ValueError("band summary gaps or coverage total disagree with its intervals")
    hours = float(summary["worker_core_hours"])
    if not isfinite(hours) or hours < 0:
        raise ValueError("invalid worker time in band summary")
    if not isinstance(summary.get("errors"), list):
        raise ValueError("band summary must contain an errors list")
    return covered


def collect(campaign_path: Path, result_roots: list[Path], output: Path) -> dict[str, Any]:
    campaign, manifest_bands = read_manifest(campaign_path)
    result_roots = list(dict.fromkeys(p.resolve() for p in result_roots))
    if not result_roots or any(not p.is_dir() for p in result_roots):
        raise ValueError("each results path must be an existing directory")
    output.mkdir(parents=True, exist_ok=True)
    k, options = int(campaign["k"]), search_options(campaign)
    errors, bands, hits = [], [], {}
    hashes: set[str] = set()
    total_d, total_hours, total_expected = 0, 0.0, 0.0
    rho = campaign.get("rho")
    if rho is not None and (not isfinite(float(rho)) or float(rho) < 0):
        raise ValueError("invalid campaign density heuristic")

    for index, (band, page_path) in enumerate(manifest_bands):
        bid = band["campaign_id"]
        destination = output / "bands" / f"b{index:03d}"
        destination.mkdir(parents=True, exist_ok=True)
        # A failed new collection must never silently reuse an older successful summary.
        for name in ("summary.json", "hits.jsonl"):
            (destination / name).unlink(missing_ok=True)
        command = [sys.executable, str(ROOT / "collect_gap.py"), "--page", str(page_path),
                   "--results", *(str(p) for p in result_roots), "--output-dir", str(destination),
                   "--require-complete"]
        completed = subprocess.run(command, capture_output=True, text=True)
        row = {"campaign_id": bid, "d_start": band["d_start"], "d_stop": band["d_stop"],
               "ratio_max": int(band["ratio_max"]), "covered_d": [],
               "gaps": [[band["d_start"], band["d_stop"]]], "d_values_covered": 0,
               "worker_core_hours": 0.0, "summary": f"bands/b{index:03d}/summary.json"}
        try:
            summary = load_json(destination / "summary.json")
            covered = validate_summary(summary, band, campaign)
            for error in summary["errors"]:
                errors.append({"band": bid, "error": error})
            if completed.returncode not in (0, 1, 2) or (completed.returncode == 1 and not summary["errors"]):
                raise ValueError(f"band collector exited {completed.returncode}: {completed.stderr.strip()}")
            if completed.returncode == 2 and not summary["gaps"]:
                raise ValueError("band collector reported missing coverage without listing gaps")
            row.update(covered_d=summary["covered_d"], gaps=summary["gaps"],
                       d_values_covered=int(summary["d_values_covered"]),
                       worker_core_hours=float(summary["worker_core_hours"]))
            total_d += row["d_values_covered"]
            total_hours += row["worker_core_hours"]
            hashes.update(summary.get("worker_sha256", []))
            if rho is not None:
                estimate = sum(expected_solutions(float(rho), a, b, row["ratio_max"],
                                                 options["height_min"]) for a, b in covered)
                row["heuristic_expected_solutions_covered"] = estimate
                total_expected += estimate
        except (OSError, ValueError, KeyError, TypeError) as exc:
            detail = str(exc)
            if completed.returncode and completed.stderr.strip():
                detail += ": " + completed.stderr.strip()[-2000:]
            errors.append({"band": bid, "error": f"invalid band collection: {detail}"})

        try:
            path = destination / "hits.jsonl"
            for line in path.read_text().splitlines() if path.exists() else []:
                if not line.strip():
                    continue
                record = json.loads(line)
                x, y, z = verify_hit(record, k, **options)
                d = int(record["d"])
                if not int(band["d_start"]) <= d < int(band["d_stop"]):
                    raise ValueError("hit lies outside its band's pair-sum interval")
                if not max(1, 3847 * d // 1000) <= abs(z) <= row["ratio_max"] * d:
                    raise ValueError("hit lies outside its band's z bounds")
                key = tuple(sorted((x, y, z)))
                if key not in hits:
                    # Preserve x,y,z roles so the verified d remains |x+y|.
                    hits[key] = {**record, "k": str(k), "x": str(x), "y": str(y), "z": str(z),
                                 "d": str(d), "campaign_bands": []}
                if bid not in hits[key]["campaign_bands"]:
                    hits[key]["campaign_bands"].append(bid)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            errors.append({"band": bid, "error": f"invalid collected hit: {exc}"})
        bands.append(row)

    summary = {
        "schema": SUMMARY_SCHEMA, "method": METHOD, "campaign_id": campaign["campaign_id"],
        "k": k, "primitive_only": options["primitive_only"], "height_min": str(options["height_min"]),
        "coverage_kind": "union_of_listed_bands", "claims_global_height_exclusion": False,
        "complete": not errors and all(not b["gaps"] for b in bands),
        "audited": False, "bands": bands, "d_values_covered": total_d,
        "worker_core_hours": total_hours, "hits": len(hits), "worker_sha256": sorted(hashes),
        "heuristic_expected_solutions_covered": total_expected if rho is not None else None,
        "errors": errors,
    }
    with (output / "hits.jsonl").open("w", encoding="utf-8") as handle:
        for key in sorted(hits):
            handle.write(json.dumps(hits[key], sort_keys=True) + "\n")
    atomic_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--campaign", type=Path, required=True)
    parser.add_argument("--results", type=Path, nargs="+", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    try:
        summary = collect(args.campaign, args.results, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({key: summary[key] for key in
                      ("campaign_id", "complete", "hits", "d_values_covered", "worker_core_hours", "errors")},
                     indent=2))
    print("Coverage uses each listed band's own ratio bound and the common strict height floor.")
    if summary["errors"]:
        return 1
    return 2 if args.require_complete and not summary["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
