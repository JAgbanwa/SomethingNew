"""A bijective, interleaved order for a finite general (a,q) enclosure.

This changes WHEN pairs are tested, not WHICH pairs exist in the enclosure.
No fixed numerator, denominator, numerator list, random seed or success-location
assumption is used. Old q-major ranks are preserved by a separate mode identifier.
"""
from __future__ import annotations


def _index(index: int, count: int) -> None:
    if type(count) is not int or count < 1:
        raise ValueError("count must be a positive integer")
    if type(index) is not int or not 0 <= index < count:
        raise ValueError("index outside the finite parameter space")


def interleaved_rank(index: int, count: int) -> int:
    """Map a traversal index to an old q-major rank, exactly and in O(log count).

    Recurrence P_C = 2*P_ceil(C/2), followed by 2*P_floor(C/2)+1.
    Thus P_C contains each rank in [0,C) once: disjoint even and odd subsets.
    Powers of two give ordinary fixed-width bit-reversal. Unlike padding and
    rejection, this definition also supplies dense indices for arbitrary C.
    """
    _index(index, count)
    rank, bit = 0, 1
    while count > 1:
        even_count = (count + 1) // 2
        if index < even_count:
            count = even_count
        else:
            index -= even_count
            rank += bit
            count //= 2
        bit <<= 1
    return rank


def traversal_index(rank: int, count: int) -> int:
    """Inverse of interleaved_rank; exact rank recovery for returned hits."""
    _index(rank, count)
    index = 0
    while count > 1:
        even_count = (count + 1) // 2
        if rank & 1:
            index += even_count
            count //= 2
        else:
            count = even_count
        rank //= 2
    return index


class InterleavedAQ:
    """Reorder an existing complete enclosure, without modifying any bound.

    Each next index selects another (a,q) throughout the enclosure rather than
    finishing a long initial fixed-a region. Repeated a or q can still occur:
    every pair must be included, even when a small domain has only one a.
    No claim is made that this order increases the probability of a solution.
    """
    MODE = "n-sixths-xy-interleaved-aq-v1"

    def __init__(self, base):
        self.base = base
        self.count = base.count
        self.q_min, self.q_max = base.q_min, base.q_max
        self.full_q_max = base.full_q_max

    def candidate(self, index: int) -> tuple[int, int]:
        return self.base.candidate(interleaved_rank(index, self.count))

    def index(self, a: int, q: int) -> int:
        return traversal_index(self.base.index(a, q), self.count)

    def iter_candidates(self, start: int, stop: int):
        if (type(start) is not int or type(stop) is not int
                or not 0 <= start <= stop <= self.count):
            raise ValueError("invalid interleaved candidate slice")
        for index in range(start, stop):
            yield self.candidate(index)
