"""Sieve arithmetic and Python/C++ agreement; see test_q_sieve_integration.py for end-to-end tests."""
from __future__ import annotations

import math
import os
from pathlib import Path
import random
import shlex
import shutil
import subprocess
import tempfile
import unittest

from q_sieve import (
    MAX_BLOCK_SIZE, PRIME_LIMIT, first_forbidden_prime, forbidden_primes,
    obstruction_mask, reject_q,
)

ROOT = Path(__file__).resolve().parents[1]


def trial_prime(n: int) -> bool:
    # Deliberately independent of the production Eratosthenes sieve.
    return n >= 2 and all(n % d for d in range(2, math.isqrt(n) + 1))


class ArithmeticTests(unittest.TestCase):
    def test_count_and_prefix(self):
        self.assertEqual(len(forbidden_primes()), 733)
        self.assertEqual(forbidden_primes()[:10],
                         (7, 19, 31, 37, 43, 67, 73, 79, 97, 127))

    def test_complete_classification_by_exhaustive_residues(self):
        bad = set(forbidden_primes())
        for p in range(2, PRIME_LIMIT):
            if not trial_prime(p):
                continue
            # Enumerate residues directly; do NOT use the cubic-character test.
            has_root = any((36 * r * r * r - 65) % p == 0 for r in range(p))
            self.assertEqual(p in bad, not has_root and p not in (2, 3), p)

    def test_special_primes_are_not_added(self):
        for p in (2, 3, 5, 13):
            self.assertNotIn(p, forbidden_primes())
        for q in (1, 5, 13, 25, 65, 169, 5**10 * 13**7):
            self.assertFalse(reject_q(q, require_integer_sqrt=True), q)

    def test_all_forbidden_prime_powers_rejected(self):
        for p in forbidden_primes():
            for q in (p, p**2, p**9):
                self.assertTrue(reject_q(q, require_integer_sqrt=True), q)
                self.assertEqual(first_forbidden_prime(q, require_integer_sqrt=True), p)

    def test_witness(self):
        self.assertEqual(first_forbidden_prime(7 * 19, require_integer_sqrt=True), 7)
        self.assertIsNone(first_forbidden_prime(65, require_integer_sqrt=True))

    def test_large_denominators(self):
        for q in (7 * 10**54, 19 * (10**53 + 1), 10**2000 * 7):
            self.assertTrue(reject_q(q, require_integer_sqrt=True))
        self.assertFalse(reject_q(5**78 * 13**17, require_integer_sqrt=True))

    def test_rational_mode_never_rejects(self):
        for q in (*forbidden_primes(), 7 * 19 * 10**54):
            self.assertFalse(reject_q(q, require_integer_sqrt=False))
            self.assertIsNone(first_forbidden_prime(q, require_integer_sqrt=False))

    def test_policy_cannot_be_omitted_or_coerced(self):
        with self.assertRaises(TypeError):
            reject_q(7)  # type: ignore[call-arg]
        for mode in (None, "false", "true", 0, 1):
            with self.assertRaises(TypeError):
                reject_q(7, require_integer_sqrt=mode)  # type: ignore[arg-type]

    def test_invalid_denominators(self):
        for q in (0, -1, -7):
            with self.assertRaises(ValueError):
                reject_q(q, require_integer_sqrt=True)
        for q in (True, False, "7", 7.0):
            with self.assertRaises(TypeError):
                reject_q(q, require_integer_sqrt=True)  # type: ignore[arg-type]

    def test_no_divisor_of_polynomial_value_is_rejected(self):
        # A complete divisor check, including both signs of n, on 501 values.
        for n in range(-250, 251):
            value = abs(36 * n**3 - 65)
            self.assertFalse(reject_q(value, require_integer_sqrt=True), n)
            for q in range(1, math.isqrt(value) + 1):
                if value % q == 0:
                    self.assertFalse(reject_q(q, require_integer_sqrt=True), (n, q))
                    self.assertFalse(reject_q(value // q, require_integer_sqrt=True))


class SegmentedTests(unittest.TestCase):
    def test_matches_individual_decisions(self):
        for start, step in ((1, 1), (1, 6), (5, 6), (7, 7), (1, 7),
                            (10**55 + 123, 1), (10**55 + 7, 6),
                            (10**80 + 1, 7 * 19), (1, 10**55 + 7)):
            mask = obstruction_mask(start, 2500, step=step, require_integer_sqrt=True)
            expected = bytearray(reject_q(start + i * step, require_integer_sqrt=True)
                                 for i in range(2500))
            self.assertEqual(mask, expected, (start, step))

    def test_unfiltered_million_count(self):
        mask = obstruction_mask(1, 1_000_000, require_integer_sqrt=True)
        self.assertEqual(sum(mask), 446013)
        self.assertEqual(sum(mask[0::6]) + sum(mask[4::6]), 146236)

    def test_block_boundaries(self):
        full = obstruction_mask(10**55 + 123, 6000, require_integer_sqrt=True)
        joined = bytearray()
        for offset in range(0, 6000, 73):
            joined += obstruction_mask(10**55 + 123 + offset, min(73, 6000 - offset),
                                       require_integer_sqrt=True)
        self.assertEqual(full, joined)

    def test_rational_mode_mask(self):
        self.assertEqual(obstruction_mask(7, 1000, step=7, require_integer_sqrt=False),
                         bytearray(1000))

    def test_empty_and_singleton_masks(self):
        self.assertEqual(obstruction_mask(1, 0, require_integer_sqrt=True), bytearray())
        self.assertEqual(obstruction_mask(7, 1, require_integer_sqrt=True), b"\x01")
        self.assertEqual(obstruction_mask(13, 1, require_integer_sqrt=True), b"\x00")

    def test_invalid_block_arguments(self):
        for start, count, step in ((0, 1, 1), (1, -1, 1), (1, 1, 0),
                                   (1, MAX_BLOCK_SIZE + 1, 1)):
            with self.assertRaises(ValueError):
                obstruction_mask(start, count, step=step, require_integer_sqrt=True)
        with self.assertRaises(TypeError):
            obstruction_mask(1, True, require_integer_sqrt=True)

    def test_repeated_denominator_and_mode_switches(self):
        for mode, expected in ((True, True), (False, False), (True, True)):
            self.assertEqual(reject_q(7, require_integer_sqrt=mode), expected)
        self.assertFalse(reject_q(13, require_integer_sqrt=True))


class NativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shlex.split(os.environ.get("CXX", "g++"))
        if not compiler or shutil.which(compiler[0]) is None:
            raise RuntimeError("C++ compiler missing: native validation is required")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "check_q_sieve"
        command = compiler + shlex.split(os.environ.get("CPPFLAGS", ""))
        command += shlex.split(os.environ.get("CXXFLAGS", "-O2 -std=c++17 -Wall -Wextra -Wpedantic"))
        command += [str(ROOT / "tests/check_q_sieve.cpp"), "-o", str(cls.binary)]
        command += shlex.split(os.environ.get("LDFLAGS", ""))
        command += shlex.split(os.environ.get("LDLIBS", "-lgmpxx -lgmp"))
        subprocess.run(command, check=True, capture_output=True, text=True, timeout=60)

    def test_cpp_prime_list_matches(self):
        result = subprocess.run([str(self.binary), "--primes"], check=True,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(tuple(map(int, result.stdout.split())), forbidden_primes())

    def test_cpp_python_differential(self):
        rng = random.Random(390)
        qs = [1, 2, 3, 5, 13, 65, 7, 19, 7**12, 13**20, 10**55, 7 * 10**54]
        qs += list(forbidden_primes())
        qs += [rng.randrange(1, 10**55) for _ in range(1000)]
        qs += [10**1000, 7 * 10**1000, 13**1000]
        cases = [(q, mode) for q in qs for mode in (True, False, True)]
        data = "".join(f"{q} {int(mode)}\n" for q, mode in cases)
        result = subprocess.run([str(self.binary)], input=data, text=True,
                                capture_output=True, check=True, timeout=30)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), len(cases))
        for (q, mode), line in zip(cases, lines):
            actual, witness = map(int, line.split())
            self.assertEqual(bool(actual), reject_q(q, require_integer_sqrt=mode), q)
            self.assertEqual(witness, first_forbidden_prime(q, require_integer_sqrt=mode) or 0)

    def test_cpp_invalid_denominators(self):
        for q in ("0", "-7", "not-an-integer"):
            result = subprocess.run([str(self.binary)], input=f"{q} 1\n", text=True,
                                    capture_output=True, timeout=30)
            self.assertEqual(result.returncode, 2, q)


if __name__ == "__main__":
    unittest.main()
