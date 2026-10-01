# Exact mathematical basis of the signed search (CE390 3.2.0)

## Scope

The target is

\[
36n^3-65=-2d x^2\left(-x-6n+
\sqrt{(x+6n)^2+(36n^3-65)/x}\right),
\]

with an **integer principal square root** `y >= 0`, rational `d`, and integers

\[
10^{43}\le |n|\le10^{45},\qquad
10^{54}\le |x|\le10^{55},\qquad
n\equiv1\pmod3,\quad x\equiv5\pmod{12},\quad7\nmid x.
\]

All bounds are inclusive. Both signs are allowed independently: `(+, +)`,
`(+, -)`, `(-, +)`, and `(-, -)`. Congruences apply to the actual signed
integers, not their absolute values. For example, negative `n` requires
`|n| = 2 mod 3`, and negative `x` requires `|x| = 7 mod 12`.

The user's additional requirement that the principal radical be an integer
is enforced by default. Nonintegral rational radicals are not target hits.
An explicit `--allow-rational-sqrt` option remains available for broader
mathematical comparisons and historical regression fixtures. The numerical
scale is a requested search region, not a proved lower bound or an existence
theorem.

## 1. Eliminate the radical and retain its principal branch

Set

\[
A=36n^3-65,\qquad S=x+6n,\qquad y=\sqrt{S^2+A/x}.
\]

In the production region `A` is nonzero and has the sign of `n`. The
original equation forces `d != 0`, and rational `d` forces rational `y`.
Conversely, a rational principal square root determines a unique `d`.
Since `(y-S)(y+S)=A/x`, cancellation gives the stable exact formula

\[
\boxed{d=-\frac{y+x+6n}{2x}.}
\]

This works for either sign of `x` and avoids numerical cancellation in the
original radical expression.

An independent integer-square certificate is

\[
M=x^2(x+6n)^2+(36n^3-65)x.
\]

The radical is rational if and only if `M=m^2` for a nonnegative integer
`m`. Indeed, `|x|y` is rational with integer square, so it is an integer.
The principal root and corresponding parameter are

\[
y=\frac m{|x|},\qquad
\boxed{d=-\frac{\operatorname{sgn}(x)m+x(x+6n)}{2x^2}.}
\]

For the required integer radical, one must additionally have `|x| | m`.
Equivalently, require `x | A`, then test whether the integer
`S^2+A/x` is a nonnegative perfect square. A square value of `M` alone
does not establish that the radical is an integer.

The independent verifier checks this square certificate, the original
rational equation, radical integrality, the principal branch, signed
congruences, and magnitude bounds. In particular, it does not reconstruct
`y` as `m/x` when `x<0`.

## 2. A small rational auxiliary parameter covers all four signs

Write

\[
N=|n|,\quad X=|x|,\quad s_n=\operatorname{sgn}(n),\quad
s_x=\operatorname{sgn}(x),\quad \tau=s_ns_x,\quad R=N/X.
\]

The bounds imply `10^-12 <= R <= 10^-9`. Consequently `S` has the sign
of `x`, and the radicand is strictly positive: for example,

\[
\frac{S^2+A/x}{X^2}\ge(1-6\cdot10^{-9})^2-37\cdot10^{-27}>0.
\]

Use a **signed auxiliary square root** `w=s_x y`, which is distinct from
the principal root `y` when `x<0`. Put `k=w-S`. Then

\[
k=\frac A{x(w+S)},\qquad
x(w+S)=X(y+|S|)>0.
\]

Thus `k` has the sign of `n`, and

\[
\boxed{\frac{w-x+6n}{x}=\tau\frac aq},\qquad
\boxed{\frac aq=12R+\frac{|k|}{X}},
\]

where `a,q>0` are reduced integers. There is exactly one such reduced
positive pair for each target solution. Its bounds follow from

\[
0<\frac{|k|}{X}
\le\frac{36N^3+65}{X^3(1-6R)}<37R^3.
\]

In particular every production solution satisfies

\[
12\cdot10^{-12}<\frac aq<12\cdot10^{-9}+37\cdot10^{-27}.
\]

The slightly wider rational enclosure used for campaign selection is

\[
\boxed{11\cdot10^{-12}<a/q<13\cdot10^{-9}.}
\]

Both enclosures imply `0<a<q`. Restricting the signed worker to `0<a<q`
therefore loses no point in the production region. For deliberately small
test rectangles its completeness claim is per admitted `(a,q)` fiber;
not every rational point in an arbitrary small rectangle need have a
parameter satisfying that restriction.

