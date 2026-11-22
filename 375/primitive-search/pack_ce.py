#!/usr/bin/env python3
"""Pair a generated page or band campaign into bounded two-core CE jobs.

This writes a source-bound bundle.json. It does not submit anything. The
reservation counts both allocated cores, including an idle final core, for the
whole CE instance allowance. A task's runtime estimate is never used to reduce
that reservation.
"""
from __future__ import annotations

import argparse
from decimal import Decimal
from pathlib import Path
import sys

from gap_common import (METHOD, PAGE_SCHEMA, atomic_json, load_json, registered_tasks,
                        search_options, sha256_file, validate_task)
from run_ce_bundle import BUNDLE_SCHEMA, validate_bundle

ROOT = Path(__file__).resolve().parent


def child_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("manifest references a file outside its campaign directory")
    return path


def pack(manifest: Path, hours: float, maximum: float) -> dict:
    record = load_json(manifest)
    if record.get("schema") == PAGE_SCHEMA:
        pages = [manifest]
    elif record.get("schema") == "ce375-primitive-bands-v1":
        bands = record.get("bands")
        if not isinstance(bands, list) or not bands:
            raise ValueError("band campaign has no bands")
        pages = []
        cursor = int(record["d_start"])
        for band in bands:
            if int(band["d_start"]) != cursor or int(band["d_stop"]) <= cursor:
                raise ValueError("campaign bands must be adjacent and disjoint")
            path = child_path(manifest.parent, band["page"])
            page = load_json(path)
            if any(page.get(key) != band.get(key) for key in ("campaign_id", "d_start", "d_stop", "ratio_max")):
                raise ValueError("band page differs from its campaign manifest")
            if search_options(page) != search_options(record):
                raise ValueError("band page search constraints differ from its campaign")
            cursor = int(band["d_stop"])
            pages.append(path)
        if cursor != int(record["d_stop"]):
            raise ValueError("campaign endpoint differs from its final band")
    else:
        raise ValueError("input must be a generated page.json or campaign.json")
    tasks, campaigns = [], []
    for path in pages:
        page = load_json(path)
        if page.get("method") != METHOD or int(page["k"]) != 375 or not search_options(page)["primitive_only"]:
            raise ValueError("only primitive-375 pages can be packed here")
        if page["campaign_id"] in campaigns:
            raise ValueError("duplicate page campaign identifier")
        campaigns.append(page["campaign_id"])
        for entry in registered_tasks(page).values():
            task = load_json(child_path(path.parent, entry["file"]))
            validate_task(task)
            if any(task.get(key) != entry.get(key) for key in ("task_id", "d_start", "d_stop")):
                raise ValueError("task identity or interval differs from its registered entry")
            if any(task.get(key) != page.get(key) for key in ("campaign_id", "method", "k", "ratio_max")):
                raise ValueError("task parameters differ from its page")
            if search_options(task) != search_options(page):
                raise ValueError("task constraints differ from its page")
            tasks.append(task)
    if not tasks:
        raise ValueError("no tasks found")
    groups = [tasks[i:i + 2] for i in range(0, len(tasks), 2)]
    reserved = Decimal(str(hours)) * 2 * len(groups)
    cap = Decimal(str(maximum))
    if not reserved.is_finite() or not cap.is_finite() or cap <= 0 or reserved > cap:
        raise ValueError(f"allocation of {reserved} core-hours exceeds the positive cap {cap}")
    bundle = {"schema": BUNDLE_SCHEMA, "campaign_id": record["campaign_id"],
              "task_campaign_ids": campaigns, "groups": groups,
              "max_instance_hours": hours, "cores_per_instance": 2,
              "total_reserved_core_hours": float(reserved),
              "worker_source_sha256": sha256_file(ROOT / "src" / "gap_worker.cpp"),
              "source_manifest_sha256": sha256_file(manifest)}
    validate_bundle(bundle)
    return bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign", type=Path, required=True, help="page.json or band campaign.json")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--instance-hours", type=float, default=1)
    parser.add_argument("--max-core-hours", type=float, default=1800)
    args = parser.parse_args()
    try:
        if args.output.exists():
            raise ValueError("output already exists; use a new filename")
        bundle = pack(args.campaign.resolve(), args.instance_hours, args.max_core_hours)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(args.output, bundle)
        print(f"{sum(map(len, bundle['groups']))} tasks; {len(bundle['groups'])} two-core instances; "
              f"{bundle['total_reserved_core_hours']:g} reserved core-hours")
        print(f"wrote {args.output}; no job submitted")
        return 0
    except (ValueError, KeyError, OSError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    sys.exit(main())
