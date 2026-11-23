import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def invoke(*args):
    proc = subprocess.run([sys.executable, str(ROOT / "search375.py"), *map(str, args)],
                          cwd=ROOT, text=True, capture_output=True, check=False)
    return proc, [json.loads(line) for line in proc.stdout.splitlines()]


class CommandLineTest(unittest.TestCase):
    def test_both_algorithms_complete_same_small_box(self):
        for command in ("booker-box", "elkies"):
            proc, records = invoke(command, "--height-max", 80, "--progress-every", 0)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(records[0]["scope"]["cube_height_max"], "80")
            self.assertTrue(records[-1]["complete"])
            self.assertEqual(records[-1]["solutions"], 0)
            self.assertFalse(any(row["type"] == "solution" for row in records))
            self.assertEqual(records[0]["required"]["gcd_X_Y"], 1)
            self.assertIn("source_sha256", records[0])

    def test_known_nonprimitive_point_is_not_reported_as_solution(self):
        proc, records = invoke("verify-point", "--n", 2, "--X", 5, "--Y", 45,
                               "--signed-d=-8")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(records[-1]["status"], "error")
        self.assertIn("gcd", records[-1]["error"])
        self.assertFalse(records[-1]["complete"])
        proc, records = invoke("verify-cubes", 20, -25, 20)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(records[-1]["solutions"], 0)

    def test_partial_lattice_run_does_not_claim_full_coverage(self):
        proc, records = invoke("elkies-shell", "--height", 100,
                               "--max-tiles", 1, "--progress-every", 0)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        self.assertFalse(records[-1]["complete"])
        self.assertEqual(records[-1]["backend_terminal"]["reason"], "tile_budget")
        self.assertGreater(int(records[-1]["backend_terminal"]["next_index"]),
                           int(records[0]["scope"]["index_start"]))

    def test_rational_d_search_has_explicit_height_and_n_scope(self):
        proc, records = invoke("rational-d", "--height-max", 12,
                               "--n-min", -10, "--n-max", 10, "--d=-8",
                               "--progress-every", 0)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertTrue(records[-1]["complete"])
        self.assertEqual(records[0]["rational_d_filter"]["values"], ["-8"])
        self.assertEqual(records[-1]["backend_counters"]["integer_scales"], 1)
        self.assertEqual(records[-1]["solutions"], 0)

    def test_box_continuation_retains_original_filters(self):
        proc, records = invoke("elkies", "--height-max", 80, "--max-tiles", 1,
                               "--d=-8", "--n-min", -10, "--n-max", 10,
                               "--d-height", 20, "--progress-every", 0)
        self.assertEqual(proc.returncode, 3, proc.stderr)
        continuation = records[-1]["resume"]["argv"]
        self.assertIn("--cube-height-max", continuation)
        self.assertEqual(continuation[continuation.index("--cube-height-max")+1], "80")
        self.assertIn("--d=-8", continuation)
        self.assertIn("--n-min=-10", continuation)
        self.assertIn("--n-max=10", continuation)
        self.assertIn("--d-height=20", continuation)
        resumed, result = invoke(*continuation)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertTrue(result[-1]["complete"])
        self.assertEqual(result[0]["scope"]["cube_height_max"], "80")

    def test_invalid_bounds_fail_and_existing_output_is_preserved(self):
        proc, records = invoke("booker", "--D-min", 5, "--D-max", 2, "--z-max", 10)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(records[-1]["complete"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "existing.jsonl"
            output.write_text("keep this\n")
            proc, _ = invoke("booker-box", "--height-max", 10, "--output", output)
            self.assertEqual(proc.returncode, 2)
            self.assertEqual(output.read_text(), "keep this\n")

    def test_cli_target_is_fixed_and_no_relaxation_flag_exists(self):
        proc, _ = invoke("booker-box", "--height-max", 10, "--target", 3)
        self.assertEqual(proc.returncode, 2)
        proc, _ = invoke("elkies", "--height-max", 30, "--include-nonprimitive")
        self.assertEqual(proc.returncode, 2)


if __name__ == "__main__":
    unittest.main()
