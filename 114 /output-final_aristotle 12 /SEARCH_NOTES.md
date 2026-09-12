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
* each of the ten explicit solutions `sat_sol₁ … sat_sol₁₀` listed below;
* **completeness for `|n| ≤ 200`**: `sat_exhaustive_abs_n_le_200` shows that `(1, -9)` and
  `(-54, -9)` are the only solutions in that range, so `sat_d_of_abs_n_le_200` gives
  `d ∈ {-1/54, 1583/54}` there. The finite part of that proof is a kernel-checked computation
  over the ≈1.5·10⁸ pairs allowed by the bound of §2.3.

**Computed, not proved**: the exhaustiveness of the large searches of §4. They are ordinary C
programs; every hit they print is re-verified exactly (and then proved in Lean), but their
completeness is not a theorem.

## 4. Searches carried out

| search | range | outcome |
| --- | --- | --- |
| box (earlier run) | `\|n\| ≤ 10⁶`, `\|x\| ≤ 10⁶` | 5 pairs |
| box (earlier run) | `\|n\| ≤ 2·10⁵`, `\|x\| ≤ 4·10⁶` | adds `(798, -1642284)` |
| by `U = 2dx²` | `\|U\| ≤ 10⁸`, any `n`, any `x` | nothing new |
| by `x = ±e y²` | `\|n\| ≤ 1.2·10⁵`, **all** `x` | nothing new (cross-check) |
| by divisor pairs | `\|n\| ≤ 10⁸`, **all** `x` | adds two new pairs |
| sieve + divisor pairs | `\|n\| ≤ 3.6·10⁹`, **all** `x` | adds two more pairs |
| sieve + divisor pairs (this run) | `3.6·10⁹ ≤ \|n\| ≤ 8·10⁹`, **all** `x` | nothing new |

(The searches skip the values of `n` for which `36n³-19` has more than 2·10⁶ divisor
combinations — about one in 12 000; they are listed in the `search/dverr_*.txt` and
`search/sverr_*.txt` logs and, for the last run, in `search/run2/skipped_n.txt` (699 984
values). For large `n` the sieve also leaves an unfactored cofactor, so beyond `|n| ≈ 10⁸` the
searches are thorough but no longer provably exhaustive. `search/run2/README.md` records the
exact ranges covered by the last run.)

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

The last four are the "particularly very large" ones: `n` reaches nine digits and `x` ten
digits.

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