### Parity and congruences of the reduced parameter

Write `y=p/r` in lowest terms, with `r>0`. The radical equation implies
`r^2 | |x|`; hence `r` is odd and not divisible by 3. Reducing the equation
modulo 4 gives `p` even, and reducing modulo 3 gives `p = 0 mod 3`.
The same properties hold for the numerator of `w=s_x p/r`.

Therefore `(w-x+6n)/x` has odd reduced numerator and denominator, neither
divisible by 3. Modulo 3 its value is `-1`. Hence

\[
\boxed{\gcd(a,q)=1,\quad\gcd(aq,6)=1,\quad\tau a+q\equiv0\pmod3.}
\]

Equivalently, since both integers are odd,

\[
q\equiv-\tau a\pmod6.
\]

For `tau=+1`, this is the old `a+q=0 mod 6` condition. For `tau=-1`, it
becomes `q-a=0 mod 6`. A campaign retaining only the old condition would
omit both mixed-sign quadrants. For an odd coprime pair with neither
component divisible by 3, exactly one `tau` survives this local filter.

### Exact integer-radical filters

The reconstructed auxiliary radical is

\[
w=\frac{(q+\tau a)x}{q}-6n.
\]

Since `gcd(a,q)=1`, also `gcd(q+tau*a,q)=1`. Therefore, for every
reduced parameter pair and either sign combination,

\[
\boxed{y\in\mathbb Z\quad\Longleftrightarrow\quad w\in\mathbb Z
\quad\Longleftrightarrow\quad q\mid X.}
\]

This equivalence does not depend on parity or the modular constraints.
It permits an immediate exclusion of an entire fiber when `q>X_max`,
and an exact divisibility rejection before constructing rational
certificates for a candidate. These exclusions apply only when integral
radicals are required.

There is also an integer-only constraint on the common coordinate factor.
The radical equation gives `x | 36n^3-65`. If `g=gcd(N,X)`, then `g`
divides both `x` and `36n^3`, and therefore divides `65`. Consequently

\[
\boxed{g\in\{1,5,13,65\}.}
\]

Rejecting other recovered scales is valid in integer-radical mode.
These are necessary filters, not substitutes for verification of the
original equation and its principal branch.

## 3. The two monotone cubics

For a fixed `(a,q)` and `tau`, reconstruct

\[
w=(1+\tau a/q)x-6n,\qquad y=s_xw.
\]

Squaring and normalizing signs gives

\[
\boxed{H_\tau(N,X)=s_n65q^2,}
\]

where

\[
H_\tau(U,V)=36q^2U^3+12q(2q+\tau a)UV^2
-a(2q+\tau a)V^3.
\]

All production solutions satisfy this equation. Conversely, a solution
of it in the magnitude bounds yields the radical identity. Its principal
branch must still be checked as `y=s_xw>=0`, and all requested signed
congruences must be checked. The implementation performs these checks
exactly, including for small test rectangles.

For a fixed `tau`, the positive-residual target `+65q^2` corresponds to
`n>0`, and the negative-residual target `-65q^2` to `n<0`. The sign of `x`
is then determined by `s_x=tau*s_n`. A single sequence of convergents can
therefore serve two opposite quadrants without duplicating root isolation.
The nonzero constant `65` is not sign-symmetric: negating both coordinates
changes the residual sign, so one cannot obtain all solutions by simply
negating an already discovered point.

For positive `x`, `d` is fixed by the parameter pair and `tau`:

\[
d=-1-\tau\frac a{2q}\qquad(x>0).
\]

For negative `x`, instead,

\[
\boxed{d=\tau\left(\frac a{2q}-\frac{6N}{X}\right)
=\tau\frac{|k|}{2X}\qquad(x<0).}
\]

Thus these are **auxiliary-parameter fibers**, not always fixed-`d`
fibers. The negative-`x` cases have `d` very close to zero; asymptotically
`d ~ tau*9(N/X)^3`. The positive-`x` cases have `d` close to `-1`.
More precisely, the four signs behave as follows:

| Sign of `n` | Sign of `x` | `tau` | Location of `d` |
|---|---|---|---|
| positive | positive | +1 | just below `-1` |
| positive | negative | -1 | just below `0` |
| negative | positive | -1 | just above `-1` |
| negative | negative | +1 | just above `0` |

These are all noninteger values in the production region. Searching only
negative `d` near `-1` would miss part of the user's signed search.

