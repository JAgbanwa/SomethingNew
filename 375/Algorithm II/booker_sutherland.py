"""Exact Booker--Sutherland integer-gap search, including the cube factor in 375.

This implements the integer gap / modular cube roots / square discriminant
architecture.  It is a portable reference implementation, not a reproduction
of all optimizations in the authors' production software.  In particular it
does not implement their cubic-reciprocity sieves.

The search region is D_min <= |u+v| <= D_max and z_min <= w <= z_max,
with inclusive integer bounds and D_min >= 1.  Returned triples satisfy
u >= v and u**3 + v**3 + w**3 == k.  There is no coordinate-order,
large-coordinate, cube-free-target, or unequal-coordinate assumption.
Different choices of the distinguished coordinate w can produce permutations
of the same unordered triple; callers decide their own deduplication policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import lru_cache
from math import gcd, isqrt
from typing import Callable, Iterator


METHOD = "booker-sutherland-integer-gap-reference-v1"
FACTOR_BLOCK_SIZE = 4096


@dataclass
class SearchStats:
    """Counters may be reused across adjacent, nonoverlapping search regions."""

    D_processed: int = 0
    D_skipped_mod3: int = 0
    D_skipped_primitive: int = 0
    D_without_roots: int = 0
    cube_roots: int = 0
    residue_classes: int = 0
    candidates: int = 0
    nonnegative_integral_discriminants: int = 0
    sieve_rejected: int = 0
    square_tests: int = 0
    nonprimitive_hits: int = 0
    hits: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _require_int(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")


def _primes_up_to(limit: int) -> list[int]:
    if limit < 2:
        return []
    mark = bytearray(b"\x01") * (limit + 1)
    mark[0:2] = b"\x00\x00"
    for p in range(2, isqrt(limit) + 1):
        if mark[p]:
            mark[p * p : limit + 1 : p] = b"\x00" * ((limit - p * p) // p + 1)
    return [p for p in range(2, limit + 1) if mark[p]]


def _factor_interval(
    lower: int, upper: int, block_size: int = FACTOR_BLOCK_SIZE
) -> Iterator[tuple[int, tuple[tuple[int, int], ...]]]:
    """Segmented, exact factorization of every integer in [lower, upper]."""
    primes = _primes_up_to(isqrt(upper))
    for start in range(lower, upper + 1, block_size):
        stop = min(upper + 1, start + block_size)
        remaining = list(range(start, stop))
        factors: list[list[tuple[int, int]]] = [[] for _ in remaining]
        for p in primes:
            if p * p >= stop:
                break
            first = ((start + p - 1) // p) * p
            for value in range(first, stop, p):
                index = value - start
                exponent = 0
                while remaining[index] % p == 0:
                    remaining[index] //= p
                    exponent += 1
                if exponent:
                    factors[index].append((p, exponent))
        for index, value in enumerate(range(start, stop)):
            if remaining[index] > 1:
                factors[index].append((remaining[index], 1))
            yield value, tuple(factors[index])


@lru_cache(maxsize=32768)
def cube_roots_prime(value: int, prime: int) -> tuple[int, ...]:
    """All cube roots modulo a prime; the caller supplies a proven prime.

    For p == 1 (mod 3), a discrete logarithm in the 3-primary subgroup
    supplies a cube root.  Its base-3 digits are extracted individually;
    the routine does not enumerate the p possible residues.
    """
    if prime < 2:
        raise ValueError("prime must be at least 2")
    value %= prime
    if value == 0:
        return (0,)
    if prime in (2, 3):
        return (value,)
    if prime % 3 == 2:
        return (pow(value, (2 * prime - 1) // 3, prime),)
    if pow(value, (prime - 1) // 3, prime) != 1:
        return ()

    cofactor = prime - 1
    exponent = 0
    while cofactor % 3 == 0:
        cofactor //= 3
        exponent += 1
    nonresidue = 2
    while pow(nonresidue, (prime - 1) // 3, prime) == 1:
        nonresidue += 1
    generator = pow(nonresidue, cofactor, prime)
    root_unity = pow(generator, 3 ** (exponent - 1), prime)
    root_unity_squared = root_unity * root_unity % prime
    inverse_three = pow(3, -1, cofactor) if cofactor > 1 else 0
    tentative = pow(value, inverse_three, prime)
    error = pow(tentative, 3, prime) * pow(value, -1, prime) % prime
    target = pow(error, -1, prime)
    inverse_generator = pow(generator, -1, prime)
    discrete_log = 0
    power_three = 1
    for digit_index in range(exponent):
        residual = target * pow(inverse_generator, discrete_log, prime) % prime
        digit_value = pow(residual, 3 ** (exponent - digit_index - 1), prime)
        if digit_value == 1:
            digit = 0
        elif digit_value == root_unity:
            digit = 1
        elif digit_value == root_unity_squared:
            digit = 2
        else:
            raise ArithmeticError("inconsistent cubic subgroup calculation")
        discrete_log += digit * power_three
        power_three *= 3
    if discrete_log % 3:
        raise ArithmeticError("a cubic residue had a nondivisible discrete log")
    root = tentative * pow(generator, discrete_log // 3, prime) % prime
    roots = tuple(sorted({root, root * root_unity % prime,
                          root * root_unity_squared % prime}))
    if len(roots) != 3 or any(pow(r, 3, prime) != value for r in roots):
        raise ArithmeticError("prime cube-root verification failed")
    return roots


def _unit_roots_prime_power(value: int, prime: int, exponent: int) -> tuple[int, ...]:
    roots = cube_roots_prime(value % prime, prime)
    modulus = prime
    for _ in range(1, exponent):
        next_modulus = modulus * prime
        if prime == 3:
            # The derivative is singular at p=3, even for units.  Three
            # possible lifts per existing root are small and exhaustive.
            roots = tuple(
                root + digit * modulus
                for root in roots
                for digit in range(3)
                if ((root + digit * modulus) ** 3 - value) % next_modulus == 0
            )
        else:
            lifted = []
            for root in roots:
                error = (root ** 3 - value) // modulus
                correction = -error * pow(3 * root * root, -1, prime) % prime
                lifted.append(root + correction * modulus)
            roots = tuple(lifted)
        modulus = next_modulus
        if not roots:
            break
    return tuple(sorted(roots))


@lru_cache(maxsize=65536)
def cube_roots_prime_power(value: int, prime: int, exponent: int) -> tuple[int, ...]:
    """All roots of r**3 == value modulo prime**exponent, including singular roots.

    The caller supplies a prime.  A non-unit target is treated by its exact
    valuation; no assumption that the target is cube free is made.
    """
    if prime < 2 or exponent < 1:
        raise ValueError("need prime >= 2 and exponent >= 1")
    modulus = prime ** exponent
    if value == 0:
        step = prime ** ((exponent + 2) // 3)
        return tuple(range(0, modulus, step))
    unit = value
    valuation = 0
    while unit % prime == 0:
        unit //= prime
        valuation += 1
    if valuation == 0:
        return _unit_roots_prime_power(value, prime, exponent)
    if exponent <= valuation:
        step = prime ** ((exponent + 2) // 3)
        return tuple(range(0, modulus, step))
    if valuation % 3:
        return ()
    root_valuation = valuation // 3
    unit_exponent = exponent - valuation
    unit_modulus = prime ** unit_exponent
    scale = prime ** root_valuation
    free_count = prime ** (2 * root_valuation)
    unit_roots = _unit_roots_prime_power(unit, prime, unit_exponent)
    return tuple(sorted(
        scale * (root + free_digit * unit_modulus)
        for root in unit_roots
        for free_digit in range(free_count)
    ))


def cube_roots_mod(
    value: int, modulus: int, factors: tuple[tuple[int, int], ...] | None = None
) -> tuple[int, ...]:
    """Compute every modular cube root by prime-power roots and exact CRT."""
    if modulus < 1:
        raise ValueError("modulus must be positive")
    if factors is None:
        _, factors = next(_factor_interval(modulus, modulus))
    roots = (0,)
    combined_modulus = 1
    for prime, exponent in factors:
        prime_power = prime ** exponent
        component = cube_roots_prime_power(value, prime, exponent)
        if not component:
            return ()
        inverse = pow(combined_modulus, -1, prime_power)
        roots = tuple(
            previous + combined_modulus * ((root - previous) * inverse % prime_power)
            for previous in roots
            for root in component
        )
        combined_modulus *= prime_power
    if combined_modulus != modulus:
        raise ValueError("factorization does not multiply to the modulus")
    return tuple(sorted(roots))


def _primitive_gap_primes(k: int) -> tuple[int, ...]:
    """p == 2 mod 3 with p**3 | k; only these primes use the gap lemma."""
    remaining = abs(k)
    if remaining == 0:
        return ()
    result = []
    prime = 2
    while prime ** 3 <= remaining:
        valuation = 0
        while remaining % prime == 0:
            remaining //= prime
            valuation += 1
        if valuation >= 3 and prime % 3 == 2:
            result.append(prime)
        prime = 3 if prime == 2 else prime + 2
    return tuple(result)


SQUARE_SIEVE_MODULI = (64, 63, 65, 11, 17, 19, 23, 31, 37, 41, 43)
SQUARE_MASKS = tuple(
    sum(1 << residue for residue in {r * r % modulus for r in range(modulus)})
    for modulus in SQUARE_SIEVE_MODULI
)


def passes_square_sieve(value: int) -> bool:
    """Necessary conditions only: every nonnegative square passes."""
    return value >= 0 and all(
        mask >> (value % modulus) & 1
        for modulus, mask in zip(SQUARE_SIEVE_MODULI, SQUARE_MASKS)
    )


def search(
    k: int,
    D_min: int,
    D_max: int,
    z_min: int,
    z_max: int,
    *,
    primitive_only: bool = False,
    square_sieve: bool = True,
    on_progress: Callable[[dict], None] | None = None,
    stats: SearchStats | None = None,
) -> Iterator[tuple[int, int, int]]:
    """Yield exact three-cube solutions throughout the declared finite region.

    All five integer bounds/parameters are exact Python integers.  Bounds are
    inclusive.  The signed distinguished coordinate is z_min <= w <= z_max;
    D denotes |u+v|, NOT a rational slope.  D=0 is outside this contract.

    The callback runs after an entire D has been completed, with completed_D,
    next_D, and counters.  If iteration is interrupted inside a D, a caller
    must restart that D; it must not mark it complete merely on receiving a hit.
    """
    for name, value in (("k", k), ("D_min", D_min), ("D_max", D_max),
                        ("z_min", z_min), ("z_max", z_max)):
        _require_int(name, value)
    if not 1 <= D_min <= D_max:
        raise ValueError("need 1 <= D_min <= D_max (inclusive)")
    if z_min > z_max:
        raise ValueError("need z_min <= z_max (inclusive)")
    if not isinstance(primitive_only, bool) or not isinstance(square_sieve, bool):
        raise ValueError("primitive_only and square_sieve must be booleans")
    counters = stats if stats is not None else SearchStats()
    special_mod9 = k % 9 in (3, 6)
    coordinate_mod3 = 1 if k % 9 == 3 else 2
    primitive_primes = _primitive_gap_primes(k) if primitive_only else ()

    for D, factorization in _factor_interval(D_min, D_max):
        factor_map = dict(factorization)
        if special_mod9 and D % 3 == 0:
            counters.D_skipped_mod3 += 1
        elif any(factor_map.get(p, 0) in (1, 2) for p in primitive_primes):
            counters.D_skipped_primitive += 1
        else:
            roots = cube_roots_mod(k, D, factorization)
            counters.cube_roots += len(roots)
            if not roots:
                counters.D_without_roots += 1
            step = 3 * D if special_mod9 else D
            for root in roots:
                if special_mod9:
                    # For k == +/-3 (mod 9), all three coordinates equal the
                    # corresponding +/-1 modulo 3.  D is coprime to 3 here.
                    root += D * ((coordinate_mod3 - root) * pow(D, -1, 3) % 3)
                counters.residue_classes += 1
                first = z_min + (root - z_min) % step
                for z in range(first, z_max + 1, step):
                    counters.candidates += 1
                    quotient = (k - z ** 3) // D
                    # (u^3+v^3)/(u+v)=u^2-uv+v^2 is positive for D>0.
                    # Consequently the sign of s=u+v is determined, and both
                    # signs of the pair sum are covered by this single choice.
                    if quotient == 0:
                        continue
                    pair_sum = D if quotient > 0 else -D
                    numerator = 4 * abs(quotient) - D * D
                    if numerator < 0 or numerator % 3:
                        continue
                    discriminant = numerator // 3
                    counters.nonnegative_integral_discriminants += 1
                    if square_sieve and not passes_square_sieve(discriminant):
                        counters.sieve_rejected += 1
                        continue
                    counters.square_tests += 1
                    difference = isqrt(discriminant)
                    if difference * difference != discriminant or (pair_sum + difference) % 2:
                        continue
                    u = (pair_sum + difference) // 2
                    v = (pair_sum - difference) // 2
                    if u ** 3 + v ** 3 + z ** 3 != k:
                        raise ArithmeticError("reconstructed triple failed exact verification")
                    if primitive_only and gcd(gcd(u, v), z) != 1:
                        counters.nonprimitive_hits += 1
                        continue
                    counters.hits += 1
                    yield u, v, z
        counters.D_processed += 1
        if on_progress is not None:
            on_progress({"completed_D": D, "next_D": D + 1,
                         "counters": counters.as_dict()})
