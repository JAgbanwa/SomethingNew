# Rational `d` for which `36n³ - 19 = -2d·x²·(-(x+6n) + √((x+6n)² + (36n³-19)/x))` has integer solutions

## 1. Reduction of the equation

Write `A = 36n³ - 19` and `s = x + 6n`. The square root is the principal (nonnegative) real
square root, so the equation implicitly requires the radicand `s² + A/x` to be nonnegative.
Under that reading (formalized as `DEquation.Sat`) the equation is **equivalent** to a pair of
purely rational conditions (theorem `DEquation.sat_iff`):

```
36n³ - 19 = 4d²x³ + 4dx³ + 24 d n x²        (E)
2dx + x + 6n ≤ 0                            (branch condition)
```

Equation (E) is the equation with the radical cleared; the inequality records which of the two
roots of that quadratic in `d` is compatible with a nonnegative square root. Putting
`e = 2dx + x + 6n`, (E) becomes `x·e² = x(x+6n)² + (36n³ - 19)` with `e ≤ 0`
(`DEquation.sat_iff_e`), and multiplying by `x`:

> **(⋆)** `t² = x²(x+6n)² + x(36n³-19)` must be a perfect square, `t = x·e`.

Hence (theorem `DEquation.exists_d_iff`) integers `n`, `x ≠ 0` occur in a solution for *some*
rational `d` iff `x²(x+6n)² + x(36n³-19)` is a perfect square, and then `d` is unique
(`DEquation.sat_unique`).

## 2. The integral structure used by the searches

Put `U = t - x(x+6n)`. Then (theorem `DEquation.sat_iff_exists_U`)

* `U = 2dx²` is always an **integer**, and
* `U² + 2Ux(x+6n) = x(36n³-19)`, `(U + x(x+6n))·x ≤ 0`;

conversely every integer `U` with these two properties yields a solution with `d = U/(2x²)`
(theorem `DEquation.sat_of_U`). All the explicit solutions below are certified in this form.

Three consequences drive the searches.

1. **`x ∣ U²`** (immediate from `U² = x(36n³-19-2U(x+6n))`).
2. **The squarefree part of `x` divides `A = 36n³-19`** (theorem `DEquation.sat_prime_dvd`:
   a prime dividing `x` exactly once divides `A`). So `x = ± e·y²` with `e` a squarefree
   divisor of `A`.
3. **`|x| ≲ 13 n²`.** This is now a *theorem*, not just a heuristic. The quadratic
   `V² + 2Vx s = xA` has the second integral root `U' = -U - 2xs`, with `U·U' = -xA`, and `x`
   divides both `U²` and `U'²`, hence `|x| ≤ min(U², U'²)`. Since `|U| + |U'| ≥ |U + U'| =
   2|xs|`, the larger root has absolute value at least `|xs|`, so the smaller one `m` obeys
   `|x| ≤ m² ≤ (xA)²/(xs)²`, i.e.

   > `|x|·(x+6n)² ≤ (36n³-19)²`  (`DEquation.sat_abs_x_mul_sq_le`),

   whence `|x| ≤ 24|n|` or `|x|³ ≤ 2(36n³-19)²` (`DEquation.sat_abs_x_le`), and in all cases
   `|x| ≤ 24|n| + 14n² + 100` (`DEquation.sat_abs_x_le_poly`). In particular, for each `n`
   only finitely many `x` are possible (`DEquation.sat_x_finite`).

Writing `x = σ e y²` (`σ = ±1`, `e` squarefree, `e ∣ A`), (⋆) is equivalent to

```
(e y s)² + σ e A = m²        for some integer m,
```

i.e. to a factorisation `σ e A = g·h` with `h - g = 2 e y s`, `s = σ e y² + 6n`. So for each
`n` one factors `A`, runs over the squarefree divisors `e` of `A` and over the (signed)
divisor pairs of `σeA`, and finally solves the cubic