## 4. Certified continued fractions cover every admitted fiber

Let `alpha_tau` be the unique positive real root of

\[
P_\tau(T)=36q^2T^3+12q(2q+\tau a)T-a(2q+\tau a).
\]

Because `0<a<q`,

\[
P_\tau'(T)=108q^2T^2+12q(2q+\tau a)>12q^2
\]

for all real `T`. The polynomial is strictly increasing, its constant
term is negative, and its positive root satisfies
`0<alpha_tau<a/(12q)`. This provides a rigorous initial upper bound for
the existing integer Newton root-isolation method. The derivative stays
positive for both sign choices; no multiple-root approximation is used.

A solution has

\[
P_\tau(N/X)=\frac{s_n65q^2}{X^3},
\]

so the mean-value theorem gives

\[
0<\left|N/X-\alpha_\tau\right|<\frac{65}{12X^3}.
\]

Write `g=gcd(N,X)`, `N=gu`, `X=gv`, with `u,v>0` coprime. Then

\[
\left|u/v-\alpha_\tau\right|<\frac{65}{12g^3v^3}
<\frac1{2v^2}
\]

whenever `65<6g^3v`. Since `g^3v=g^2X>=X`, this holds whenever `X>=11`,
in particular throughout the production region. Legendre's criterion
therefore makes `u/v` a regular continued-fraction convergent of
`alpha_tau`.

Homogeneity yields

\[
g^3H_\tau(u,v)=s_n65q^2.
\]

It is sufficient to generate every convergent with `v<=X_max`, require
`H_tau(u,v)!=0`, and test whether

\[
65q^2/|H_\tau(u,v)|
\]

is an exact positive integer cube `g^3`. The sign of `H_tau(u,v)` supplies
`s_n`; `tau` then supplies `s_x`. Reconstruct the signed coordinates,
check the magnitude bounds, require `q | X` for the target integer radical,
and verify the original equation and branch.
Both upper and lower convergents matter: their residual signs correspond
to different signs of `n`.

For small-domain validation, the worker also checks every `X<=10` in the
requested magnitude interval. At fixed `X`, strict monotonicity of
`H_tau(N,X)` permits exact binary search for each of the two targets.
This covers every potential exception to the sufficient CF inequality,
including exceptions with `g>1`. It makes exhaustive comparisons on small
rectangles meaningful without imposing the production-scale argument.

The CF argument covers rational radicals, and therefore covers their
integer subset. The exact `q | X` filter retains every point in the
requested integer subset. This establishes completeness for each fully
processed admitted `(a,q)` fiber, radical mode, and requested sign quadrant.
It does not claim that a finite campaign has processed all possible pairs.

## 5. Exact arithmetic and completion certificates

The separation `N/X-alpha_tau` can be of order `X^-3`, around `10^-165`
at the upper bound. Ordinary double precision, an uncertified decimal
root, or guessed continued-fraction digits cannot establish coverage.

Root isolation and continued-fraction extraction use integer/rational
bounds and certified common partial quotients, refining an enclosure
when needed. A precision cap, interrupted fiber, or unresolved enclosure
is unfinished work and must never be counted as completed coverage. All
residual signs, divisibility decisions, cube tests, square tests, and
final rational values use exact arithmetic.

The root is in fact irrational for the admitted family. Otherwise set
`n=alpha_tau`, `x=tau`, and `y=1+tau*a/q-6*tau*alpha_tau`. These are
nonzero rational coordinates satisfying the homogeneous radical equation
`y^2=(x+6n)^2+36n^3/x`. Consequently

\[
(y-x)^3+(-x-y)^3+(2x+6n)^3=0.
\]

Fermat's theorem for exponent 3 implies that at least one of these three
bases is zero. Either of the first two cases forces
`n*(x^2+3nx+3n^2)=0`, impossible for nonzero real `n,x` because the
quadratic is positive definite. The third case gives `x=-3n` and then
`y^2=-3n^2`, also impossible. This proves irrationality for both `tau`
choices. The implementation's handling of detected exact rational roots
is defensive; the production completeness argument does not depend on
such a root ever occurring.

## 6. What a bounded campaign proves

For the required integer radical, the preceding divisibility proof gives

\[
\boxed{q\mid X,\qquad q\le X\le10^{55}.}
\]

Combined with the slope enclosure, this is a finite parameter search
region. It remains far too large for a practical exhaustive sweep. Each
campaign must identify the auxiliary parameter pairs, radical mode, and
sign quadrants it actually covers. Prioritizing small numerators is a
transparent search strategy, not a theorem that a solution must have small
numerator or denominator.

