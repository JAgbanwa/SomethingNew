# Adapting the projective Elkies search to the rational-y equation

The attached `Elkies_allg.tar` describes a three-dimensional projective lattice
search. It normalizes cube-coordinate magnitudes by their largest coordinate,
covers a real curve with tangent tiles, reduces a rank-three lattice, and
enumerates the lattice points in an enclosing region. The native backend in
this folder implements those defining steps with arbitrary-precision integers,
rational enclosures and exact enumeration. Its finite-region proof is in
[EJ_METHOD.md](EJ_METHOD.md).

The additional layer here translates that search into the user's equation,
restricts the whole integer `n` interval through a coordinate-sum condition,
and preserves precise coverage. It does not select a few n-values and describe
them as an interval search. Nor does creating a full-region plan constitute
performing its potentially enormous computation.

## 1. Exact change of variables

Let

$$
S=6n+3,\quad T=S+x,\quad
N=36n^3+54n^2+27n-58=(S^3-375)/6.
$$

For `x != 0` and `T != 0`, define `t=yT` and

$$
(A,B,C)=(-x-t,-x+t,S+2x).
$$

Then

$$
A+B+C=S,\qquad
A^3+B^3+C^3=375-6R,
\qquad R=x(t^2-T^2)-N.
$$

An exact point of the original equation has `R=0`. Its cube lift is integral
exactly when `t` is an integer. The projective integer lattice searches this
integer-lift case. Rational `y` itself can still have a denominator: division
by `T` recovers it exactly after an integer cube triple is found.

Conversely, take an integer triple of cube sum 375 and total `S=6n+3`.
For each unordered pair of coordinates `A,B` of the same parity, set

$$
x=-(A+B)/2,\qquad t=(B-A)/2,\qquad y=t/(S+x).
$$

Swapping `A,B` changes the sign of y. A triple may yield more than one
integer-x point, so the adapter must try every eligible coordinate pair,
check both denominator poles, and deduplicate the resulting `(n,x,|y|)`
points. Every emitted point is checked again in the original equation and
its cube identity. A green primitive marker additionally requires gcd 1.

The integer lattice does **not** cover rational-y points whose cube coordinates
are nonintegral. Those remain the responsibility of the separately identified
fixed-n factor-pair search. It would be incorrect to label an empty projective
integer-cube search as proving the absence of every rational y.

## 2. Applying an n interval to a projective search

The native magnitudes are `0 < a <= b < c`. A shell/band is

$$
H\le c<2H,\qquad L\le I=5Ha/c<R,
$$

with the global upper ratio endpoint `R=4H` included. Its two canonical
signed outputs have cube sum +375: `(a,b,-c)` and `(-a,-b,c)`.

For positive integer `n`, `S=6n+3>=9`. The second sign pattern cannot have
positive total S: if `c=S+a+b`, then
`c^3-a^3-b^3 >= S^3 > 375`. Thus the requested positive-n interval admits
only `(a,b,-c)` in the native region, with

$$
S=a+b-c.
$$

The adapter accepts precisely the inclusive strip

$$
6n_{min}+3\le a+b-c\le6n_{max}+3,
$$

together with its chosen coordinate-height bounds. This filters n-values
collectively; there is no iteration over each n. The native search can produce
extra candidates outside the strip, which must be discarded before recording
original-equation hits.

The native sign/canonical proof applies for all largest coordinate magnitudes
at least 25 for target 375. Lower heights are a separate finite region. They
must be checked directly when included in the plan; for example `(5,5,5)` at
`n=2` lies below the native region, while `(20,20,-25)` lies exactly on its
first height shell and global ratio boundary.

## 3. A finite upper height follows from the n bound

A bound on n is a bound on the coordinate sum, not on each coordinate.
The cube coordinates can be much larger than n. Nevertheless the requested
positive-n interval implies a finite upper height for the integer-lift search.

For a canonical candidate, put

$$
u=c-a,\qquad v=c-b.
$$

Then `u,v>0`, `a=S+v`, `b=S+u`, `c=S+u+v`, and

$$
S^3-375=3uv(2S+u+v).
$$

Cubes modulo 9 force `a=b=2 (mod3)` and `c=1 (mod3)`. Hence
`u=v=2 (mod3)`, in particular `u,v>=2`. Writing `w=u+v`,

$$
uv\ge2(w-2)
$$

because `(u-2)(v-2)>=0`. Substitution yields

$$
2(S+c)(c-S-2)\le(S^3-375)/3,
$$

or

$$
(c-1)^2\le(S+1)^2+(S^3-375)/6.
$$

Therefore a valid inclusive upper bound is

$$
C_{max}(S)=1+\left\lfloor
\sqrt{(S+1)^2+(S^3-375)/6}\right\rfloor,
$$

rounded downward to the class `c=1 (mod3)`. The expression increases with
positive S, so use `S=6n_max+3` for the whole interval. The planner reserves
all heights below 25 separately even if this canonical bound is smaller.

