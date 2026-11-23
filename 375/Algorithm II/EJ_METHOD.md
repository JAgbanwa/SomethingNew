# Exact lattice backend: region and coverage proof

`ej_worker.cpp` is a self-contained copy of the repository's exact rational
Elkies--Elsenhans--Jahnel style backend, from
`375/Scripts for large-scale computations/elkies-jahnel/src/elkies375_worker.cpp`
at commit `857adf3f89831816461641d6d4f7bbf89783304f`. Its mathematical search
implementation is preserved. The added provenance header and version distinguish
this copy; `elkies_jahnel.py` supplies an independently checked output interface.
The tests retain the source backend's mathematical controls and add tests for
invalid, interrupted, and incomplete worker output.

This is a repository implementation of Elkies' geometric method, with rational
enclosures and exact lattice arithmetic. It is not the historical authors'
optimized fixed-point executable, and it makes no claim of matching their speed.
The defining features are tangent tiles, rank-three LLL lattice reduction, and
complete enumeration of the lattice points in a certified enclosure. The code
does not replace these steps with a scan of all pairs of coordinates.

## 1. Target and finite search region

Let `K` be positive and not a cube. A native task specifies

\[
H\le c<2H,\qquad
L\le (5H)a/c<R,
\]

where `R=4H` includes its right endpoint. It searches both

\[
a^3+b^3-c^3=\pm K,\qquad 0<a\le b<c.
\]

The reported signed triple always has sum of cubes `+K`: it is `(a,b,-c)`
for residual `+K` and `(-a,-b,c)` for residual `-K`. Native primitivity means
`gcd(a,b,c)=1`. Algorithm II's common verifier subsequently imposes the original
equation's stronger odd, coprime `X,Y` requirements, the integer `n` condition,
and the principal square-root sign. A native cube hit alone is not an accepted
solution of the original equation.

The worker enforces

\[
H\ge25,\qquad 125K\le3H^3,\qquad 3H^2-3H+1>K.
\]

These all hold for `K=375,H=25`. Heights below the chosen starting shell are
outside a native task's coverage and need separate finite work. Successive
shells `H,2H,4H,...` have no gaps or overlaps in their height intervals.

### Canonical signs and magnitudes

At these heights, every sum-of-three-cubes representation of `K` can be put
in one of the canonical forms above. Equal largest magnitudes would cancel
to a cube or give magnitude larger than `K`; `K` is not a cube. If the two
largest magnitudes have the same sign, the remaining smaller cube cannot
cancel them down to `K`. If they have opposite signs but the smallest cube
has the sign of the largest, the absolute residual is at least

\[
c^3-(c-1)^3=3c^2-3c+1>K.
\]

The remaining arrangement is precisely the canonical pair of signs. A zero
coordinate is excluded by the same gap inequality. All-positive triples are
also impossible at these heights.

### Entire ratio interval

Since `a<=b`,

\[
2a^3\le c^3+K,\qquad
(a/c)^3\le(1+K/H^3)/2\le64/125.
\]

Thus `a/c<=4/5`, explaining the global upper grid index `4H` and its included
endpoint. In the other direction,

\[
a^3\ge c^3-(c-1)^3-K\ge3H^2-3H+1-K.
\]

Put `A=ceil_cuberoot(3H^2-3H+1-K)`. Because `c<2H`, every solution satisfies
`(5H)a/c>5A/2`. The safe inclusive lower index is therefore

\[
L_{\min}=\left\lfloor5A/2\right\rfloor.
\]

Taking `[L_min,4H]` covers the entire shell. A narrower band covers only that
band. Interior band and tile boundaries belong to the interval on their right;
only the global upper endpoint is included.

## 2. Rational enclosure of every candidate

On a ratio tile `[l,r]`, write `t=a/c`, midpoint `m=(l+r)/2`, half-width
`h=(r-l)/2`, and

\[
f(t)=(1-t^3)^{1/3},\qquad Q=64H^2.
\]

The worker obtains rational lower cube-root bounds with denominator `Q`:

\[
q_0\le f(m)<q_0+1/Q,\quad q_r\le f(r),\quad
0<g\le(1-r^3-K/H^3)^{1/3}.
\]

These bounds use integer cube roots, with no floating-point approximation.
Define

\[
s=-m^2/q_0^2,\quad C=2r/q_r^5,\quad
S=2m^2/(Qq_0^3),\quad P=K/(3H^3g^2).
\]

Here `|f''(t)|<=C`, since `f''(t)=-2t/f(t)^5`, and
`|f'(m)-s|<=S`. Concavity and Taylor's theorem give a one-sided remainder
between `-Ch^2/2` and `0`. Center this remainder and the root approximation
interval by setting