Only in the explicitly selected broader rational-radical mode is the
weaker bound needed: if `y=p/r` is reduced, then `r^2 | X` and `q | Xr`,
giving `q <= X*floor(sqrt(X)) < 3.163*10^82` and `q^2 | X^3`.

No hit means only that the completed fibers in the reported campaign
contain no verified solution. It proves neither nonexistence throughout
the requested signed region nor that further computation must find a
solution. Existing campaign results cover the sign scope and radical mode
they actually processed; changing that scope requires new task identities
and completion certificates.

## 7. Integer-radical target and the number 390

For the required integer principal radical, set `k_0=y-x-6n`. Then `k_0`
is an integer, and direct algebra gives

\[
(6n+k_0)^3+(-2x-6n-k_0)^3+(2x+6n)^3=390.
\]

This identity is valid with signed `n,x`; `k_0` need not be positive.
Thus every accepted production hit supplies an integer solution of this
sum-of-three-cubes identity. In the explicitly selected broader mode,
a reduced rational radical `y=p/r` instead gives right-hand side
`390r^3` after clearing denominators. A historical rational-radical
fixture is not evidence of an integer-radical target hit.

## 8. Independent validation checklist

Meaningful validation includes:

- Exact checks that both signed cubics imply the radical identity.
- An independent verifier based on `M=m^2`, with `y=m/|x|`, and a required
  integrality check in the default mode.
- Genuine nonempty fixtures with negative coordinates and nonintegral
  radicals; for example `n=-5,x=81,y=454/9,d=-913/1458` must be rejected
  in the default mode and accepted only with explicit rational-mode scope.
- Independent checks of `y` integral if and only if `q | X`, the bound
  `q <= X_max`, and the integer-only common-factor restriction `g | 65`.
- Exact cube-scale recovery for both residual signs.
- Exhaustive small-domain comparisons across all four quadrants,
  including `X<=10`, wrong principal branches, and signed residues.
- Certified brackets and CF prefixes for both `tau` polynomials, checked
  against independent computations and refinement-boundary cases.
- Interrupted-run/resume comparisons and independent final certificates
  that bind the sign scope as well as all magnitude bounds.

This checklist specifies what must be tested. The release validation
report records the executed checks and their actual outcomes.

## 9. General a/q campaign enclosure and indexing

The `general-aq-v1` campaign derives an enclosure for **all reduced
auxiliary fractions associated with the requested integer-radical
solutions**. It does not fix `a=1`, select a numerator list, or impose a
numerator ceiling independently of the coordinate bounds. The following
proof assumes the original congruences and integer-radical mode, positive
ordered magnitude bounds, and these guards:

\[
N_{\min}\ge2,\qquad X_{\min}>6N_{\max},\qquad
M_{\max}<X_{\min}.
\]

The last quantity is derived below. The first guard ensures that
`36n^3-65` has the sign of `n` in both signed branches. In particular,
positive `n=1` is exceptional and must not be included by this enclosure.
All three guards hold for the requested production rectangle. The
coprime-to-6 filters below rely on the original congruences; this is not a
completeness claim for an unconstrained small-domain test problem.

### A finite enclosure with no selected numerator

Keep `N=|n|`, `X=|x|`, `S=x+6n` and the signed radical `w=s_x y` from
Section 2, and define the positive integer

\[
K=|w-S|.
\]

Since `S` has the sign of `x`,

\[
x(w+S)=X(y+|S|)>0,
\qquad
K=\frac{|36n^3-65|}{X(y+|S|)}.
\]

The radical and `S` are integers, and `36n^3-65` is nonzero, so `K>=1`.
Using `y>=0` and `|S|>=X-6N` gives the exact integer upper bound

\[
K\le K_{\max}:=
\left\lfloor
\frac{36N_{\max}^3+65}
{X_{\min}(X_{\min}-6N_{\max})}
\right\rfloor.
\]

Allowing equality here is conservative. If `K_max=0`, no integer-radical
target exists in these bounds and the candidate enclosure is empty.

As `w-S` has the sign of `n`, the positive numerator before reduction is

\[
M=|w-x+6n|=12N+K,
\qquad
M_{\min}=12N_{\min}+1,
\qquad
M_{\max}=12N_{\max}+K_{\max}.
\]

