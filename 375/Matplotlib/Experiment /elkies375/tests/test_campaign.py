"""Coverage, restart and tamper controls for actual lattice campaigns."""
from copy import deepcopy
from fractions import Fraction
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import campaign
import ej_backend
import equation
import region


class CampaignControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worker = ej_backend.build_worker()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT/"build")
        self.directory = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def make(self, *, target="cubes", width=1000, n_min=2, n_max=2,
             height_min=None, height_max=None, name="campaign"):
        directory = self.directory/name
        area = region.make_region(n_min, n_max, height_min, height_max)
        manifest = campaign.ensure_manifest(directory, area, target=target, band_width=width)
        return directory, area, manifest

    def finish(self, directory, area, manifest):
        return campaign.run(directory, manifest, area, max_tasks=10, max_tiles=0,
                            schedule="sequential", progress=lambda _: None)

    def native_record(self, name="campaign"):
        directory, area, manifest = self.make(name=name)
        task = next(region.iter_tasks(area))
        result = campaign.attempt_task(directory, task, manifest, max_tiles=0, worker=self.worker)
        return directory, area, manifest, task, result

    def test_full_n2_cubes_control_and_integer_only_completeness(self):
        directory, area, manifest = self.make()
        summary = self.finish(directory, area, manifest)
        points = json.loads((directory/"points.json").read_text())
        self.assertEqual({(p["n"], p["x"], p["y"]) for p in points},
                         {("2", "-5", "0"), ("2", "-20", "0")})
        self.assertEqual(summary["canonical_cube_hits"], 2)
        self.assertEqual(summary["equation_points"], 2)
        self.assertEqual(summary["primitive_equation_points"], 0)
        self.assertTrue(summary["all_planned_regions_complete"])
        self.assertTrue(summary["complete_target_search_in_n_interval"])
        self.assertFalse(summary["general_rational_y_search_complete"])
        for point in points:
            self.assertEqual(point["cube_gcd"], "5")
            self.assertEqual(sum(Fraction(v)**3 for v in point["cube_triple"]), 375)

    def test_primitive_target_and_restricted_height_scope_are_distinct(self):
        directory, area, manifest = self.make(target="primitive")
        summary = self.finish(directory, area, manifest)
        self.assertTrue(summary["complete_target_search_in_n_interval"])
        self.assertEqual(summary["equation_points"], 0)
        self.assertFalse(summary["general_rational_y_search_complete"])
        directory, area, manifest = self.make(height_min=25, height_max=25, name="restricted")
        summary = self.finish(directory, area, manifest)
        self.assertTrue(summary["all_planned_regions_complete"])
        self.assertFalse(summary["full_height_scope"])
        self.assertFalse(summary["complete_target_search_in_n_interval"])
        self.assertEqual(summary["equation_points"], 1)

    def test_unstarted_regions_and_missing_small_region_never_claim_complete(self):
        directory, area, manifest = self.make(width=1)
        tasks = list(region.iter_tasks(area, 1))
        campaign.search_small_heights(directory, area, primitive=False)
        campaign.attempt_task(directory, tasks[-1], manifest, max_tiles=0, worker=self.worker)
        summary = campaign.summarize(directory, manifest, area)
        self.assertEqual(summary["complete_tasks"], 1)
        self.assertEqual(int(summary["unstarted_tasks"]), len(tasks)-1)
        self.assertFalse(summary["complete_target_search_in_n_interval"])
        directory, area, manifest, task, _ = self.native_record(name="native_only")
        summary = campaign.summarize(directory, manifest, area)
        self.assertEqual(summary["complete_tasks"], 1)
        self.assertFalse(summary["small_height_complete"])
        self.assertFalse(summary["complete_target_search_in_n_interval"])

    def test_resume_uses_exact_contiguous_remaining_interval(self):
        directory, area, manifest = self.make(n_max=20, width=10**6)
        task = next(region.iter_tasks(area, 10**6))
        partial = campaign.attempt_task(directory, task, manifest, max_tiles=1, worker=self.worker)
        self.assertEqual(partial["status"], "partial")
        self.assertGreater(int(partial["next_index"]), task.index_start)
        original = ej_backend.iter_shell
        with patch.object(ej_backend, "iter_shell", wraps=original) as spy:
            complete = campaign.attempt_task(directory, task, manifest, max_tiles=0, worker=self.worker)
        self.assertEqual(spy.call_args.kwargs["index_start"], task.index_start)
        self.assertEqual(spy.call_args.kwargs["index_stop"], int(partial["next_index"]))
        self.assertEqual(complete["status"], "complete")
        other, area2, manifest2 = self.make(n_max=20, width=10**6, name="uninterrupted")
        control = campaign.attempt_task(other, next(region.iter_tasks(area2, 10**6)), manifest2,
                                        max_tiles=0, worker=self.worker)
        for key in ("next_index", "tiles_count", "lattice_points", "tiles", "points", "cube_triples"):
            self.assertEqual(complete[key], control[key], key)

    def test_worker_failure_discards_unvalidated_coverage_and_hits(self):
        directory, area, manifest = self.make()
        task = next(region.iter_tasks(area))
        before = campaign.attempt_task(directory, task, manifest, max_tiles=1, worker=self.worker)
        self.assertEqual(before["status"], "partial")

        def failed_worker(*args, **kwargs):
            yield {"type": "hit", "x": "20", "y": "20", "z": "-25"}
            yield {"type": "progress", "next_index": str(task.index_start),
                   "tiles": 1, "lattice_points": "19"}
            yield {"type": "end", "complete": True, "next_index": str(task.index_start),
                   "tiles": 1, "lattice_points": "19", "reason": "complete"}
            raise ej_backend.EJWorkerError("simulated nonzero exit after terminal")

        with patch.object(ej_backend, "iter_shell", side_effect=failed_worker):
            with self.assertRaisesRegex(ej_backend.EJWorkerError, "simulated"):
                campaign.attempt_task(directory, task, manifest, max_tiles=1, worker=self.worker)
        after = campaign.read_task(directory, task)
        self.assertEqual(after["status"], "error")
        for key in ("next_index", "tiles_count", "lattice_points", "tiles", "points", "cube_triples"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["attempts"][-1]["status"], "failed")
        summary = campaign.summarize(directory, manifest, area)
        self.assertEqual(summary["error_tasks"], 1)
        self.assertFalse(summary["complete_target_search_in_n_interval"])
        resumed = campaign.attempt_task(directory, task, manifest, max_tiles=0, worker=self.worker)
        self.assertEqual(resumed["status"], "complete")

    def test_manifest_source_region_and_exact_metadata_tampering_rejected(self):
        directory, area, manifest = self.make()
        mutations = [
            lambda m: m["source_sha256"].__setitem__("ej_worker.cpp", "0"*64),
            lambda m: m["region"].__setitem__("complete_height_scope", False),
            lambda m: m.__setitem__("planned_task_count", "999"),
            lambda m: m.__setitem__("schema_version", True),
            lambda m: m.__setitem__("n_min", 2),
        ]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                damaged = deepcopy(manifest)
                mutate(damaged)
                campaign.write_json(directory/"manifest.json", damaged)
                with self.assertRaises(ValueError):
                    campaign.load_manifest(directory)
        campaign.write_json(directory/"manifest.json", manifest)
        self.assertEqual(campaign.load_manifest(directory), manifest)

    def test_every_exact_point_field_and_source_are_rechecked(self):
        directory, _, _, task, good = self.native_record()
        mutations = {"t": "1", "S": "999", "N": "999", "cube_sum": "374",
                     "square_integer_H": "1", "direct_discrepancy": "1/10",
                     "exact": False, "integral_lift": False, "primitive": 0,
                     "source_cube_triple": ["5", "5", "5"], "source": "invented"}
        for field, value in mutations.items():
            with self.subTest(field=field):
                damaged = deepcopy(good)
                damaged["points"][0][field] = value
                campaign.write_json(campaign.task_path(directory, task), damaged)
                with self.assertRaises(ValueError):
                    campaign.read_task(directory, task)

    def test_valid_point_in_wrong_height_or_target_is_rejected(self):
        directory, _, _, task, good = self.native_record()
        damaged = deepcopy(good)
        damaged["points"] = equation.points_from_cube((5,5,5))
        damaged["cube_triples"] = [["5", "5", "5"]]
        campaign.write_json(campaign.task_path(directory, task), damaged)
        with self.assertRaisesRegex(ValueError, "height|sum"):
            campaign.read_task(directory, task)
        primitive, area, _ = self.make(target="primitive", name="primitive")
        primitive_task = next(region.iter_tasks(area))
        campaign.write_json(campaign.task_path(primitive, primitive_task), good)
        with self.assertRaisesRegex(ValueError, "primitive"):
            campaign.read_task(primitive, primitive_task)

    def test_forged_completion_gaps_and_attempt_counter_changes_rejected(self):
        directory, _, _, task, good = self.native_record()
        forged = campaign.empty_task(task)
        forged.update(status="complete", next_index=str(task.index_start))
        damaged_cases = [forged]
        missing_tile = deepcopy(good)
        missing_tile["tiles"].pop(0)
        missing_tile["tiles_count"] = str(len(missing_tile["tiles"]))
        damaged_cases.append(missing_tile)
        wrong_attempt = deepcopy(good)
        wrong_attempt["attempts"][0]["terminal"]["lattice_points"] = "0"
        damaged_cases.append(wrong_attempt)
        wrong_task = deepcopy(good)
        wrong_task["task"]["height"] = str(task.height+1)
        damaged_cases.append(wrong_task)
        missing_point = deepcopy(good)
        missing_point["points"] = []
        damaged_cases.append(missing_point)
        for damaged in damaged_cases:
            campaign.write_json(campaign.task_path(directory, task), damaged)
            with self.assertRaises(ValueError):
                campaign.read_task(directory, task)

    def test_small_height_scope_counter_and_missing_solution_rejected(self):
        directory, area, manifest = self.make()
        good = campaign.search_small_heights(directory, area, primitive=False)
        mutations = [
            lambda d: d["scope"].__setitem__("n_min", "999"),
            lambda d: d.__setitem__("complete", "yes"),
            lambda d: d.__setitem__("pairs_checked", 0),
            lambda d: d.__setitem__("points", []),
            lambda d: d["source_sha256"].__setitem__("equation.py", "0"*64),
        ]
        for mutate in mutations:
            damaged = deepcopy(good)
            mutate(damaged)
            campaign.write_json(directory/"low_height.json", damaged)
            with self.assertRaises(ValueError):
                campaign.summarize(directory, manifest, area)

    def test_huge_task_offset_is_exact_and_lazily_paged(self):
        directory, area, manifest = self.make(n_min=10**17, n_max=10**20)
        count = region.task_count(area, 1000)
        self.assertGreater(count, 2**53)
        selected = campaign.select_tasks(directory, area, band_width=1000,
                                         maximum=4, schedule="sequential", offset=count-2)
        self.assertEqual([task.logical_index for task in selected], [count-2, count-1])
        self.assertEqual(selected, list(region.iter_tasks(area, 1000, start=count-2, limit=4)))
        for task in selected:
            self.assertEqual(task.to_dict()["logical_index"], str(task.logical_index))
        summary = campaign.summarize(directory, manifest, area)
        self.assertEqual(summary["unstarted_tasks"], str(count))
        self.assertFalse(summary["complete_target_search_in_n_interval"])

    def test_empty_clipped_height_region_round_trips_without_claiming_full_search(self):
        directory, area, manifest = self.make(height_min=1000)
        self.assertGreater(area.height_min, area.height_max)
        loaded = campaign.load_manifest(directory)
        self.assertEqual(campaign.region_from_manifest(loaded), area)
        self.assertEqual(loaded, manifest)
        summary = self.finish(directory, area, manifest)
        self.assertEqual(summary["planned_tasks"], "0")
        self.assertTrue(summary["all_planned_regions_complete"])
        self.assertFalse(summary["full_height_scope"])
        self.assertFalse(summary["complete_target_search_in_n_interval"])
        damaged = deepcopy(manifest)
        damaged["region"]["height_max"] = str(area.height_max-1)
        campaign.write_json(directory/"manifest.json", damaged)
        with self.assertRaises(ValueError):
            campaign.load_manifest(directory)


if __name__ == "__main__":
    unittest.main()
