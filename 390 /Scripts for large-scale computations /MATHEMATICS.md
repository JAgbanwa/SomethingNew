# Exact mathematical basis of the search

## Scope

The production target is

\[
36n^3-65=-2d x^2\left(-x-6n+
\sqrt{(x+6n)^2+(36n^3-65)/x}\right),
\]

with the **principal**, nonnegative square root, rational `d`, and integers

\[
10^{43}\le n\le10^{45},\qquad
10^{54}\le x\le10^{55},\qquad
n\equiv1\pmod3,\quad x\equiv5\pmod{12},\quad7\nmid x.
\]

All bounds are inclusive. This search allows a rational, nonintegral square
root. Requiring an integer square root would discard legitimate solutions
to the stated rational-`d` problem. The numerical scale supplied with the
problem is treated as a requested search region, not as a proved lower
bound for solutions or a proof that this region contains a solution.

## 1. Eliminate the radical without losing its sign

Set

\[
A=36n^3-65,\qquad s=x+6n,\qquad
y=\sqrt{s^2+A/x}.
\]

In the production region, `A`, `x`, and `s` are positive, so `y>s>0`.
The original equation implies `d != 0` and makes `y` rational whenever
`d` is rational. Conversely, a rational principal square root determines
exactly one `d`. Since `(y-s)(y+s)=A/x` and `A != 0`, cancellation gives

\[
\boxed{d=-\frac{y+x+6n}{2x}.}
\]

This identity uses no numerical subtraction of nearly equal radicals.

For independent verification define

\[
M=x^2(x+6n)^2+(36n^3-65)x.
\]

The radical is rational **if and only if** `M` is the square of an integer
`m`. Indeed, `m=xy` is rational and has integer square, so it is an integer;
the converse is immediate. The principal branch requires `m>=0`. The
result is then

\[
y=m/x,\qquad
\boxed{d=-\frac{m+x(x+6n)}{2x^2}.}
\]

Checking this integer-square identity, the original equation with exact
rationals, the principal branch, the requested bounds, and the congruences
provides a verifier independent of the continued-fraction search.

## 2. Every target solution has the searched rational-parameter form

Write

\[
\boxed{d=-1-\frac{a}{2q}},\qquad a>0,\quad q>0,\quad\gcd(a,q)=1.
\]

For every production solution, this reduced representation exists with
`a` and `q` odd. In fact, it has the stronger necessary conditions

\[
\gcd(a,6)=\gcd(q,6)=1,\qquad a+q\equiv0\pmod6.
\]

To prove the parity assertions, write `y=p/r` in lowest terms with `r>0`.
The equation `p^2/r^2=s^2+A/x` implies `r^2|x`, hence `r` is odd and not
divisible by 3. Modulo 4, `x=1`, `s^2=1`, and `A=3`, so `p` is even.
Modulo 3, `x=2`, `s^2=1`, and `A=1`, so `p` is divisible by 3.
Now

\[
\frac aq=\frac{y-x+6n}{x}
=\frac{p-rx+6nr}{rx}.
\]

Its numerator and denominator are odd; neither is divisible by 3.
Reduction preserves these facts. Modulo 3 this rational number equals
`-1`, proving `a+q=0 mod 3`. Positivity follows from `y>x+6n`.

The reduced denominator of `d` is therefore exactly `2q`, with precisely
one factor of 2. A campaign that enumerates these reduced pairs does not
duplicate a solution under different representations of `d`.

The auxiliary quantity `k=y-x-6n` is positive and satisfies

\[
A=xk(2x+12n+k),\qquad0<k<18n^3/x^2.
\]

Consequently

\[
12n/x<a/q<12n/x+18(n/x)^3.
\]

Across the requested rectangle this yields the exact, useful enclosure

\[
\boxed{12\cdot10^{-12}<a/q<12\cdot10^{-9}+18\cdot10^{-27}.}
\]

In particular,

\[
-1-6\cdot10^{-9}-9\cdot10^{-27}<d<-1-6\cdot10^{-12}.
\]

Thus **every solution in the requested region has a noninteger `d`**;
there is no reason to search arbitrary magnitudes of `d`.

## 3. The binary cubic equation

For a fixed reduced pair `(a,q)`, the radical must be

\[
y=(1+a/q)x-6n.
\]

Substitution and multiplication by `q^2` give the exact binary cubic

\[
\boxed{F_{a,q}(n,x)=65q^2,}
\]

where

\[
F_{a,q}(u,v)=36q^2u^3+12q(2q+a)uv^2-a(2q+a)v^3.
\]

Every target solution satisfies this equation. Conversely, if a positive
integer pair in the production rectangle satisfies it, then

\[
(2+a/q)x^2((a/q)x-12n)=36n^3-65>0.
\]

Hence `(a/q)x>12n` and the reconstructed radical obeys
`y>x+6n>0`. Thus the principal-branch condition follows in the production
region. The independent verifier nevertheless checks it explicitly.

## 4. Why continued fractions cover every solution in a processed fiber

Let `alpha` be the unique real zero of

\[
P(T)=36q^2T^3+12q(2q+a)T-a(2q+a).
\]

It is positive because `P(0)<0`, and uniqueness follows from

\[
P'(T)=108q^2T^2+12q(2q+a)>24q^2
\]

for all real `T`. A solution has

\[
P(n/x)=65q^2/x^3>0,
\]

so the mean-value theorem gives

\[
0<n/x-\alpha<\frac{65}{24x^3}.
\]