The auxiliary fraction is exactly `a/q=M/X`. If `T=gcd(M,X)`, its reduced
form has `a=M/T` and `q=X/T`; therefore `a<=M_max` and `q<=X_max`.
For each denominator `1<=q<=X_max`, every target numerator lies in the
inclusive interval

\[
\boxed{
L(q):=\left\lceil\frac{M_{\min}q}{X_{\max}}\right\rceil
\ \le a\le\
U(q):=\min\left(
\left\lfloor\frac{M_{\max}q}{X_{\min}}\right\rfloor,
M_{\max}\right).
}
\]

These bounds follow from
`M_min/X_max <= M/X <= M_max/X_min` and retain boundary values. The guard
`M_max<X_min` implies `a<q` throughout this enclosure, as required by the
CF worker. The Section 2 congruence argument further implies that both
`a` and `q` are coprime to 6. Their mutual coprimality and the branch
condition `q=-tau*a (mod 6)` remain necessary.

Every target in the signed coordinate rectangle thus maps to a unique
reduced pair in this derived enclosure. Membership is only a necessary
condition: most enclosed pairs need not yield any target. The existing
certified CF search and independent verification determine whether a
completed admissible pair has a solution in the requested bounds.

### Exact indices and continuation boundaries

Indices enumerate eligible denominators in increasing order, followed by
eligible numerators in increasing order within each row. Here eligible
means positive and coprime to 6, with `L(q)<=a<=U(q)`. Pairs with
`gcd(a,q)>1` deliberately retain an index and are rejected cheaply by the
runner. They are not interpreted as additional reduced fractions or as
additional mathematical coverage. This convention makes the index space
independent of factorization or a changing coprimality sieve.

For an integer `z>=0`, the exact number of positive integers at most `z`
that are coprime to 6 is

\[
C(z)=\left\lfloor\frac{z+5}{6}\right\rfloor
     +\left\lfloor\frac{z+1}{6}\right\rfloor,
\qquad C(z)=0\quad(z<0).
\]

When `K_max>=1`, the prefix count through denominator `Q` is

\[
P(Q)=\sum_{\substack{1\le q\le Q\\\gcd(q,6)=1}}
\bigl(C(U(q))-C(L(q)-1)\bigr).
\]

It is evaluated with exact integers. No loop over all preceding
denominators is needed: split `q` into its residue classes 1 and 5 modulo
6, split the upper bound at `q=X_min`, and use ordinary affine floor
sums. In particular,

\[
L(q)-1=\left\lfloor\frac{M_{\min}q-1}{X_{\max}}\right\rfloor,
\]

and for the nonnegative inner floors used here,

\[
C\!\left(\left\lfloor\frac{bq+\delta}{c}\right\rfloor\right)
=\left\lfloor\frac{bq+\delta+5c}{6c}\right\rfloor
 +\left\lfloor\frac{bq+\delta+c}{6c}\right\rfloor.
\]

Euclidean reduction evaluates each sum
`sum(floor((b*i+d)/c), i=0,...,t-1)` without materializing its terms.
Binary search on the monotone integer prefix `P` locates the row of an
arbitrary candidate index, including indices too large for fixed-width
machine integers. Once that first row is located, a task streams
successive pairs without repeating a prefix inversion per pair.

For an optional inclusive denominator window `[q_min,q_max]`, the index
count is `P(q_max)-P(q_min-1)` and indices are relative to that window.
The full denominator window is `[1,X_max]`; a smaller window is an
explicit restriction of coverage. Each task processes a half-open index
interval `[start_index,stop_index)`. Its checkpoint and continuation
identify the next candidate index, rather than the number of hits or the
number of CF solves. Consequently cheap rejections, including noncoprime
pairs, still count toward completed indices. The ordered enclosure, all
coordinate bounds and any denominator window must remain bound to the
campaign and continuation identity.

### Coverage and resource interpretation

Completing every index of the full derived enclosure, with every
admissible sign branch and the required radical mode, would cover the
entire requested signed coordinate rectangle. The enclosure is far too
large for that statement to imply a practical exhaustive computation.
A completed finite prefix or denominator window covers only its recorded
parameter pairs. Denominator-first ordering is an explicit scheduling
choice, not a theorem that a target must have small denominator.

This general campaign has a different workload and different indices
from the historical selected-`a=1` campaign. Its completion time cannot be
inferred from the former campaign's 49.95-billion-index size or runtime
extrapolation. Neither this enclosure nor a CPU budget guarantees a hit;
resource estimates must refer to the particular finite tasks actually
selected and to measurements of their processing rate.