```
σ e y³ + 6 n y = (h - g)/(2e)
```

for an integer `y ≥ 1`. This costs only `O(3^ω(A))` arithmetic operations per `n` — instead of
`O(n²)` for a naive sweep over `x` — and is what makes a search over `|n| ≤ 8·10⁹`, with
**all** `x` allowed, possible. (Programs: `search/search_div.c`, using 128-bit Montgomery
arithmetic for the factorisations; `search/search_sv.c`, which replaces the per-`n`
factorisation by a line sieve over blocks of `n`; `search/search_ey.c` and
`search/search_u.c` are two independent, slower searches used to cross-check them.)

## 3. What is proved, and what is only computed

**Proved in Lean** (`RequestProject/Main.lean`, no `sorry`):

* the reduction `sat_iff`, the perfect-square criterion `exists_d_iff`, uniqueness of `d`
  (`sat_unique`), the integral description `sat_iff_exists_U` / `sat_of_U`, the divisibility
  structure `sat_prime_dvd`;
* the bounds `sat_abs_x_mul_sq_le`, `sat_abs_x_le`, `sat_abs_x_le_poly` and the finiteness
  statement `sat_x_finite`;
* each of the eleven explicit solutions `sat_sol₁ … sat_sol₁₁` listed below;
* **completeness for `|n| ≤ 100`**: `sat_exhaustive_abs_n_le_100` shows that `(1,-9)` and
  `(-54,-9)` are the *only* solutions in that range, so `sat_d_of_abs_n_le_100` gives
  `d ∈ {-1/54, 1583/54}` there (and `exists_sat_abs_n_le_100_iff` states the equivalence).
  The finite part of the proof is a machine-checked computation over the ≈2·10⁷ pairs allowed
  by the bound of §2.3.  A pair only reaches the exact big-integer square test if it survives
  six modular filters (four of them tables, rebuilt for each `n`, of the residues `x mod mᵢ`
  for which `V(n,x)` is a square modulo `mᵢ ∈ {4032, 715, 7429, 33263}`, and two tests of the
  exact value `V(n,x)` modulo `82861` and `190747`).  The soundness of every filter and of
  both loops is proved in Lean (`look_resTab`, `look_sqTab_of_square`, `pairOK_sound`,
  `scanX_sound`, `scanN_sound`), so the only thing trusted beyond the kernel is the Lean
  compiler (the `native_decide` axioms `Lean.ofReduceBool`, `Lean.trustCompiler`).  The
  argument is proved for a general bound `N` (`sat_exhaustive_of_scan`): running the same
  scan for `N = 1000` — about `2·10¹⁰` pairs, which needs the computational kernel to be
  compiled to native code ahead of time — gives that `(1,-9)`, `(-54,-9)`, `(909,784)` and
  `(798,-1642284)` are the only solutions with `|n| ≤ 1000`, whence
  `d ∈ {-1/54, 1583/54, -414553/43904, -1/965662992}` in that larger range.

**Computed, not proved**: the exhaustiveness of the large searches of §4. They are ordinary C
programs; every hit they print is re-verified exactly (and then proved in Lean), but their
completeness is not a theorem.

## 4. Searches carried out

### 4.1 A correction to the earlier runs: the `x`-range was not what it claimed

The programs `search_div.c` and `search_sv.c` hold every divisor of `e·|A|` in a 128-bit
integer.  To avoid overflow they silently replace the bound `|x| ≤ 13n²` of §2.3 by

```
|x| ≤ XCAP(n) = 2^125/|A|   (search_sv.c)     resp.   10^37/|A|   (search_div.c),
```

which for large `n` is *far* smaller than `13n²`.  In terms of the ratio `|x|/|n|` the
effective coverage of those runs was

