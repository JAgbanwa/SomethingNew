#!/usr/bin/env python3
"""Independently verify CE390 JSONL certificates using Python integer arithmetic.

No worker code, floating-point arithmetic, numerical tolerances, or third-party
packages are used here.  Default bounds and congruences are the production
campaign.  A successful check certifies individual solutions, not search
coverage or the existence of a solution in an unsearched region.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from fractions import Fraction
import json
from math import isqrt
from pathlib import Path
import re
import sys
from typing import Any


DECIMAL = re.compile(r"-?(?:0|[1-9][0-9]*)\Z")


class VerificationError(ValueError):
    """A candidate is not an exact certificate under the requested policy."""


@dataclass(frozen=True)
class Bounds:
    n_min: int = 10**43
    n_max: int = 10**45
    x_min: int = 10**54
    x_max: int = 10**55

    def __post_init__(self) -> None:
        if self.n_min > self.n_max or self.x_min > self.x_max:
            raise ValueError("bounds must be ordered inclusive intervals")


def integer(value: Any, field: str) -> int:
    """Accept decimal strings and JSON integers, never floats or booleans."""
    if isinstance(value, bool):
        raise VerificationError(f"{field}: booleans are not integers")
    if isinstance(value, int):
        return value
    if isinstance(value, str) and DECIMAL.fullmatch(value):
        return int(value)
    raise VerificationError(f"{field}: expected an integer or decimal integer string")


def rational(record: dict[str, Any], prefix: str) -> Fraction:
    try:
        numerator = integer(record[f"{prefix}_num"], f"{prefix}_num")
        denominator = integer(record[f"{prefix}_den"], f"{prefix}_den")
    except KeyError as exc:
        raise VerificationError(f"missing required field: {exc.args[0]}") from exc
    if denominator <= 0:
        raise VerificationError(f"{prefix}_den: denominator must be positive")
    value = Fraction(numerator, denominator)
    if (value.numerator, value.denominator) != (numerator, denominator):
        raise VerificationError(f"{prefix}: numerator/denominator must be reduced")
    return value


def verify_record(
    record: dict[str, Any],
    bounds: Bounds | None = None,
    *,
    require_congruences: bool = True,
    require_noninteger_d: bool = True,
    require_integer_sqrt: bool = False,
) -> dict[str, Any]:
    """Check one solution against the original radical equation.

    Passing custom signed bounds is supported for regression fixtures.  It is
    never implicit: omitted bounds always select the positive production box.
    The principal square root is required, including in signed test fixtures.
    """
    if not isinstance(record, dict):
        raise VerificationError("certificate must be a JSON object")
    bounds = bounds or Bounds()
    try:
        n = integer(record["n"], "n")
        x = integer(record["x"], "x")
    except KeyError as exc:
        raise VerificationError(f"missing required field: {exc.args[0]}") from exc
    if x == 0:
        raise VerificationError("x must be nonzero")
    if not bounds.n_min <= n <= bounds.n_max:
        raise VerificationError("n is outside the inclusive requested bounds")
    if not bounds.x_min <= x <= bounds.x_max:
        raise VerificationError("x is outside the inclusive requested bounds")
    if require_congruences and not (n % 3 == 1 and x % 12 == 5 and x % 7 != 0):
        raise VerificationError("the production congruences fail")

    d = rational(record, "d")
    y = rational(record, "y")
    if require_noninteger_d and d.denominator == 1:
        raise VerificationError("d is an integer")
    if y < 0:
        raise VerificationError("y is not the principal (nonnegative) square root")

    t = 36 * n**3 - 65
    a = x + 6 * n
    m_squared = x * x * a * a + t * x
    if m_squared < 0:
        raise VerificationError("the original radicand is negative")
    m = isqrt(m_squared)
    if m * m != m_squared:
        raise VerificationError("the original radical is not rational")
    exact_y = Fraction(m, abs(x))
    if y != exact_y:
        raise VerificationError("the reported y does not equal the original radical")
    # Both checks are deliberately retained.  The first tests the radical;
    # the second checks the original unsquared equation and its branch.
    if y * y != a * a + Fraction(t, x):
        raise VerificationError("the original radical identity fails")
    if Fraction(t) != -2 * d * x * x * (y - a):
        raise VerificationError("the original unsquared equation fails")
    if d != -(y + a) / (2 * x):
        raise VerificationError("the rationalized d identity fails")
    if require_integer_sqrt and y.denominator != 1:
        raise VerificationError("the radical is rational but not an integer")
    if "sqrt_integer" in record:
        if not isinstance(record["sqrt_integer"], bool):
            raise VerificationError("sqrt_integer must be a JSON boolean")
        if record["sqrt_integer"] != (y.denominator == 1):
            raise VerificationError("sqrt_integer does not match the exact radical")

    if ("gap_num" in record) != ("gap_den" in record):
        raise VerificationError("gap_num and gap_den must be supplied together")
    if "gap_num" in record and rational(record, "gap") != y - a:
        raise VerificationError("gap does not equal y-(x+6n)")
    if ("a" in record) != ("q" in record):
        raise VerificationError("a and q must be supplied together")
    if "a" in record:
        fiber_a = integer(record["a"], "a")
        fiber_q = integer(record["q"], "q")
        if fiber_a <= 0 or fiber_q <= 0:
            raise VerificationError("fiber a and q must be positive")
        if Fraction(-1) - Fraction(fiber_a, 2 * fiber_q) != d:
            raise VerificationError("the fiber a,q do not reproduce d")

    return {
        "n": str(n), "x": str(x),
        "d_num": str(d.numerator), "d_den": str(d.denominator),
        "y_num": str(y.numerator), "y_den": str(y.denominator),
        "sqrt_integer": y.denominator == 1,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="runner hits.jsonl file (one certificate per line)")
    parser.add_argument("--n-min", type=int, default=10**43)
    parser.add_argument("--n-max", type=int, default=10**45)
    parser.add_argument("--x-min", type=int, default=10**54)
    parser.add_argument("--x-max", type=int, default=10**55)
    parser.add_argument("--relax-congruences", action="store_true",
                        help="TEST ONLY: allow certificates outside production residue classes")
    parser.add_argument("--allow-integer-d", action="store_true")
    parser.add_argument("--require-integer-sqrt", action="store_true")
    args = parser.parse_args(argv)
    try:
        bounds = Bounds(args.n_min, args.n_max, args.x_min, args.x_max)
        count = 0
        seen: set[tuple[str, str, str, str]] = set()
        with args.input.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                if not line.strip():
                    continue
                try:
                    result = verify_record(
                        json.loads(line), bounds,
                        require_congruences=not args.relax_congruences,
                        require_noninteger_d=not args.allow_integer_d,
                        require_integer_sqrt=args.require_integer_sqrt,
                    )
                except (VerificationError, json.JSONDecodeError) as exc:
                    raise VerificationError(f"line {line_number}: {exc}") from exc
                count += 1
                seen.add((result["n"], result["x"], result["d_num"], result["d_den"]))
        print(json.dumps({"status": "verified", "certificates": count,
                          "unique_solutions": len(seen),
                          "duplicates": count - len(seen),
                          "note": "Individual certificates only; this does not certify search coverage."},
                         sort_keys=True))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
