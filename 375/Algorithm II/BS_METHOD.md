# Booker–Sutherland backend: exact scope

`booker_sutherland.py` implements the integer gap, cube-root, Chinese remainder,
and square-discriminant search architecture used by Booker and Sutherland.
It is a Python reference implementation. It does not claim the performance or
the full collection of cubic-reciprocity optimizations of their production code.

## Search contract

```python
from booker_sutherland import SearchStats, search

stats = SearchStats()
for u, v, w in search(375, 1, 1000, -1000, 1000, stats=stats):
    assert u**3 + v**3 + w**3 == 375
print(stats.as_dict())
```

All bounds are inclusive. The exact searched region is

```text
D_min <= |u+v| <= D_max,    z_min <= w <= z_max,    u >= v.
```

The distinguished coordinate `w` is signed. Both signs of `u+v` are included.
The backend does not require an ordering of coordinate magnitudes, a lower
bound involving `sqrt(k)`, or distinct coordinates. Small, zero, and equal
coordinates therefore receive the same exact search. `D_min` must be at least
one. The excluded `u+v=0` case would require `w^3=k`; it is impossible for 375.
For another target that is a cube, that case is explicitly outside this region.

An unordered cube triple can occur with different distinguished coordinates.
The caller must deduplicate permutations if that is its desired output. A bound
on `D` and `w` is not a bound on every cube coordinate, and neither is a bound
on the user's rational parameter `d`.

## Exact reduction and completeness

For `s=u+v`, `D=|s|>0`, and `w=z`, the sum-of-cubes equation implies

```text
z^3 == k (mod D),
Delta = (4(k-z^3)/s - s^2)/3 = (u-v)^2.
```

Conversely, a root progression for `z` gives a solution exactly when `Delta`
is a nonnegative integer square with square root of the same parity as `s`.
Reconstruction is `u=(s+sqrt(Delta))/2`, `v=(s-sqrt(Delta))/2`.
The sign of `s` equals the sign of `k-z^3`, since
`(u^3+v^3)/(u+v)=u^2-uv+v^2>0` for `D>0`.

The implementation factors each gap with a segmented sieve, computes all
roots modulo its prime powers, combines them with the Chinese remainder
theorem, and visits every resulting progression in the signed `z` interval.
Exact modular square tests discard only nonsquares; the final test uses
arbitrary-precision integer arithmetic and rechecks the original cube sum.
These facts establish completeness within the stated finite region, subject
to the program completing successfully. No empirical frontier or asymptotic
ordering bound is used to exclude a candidate.

For targets `k == +/-3 (mod 9)`, every cube coordinate has the corresponding
residue `+/-1 modulo 3`. Gaps divisible by three are impossible, and a CRT
condition modulo three reduces the remaining `z` progressions. This includes
375 and remains valid despite its cube factor.

## Singular prime-power roots and primitive solutions

The target 375 is `3*5^3`, so it must not be replaced by 3 when searching for
primitive representations. For `k=p^v*u`, with `p` not dividing `u`, all roots
modulo `p^e` are constructed as follows:

* If `e <= v`, they are precisely the multiples of `p^ceil(e/3)`.
* If `e > v` and `v` is not divisible by three, there are no roots.
* Otherwise write `z=p^(v/3)*r`, solve the unit equation modulo `p^(e-v)`,
  and include all `p^(2v/3)` free lifts of each unit root.

Consequently the root construction includes all 25 roots modulo `5^e` for
375 when `e >= 3`, including arbitrarily large exponents. Unit roots at three
use exhaustive three-way Hensel lifting; other unit roots use the nonsingular
derivative. Prime roots for primes congruent to one modulo three use a
base-three discrete logarithm in the corresponding subgroup, not a scan of
all residues modulo the prime.

With `primitive_only=True`, every hit must have `gcd(u,v,w)=1`. A safe extra
gap filter is used only for primes `p == 2 (mod 3)` with `p^3 | k`: a primitive
solution cannot have `v_p(D)=1` or `2`. For 375 this skips exactly the gaps with
5-adic valuation one or two. Primes congruent to one modulo three do not use
this lemma. Cube primitivity alone is not the user's stronger chart condition;
the common verifier must still check odd `X,Y`, `gcd(X,Y)=1`, integer `n`, the
principal square-root sign, and the exact original equation.

## Progress and practical limits

An optional `SearchStats` instance receives counters. `on_progress` is called
once after each whole gap is finished, with `completed_D`, `next_D`, and a
`counters` dictionary. A hit does not certify that its entire gap is complete.
An interrupted gap must be restarted, with duplicate hits handled by the
caller. Reusing this callback to checkpoint gives a precise restart boundary.

The factorization sieve stores primes through `isqrt(D_max)`, and each segment
contains at most 4096 gaps. Its prime-table memory and initialization depend
on the absolute upper bound, even when the requested interval is short.
Prime-power root results are cached with finite cache-entry limits. Singular
targets other than 375 can have many roots, so root-list size can also matter.
This implementation is intended for exact bounded runs, validation, and a
clear method comparison; use measured timings before assigning large ranges.
It makes no promise that an unspecified or exhausted finite region contains a
primitive solution.

## Sources and implementation relationship

* Andrew R. Booker and Andrew V. Sutherland, *On a question of Mordell*:
  https://arxiv.org/abs/2007.01209
* Authors' implementation:
  https://github.com/AndrewVSutherland/SumsOfThreeCubes

The new backend is self-contained. It uses the same fundamental gap/root/
square architecture and the prime-power valuation adaptation already described
in this repository's `375/gap-search/README.md`. It does not import the existing
gap worker or claim that the authors' cube-free specialization applies
unchanged to primitive 375.