| `n` | `10⁷` | `10⁸` | `10⁹` | `3·10⁹` | `8·10⁹` |
| --- | --- | --- | --- | --- | --- |
| largest `\|x\|/\|n\|` reached | `3·10⁷` | `1.2·10⁴` | `1.2` | `1.5·10⁻²` | `2.9·10⁻⁴` |

The ten solutions known have `|x|/|n|` between `0.17` and `2058`, so for `|n| ≲ 10⁸` the old
runs did cover the relevant band, but from `|n| ≈ 5·10⁸` on they missed essentially all of it:
the entry "`|n| ≤ 8·10⁹`, **all** `x`" in the earlier version of this table is wrong, and the
absence of new solutions in `10⁹ ≤ |n| ≤ 8·10⁹` says very little.

A second, smaller loss affects the same runs.  The line sieve removes the primes `≤ 3·10⁷`
from `A`; whatever is left is used as a single opaque factor even when it is composite.  For
`A` of 26 digits that costs about 15% of the divisor combinations, for 31 digits about 46%
(`search/facstat.c` measures this).  Two of the ten known solutions — the two largest,
`(-64722106, -23707161)` and `(101116178, -1691117901)` — are only found when that cofactor is
split.

### 4.2 `search_xl.c`: the same algorithm without the `x` cut-off

`search/search_xl.c` runs the divisor-pair algorithm of §2 with no 128-bit restriction on
`|x|`.  Every quantity is carried twice: exactly **modulo 2^128** (wrapping `unsigned __int128`
arithmetic) and approximately as a **double** (magnitude only).  The doubles locate the
candidate `y` (the cubic is solved in floating point), and the final test is the congruence
modulo `2^128`, which is exact.  Catastrophic cancellation could only occur for `|g| ≈ |h|`,
and there `|g|,|h| ≤ sqrt(e|A|) < 2^126`, so both values are exact integers anyway.  Each
unordered divisor pair is used once (the pairs `(g,h)` and `(h,g)` produce the same four
signed differences).  The cofactor left by the sieve can be factored completely with a
128-bit Montgomery Pollard-rho (`search/fac128.h`), under an iteration budget.

Checks performed on the program:

* it re-finds all ten known solutions (with the rho budget large enough for the two that need
  the cofactor split);
* over `|n| ≤ 200` with the full range `|x| ≤ 13n²` it returns exactly `(1,-9)` and `(-54,-9)`,
  which extends the list that `DEquation.sat_exhaustive_abs_n_le_100` proves in Lean;
* an internal consistency test (`-DDEBUG_RESID`) verified on 3.9·10⁷ candidates near
  `n = 10¹⁰` that the residual of every candidate has the magnitude predicted by the
  derivative, i.e. that the floating-point root finding is accurate and the 128-bit residues
  are consistent.

The program takes the ratio bound `K` as a parameter and searches `|x| ≤ min(13n², K|n|)`.
Cost per `n` at `n ≈ 10⁸` is about 55 µs for `K = 10⁴` (the whole band in which all known
solutions lie) against about 280 µs for the complete range `K = 13|n|`.

### 4.3 The runs