For `n_max=10^20`, the canonical upper bound is exactly

```text
6000000000000000000075000000001
```

This is about `6*10^30`, rather than `10^20`. A user-specified height cap
below the proved bound restricts the search; it cannot establish coverage of
the full requested n interval by itself.

## 4. A useful lower height

The identity above gives `c>=S+4`. A stronger bound follows from convexity:

$$
a^3+b^3\ge(a+b)^3/4,
$$

so

$$
(S+c)^3\le4(c^3+375).
$$

For fixed S, the left-minus-right polynomial decreases on `c>=S` and is
negative by `c=2S`. Integer bisection in `[S+4,2S]` finds the first allowed
integer, which is then rounded upward to `c=1 (mod3)`. This is again a
necessary bound, not an existence assertion. Using `S=6n_min+3` gives a safe
lower height for the whole interval.

At `n_min=10^17`, this lower height is exactly

```text
1021448630351589166
```

The native dyadic shells start at `H=25` and double. Only shells intersecting
the selected height interval are materialized. The first or last shell can
overhang a selected height bound; task metadata records the exact inclusive
`c_min,c_max`, and the adapter filters those overhangs.

## 5. Pruning ratio bands with the sum strip

Simple outward bounds already remove substantial irrelevant work. Let
`d=c-b`. Then `a=S+d>=S+2`. Also, since `b>=a`,

$$
(b+a/3)^3>a^3+b^3>c^3,
$$

so `S=a+b-c>2a/3`, giving `a<3S/2`. With the clipped c-range of a shell,
these yield an inclusive lower and an exclusive upper integer index bound.

The planner tightens them further using exact quadratics. Write `z=a/c` and
`w=b/c`; then

$$
w^3=1-z^3+375/c^3,\qquad S/c=z+w-1.
$$

For the lower sum bound, put

$$
\delta=S_{min}/c_{max},\qquad\epsilon=375/c_{min}^3.
$$

A candidate must satisfy

$$
F(z)=z^3+(1+\delta-z)^3-1-\epsilon\le0.
$$

The cubic terms cancel, leaving an upward-opening quadratic. A negative
discriminant proves that the shell/strip combination has no candidates;
otherwise its two roots enclose the permitted ratio interval.

For the upper sum bound, set `delta=S_max/c_min` and
`epsilon=375/c_max^3`. The reverse inequality `F(z)>=0` is necessary.
Canonical `a<=b` puts z on the left of the quadratic's vertex, so this gives
an upper ratio bound at its smaller root whenever the discriminant is
nonnegative.

All coefficients are rational. After multiplying by common denominators and
using `I=5Hz`, the planner computes integer discriminants and exact integer
square roots. It rounds lower bounds down and ordinary upper stops strictly
up. The exceptional included global endpoint is retained explicitly. No
floating-point ratio can silently remove a candidate at a very large height.

These bounds are only necessary enclosures; the native worker still performs
its actual tangent-tile and rank-three LLL search within the surviving bands.

## 6. Modular conditions and scope

Every integer cube lift requires

$$
x\equiv1\pmod3,\quad t\equiv0\pmod3,\quad
n\bmod27\in\{2,5,14,20,23\}.
$$

For the last condition, the residual gives `n=2+3k` and
`R=9(v^2-k) (mod27)` when `t=3v`. Thus `n=2 or5 (mod9)`.
On the first branch write `n=2+9l`, `x=1+3q`, `t=9w`; then

$$
R\equiv27(q^2-l-1)\pmod{81}.
$$

Since squares modulo3 are0 or1, this keeps `n=2,20 (mod27)` from that
branch; the other branch gives `5,14,23 (mod27)`.

These are necessary conditions for integer cube lifts. Passing them does not
prove a solution. They cannot exclude rational-only y points whose cube lift
is nonintegral.

## 7. Lazy planning, interruption and completeness

`region.py` produces a compact descriptor and a lazy sequence of exact
shell/ratio-band tasks. It can jump to an arbitrarily large logical task index
without creating files or iterating over the preceding tasks. The descriptor
records the requested n interval, selected height limits, mathematically
proved bounds, modular counts and logical task count.

For `10^17 <= n <= 10^20` and band width1000, the current plan has 43 native
shells and **100,763,245,124,579,414,319** logical band tasks. This is a plan
size, not completed work or a runtime prediction. It makes clear why a short
run cannot truthfully report that the entire large interval was exhausted.

A native completed band certifies its precise height/ratio region. A tile
budget or interruption leaves an exact uncovered ratio endpoint to resume.
The overall interval can be reported complete only after every required band
and the included low-height region are complete, with no user-imposed height
gap. Geometric sample slices used for plotting must be labelled as geometry,
not as exact searches of those n-values.

The focused planning tests independently check a brute-force small-height
cube oracle, the exact `(20,20,-25)` ratio endpoint, low-height fallback,
partition/resume boundaries, huge-integer root rounding, modular interval
counts and lazy access to the last task of the large plan.
