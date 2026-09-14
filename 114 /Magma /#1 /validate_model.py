#!/usr/bin/env python3
"""Independent exact-arithmetic regression checks for the corrected Magma model.

Run from any directory with Python 3:
    python validate_model.py
To validate a different checkout:
    python validate_model.py --root /path/to/the/number-1/directory

This checks the algebra and the historical counterexamples. It does not run
Magma, certify ranks, or claim the existence/nonexistence of a requested solution.
Only the Python standard library is used.
"""

import argparse
from fractions import Fraction as Q
from pathlib import Path
import re


def original_equation(m, u, y):
    m, u, y = map(Q, (m, u, y))
    a = 12 * u + 7
    b = a + 18 * m
    return a != 0 and b != 0 and y * y == 1 + (972 * m**3 - 19) / (a * b**2)


def requested_solution(m, u, y, allow_integer_y=False):
    m, u, y = map(Q, (m, u, y))
    return (
        m.denominator == u.denominator == 1
        and (allow_integer_y or y.denominator != 1)
        and original_equation(m, u, y)
    )


# Sparse Laurent polynomials over Q in a,b,y. Negative exponents allow exact
# symbolic substitution x=6*(b^3-114)/a without a symbolic-algebra dependency.
def constant(value):
    return {(0, 0, 0): Q(value)} if value else {}


def add(*polynomials):
    result = {}
    for polynomial in polynomials:
        for powers, coefficient in polynomial.items():
            result[powers] = result.get(powers, Q(0)) + coefficient
    return {powers: coefficient for powers, coefficient in result.items() if coefficient}


def mul(*polynomials):
    result = constant(1)
    for polynomial in polynomials:
        product = {}
        for powers, coefficient in result.items():
            for other_powers, other_coefficient in polynomial.items():
                key = tuple(a + b for a, b in zip(powers, other_powers))
                product[key] = product.get(key, Q(0)) + coefficient * other_coefficient
        result = {powers: coefficient for powers, coefficient in product.items() if coefficient}
    return result


def power(polynomial, exponent):
    assert exponent >= 0
    return mul(*([polynomial] * exponent))


def check_symbolic_identity():
    a, b, y = ({(1, 0, 0): Q(1)}, {(0, 1, 0): Q(1)}, {(0, 0, 1): Q(1)})
    d = add(power(b, 3), constant(-114))
    x = mul(constant(6), d, {(-1, 0, 0): Q(1)})
    w = mul(constant(6), b, x, y)
    curve_residual = add(
        power(w, 2),
        mul(constant(-1), power(x, 3)),
        mul(constant(-18), power(b, 2), power(x, 2)),
        mul(constant(-108), b, d, x),
        mul(constant(216), power(d, 2)),
    )
    b_minus_a = add(b, mul(constant(-1), a))
    # This is 6*a*b^2 times the residual in the original equation,
    # because 972*((b-a)/18)^3 = (b-a)^3/6.
    cleared_original_residual = add(
        mul(constant(6), a, power(b, 2), power(y, 2)),
        mul(constant(-6), a, power(b, 2)),
        mul(constant(-1), power(b_minus_a, 3)),
        constant(114),
    )
    difference = add(
        curve_residual,
        mul(constant(-216), power(d, 2), {(-3, 0, 0): Q(1)}, cleared_original_residual),
    )
    assert not difference, "Corrected curve does not match the original equation symbolically"


def check_positive_fixture():
    # A rational solution used only to test the map. Its nonintegral m makes
    # it inadmissible for the user's integer-(m,u) problem.
    m, u, y = Q(10891036, 1440747), Q(-21), Q(-78246760204, 84593013813)
    assert original_equation(m, u, y)
    assert original_equation(m, u, -y)
    assert not requested_solution(m, u, y)
    assert not requested_solution(m, u, y, allow_integer_y=True)
    a = 12 * u + 7
    b = a + 18 * m
    d = b**3 - 114
    x = 6 * d / a
    w = 6 * b * x * y
    assert w**2 == x**3 + 18 * b**2 * x**2 + 108 * b * d * x - 216 * d**2
    recovered_a = 6 * d / x
    assert ((b - recovered_a) / 18, (recovered_a - 7) / 12, w / (6 * b * x)) == (m, u, y)
    assert not original_equation(m, u, y + 1)
    assert not original_equation(0, Q(-7, 12), 0)  # a=0: undefined
    assert not original_equation(Q(-7, 18), 0, 0)  # b=0: undefined


def check_historical_candidates(root):
    path = root / "folder1 " / "answers.folder1"
    text = path.read_text(encoding="utf-8")
    # Magma wraps long integers using backslash-newline continuation.
    text = re.sub(r"\\\s*\n\s*", "", text)
    rational = r"([+-]?\d+(?:/\d+)?)"
    pattern = re.compile(r"k=(\d+)\s*:\s*u=" + rational + r",\s*m=" + rational + r",\s*y=" + rational)
    matches = pattern.findall(text)
    assert len(matches) == 7, f"Expected seven complete historical candidates in {path}; got {len(matches)}"
    for number, raw_u, raw_m, raw_y in matches:
        m, u, y = Q(raw_m), Q(raw_u), Q(raw_y)
        a = 12 * u + 7
        b = a + 18 * m
        rhs = 1 + (972 * m**3 - 19) / (a * b**2)
        assert b == Q(-30, 11), f"Historical candidate {number}: unexpected B"
        assert rhs == a * y**2, f"Historical candidate {number}: no longer reproduces missing-factor error"
        assert rhs < 0, f"Historical candidate {number}: expected negative original RHS"
        assert m.denominator != 1 and u.denominator != 1
        assert not original_equation(m, u, y)
        assert not requested_solution(m, u, y, allow_integer_y=True)
    return len(matches)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    check_symbolic_identity()
    check_positive_fixture()
    count = check_historical_candidates(args.root)
    print("PASS: corrected curve identity verified by exact symbolic expansion.")
    print("PASS: rational positive fixture, inverse map, and domain rejection verified.")
    print(f"PASS: all {count} complete historical candidates rejected using exact fractions.")
    print("These checks do not execute Magma or constitute a search for solutions.")


if __name__ == "__main__":
    main()
