"""Exact, lazy planning of projective EJ regions for the rational-y equation.

This module plans the integer-cube-lift part of the problem.  It never loops
over individual n-values, and a plan is not a completed search.  The native
worker covers H <= c < 2H and an interval in I = 5H*a/c.  An adapter must also
apply each task's inclusive c and coordinate-sum bounds to emitted candidates.

General rational-y points with nonintegral cube coordinates are outside this
integer lattice; the independent fixed-n factor-pair engine handles those.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from fractions import Fraction
from hashlib import sha256
import json
from math import gcd, isqrt, lcm
from typing import Iterator


TARGET = 375
NATIVE_MIN_HEIGHT = 25
N_RESIDUES = (2, 5, 14, 20, 23)
REGION_VERSION = 1


def floor_cuberoot(value: int) -> int:
    """Return floor(cuberoot(value)) using integers only."""
    if value < 0:
        raise ValueError("cube-root input must be nonnegative")
    if value < 2:
        return value
    root = 1 << ((value.bit_length() + 2) // 3)
    while True:
        nxt = (2 * root + value // (root * root)) // 3
        if nxt >= root:
            return root
        root = nxt


def ceil_cuberoot(value: int) -> int:
    root = floor_cuberoot(value)
    return root + (root**3 != value)


def canonical_height_bound(total: int) -> int:
    """Inclusive largest c for (a,b,-c), a<=b<c, sum=total, cubes=375.

    For total=6n+3, n>=1, write u=c-a and v=c-b.  Cubes modulo 9 give
    u=v=2 (mod 3), hence u,v>=2.  The identity

        total**3-375 = 3*u*v*(2*total+u+v)

    and uv>=2(u+v-2) imply

        (c-1)**2 <= (total+1)**2 + (total**3-375)//6.

    Finally c=1 (mod 3), so round the upper bound down to that class.
    This concerns the canonical mixed-sign region.  All remaining sign or
    zero-coordinate possibilities have height below 25, by the native
    worker's separately documented canonical-sign proof.
    """
    if total < 9 or total % 6 != 3:
        raise ValueError("total must equal 6*n+3 for an integer n>=1")
    bound = 1 + isqrt((total + 1) ** 2 + (total**3 - TARGET) // 6)
    return bound - (bound - 1) % 3


def canonical_height_lower(total: int) -> int:
    """Necessary inclusive lower c, sharpened by a^3+b^3 >= (a+b)^3/4.

    Since a+b=total+c, every candidate has
    (total+c)^3 <= 4*(c^3+375).  Its left-minus-right polynomial decreases
    on c>=total and is negative by c=2*total.  Integer bisection therefore
    gives an exact necessary bound.  Round upward to c=1 (mod 3).
    """
    if total < 9 or total % 6 != 3:
        raise ValueError("total must equal 6*n+3 for an integer n>=1")
    lower, upper = total + 4, 2 * total
    while lower < upper:
        middle = (lower + upper) // 2
        if (total + middle)**3 <= 4 * (middle**3 + TARGET):
            upper = middle
        else:
            lower = middle + 1
    return lower + (1 - lower) % 3


def native_ratio_lower(height: int) -> int:
    """Safe inclusive lower grid index for the whole native shell."""
    if height < NATIVE_MIN_HEIGHT:
        raise ValueError("native shell height must be at least 25")
    return (5 * ceil_cuberoot(3 * height * height - 3 * height + 1 - TARGET)) // 2


def admissible_n_count(n_min: int, n_max: int) -> int:
    """Count the necessary integer-cube classes, without enumerating n."""
    if n_min > n_max:
        return 0
    return sum((n_max - r) // 27 - (n_min - 1 - r) // 27 for r in N_RESIDUES)


def _ratio_root_floors(total_ratio: Fraction, perturbation: Fraction,
                      grid: int) -> tuple[int, int] | None:
    """Floors of the two roots in I=grid*u of a necessary sum-strip quadratic.

    F(u)=u^3+(1+delta-u)^3-1-epsilon is a quadratic because the cubic
    terms cancel.  A negative discriminant returns None.  The returned
    floors are exact even when a root is extremely close to an integer.
    """
    beta = 1 + total_ratio
    coeff = (3 * beta / grid**2, -3 * beta**2 / grid,
             beta**3 - 1 - perturbation)
    denominator = lcm(*(c.denominator for c in coeff))
    a, b, c = (int(value * denominator) for value in coeff)
    common = gcd(gcd(a, b), c)
    a, b, c = a // common, b // common, c // common
    discriminant = b*b - 4*a*c
    if discriminant < 0:
        return None
    root = isqrt(discriminant)
    # sqrt(D) in [root,root+1).  At the smaller root, an irrational sqrt
    # moves an otherwise integral upper estimate strictly down by <1/(2a).
    lower_floor = (-b - root - (root*root != discriminant)) // (2*a)
    upper_floor = (-b + root) // (2*a)
    return lower_floor, upper_floor


@dataclass(frozen=True)
class Region:
    n_min: int
    n_max: int
    sum_min: int
    sum_max: int
    canonical_height_max: int
    proven_height_max: int
    height_min: int
    height_max: int
    complete_height_scope: bool
    small_height_required: bool
    small_height_min: int
    small_height_max: int
    scope_id: str

    @property
    def native_c_min(self) -> int:
        return max(NATIVE_MIN_HEIGHT, self.height_min,
                   canonical_height_lower(self.sum_min))

    @property
    def native_c_max(self) -> int:
        return min(self.height_max, self.canonical_height_max)


@dataclass(frozen=True)
class Shell:
    height: int
    index_start: int
    index_stop: int
    c_min: int
    c_max: int
    global_index_start: int
    global_index_stop: int

    @property
    def include_right_endpoint(self) -> bool:
        return self.index_stop == self.global_index_stop

    def band_count(self, band_width: int) -> int:
        if band_width <= 0:
            raise ValueError("band_width must be positive")
        return (self.index_stop - self.index_start + band_width - 1) // band_width


@dataclass(frozen=True)
class Task:
    task_id: str
    shell_index: int
    band_index: int
    logical_index: int
    height: int
    index_start: int
    index_stop: int
    c_min: int
    c_max: int
    sum_min: int
    sum_max: int
    include_right_endpoint: bool

    @property
    def id(self) -> str:
        return self.task_id

    def to_dict(self) -> dict:
        """Lossless JSON-ready task metadata; arithmetic values are strings."""
        return {key: value if isinstance(value, (str, bool)) else str(value)
                for key, value in asdict(self).items()}


def make_region(n_min: int, n_max: int, height_min: int | None = None,
                height_max: int | None = None) -> Region:
    """Plan positive integer n in an inclusive range.

    height_min/height_max, when supplied, are inclusive bounds on the largest
    absolute cube coordinate, not native shell starting heights.  Restricting
    them can leave parts of the requested n interval's possible height region
    outside the plan.  The scope flag reports that limitation explicitly.
    """
    if not isinstance(n_min, int) or not isinstance(n_max, int):
        raise TypeError("n bounds must be integers")
    if n_min < 1 or n_max < n_min:
        raise ValueError("require 1 <= n_min <= n_max")
    if height_min is not None and (not isinstance(height_min, int) or height_min < 0):
        raise ValueError("height_min must be a nonnegative integer")
    if height_max is not None and (not isinstance(height_max, int) or height_max < 0):
        raise ValueError("height_max must be a nonnegative integer")
    if height_min is not None and height_max is not None and height_max < height_min:
        raise ValueError("height_max must be at least height_min")
    low_sum, high_sum = 6 * n_min + 3, 6 * n_max + 3
    canonical_max = canonical_height_bound(high_sum)
    # The canonical-sign theorem applies from height25; reserve everything
    # smaller for a separate exact finite check, even if the sharper mixed-sign
    # bound is below24.
    proved_max = max(NATIVE_MIN_HEIGHT - 1, canonical_max)
    selected_min = 0 if height_min is None else height_min
    selected_max = proved_max if height_max is None else min(height_max, proved_max)
    # Any height below25 has |A+B+C|<=72.  Larger n cannot occur there.
    needs_low = n_min <= 11 and selected_min < 25 and selected_max >= selected_min
    low_min = selected_min if needs_low else 0
    low_max = min(24, selected_max) if needs_low else -1
    # All n in a modularly excluded interval are impossible integer-cube lifts;
    # still preserve the physical scope rather than conflating that fact with
    # completed numerical work.
    mandatory_min = 0 if n_min <= 11 else canonical_height_lower(low_sum)
    full_scope = selected_min <= mandatory_min and selected_max >= proved_max
    signature = {
        "version": REGION_VERSION, "target": TARGET, "n_min": str(n_min),
        "n_max": str(n_max), "height_min": str(selected_min),
        "height_max": str(selected_max),
    }
    scope = sha256(json.dumps(signature, sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:16]
    return Region(n_min, n_max, low_sum, high_sum, canonical_max, proved_max,
                  selected_min, selected_max, full_scope, needs_low,
                  low_min, low_max, scope)


def iter_shells(region: Region) -> Iterator[Shell]:
    """Yield only native shells intersecting this exact sum/height region.

    In a positive-sum canonical +375 triple, put d=c-b.  Then
    a=S+d>=S+2.  Also b>=a implies (b+a/3)^3>a^3+b^3>c^3,
    so S=a+b-c>2a/3 and a<3S/2.  Combining these inequalities
    with a shell's clipped integer c-range gives conservative ratio bounds.
    Exact quadratic enclosures of S/c=u+(1-u^3+375/c^3)^(1/3)-1 sharpen
    those bounds.  All rounding is outward; no floating point is used.
    """
    c_lo, c_hi = region.native_c_min, region.native_c_max
    if c_hi < c_lo or admissible_n_count(region.n_min, region.n_max) == 0:
        return
    height = NATIVE_MIN_HEIGHT
    while 2 * height <= c_lo:
        height *= 2
    max_a = (3 * region.sum_max - 1) // 2
    while height <= c_hi:
        lower_c, upper_c = max(height, c_lo), min(2 * height - 1, c_hi)
        global_lower, global_upper = native_ratio_lower(height), 4 * height
        # The lower endpoint is inclusive; floor preserves candidates whose
        # nonintegral index lies below the next integer.  At the upper end add
        # one to a floor, because ordinary band stops are excluded.
        min_a = max(region.sum_min + 2,
                    ceil_cuberoot(3 * height * height - 3 * height + 1 - TARGET))
        lower = max(global_lower, (5 * height * min_a) // upper_c)
        upper = min(global_upper, (5 * height * max_a) // lower_c + 1)
        # S>=Smin and c<=cmax imply v>=1+Smin/cmax-u.  Meanwhile
        # v^3<=1-u^3+375/cmin^3.  Their conjunction is F(u)<=0.
        roots = _ratio_root_floors(Fraction(region.sum_min, upper_c),
                                   Fraction(TARGET, lower_c**3), 5*height)
        if roots is None:
            height *= 2
            continue
        lower, upper = max(lower, roots[0]), min(upper, roots[1] + 1)
        # S<=Smax gives the reverse quadratic inequality F(u)>=0.
        # Canonical a<=b puts u on the left of its vertex, so only the
        # interval ending at the smaller root can contain a candidate.
        roots = _ratio_root_floors(Fraction(region.sum_max, lower_c),
                                   Fraction(TARGET, upper_c**3), 5*height)
        if roots is not None:
            upper = min(upper, roots[0] + 1)
        # The sole included upper endpoint still needs a positive-width native
        # task if outward clipping happens to leave only that endpoint.
        if lower == upper == global_upper:
            lower -= 1
        if lower < upper:
            yield Shell(height, lower, upper, lower_c, upper_c,
                        global_lower, global_upper)
        height *= 2


def task_count(region: Region, band_width: int = 1000) -> int:
    if band_width <= 0:
        raise ValueError("band_width must be positive")
    return sum(shell.band_count(band_width) for shell in iter_shells(region))


def iter_tasks(region: Region, band_width: int = 1000, start: int = 0,
               limit: int | None = None) -> Iterator[Task]:
    """Yield a lazy page of disjoint ratio bands; skip arbitrarily many in O(shells)."""
    if band_width <= 0 or start < 0 or (limit is not None and limit < 0):
        raise ValueError("require band_width>0, start>=0 and limit>=0")
    if limit == 0:
        return
    offset, emitted = 0, 0
    for shell_index, shell in enumerate(iter_shells(region)):
        count = shell.band_count(band_width)
        if start >= offset + count:
            offset += count
            continue
        band_index = max(0, start - offset)
        while band_index < count:
            left = shell.index_start + band_index * band_width
            right = min(left + band_width, shell.index_stop)
            task_id = f"{region.scope_id}-h{shell.height}-i{left}-{right}"
            yield Task(task_id, shell_index, band_index, offset + band_index,
                       shell.height, left, right, shell.c_min, shell.c_max,
                       region.sum_min, region.sum_max, right == 4 * shell.height)
            emitted += 1
            if limit is not None and emitted >= limit:
                return
            band_index += 1
        offset += count


def describe_region(region: Region, band_width: int = 1000) -> dict:
    """A compact complete plan descriptor, never an assertion of searched coverage."""
    shells = list(iter_shells(region))
    return {
        "region_version": REGION_VERSION,
        "target": TARGET,
        "scope_id": region.scope_id,
        "n_min": str(region.n_min), "n_max": str(region.n_max),
        "sum_min": str(region.sum_min), "sum_max": str(region.sum_max),
        "integer_n_count": str(region.n_max - region.n_min + 1),
        "admissible_n_count": str(admissible_n_count(region.n_min, region.n_max)),
        "necessary_n_modulus": 27, "necessary_n_residues": list(N_RESIDUES),
        "canonical_height_max": str(region.canonical_height_max),
        "canonical_height_min": str(canonical_height_lower(region.sum_min)),
        "proven_height_max": str(region.proven_height_max),
        "height_min": str(region.height_min), "height_max": str(region.height_max),
        "complete_height_scope": region.complete_height_scope,
        "small_height_required": region.small_height_required,
        "small_height_min": str(region.small_height_min),
        "small_height_max": str(region.small_height_max),
        "native_shell_count": len(shells),
        "band_width": str(band_width),
        "logical_native_tasks": str(sum(s.band_count(band_width) for s in shells)),
        "shells": [dict(height=str(s.height), index_start=str(s.index_start),
                        index_stop=str(s.index_stop), c_min=str(s.c_min),
                        c_max=str(s.c_max), logical_tasks=str(s.band_count(band_width)),
                        include_right_endpoint=s.include_right_endpoint)
                   for s in shells],
        "coverage_status": "planned; no search is established by this descriptor",
        "scope_note": "Native tasks cover integer cube lifts across all n in the requested sum strip, subject to their height and ratio bounds. General rational-only y points require the separate factor-pair engine.",
    }