| search | range | outcome |
| --- | --- | --- |
| box (earlier run) | `\|n\| ≤ 10⁶`, `\|x\| ≤ 10⁶` | 5 pairs |
| box (earlier run) | `\|n\| ≤ 2·10⁵`, `\|x\| ≤ 4·10⁶` | adds `(798, -1642284)` |
| by `U = 2dx²` | `\|U\| ≤ 10⁸`, any `n`, any `x` | nothing new |
| by `x = ±e y²` | `\|n\| ≤ 1.2·10⁵`, all `x` | nothing new (cross-check) |
| by divisor pairs | `\|n\| ≤ 10⁸`, `\|x\| ≤ 10³⁷/\|A\|` | adds two new pairs |
| sieve + divisor pairs | `\|n\| ≤ 8·10⁹`, `\|x\| ≤ 2¹²⁵/\|A\|` | nothing new |
| `search_xl` (run3) | `\|n\| ≤ 1.33·10⁹`, `\|x\| ≤ 10⁴\|n\|` | adds `(-516368250, 55022141248)` |
| `search_xl` (run4) | `\|n\| ≤ 1.48·10⁹`, **all** `x` (`\|x\| ≤ 13n²`) | nothing further |
| `search_xl` (run5) | the `n` skipped by all earlier runs, `\|n\| ≤ 1.07·10⁹`, all `x`, cofactor split | nothing |
| `search_xl` (run6) | `[1.486·10⁹ , 1.616·10⁹]`, both signs, **all** `x` | nothing |
| `search_xl` (run6) | `[1.616·10⁹ , 1.744·10⁹]`, both signs, `\|x\| ≤ 10⁴\|n\|` | nothing |
| `ec_scan.py` (earlier run) | all `n`, by Mordell curves over `\|x\| ≤ 12000` and `15001 ≤ \|x\| ≤ 16550` | re-found `(1,-9)`, `(-54,-9)`, `(909,784)` |
| `ec_scan.py` (run7) | the ranges left open, `12001 ≤ \|x\| ≤ 21800` | nothing |

(The searches skip the values of `n` for which `36n³-19` has more than 2·10⁶ divisor
combinations — about one in 12 000; they are listed in the `search/dverr_*.txt`,
`search/sverr_*.txt` and `search/run3/err_*.txt` logs and, for the run of `search/run2`, in
`search/run2/skipped_n.txt` (699 984 values); those with `|n| ≤ 1.07·10⁹` have since been
processed individually in run5, see §4.4.  None of the large searches is exhaustive: the
`x`-range is cut at `K|n|`, the unsieved cofactor of `A` is not split, and the values above
are skipped.  Every hit that is printed is, on the other hand, re-verified exactly and then
proved in Lean.)

**All solutions known** (each `d` is the unique one for its pair, and each is proved in
`RequestProject/Main.lean`):

| `d` | `n` | `x` | digits of `n`, `x` |
| --- | --- | --- | --- |
| `-1/54` | `1` | `-9` | 1, 1 |
| `1583/54` | `-54` | `-9` | 2, 1 |
| `-414553/43904` | `909` | `784` | 3, 3 |
| `-25160015/2249728` | `14709` | `10816` | 5, 5 |
| `-15849629/24357888` | `-29317` | `507456` | 5, 6 |
| `-1/965662992` | `798` | `-1642284` | 3, 7 |
| `308597/41724656` | `-1160307` | `-10431164` | 7, 8 |
| `-186487860451/3639943440` | `12512774` | `2548980` | 8, 7 |
| `1706615972245/230860333818` | `-64722106` | `-23707161` | 8, 8 |
| `-336451937/111613781466` | `101116178` | `-1691117901` | 9, 10 |
| `-14123191460839/14966022419456` | `-516368250` | `55022141248` | 9, **11** |

The last five are the "particularly very large" ones.  The last line has an **eleven-digit**
`x`, and its ratio `|x|/|n| = 106.6` lies exactly in the band that the earlier programs could
not see at that size (they reached only `|x|/|n| ≤ 16.6` at `|n| ≈ 5·10⁸`).

### 4.4 The complete-`x` sweep (run4/run5)

The runs recorded in `search/run4` and `search/run5` (see `search/run4/README.md`) removed the
two remaining gaps of §4.1 over the whole low range:

* `|n| ≤ 1.616·10⁹` was swept with the **complete** `x`-range `|x| ≤ 13n²` (run4 up to
  `1.486·10⁹`, run6 above it) — at `|n| = 10⁹` that
  is `|x| ≤ 1.3·10¹⁹`, i.e. ratios up to `1.3·10¹⁰`, against the `1.2` that the old programs
  reached there;
