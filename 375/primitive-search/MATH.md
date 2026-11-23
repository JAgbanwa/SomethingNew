# Mathematical restrictions and the search model

## Target and canonical variables

Let `d = abs(x+y)` for the two coordinates of largest magnitude, and let `t = abs(z)` for the remaining coordinate. At the large heights searched here, the large pair have opposite signs and nearly cancel. Write their magnitudes as `a` and `a-d`, where `a` is the maximum coordinate height. For one of the two signs `s`:

\[
t^3=a^3-(a-d)^3+s\,375
    =3da^2-3d^2a+d^3+s\,375.
\]

The worker uses cube roots modulo `d`, 3-adic restrictions, quadratic-residue filters and an exact square test. Its finite region is explicit: a half-open `d` interval, `floor(3847*d/1000) <= t <= R*d`, and exact maximum height strictly above the chosen `H`. The slight rounding below the asymptotic canonical lower ratio is conservative. `H` and `R` do not define a complete height box.

## Primitive 375 and powers of 5

If `g = gcd(x,y,z)`, then `g^3` divides `375 = 3*5^3`. Consequently `g` is either 1 or 5. Every primitive solution has all coordinates congruent to 2 modulo 3, since 375 is 6 modulo 9 and cubes modulo 9 are 0 or ±1.

If 5 divides `d`, reduction of the cube equation modulo 5 implies 5 divides `z`. In a primitive triple the other two coordinates are units modulo 5. For such coordinates with 5 dividing their sum,

\[
v_5(x^3+y^3)=v_5(x+y),
\]

because `x^2-xy+y^2` is `3*x^2` modulo 5 and is a unit. On the other hand, `375-z^3` is divisible by 125. Thus **valuations 1 and 2 of `d` are impossible for a primitive triple**. This is a necessary-condition filter, not an existence claim for the remaining valuations.

For `125 | d`, take a signed target `K = ±375` in the worker's positive-`t` normalization and a root `r^3 = K (mod d)`. Set

\[
w=(r^3-K)/d\pmod5.
\]

The reconstruction discriminant is

\[
\Delta=\frac{4(t^3-K)/d-d^2}{3}.
\]

Modulo 5, it is `3*w`. For primitive coordinates its square root must be a unit. Therefore `3*w` is 1 or 4 modulo 5, equivalently **`w` is 2 or 3**. The worker computes this quotient using residues modulo `5*d` before scanning the progression. Replacing `r` by `r+n*d` leaves the quotient modulo 5 unchanged in this case. Final gcd verification remains mandatory.

## Complete roots modulo singular prime powers

For `p != 3`, write `v_p(k)=v`. If `e <= v`, the roots of `z^3 = k (mod p^e)` are exactly the multiples of `p^ceil(e/3)` modulo `p^e`.

If `e > v` and `v` is not divisible by 3, there are no roots. If `v = 3*s`, write `z=p^s*u`; then `u` is a unit satisfying

\[
u^3=k/p^{3s}\pmod {p^{e-3s}}.
\]

Lift the unit roots by nonsingular Hensel lifting and enumerate their `p^(2*s)` lifts when converting back to residues `z (mod p^e)`. This avoids brute-force iteration through an enormous modulus. For 375 and `p=5`, `s=1`: above exponent 3 there are 25 roots before primitive filtering. The worker's root-dump mode retains all of them so it can be compared with an independent root enumerator.

## Exact height pruning

Define `F(d,H)=H^3-(H-d)^3`. For `0 < d <= H`, this increases with `d`; for `a > H`, `F(d,a)>F(d,H)`. A block starts at `d=A`. Every sought triple in a block with `A <= H` therefore satisfies

\[
t^3>F(A,H)-375.
\]

The worker computes the integer cube root of this lower bound with GMP and starts above it. If the expression is negative, no positive cutoff is imposed. For blocks starting above `H`, the geometry already forces the maximum height above `H`. A block that crosses `H` is still safe: for `d>H`, the canonical height is at least `d`, giving an even larger bound. Every returned hit is finally checked against `a>H` with exact arithmetic.

This is independent of floating-point planning formulas. Changing or disproving the probability model would not change enumeration correctness.

## Density and runtime models

Booker and Sutherland's Table 1 gives `rho_3 = 0.061052`. Scaling by 5 is a unit transformation at every prime except 5. Modulo 5, the zero-target cubic has 25 solutions, of which 24 are nonsingular primitive classes; the nonzero target 3 has 25 nonsingular classes. The primitive local-density factor for 375 is therefore `24/25`, giving the heuristic coefficient

\[
\rho_{375,\mathrm{primitive}}=\frac{24}{25}\rho_3=0.05860992.
\]

The planner uses this local calculation with the Heath-Brown/Booker–Sutherland density heuristic. It is not a theorem that counts in a particular finite region follow it.

Neglecting the fixed constant 375 at very large height, the lower ratio imposed by `H` is

\[
r_{\min}(d)=\max\left(\frac1\alpha,
 (3(H/d)^2-3H/d+1)^{1/3}\right),
\qquad \alpha=\sqrt[3]{2}-1,
\]

with `1/alpha` used once `d>=H`. Using the asymptotic angular tail proportional to `r^(-1/2)`, a constant-`R` band has expected count

\[
\lambda\approx\rho_{375,\mathrm{primitive}}
\int_{d_0}^{d_1}
\left[\frac1{\sqrt{\alpha r_{\min}(d)}}-
      \frac1{\sqrt{\alpha R}}\right]_+\frac{\mathrm{d}d}{d}.
\]

The local benchmark fits cost per `d` to `a+b*max(0,R-r_min(d))`. Equal marginal modeled yield suggests `R(d)` roughly proportional to `d^(-2/3)` for `d << H`. The planner optimizes this family, represents it by disjoint geometric bands with constant integer ratios, and integrates both the expected count and modeled cost of those actual bands. It does not prove global optimality over all algorithms or search regions.

Finally, `1-exp(-lambda)` uses an additional Poisson assumption. It is a planning estimate, not a measured probability, a confidence level or evidence that an empty interval contains no solution. The local timing fit must also be checked on CE hardware before using it for a large allocation.

Reference: Booker and Sutherland, [On a question of Mordell](https://arxiv.org/abs/2007.01209), especially the density and search-region discussion.