\[
\beta=q_0-sm+1/(2Q)-Ch^2/4,\qquad
E=1/(2Q)+Ch^2/4+Sh+P.
\]

For either residual sign, the actual second coordinate satisfies

\[
b/c=(1-t^3\pm K/c^3)^{1/3}.
\]

The mean value theorem bounds its distance from `f(t)` by `P`, because every
intermediate cube-root value is at least `g`. Consequently **every** candidate
in the tile satisfies

\[
|b/c-(st+\beta)|\le E.
\]

Changing `tile_scale` changes the subdivision and runtime, not this proof or
the covered region.

## 3. Exact lattice enumeration

The linear map

\[
(a,b,c)\longmapsto
\left(\frac{a-mc}{2Hh},\frac{b-sa-\beta c}{2HE},\frac{2c}{H}\right)
\]

sends all candidates into the closed ball of squared radius `3` centered at
`(0,0,3)`: the first two coordinates have absolute value at most `1`, and
the third lies in `[2,4)`. The enclosing ball may contain extra candidates;
all emitted hits undergo exact sign, shell, tile, and cube-identity tests.

When `K=+/-3 (mod 9)`, cube residues force `a=b=-c (mod 3)`. The code searches
the index-nine sublattice generated by `(3,0,0),(0,3,0),(-1,-1,1)`. For other
targets it searches the full integer lattice. This restriction is valid for
non-cube-free `375`: it is a direct congruence, not a cube-free-specific sieve.

Rank-three LLL uses exact GMP rationals for Gram--Schmidt coefficients and
integral row operations. Its warm-start transformation is checked to have
determinant `+1` or `-1`, so it preserves the entire lattice. Nested
Gram--Schmidt enumeration bounds all three integral coefficients inclusively.
Each coefficient interval is found with integer square roots of exact rational
bounds; points on the enclosing ball boundary are retained.

Short innermost intervals use exact cubic finite differences. Long ones are
searched algebraically for every integer root of each of the two residual
cubics: derivative roots are enclosed with rational/integer bounds, nearby
integers are checked individually, and the remaining monotone intervals are
searched by integer binary search. A zero polynomial falls back to enumeration.
This shortcut skips only values proved not to solve either cubic; it imposes
no candidate-count or solution-count limit.

## 4. Completion and interruption

The worker emits `start`, optional `hit` and `progress`, and one terminal `end`
record. Each completed tile reduces `next_index`. An end record with
`complete=true` is valid only when `next_index=index_start`; an explicit tile
budget or a signal leaves `complete=false` and records the uncovered endpoint.
Signals finish the current tile. Very wide tiles can therefore take time to
stop; use narrow bands or sensible tile widths for short jobs.

The Python interface independently verifies every emitted cube identity,
canonical ordering, gcd flag, region, and progress record. It withholds the
terminal record until successful process exit and EOF. Nonzero exit, missing
terminal output, changed scope, malformed data, or inconsistent completion
raises an error; none becomes completed coverage. A partial result can resume
with the same `index_start` and `index_stop=next_index`.

`lattice_points` counts all points covered by the innermost intervals, including
intervals handled by polynomial root isolation. It is not a count of individual
cube evaluations. Different partitions can change enclosure volumes and counts;
they must agree on exact hits and on the union of their certified regions.

## 5. Focused verification

The independent test oracle exhausts integer magnitudes in small shells without
using curve, lattice, or residue filters. Controls include nonempty primitive
targets, both residual signs, the nonprimitive `(20,20,-25)` for `375`, exact
ratio and height boundaries, tile-width changes, true tile-boundary resume,
arbitrary-precision coordinates, and integer polynomial roots above fifty
digits. Contract tests reject malformed or incomplete native results.

These checks and the enclosure proof establish the intended finite coverage;
they do not establish a practical runtime for a large complete shell or a
probability of discovering a new primitive representation.

## References

- Noam D. Elkies, *Rational points near curves and small nonzero
  |x^3-y^2| via lattice reduction*, sections 2.1 and 3.2:
  <https://arxiv.org/abs/math/0005139>.
- Andreas-Stephan Elsenhans and Jörg Jahnel, *New sums of three cubes*:
  <https://wwwuser.gwdguser.de/~jjahnel/Arbeiten/elk_ants6c.pdf>.
- Repository source commit for this copied backend:
  <https://github.com/JAgbanwa/SomethingNew/commit/857adf3f89831816461641d6d4f7bbf89783304f>.