* all 83 500 values of `n` with `|n| ≤ 1.07·10⁹` that every earlier run had skipped (because
  `36n³-19` has more than 2·10⁶ divisor combinations — these are the *most* productive `n`,
  since the expected number of solutions per `n` grows with the number of divisor
  combinations) were re-processed individually, with the complete `x`-range and with the
  unsieved cofactor of `36n³-19` factored completely.

No solution other than the eleven listed above exists in that region.  In particular there is
**no** solution at all with `10⁶ ≤ |n| ≤ 1.616·10⁹` apart from `(-516368250, 55022141248)`, and since
`|x| ≤ 13n²`, a solution with a fifteen-digit `|x|` would need `|n| ≥ 8.8·10⁶`; the sweep shows
that none occurs below `|n| = 1.616·10⁹`.  (The sweeps do not split the sieve cofactor, which
costs about 15% of the divisor combinations at `|n| ≈ 10⁸`, so this is a very thorough search
rather than a proof.)

As consistency checks the sweep re-found every known solution lying in the swept range —
`(-1160307,-10431164)`, `(12512774,2548980)` and `(-516368250,55022141248)` — and a separate
run over the eleven known `n` with the complete `x`-range and deep factoring confirmed that
each of those `n` carries exactly one `x`.

### 4.5 The latest runs (run6, run7)

Two further pushes are recorded in `search/run6/README.md` and `search/run7/README.md`:

* `search_xl` extended the **complete-`x`** sweep contiguously from `|n| = 1.486·10⁹` to
  `|n| = 1.616·10⁹` (both signs, including the two small holes the earlier runs had left),
  and then covered `1.616·10⁹ ≤ |n| ≤ 1.744·10⁹` in the band `|x| ≤ 10⁴|n|` that contains
  every solution known (their ratios `|x|/|n|` lie between `0.17` and `2058`).
* `ec_scan.py` continued the complementary search *over `x`*: for a fixed `x` the condition
  `t² = x²(x+6n)² + x(36n³-19)` is the Mordell curve `Y² = Z³ - 432x³(x³+57)` with
  `Z = 36xn + 12x²`, so PARI's Mordell–Weil generators give the `n` — including, in
  principle, enormous ones — for that `x`.  The ranges the earlier run had left open were
  completed, so that scan is now contiguous for `|x| ≤ 20000` and reaches `|x| ≤ 21800`.

Neither run produced a new solution, so the list of eleven values of `d` is unchanged.

## 5. Why still larger solutions are out of reach of a search

The solutions are not members of a family: the elliptic surface behind (⋆) has **no
non-trivial sections**. Concretely, fibring over `x` one gets `Y² = Z³ - 432x³(x³+57)`
(with `Z = 36xn + 12x²`, `Y = 36xt`), and fibring over `n` one gets
`Y² = Z³ - 228nZ - 432n⁶ + 1368n³ + 361` (with `Z = (36n³-19)/x + 12n²`). Both are rational
elliptic surfaces, so all their sections are polynomial of degree `≤ 2` in the base
parameter; solving the corresponding coefficient systems (`search/sect2.py`) shows that the
only sections are the trivial ones (the obstruction is that `24624` is not a cube). So there
is no polynomial family `x = x(k)`, `n = n(k)` of solutions, and every solution has to be
found individually.

A standard density heuristic (a "random" integer `V` is a square with probability
`1/(2√V)`) gives, for the number of solutions with `|n| ≤ N`,

```
Σ_{n ≤ N} Σ_x 1/(2√(x²(x+6n)² + x(36n³-19)))  ≈  c · log N ,
```

i.e. only a *logarithmic* growth — matching the ten solutions found for `|n| ≤ 8·10⁹`. The
same computation shows that a solution with **both** `|n|` and `|x|` of ten digits requires
`|n| ≈ 10¹⁰`, where `36n³-19` has 32 digits and would have to be factored for each of `10¹⁰`
values of `n`. That is far beyond the compute available here, so such pairs, while
heuristically expected to exist, cannot be exhibited by this method.

