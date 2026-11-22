"""Band collection must preserve constraints, exact hits, and incomplete coverage."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from collect_campaign import CAMPAIGN_SCHEMA, collect, read_manifest  # noqa: E402
from gap_common import CHECKPOINT_SCHEMA, COUNTERS, METHOD, PAGE_SCHEMA, TASK_SCHEMA  # noqa: E402


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def fixture(base: Path, bands=((1, 2, 4), (2, 4, 8)), *, k=3, height_min=0,
            hits: dict[int, list[dict]] | None = None) -> tuple[Path, Path]:
    bundle, results = base / "planned", base / "results"
    results.mkdir(parents=True)
    manifest = {"schema": CAMPAIGN_SCHEMA, "method": METHOD, "campaign_id": "fixture",
                "k": k, "primitive_only": True, "height_min": str(height_min),
                "d_start": str(bands[0][0]), "d_stop": str(bands[-1][1]), "rho": 0.05, "bands": []}
    for i, (lo, hi, ratio) in enumerate(bands):
        bid, tid = f"fixture-b{i:03d}", f"fixture-b{i:03d}-0"
        row = {"campaign_id": bid, "d_start": str(lo), "d_stop": str(hi),
               "ratio_max": ratio, "page": f"bands/b{i:03d}/page.json"}
        manifest["bands"].append(row)
        task = {"schema": TASK_SCHEMA, "method": METHOD, "campaign_id": bid, "task_id": tid,
                "k": k, "d_start": str(lo), "d_stop": str(hi), "ratio_max": ratio,
                "primitive_only": True, "height_min": str(height_min), "deadline_seconds": 0}
        page = {**task, "schema": PAGE_SCHEMA, "rho": 0.05,
                "tasks": [{"task_id": tid, "file": f"tasks/{tid}.json",
                           "d_start": str(lo), "d_stop": str(hi)}]}
        page.pop("task_id")
        write(bundle / row["page"], page)
        write((bundle / row["page"]).parent / "tasks" / f"{tid}.json", task)
        returned = results / f"b{i:03d}"
        write(returned / "task.json", task)
        found = (hits or {}).get(i, [])
        counts = {name: 0 for name in COUNTERS}
        counts.update(d_total=hi - lo, d_no_roots=hi - lo)
        if found:
            counts.update(d_no_roots=hi - lo - 1, d_live=1, roots=1, candidates=1,
                          pass_2adic=1, pass_residue=1, exact_checks=1, hits=len(found))
        checkpoint = {**task, "schema": CHECKPOINT_SCHEMA, "covered_start": str(lo),
                      "d_next": str(hi), "worker_sha256": "a" * 64, "counters": counts,
                      "worker_seconds": 3.6}
        write(returned / "checkpoint.json", checkpoint)
        write(returned / "status.json", {"state": "complete", "worker_seconds": 3.6})
        (returned / "hits.jsonl").write_text("".join(json.dumps(hit) + "\n" for hit in found))
    write(bundle / "campaign.json", manifest)
    return bundle / "campaign.json", results


class CampaignCollection(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="collector-test-", dir=ROOT)
        self.base = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_bands_keep_distinct_geometry_and_verified_hits(self):
        hit = {"k": "3", "x": "4", "y": "-5", "z": "4", "d": "1"}
        manifest, results = fixture(self.base, hits={0: [hit, hit]})
        summary = collect(manifest, [results, results / "b000"], self.base / "collected")
        self.assertTrue(summary["complete"])
        self.assertEqual(summary["errors"], [])
        self.assertEqual(summary["hits"], 1)
        self.assertEqual(summary["d_values_covered"], 3)
        self.assertAlmostEqual(summary["worker_core_hours"], 0.002)
        self.assertEqual([b["ratio_max"] for b in summary["bands"]], [4, 8])
        self.assertFalse(summary["claims_global_height_exclusion"])
        self.assertFalse(summary["audited"])
        saved = [json.loads(line) for line in (self.base / "collected" / "hits.jsonl").read_text().splitlines()]
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["campaign_bands"], ["fixture-b000"])

    def test_partial_band_reports_its_exact_gap_and_exit_status(self):
        manifest, results = fixture(self.base, bands=((1, 2, 4), (2, 6, 8)))
        cp_path = results / "b001" / "checkpoint.json"
        cp = json.loads(cp_path.read_text())
        cp["d_next"] = "4"
        cp["counters"].update(d_total=2, d_no_roots=2)
        write(cp_path, cp)
        destination = self.base / "collected"
        run = subprocess.run([sys.executable, str(ROOT / "collect_campaign.py"),
                              "--campaign", str(manifest), "--results", str(results),
                              "--output-dir", str(destination), "--require-complete"],
                             capture_output=True, text=True)
        self.assertEqual(run.returncode, 2, run.stderr)
        summary = json.loads((destination / "summary.json").read_text())
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["errors"], [])
        self.assertEqual(summary["bands"][1]["gaps"], [["4", "6"]])
        self.assertEqual(summary["d_values_covered"], 3)

    def test_imprimitive_375_hit_is_an_error(self):
        hit = {"k": "375", "x": "20", "y": "-25", "z": "20", "d": "5"}
        manifest, results = fixture(self.base, bands=((5, 6, 4),), k=375, hits={0: [hit]})
        summary = collect(manifest, [results], self.base / "collected")
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["hits"], 0)
        self.assertTrue(summary["errors"])

    def test_valid_identity_outside_band_geometry_is_not_credited(self):
        hit = {"k": "3", "x": "1", "y": "1", "z": "1", "d": "2"}
        manifest, results = fixture(self.base, bands=((2, 3, 4),), hits={0: [hit]})
        summary = collect(manifest, [results], self.base / "collected")
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["hits"], 0)
        self.assertTrue(summary["errors"])

    def test_inconsistent_checkpoint_cannot_claim_complete_coverage(self):
        manifest, results = fixture(self.base)
        cp_path = results / "b001" / "checkpoint.json"
        cp = json.loads(cp_path.read_text())
        cp["counters"]["d_total"] = 1
        write(cp_path, cp)
        summary = collect(manifest, [results], self.base / "collected")
        self.assertFalse(summary["complete"])
        self.assertEqual(summary["bands"][1]["gaps"], [["2", "4"]])
        self.assertTrue(summary["errors"])

    def test_overlap_is_rejected_before_collection(self):
        manifest, _ = fixture(self.base)
        plan = json.loads(manifest.read_text())
        plan["bands"][1]["d_start"] = "1"
        write(manifest, plan)
        with self.assertRaisesRegex(ValueError, "partition"):
            read_manifest(manifest)

    def test_page_constraint_mismatch_is_rejected(self):
        manifest, _ = fixture(self.base)
        page_path = manifest.parent / "bands" / "b001" / "page.json"
        page = json.loads(page_path.read_text())
        page["height_min"] = "100"
        write(page_path, page)
        with self.assertRaisesRegex(ValueError, "disagrees"):
            read_manifest(manifest)

    def test_page_path_cannot_escape_the_campaign_bundle(self):
        manifest, _ = fixture(self.base)
        plan = json.loads(manifest.read_text())
        plan["bands"][0]["page"] = "../outside.json"
        write(manifest, plan)
        with self.assertRaisesRegex(ValueError, "within"):
            read_manifest(manifest)


if __name__ == "__main__":
    unittest.main()
