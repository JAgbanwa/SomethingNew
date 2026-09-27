# Exact mathematical basis of the signed search (CE390 3.1.0)

## Scope

The target is

\[
36n^3-65=-2d x^2\left(-x-6n+
\sqrt{(x+6n)^2+(36n^3-65)/x}\right),
\]

with the **principal**, nonnegative square root, rational `d`, and integers

\[
10^{43}\le |n|\le10^{45},\qquad
10^{54}\le |x|\le10^{55},\qquad
n\equiv1\pmod3,\quad x\equiv5\pmod{12},\quad7\nmid x.
\]

All bounds are inclusive. Both signs are allowed independently: `(+, +)`,
`(+, -)`, `(-, +)`, and `(-, -)`. Congruences apply to the actual signed
integers, not their absolute values. For example, negative `n` requires
`|n| = 2 mod 3`, and negative `x` requires `|x| = 7 mod 12`.

The search permits a rational, nonintegral square root. Requiring an integer
square root would discard legitimate solutions to the stated rational-`d`
problem; it is an optional additional filter. The numerical scale is a
requested search region, not a proved lower bound or an existence theorem.

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

The independent verifier checks this square certificate, the original
rational equation, the principal branch, signed congruences, and magnitude
bounds. In particular, it does not reconstruct `y` as `m/x` when `x<0`.

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
check the magnitude bounds, and verify the original equation and branch.
Both upper and lower convergents matter: their residual signs correspond
to different signs of `n`.

For small-domain validation, the worker also checks every `X<=10` in the
requested magnitude interval. At fixed `X`, strict monotonicity of
`H_tau(N,X)` permits exact binary search for each of the two targets.
This covers every potential exception to the sufficient CF inequality,
including exceptions with `g>1`. It makes exhaustive comparisons on small
rectangles meaningful without imposing the production-scale argument.

This establishes completeness for each fully processed admitted `(a,q)`
fiber and each requested sign quadrant. It does not claim that a finite
campaign has processed all possible pairs.

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

If `y=p/r` is reduced, then `r^2 | X`. The reduced denominator of the
auxiliary slope divides `Xr`, so

\[
\boxed{q\le X\lfloor\sqrt X\rfloor<3.163\cdot10^{82}.}
\]

Also `q^2 | X^3`. These finite necessary bounds are much too large for a
practical exhaustive sweep. Each campaign must identify the auxiliary
parameter pairs and sign quadrants it actually covers. Prioritizing
small numerators is a transparent search strategy, not a theorem that a
solution must have small numerator or denominator.

No hit means only that the completed fibers in the reported campaign
contain no verified solution. It proves neither nonexistence throughout
the requested signed region nor that further computation must find a
solution. Existing positive-only campaign results cover the positive
quadrant they actually processed; changing the scope requires new task
identities and completion certificates.

## 7. Integer-radical subcase and the number 390

If the principal radical happens to be an integer, set
`k_0=y-x-6n`. Direct algebra gives

\[
(6n+k_0)^3+(-2x-6n-k_0)^3+(2x+6n)^3=390.
\]

This identity is valid with signed `n,x`; `k_0` need not be positive.
For a reduced rational radical `y=p/r`, clearing denominators gives
right-hand side `390r^3`. Searching only integral radicals would cover
only a subset of the rational-`d` problem.

## 8. Independent validation checklist

Meaningful validation includes:

- Exact checks that both signed cubics imply the radical identity.
- An independent verifier based on `M=m^2`, with `y=m/|x|`.
- Genuine nonempty fixtures with negative coordinates and nonintegral
  radicals; for example `n=-5,x=81,y=454/9,d=-913/1458` checks that the
  verifier does not impose the original positive-only bounds.
- Exact cube-scale recovery for both residual signs.
- Exhaustive small-domain comparisons across all four quadrants,
  including `X<=10`, wrong principal branches, and signed residues.
- Certified brackets and CF prefixes for both `tau` polynomials, checked
  against independent computations and refinement-boundary cases.
- Interrupted-run/resume comparisons and independent final certificates
  that bind the sign scope as well as all magnitude bounds.

This checklist specifies what must be tested. The release validation
report records the executed checks and their actual outcomes.