Quantitatively: the searches yield about `0.44` solutions per `e`-fold of `|n|`, while the
cost of an `e`-fold grows linearly in `|n|` (about `10⁵` core-seconds per `e`-fold at
`|n| ≈ 10⁹` for the complete `x`-range).  An eleven-digit `|n|` is therefore some two orders
of magnitude more expensive per new solution than the region already covered; with eight
cores one `e`-fold at `|n| ≈ 10¹⁰` costs several days of computation for an expected `0.44`
solutions.  Nothing in the structure of the problem shortens this: there is no family, no
section of the elliptic surface, and the `U = 2dx²` side of the problem is worse still
(`|U| ≈ x²`, so a twelve-digit `x` needs `U` of twenty-four digits).  The practical
consequence is that the reachable frontier moves by a factor of a few in `|n|` per day of
computation, and the largest solution that can be exhibited today remains the one with
`|n| ≈ 5·10⁸` and the eleven-digit `x = 55 022 141 248`.

## 6. The grid algorithms (`ALGORITHMS.md`, `grid/`) and the run of this session

The question "which rational `d` work?" is best attacked through the integer certificate
`U = 2dx²`, because `d` is determined by `(n,x)` and conversely `U` determines `d`.  Three
facts, now proved in `RequestProject/Algorithm.lean`, turn that into a search *over `d`*:

* `sat_iff_dSweep`: `Sat d n x` **iff** there are integers `U`, `c` with `U = 2dx²`,
  `U² = c·x`, `36n³ − 12Un = c + 2Ux + 19` and `(U + x(x+6n))·x ≤ 0`.  So one enumerates
  `U`, then `x ∣ U²`, and *solves* the cubic for `n` — no enumeration of `n` or `x`.
* `abs_n_le_abs_U`: `|n| ≤ |U|` in every solution.  This calibrates the search: a `D`-digit
  `n` needs a `D`-digit certificate.
* `sat_U_mod_twelve`: `x ≡ 7 (mod 12)` forces `U ≡ 5, 11 (mod 12)`, a free factor 6.

(The remark at the end of §5 that "`|U| ≈ x²`" is not right in general: `U = 2dx²` and `d`
can be very small.  The solution `(n,x) = (798, −1642284)` has a seven-digit `x` but
`U = −5586`; that is precisely why sweeping `U` reaches much further than sweeping `x`.)

`ALGORITHMS.md` describes the four programs in `grid/` built on this — the exhaustive
d-first sweep `dsweep`, the smooth-certificate sweep `dsmooth` (which reaches twenty to
thirty digit `U`), the per-`x` scan `xscan`, and the Mordell-curve phase `xcurve` — their
measured throughputs, the work-unit generator, and the digit-band escalation schedule for a
grid.

**Computations carried out in this session** (logs in `search/run8/`; unverified
computations, like the other searches recorded here, although the *criterion* they apply is
proved): with the family
restriction `x ≡ 7 (mod 12)` the exhaustive d-first sweep covered every certificate
`|U| < 2·10¹⁰` (1.16·10¹¹ pairs `(U,x)`) and the smooth-certificate sweep covered every
50-smooth certificate with `10¹⁰ ≤ |U| < 10¹⁸` (18 369 950 certificates, 3.99·10¹¹ pairs,
723 304 of them only partly, those whose `U²` has more than 200 000 divisors).  Neither
found a solution.  Together with the earlier runs this means: no solution of the
requested family `n = 3m`, `x = 12u+7` has a certificate of ten digits or fewer.  It is
worth recording that **none of the eleven known solutions lies in that family** — their `x`
are `≡ 0, 3, 4 (mod 12)`, never `7`, and every one of them is divisible by 2 or by 3 — while
there is no local obstruction to the family (the congruences are solvable modulo every
prime power tested).
