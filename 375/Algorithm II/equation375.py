"""Exact acceptance rules for the user's equation; public searches fix target=375.

The optional target argument exists for nonempty mathematical regression tests.
For target 375, coefficient(n) is exactly 36*n**3+54*n**2+27*n-58.
No floating-point square root, tolerance, or relaxed primitivity is used by the CLI.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import permutations
from math import gcd
from typing import Iterable

TARGET = 375


def _integer(value: object, name: str) -> int:
    if type(value) is not int:
        raise ValueError(f"{name} must be an integer (not a float or boolean)")
    return value


def coefficient(n: int, target: int = TARGET) -> Fraction:
    _integer(n, "n")
    _integer(target, "target")
    return Fraction((6 * n + 3) ** 3 - target, 6)


@dataclass(frozen=True)
class Point:
    n: int
    X: int
    Y: int
    d: Fraction
    target: int = TARGET

    @property
    def x(self) -> Fraction:
        return Fraction(self.X, 2)

    @property
    def y(self) -> Fraction:
        return Fraction(self.Y, 2)

    @property
    def cubes(self) -> tuple[int, int, int]:
        return (self.X + 6 * self.n + 3, -(self.X + self.Y) // 2,
                (self.Y - self.X) // 2)

    def as_dict(self) -> dict:
        """Integers are decimal strings so JSON consumers cannot round large hits."""
        return {
            "n": str(self.n), "X": str(self.X), "Y": str(self.Y),
            "x": str(self.x), "y": str(self.y), "d": str(self.d),
            "abs_d": str(abs(self.d)),
            "d_numerator": str(self.d.numerator),
            "d_denominator": str(self.d.denominator),
            "d_height": str(max(abs(self.d.numerator), self.d.denominator)),
            "cube_triple": [str(v) for v in self.cubes],
            "target": self.target, "gcd_X_Y": gcd(self.X, self.Y),
            "principal_square_root": True,
        }


def validate_point(n: int, X: int, Y: int, d: Fraction | None = None, *,
                   target: int = TARGET, require_coprime: bool = True) -> Point:
    """Verify the original radical equation exactly and return its signed d.

    With Y>0, equality of the rational squares proves that Y/2 is the
    principal square root, without ever evaluating a numerical square root.
    require_coprime=False is solely a diagnostic/test facility, not a CLI mode.
    """
    for value, name in ((n, "n"), (X, "X"), (Y, "Y"), (target, "target")):
        _integer(value, name)
    if X % 2 != 1 or Y % 2 != 1:
        raise ValueError("X and Y must both be odd integers")
    if Y <= 0:
        raise ValueError("Y must be positive: y is the principal square root")
    if require_coprime and gcd(X, Y) != 1:
        raise ValueError("gcd(X,Y) must equal 1")
    x, y = Fraction(X, 2), Fraction(Y, 2)
    A, B = coefficient(n, target), x + 6 * n + 3
    if A == 0:
        raise ValueError("the degenerate A=0 chart is outside this parameterization")
    radicand = B * B + A / x
    if radicand != y * y:
        raise ValueError("the exact radical relation fails")
    forced_d = -(y + B) / (2 * x)
    if d is not None:
        if not isinstance(d, (Fraction, int)) or isinstance(d, bool):
            raise ValueError("d must be an exact Fraction or integer")
        if Fraction(d) != forced_d:
            raise ValueError("d is not the signed parameter forced by the equation")
    if A != -2 * forced_d * x * x * (y - B):
        raise ValueError("the original unsquared equation fails")
    point = Point(n, X, Y, forced_d, target)
    if sum(v ** 3 for v in point.cubes) != target:
        raise ValueError("the independent three-cubes identity fails")
    return point


def points_from_cubes(cubes: Iterable[int], *, target: int = TARGET,
                      require_coprime: bool = True) -> list[Point]:
    """Return all qualifying charts, including negative n and both signs of x.

    All cube permutations are considered. Opposite square-root signs are NOT
    both returned: only c>b gives the user's specified principal square root.
    """
    triple = tuple(cubes)
    if len(triple) != 3 or any(type(v) is not int for v in triple):
        raise ValueError("a cube triple must contain exactly three integers")
    if sum(v ** 3 for v in triple) != target:
        raise ValueError("cube triple does not sum to the target")
    S = sum(triple)
    if (S - 3) % 6:
        return []
    n = (S - 3) // 6
    out: dict[tuple[int, int, int], Point] = {}
    for a, b, c in sorted(set(permutations(triple))):
        X, Y = -(b + c), c - b
        if X % 2 != 1 or Y % 2 != 1 or Y <= 0:
            continue
        if require_coprime and gcd(X, Y) != 1:
            continue
        point = validate_point(n, X, Y, target=target,
                               require_coprime=require_coprime)
        out[(n, X, Y)] = point
    return [out[key] for key in sorted(out)]


@dataclass(frozen=True)
class RationalDFilter:
    """Optional restrictions on signed rational d; defaults add no restriction."""
    values: frozenset[Fraction] | None = None
    minimum: Fraction | None = None
    maximum: Fraction | None = None
    height: int | None = None

    def __post_init__(self) -> None:
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("d-min must be at most d-max")
        if self.height is not None and self.height < 1:
            raise ValueError("d-height must be positive")

    def accepts(self, d: Fraction) -> bool:
        return ((self.values is None or d in self.values)
                and (self.minimum is None or d >= self.minimum)
                and (self.maximum is None or d <= self.maximum)
                and (self.height is None
                     or max(abs(d.numerator), d.denominator) <= self.height))

    def as_dict(self) -> dict:
        return {
            "values": None if self.values is None else [str(v) for v in sorted(self.values)],
            "minimum": None if self.minimum is None else str(self.minimum),
            "maximum": None if self.maximum is None else str(self.maximum),
            "height": None if self.height is None else str(self.height),
        }
