# Rational `d` with integer `(n, x)` — method, algorithms, and results

**Equation.**

```
36 n^3 - 65  =  -2 d x^2 ( -(x + 6n) + sqrt( (x + 6n)^2 + (36 n^3 - 65)/x ) ),
n, x ∈ ℤ,  x ≠ 0,  d ∈ ℚ.
```

## 1. The single most important fact

`d` is **not** a free parameter: it is *determined* by `(n, x)`.  Multiplying by
the conjugate of the radical removes the square root completely and gives

```
K = 36n^3 - 65,   A = x(x+6n),   D = A^2 + xK = x^4 + 12n x^3 + 36 n^2 x^2 + K x,

        d = ( -A - sgn(x)·√D ) / (2 x^2)          and equivalently
        36 n^3 - 65 = 4 d(d+1) x^3 + 24 d n x^2 .
```

Hence

> **there is a rational `d` for the pair `(n,x)` ⟺ `D = x²(x+6n)² + x(36n³-65)`
> is a perfect square**,

and then `d` is that one explicit rational, with denominator dividing `2x²`.
Both directions are machine-checked (`DSearch.satisfiesEq_of_sq`,
`DSearch.exists_sq_of_satisfiesEq`), so the search below provably misses
nothing.  Size of `d`:

```
|d| ≈ 3 |n|^{3/2} / |x|^{3/2}   if |x| ≪ |n|      (large d lives here)
|d| ≈ |x+6n|/|x|  or  ≈ 0       if |x| ≫ |n|.
```

## 2. The algorithms (all in `algorithms/`, ready to run on macOS)

| engine | what it does | why it is potent |
|---|---|---|
| **F** `engine_full.py` | for a fixed `n`: factor `K`, run over squarefree divisors `s` of `K`, factor `K/s = u·v`, put `W=(v-u)/2` and solve the cubic `s t³ + 6n t = W`; every root gives `x = s t²` | **complete over *all* `x ∈ ℤ`, with no bound whatsoever**, in ~1 ms per `n` |
| **E** `engine_sqfree.c` | `x = ±s t²` with `s` odd squarefree, `3∤s`; then `n` must satisfy `36n³ ≡ 65 (mod s)`, so only ~`1/s` of all `n` are tested | covers `|x| ≤ X, |n| ≤ N` in `≈3.2·N·√X` tests instead of `4NX`; best for the large-`|d|` regime |
| **C** `engine_m.c` | with `m = √D - A`: `(P-R)(P+R) = 8m³`, `P = 12mn-K`; factor `8m³`, solve a cubic for `n`, read off `x` | reaches `\|x\| ~ 10¹²–10¹⁴` that no scan could enumerate; every candidate is an exact solution, no square test needed |
| **B** `scan_box.c`, **A** `scan_curve.c` | exhaustive sweeps by 3rd/4th-order finite differences (no multiplications in the inner loop) + mod 64/63/65/11 square filter | `3·10⁸` pairs per second per core |
| **D** `engine_divK.py` | the `x \| K` sub-family via Pollard rho | reaches `\|x\|` up to `\|K\| ~ 10¹⁶` |
| `verify.py`, `make_report.py` | exact rational re-verification (radical included) and report/Lean generation | zero trust in floating point |

Two **pruning theorems** make all of this fast (both machine-checked in
`RequestProject/Prune.lean`): `x | m²` forces the squarefree kernel `s` of `x`
to divide `K = 36n³-65`; since `K` is always odd and `≡ 1 (mod 3)`,

* the exponents of `2` and `3` in `x` are **even** — `x = ±2, ±3, ±6, ±8, ±12,
  ±18, ±24, ±27, …` are impossible;
* for every other `x`, `n` is pinned to the roots of `36n³ ≡ 65 (mod s)`.

Run everything with `sh algorithms/run_all.sh 8`.

## 3. What the search found

See `SOLUTIONS.md` for the table (and `RequestProject/Solutions.lean` for the
machine-checked proof of each row).  Searched so far:

* **every `x ∈ ℤ` whatsoever, for every `|n| ≤ 5·10⁶`** (engine F — complete,
  no bound on `|x|`);  this is an exhaustive result, not a windowed one;
* `|x| ≤ 10⁶`, `|n| ≤ 10⁸` (engine E);
* `|x| ≤ 10⁶`, `|n| ≤ 2·10⁴` (engine B, exhaustive box: 8·10¹⁰ pairs);
* `|m| ≤ 10⁷` (engine C, reaching `|x|` beyond `10¹²`);
* the `x | K` family for `|n| ≤ 2·10⁵` (engine D).

**Six solutions exist in that range, and no others**:

| n | x | d |
|---|---|---|
| -5 | 81 | `-913/1458` |
| -2960189 | 34556096 | `-262121371/552897536` |
| 46219 | -394731 | `-144791/2368386` |
| 1847965 | -16010260 | `-761139263/13896905680` |
| 166 | -2500 | `-1103/250000` |
| 2047 | -45972 | `-599/551664` |

## 4. An honest word about "very large `d`"

The solution set is genuinely **thin**.  The standard heuristic (a number of
size `D` is a square with probability `1/(2√D)`) gives, for the region
`|n| ≤ N`, an expected number of solutions growing only like `c·log N` — and
the data match: `8·10¹⁰` exhaustively tested pairs produce 3 solutions, and
each further solution costs roughly a whole extra decade of search.

Worse for the "large `d`" wish: `|d| ≳ 1` needs `|x| ≲ |n|`, and in that
sub-region the expected count is about `(1/6)·ln N` times a local-density
factor `≈ 0.15`, i.e. **well under one solution per decade**.  Equivalently, a
large-`|d|` solution requires `K/s` to have a divisor within `~6nt` of `√(K/s)`
— a divisor in a *very* short interval around the square root, which is rare.

So every solution found so far has `|x| ≫ |n|` and therefore a small `|d|`
(but a genuinely large *denominator* and numerator: up to
`-761139263/13896905680`).  No solution with `|d| > 1` exists in any region searched, and the
heuristic says one should not expect one until the search is pushed several
more decades.  The engines above are exactly the tools that buy those decades
at the lowest possible cost: engine F is complete in `x` at ~1 ms per `n`, so
letting it run over `|n| ≤ 10⁸` (a few CPU-days, trivially parallel) is the
single best way to continue the hunt, with engine E covering the small-`|x|`,
huge-`|n|` corner where the largest `d` would live.
