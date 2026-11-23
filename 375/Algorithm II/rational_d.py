"""Optional exact d-first search, separate from the two named algorithms.

For d=p/q reduced, X=q*m and t=2*n+1, all integer scales m satisfy
    p*q*(p+q)*m**3 + 6*p*q*t*m**2 + 125 - 9*t**3 = 0.
Integer roots are isolated exactly, so m is NOT restricted to +/-1 or to a
user-specified cutoff. A finite job bounds rational height and n instead.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd, isqrt
from typing import Callable, Iterable, Iterator

from equation375 import Point, RationalDFilter, validate_point


def integer_roots(coefficients: Iterable[int]) -> tuple[int, ...]:
    """All integer roots of a nonzero polynomial of degree at most three.

    Coefficients are highest degree first. A Cauchy root bound encloses every
    root. Exact rational enclosures of derivative roots split the remaining
    integer intervals into monotone pieces, which need only binary search.
    No factorization, float, approximate root or arbitrary precision cutoff.
    """
    cs = tuple(coefficients)
    if not cs or any(type(v) is not int for v in cs):
        raise ValueError("coefficients must be a nonempty sequence of integers")
    while len(cs) > 1 and cs[0] == 0:
        cs = cs[1:]
    degree = len(cs) - 1
    if degree > 3:
        raise ValueError("only degree at most three is supported")
    if degree == 0:
        if cs[0] == 0:
            raise ValueError("zero polynomial has infinitely many integer roots")
        return ()
    if degree == 1:
        a, b = cs
        return (-b // a,) if (-b) % a == 0 else ()
    if degree == 2:
        a, b, c = cs
        discriminant = b * b - 4 * a * c
        if discriminant < 0:
            return ()
        r = isqrt(discriminant)
        if r * r != discriminant:
            return ()
        return tuple(sorted({v // (2 * a) for v in (-b-r, -b+r)
                             if v % (2 * a) == 0}))
    a, b, c, e = cs
    lead = abs(a)
    bound = 1 + max((abs(v) + lead - 1) // lead for v in (b, c, e))

    def value(x: int) -> int:
        return ((a * x + b) * x + c) * x + e

    special = {-bound, bound}
    disc = 4 * b * b - 12 * a * c
    if disc >= 0:
        root = isqrt(disc)
        # sqrt(disc) lies in [root,root+1]. With a negative denominator the
        # endpoint order reverses; considering both endpoints handles it.
        for sign in (-1, 1):
            for r in (root, root + 1):
                near = (-2 * b + sign * r) // (6 * a)
                for offset in range(-2, 3):
                    candidate = near + offset
                    if -bound <= candidate <= bound:
                        special.add(candidate)
    cuts = sorted(special)
    roots = {x for x in cuts if value(x) == 0}
    for left, right in zip(cuts, cuts[1:]):
        lo, hi = left + 1, right - 1
        if lo > hi:
            continue
        vlo, vhi = value(lo), value(hi)
        if vlo == 0:
            roots.add(lo)
            continue
        if vhi == 0:
            roots.add(hi)
            continue
        if (vlo > 0) == (vhi > 0):
            continue
        increasing = vlo < vhi
        while lo <= hi:
            mid = (lo + hi) // 2
            v = value(mid)
            if v == 0:
                roots.add(mid)
                break
            if (v < 0) == increasing:
                lo = mid + 1
            else:
                hi = mid - 1
    return tuple(sorted(roots))


def rational_parameters(height_min: int, height_max: int) -> Iterator[Fraction]:
    """All reduced candidates by height, using proved odd/mod-3 filters.

    Every admissible parameter has q odd and p == q != 0 (mod 3).
    Each rational is visited once, at H=max(abs(p),q).
    """
    if height_min < 1 or height_max < height_min:
        raise ValueError("need 1 <= height_min <= height_max")
    for h in range(height_min, height_max + 1):
        for q in range(1, h + 1, 2):
            if q % 3 == 0:
                continue
            for p in (-h, h):
                if p % 3 == q % 3 and gcd(p, q) == 1:
                    yield Fraction(p, q)
        if h % 2 and h % 3:
            for p in range(-h + 1, h):
                if p % 3 == h % 3 and gcd(p, h) == 1:
                    yield Fraction(p, h)


@dataclass
class SearchStats:
    parameters: int = 0
    n_values: int = 0
    integer_scales: int = 0
    accepted_points: int = 0


def search(height_min: int, height_max: int, n_min: int, n_max: int, *,
           d_filter: RationalDFilter | None = None,
           stats: SearchStats | None = None,
           on_progress: Callable[[dict], None] | None = None) -> Iterator[Point]:
    """Complete in the declared rational-height/n region, for target 375 only."""
    if n_min > n_max:
        raise ValueError("n_min must be at most n_max")
    filt = d_filter or RationalDFilter()
    counts = stats if stats is not None else SearchStats()
    # Validate height bounds even if a values-only filter is supplied.
    if height_min < 1 or height_max < height_min:
        raise ValueError("need 1 <= height_min <= height_max")
    if filt.values is None:
        parameters = rational_parameters(height_min, height_max)
    else:
        parameters = (d for d in sorted(filt.values)
                      if height_min <= max(abs(d.numerator), d.denominator) <= height_max
                      and d.denominator % 2 and d.denominator % 3
                      and d.numerator % 3 == d.denominator % 3)
    first_n = n_min + (2 - n_min) % 3
    for d in parameters:
        if not filt.accepts(d):
            continue
        p, q = d.numerator, d.denominator
        for n in range(first_n, n_max + 1, 3):
            t = 2 * n + 1
            counts.n_values += 1
            for m in integer_roots((p*q*(p+q), 6*p*q*t, 0, 125-9*t**3)):
                counts.integer_scales += 1
                X, Y = q * m, -(2 * p + q) * m - 6 * t
                if m % 2 != 1 or Y <= 0 or gcd(X, Y) != 1:
                    continue
                point = validate_point(n, X, Y, d)
                counts.accepted_points += 1
                yield point
        counts.parameters += 1
        if on_progress is not None:
            on_progress({"last_d": str(d), "parameters": counts.parameters,
                         "n_values": counts.n_values,
                         "integer_scales": counts.integer_scales,
                         "accepted_points": counts.accepted_points})
