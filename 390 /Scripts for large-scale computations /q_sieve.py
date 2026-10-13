"""Exact additional denominator sieve for CE390's integer-radical target.

Used by run_task.py before dispatching a fibre to the native worker.
It deliberately leaves the existing 2/3, gcd(a,q), and other filters intact.
A False result means ONLY 'not rejected by these 733 primes'.

Every public decision API requires the already-resolved integer-radical policy
explicitly. Do not silently reinterpret legacy rational-radical tasks.
"""
from __future__ import annotations

from functools import lru_cache
from math import gcd, isqrt, prod

SIEVE_ID = "ce390-q-prime-obstruction-v1"
PRIME_LIMIT = 20_000  # Strict upper bound: p < PRIME_LIMIT.
MAX_BLOCK_SIZE = 1_048_576  # At most 1 MiB per byte mask.


def _integer(value: int, name: str, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer, not a boolean")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _policy(require_integer_sqrt: bool) -> None:
    if type(require_integer_sqrt) is not bool:
        raise TypeError("require_integer_sqrt must be an explicitly resolved bool")


def _primes_below(limit: int) -> tuple[int, ...]:
    if limit <= 2:
        return ()
    flags = bytearray(b"\x01") * limit
    flags[0:2] = b"\x00\x00"
    for p in range(2, isqrt(limit - 1) + 1):
        if flags[p]:
            start = p * p
            flags[start:limit:p] = b"\x00" * ((limit - 1 - start) // p + 1)
    return tuple(p for p in range(2, limit) if flags[p])


@lru_cache(maxsize=1)
def forbidden_primes() -> tuple[int, ...]:
    """The 733 additional obstructing primes below 20,000.

    For p not dividing 2*3*5*13 and p == 1 mod 3, 36*n^3 == 65 has
    a root iff 65^((p-1)/3) == 36^((p-1)/3) (mod p). This form avoids
    modular inversion. Primes 5 and 13 have the root n == 0 and MUST
    NOT be rejected. Primes 2 and 3 belong to the pre-existing filters.
    """
    return tuple(
        p for p in _primes_below(PRIME_LIMIT)
        if p % 3 == 1 and p not in (5, 13)
        and pow(65, (p - 1) // 3, p) != pow(36, (p - 1) // 3, p)
    )


@lru_cache(maxsize=1)
def _forbidden_product() -> int:
    return prod(forbidden_primes())


@lru_cache(maxsize=4096)
def _reject_integer_q(q: int) -> bool:
    # One exact gcd replaces up to 733 Python-level divisions. The bounded
    # cache reuses a denominator's decision across its different numerators.
    return gcd(q, _forbidden_product()) != 1


def reject_q(q: int, *, require_integer_sqrt: bool) -> bool:
    """True certifies this reduced denominator cannot yield a target solution.

    q must be a positive denominator; use after normal input validation and
    reduction/gcd policy. In rational-radical mode this ALWAYS returns False.
    Python integers remain exact for q around 10**55 and beyond.
    """
    _integer(q, "q", 1)
    _policy(require_integer_sqrt)
    return require_integer_sqrt and _reject_integer_q(q)


def first_forbidden_prime(q: int, *, require_integer_sqrt: bool) -> int | None:
    """An independently checkable prime witness, or None.

    Intended for diagnostics/aggregate audit records, not every hot-loop
    iteration. None does not certify solvability modulo all primes.
    """
    if not reject_q(q, require_integer_sqrt=require_integer_sqrt):
        return None
    return next(p for p in forbidden_primes() if q % p == 0)


def obstruction_mask(
    start: int,
    count: int,
    *,
    step: int = 1,
    require_integer_sqrt: bool,
) -> bytearray:
    """Mask[i] == 1 iff q = start + i*step is rejected by this sieve.

    Optional segmented path for a contiguous/arithmetic-progression q scan.
    Arbitrarily large start and step are exact; memory is bounded by count.
    This returns a mask, NOT a reindexed survivor list. Keep original task
    indices and record sieved indices as completed local obstructions.
    """
    _integer(start, "start", 1)
    _integer(count, "count", 0)
    _integer(step, "step", 1)
    _policy(require_integer_sqrt)
    if count > MAX_BLOCK_SIZE:
        raise ValueError(f"count exceeds MAX_BLOCK_SIZE={MAX_BLOCK_SIZE}")
    mask = bytearray(count)
    if not require_integer_sqrt or count == 0:
        return mask
    for p in forbidden_primes():
        step_mod_p = step % p
        if step_mod_p == 0:
            if start % p == 0:
                mask[:] = b"\x01" * count
                break
            continue
        first = ((-start % p) * pow(step_mod_p, -1, p)) % p
        if first < count:
            mask[first:count:p] = b"\x01" * ((count - 1 - first) // p + 1)
    return mask