Write `g=gcd(n,x)` and reduce `n/x=u/v`, with `u,v>0` coprime. Then

\[
0<u/v-\alpha<\frac{65}{24g^3v^3}.
\]

In the production rectangle, `g<=n`, and therefore

\[
v=x/g\ge x/n\ge10^9.
\]

In particular `65<12g^3v`, giving

\[
\boxed{|u/v-\alpha|<1/(2v^2).}
\]

The continued-fraction approximation theorem (Legendre's criterion)
therefore implies that `u/v` is a regular continued-fraction convergent
of `alpha`.

For each such convergent, homogeneity gives

\[
g^3 F_{a,q}(u,v)=65q^2.
\]

Thus it is sufficient to:

1. Generate every convergent with denominator `v<=10^55`.
2. Require `F(u,v)>0` and exact divisibility of `65q^2` by `F(u,v)`.
3. Require the quotient to be an exact positive integer cube `g^3`.
4. Reconstruct `n=gu`, `x=gv`.
5. Apply the exact independent verifier and all requested filters.

This is **complete for each fully processed `(a,q)` fiber**. It replaces
an enormous scan of individual `(n,x)` values by a short list of rational
approximations to one cubic root. Convergents on the lower side of `alpha`
have `F(u,v)<0` and cannot produce positive-scale solutions.

The implementation also covers arbitrary positive test rectangles. Since
`g^3 v=g^2 x`, the same strict inequality holds whenever `x>=6`.
If `g>=2`, it holds even for `x<6`. Thus possible exceptions are confined
to `g=1` and `x<=5`. The worker explicitly checks each of the at most five
such `x` values by exact binary search in `n`, using the strict monotonicity
of `F(n,x)` in positive `n`. This makes small-domain exhaustive comparisons
meaningful without assuming the production scale.

In fact the positive root is irrational. If it were rational, put
`n=alpha`, `x=1`, `y=1+a/q-6alpha`, and `k=y-1-6alpha` in the homogeneous
equation `F(n,x)=0`. It gives `k>0` and

\[
(6\alpha+k)^3+(2+6\alpha)^3=(2+6\alpha+k)^3.
\]

All three bases would be positive rational numbers. Clearing denominators
would contradict Fermat's theorem for exponent 3. Exact finite-root
handling in the worker is therefore defensive; it is not needed for an
admissible positive fiber.

## 5. Exact arithmetic is essential

The separation `n/x-alpha` can be of order `x^-3`, around `10^-165` at the
largest requested `x`. Ordinary double precision, an unverified decimal
root, or guessed continued-fraction digits cannot certify coverage.

Root isolation and continued-fraction extraction must use integer/rational
bounds with a certified common partial quotient, refining an enclosure
whenever its endpoints do not certify the same next quotient. A precision
limit, interrupted fiber, or unresolved enclosure is unfinished work and
must be reported or checkpointed, never counted as a completed fiber.
All polynomial residuals, divisibility decisions, integer cube tests,
integer square tests, and final rational values must be exact.

## 6. What a bounded campaign proves

The search rectangle is enormous, and the continued-fraction theorem does
not make the set of all rational-parameter fibers small. For a solution,
if `y=p/r` is reduced then `r^2|x`, and the reduced denominator `q` of
`a/q` divides `xr`. Hence

\[
q\le x\lfloor\sqrt{x}\rfloor<3.163\cdot10^{82}.
\]

Another useful necessary property is `q^2|x^3`: the divisibilities
`q|xr` and `r^2|x` give `q^2 | x^2 r^2 | x^3`.

These are finite bounds, but they are much too large for a practical
exhaustive sweep. A campaign must name the numerator/denominator fibers
it actually covers. Searching small numerators first is a transparent
prioritization of rational numbers near `d=-1`; it is not a theorem that
the first or any solution has a small numerator.

No hit means only that the completed fibers in the reported campaign
contained no verified solution. It does not prove nonexistence in the
whole rectangle. No implementation or allocation of CPU cores can
guarantee a solution exists in the requested rectangle.

## 7. Integer-radical subcase and the number 390

If the square root happens to be an integer, `k=y-x-6n` is a positive
integer, `k=1 mod 6`, and

\[
(6n+k)^3+(-2x-6n-k)^3+(2x+6n)^3=390.
\]

This explains the sum-of-three-cubes structure, but an integer-`k` search
alone would cover only a subset of the rational-`d` request. For a reduced
rational radical `y=p/r`, the analogous scaled identity has right-hand
side `390r^3`, not `390`. The rational-parameter cubic above covers both
cases.

## 8. Independent validation checklist

Meaningful validation should include:

- Direct symbolic or exact-integer checks that the radical identity and
  the binary cubic give the same result.
- An independent verifier based on `M=m^2`, not just another evaluation
  of `F`.
- A supplied rational-radical example, such as
  `n=-5, x=81, y=454/9, d=-913/1458`, to ensure the verifier distinguishes
  a rational radical from an integer one. This example is deliberately
  outside the production region and must not be accepted as a target hit.
- Exact recovery of scale `g` and rejection of noncube quotients.
- Small-domain comparisons, including `x<=5`, to exercise both the
  continued-fraction theorem and the supplementary monotone search.
- Certified root brackets and continued-fraction prefixes compared with
  a second implementation, including refinement-boundary cases.
- Interrupted-run/resume comparisons and independent final-certificate
  verification.

The checklist specifies properties to test; it is not itself a claim that
any particular test has been run. The release validation report records
the actual executed checks and their outcomes.
