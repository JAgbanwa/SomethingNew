# How the search algorithm works, and how efficient it is

This note answers two questions about the machinery in [`grid/`](grid/):

1. **Modus operandi** — what the algorithm actually does, step by step, and why.
2. **Efficiency** — what it costs, how far it can reach, what it is blind to, and what the
   realistic prospects are of it eventually returning a solution of the requested family
   (`n = 3m`, `x = 12u + 7`) with very large `n`, `x`.

The derivation and the work-unit format are in [`ALGORITHMS.md`](ALGORITHMS.md); the
mathematical facts used below are proved in Lean in
[`RequestProject/Algorithm.lean`](RequestProject/Algorithm.lean) and
[`RequestProject/Main.lean`](RequestProject/Main.lean). All throughput numbers quoted in
§2 were **re-measured during this session** on one core of the machine this project runs
on (gcc `-O3`); they are not copied from earlier runs.

---

## 1. Modus operandi

### 1.1 The one idea that makes a search possible

`d` is not free. For a given integer pair `(n, x)`, `x ≠ 0`, the equation

```
36n³ − 19 = −2d·x²·( −(x+6n) + √( (x+6n)² + (36n³−19)/x ) )            (E)
```

has a rational solution `d` **iff** `x²(x+6n)² + x(36n³−19)` is a perfect square, and then
`d` is unique (`exists_d_iff`, `sat_unique`). So one cannot "loop over `d`" directly; one
has to loop over something that *determines* `d` and lets the other unknowns be **solved
for** instead of enumerated. That object is the integer

```
U = 2d·x²            (the numerator of d = U/(2x²)),
```

which is always an integer for a solution (`sat_iff_exists_U`), and in terms of which (E)
becomes the single Diophantine identity

```
U² + 2U·x(x+6n) = x(36n³ − 19),        together with   (U + x(x+6n))·x ≤ 0.       (★)
```

The inequality is the *branch condition*: it records which square root of the quadratic is
the principal (nonnegative) one. It is the reason a naive "clear the radical and solve"
approach produces spurious answers — the sweep tests it explicitly, and so does the
verifier.

### 1.2 The main loop (Algorithm A, `grid/dsweep.c`)

Three proved facts turn (★) into a program:

| proved fact | what it buys |
|---|---|
| `sat_U_dvd`: `x ∣ U²` | for fixed `U`, `x` ranges only over **divisors of `U²`** — a handful, not a range |
| `cubic_in_n`: with `U² = c·x`, (★) reads `36n³ − 12U·n = c + 2Ux + 19` | `n` is obtained by **one cube root**, never enumerated |
| `abs_n_le_abs_U`: `\|n\| ≤ \|U\|` | tells you exactly how far you must sweep to have a chance at a `D`-digit `n` |
| `sat_U_mod_twelve`: `x ≡ 7 (mod 12)` ⇒ `U ≡ 5, 11 (mod 12)` | 10 of every 12 certificates are skipped outright for the requested family |

so the sweep is:

```
for |U| in this work unit's interval, U ≡ 5 or 11 (mod 12):
    factor U                                   (segmented sieve + Pollard rho)
    for each divisor D of U² with ±D ≡ 7 (mod 12):
        x = ±D  (sign forced by the congruence);  c = U²/x;  K = c + 2Ux + 19
        cheap modular pre-filter on K                        (rejects ~94–99.8%)
        solve 36n³ − 12U·n = K in floating point, round, test the 3 neighbours exactly
        check the branch condition            → emit the certificate (U, x, n)
```

Everything else in the suite is a variation on, or a complement to, this loop:

* **`dsmooth.c` (A′)** — same inner loop, but the outer loop enumerates only `B`-smooth
  `U` by a depth-first product enumeration, so the factorisation is free and `U` may have
  20 or 30 digits. These are also the `U` with the *most* divisors, i.e. the most candidate
  `x` per unit of work.
* **`xscan.c` (B)** — the complementary direction: fix `x = 12u+7`, and test the cubic
  `F_x(n) = x²(x+6n)² + x(36n³−19)` for squareness over a window of `n = 3m`, using a
  precomputed quadratic-residue wheel modulo `5·7·11·13·17·19` plus 34 further primes.
  One memory access per candidate `m`.
* **`xcurve.gp` / `xcurve.py` (C)** — the same fixed-`x` problem as the Mordell curve
  `V² = Z³ − 432x³(x³+57)` with `Z = 12x(3n+x)`, `V = 36xY` (`mordell_of_sat`,
  `sat_of_mordell`): compute the rank and generators of that curve, then read off the
  integral points whose `Z`, `V` satisfy the congruences that make `n` an integer.

### 1.3 Trust model

The floating-point cube root, the modular pre-filters and the 61-bit confirmations are all
**one-sided**: they may in principle let a non-solution through, but they can never reject
a genuine one (`xscan --selftest` checks precisely that property for the residue wheel).
Every hit is then re-checked in exact arithmetic by `verify.py`, which prints the certified
rational `d`, and a certified hit is finally turned into a Lean theorem. So the pipeline is
"fast and sloppy in the filters, exact at the gate". Completeness of a *range* rests on the
Lean theorem `sat_iff_dSweep`, which says that the loop above is exactly equivalent to (E):
nothing inside the swept interval of `U` can escape it.

The self-tests were re-run in this session: `dsweep --general` and `dsmooth --test` over
`|U| ≤ 2·10⁴` both return the same three certified solutions (`d = −1/54`, `1583/54`,
`−1/965662992`) through independent code paths, and both correctly *reject* the near-miss
`U = −10743, x = −9, n = −54` on the branch condition; `xscan --selftest` passes.

---

## 2. Efficiency

### 2.1 Measured throughput (one core, this session)

| program | measurement made here | rate |
|---|---|---|
| `dsweep`, `\|U\| ≈ 10⁹` | 2·10⁶ certificates, 9.85·10⁶ `(U,x)` pairs, 2.54 s | **2.8·10⁹ `U`/core-hour** (≈ 5 divisor candidates per `U`) |
| `dsweep`, `\|U\| ≈ 10¹⁴` | 5·10⁷ certificates, 5.38·10⁸ pairs, 99.4 s | **1.8·10⁹ `U`/core-hour** (≈ 11 candidates per `U`) |
| `dsmooth`, `U ∈ [10²⁰,10²¹)`, `B = 60` | 1 shard of 20 000: 4 541 certificates, 3.06·10⁸ pairs, 23.2 s | **4.7·10¹⁰ pairs/core-hour** |
| `xscan`, one `x` | 10⁹ values of `m`, 4.60 s | **7.8·10¹¹ `m`/core-hour** |

These confirm the figures recorded earlier (they are the same to within the speed of the
host). The interesting ratios: the modular pre-filter reduces 3.06·10⁸ candidate pairs to
6.5·10⁵ cube-root extractions in the smooth run — a 99.8 % rejection rate — which is why
the per-pair cost is a few nanoseconds rather than a hundred.

### 2.2 Cost of exhausting a digit band

Because `|n| ≤ |U|`, a `D`-digit `n` needs certificates of at least `D` digits, and the
number of certificates in a decade grows by a factor 10 per digit. With the rate above
(and allowing the mild slow-down with size), the exhaustive sweep costs:

| all certificates `\|U\| ≤ X` | core-hours (both signs) | comment |
|---|---|---|
| 10¹⁰ | ≈ 8 | done in this project for the family |
| 10¹² | ≈ 1.1·10³ | a day on a few hundred cores |
| 10¹⁴ | ≈ 1.1·10⁵ | ≈ 13 core-years — a realistic grid month |
| 10¹⁶ | ≈ 1.2·10⁷ | ≈ 1 400 core-years — a large grid year |
| 10¹⁸ | ≈ 1.2·10⁹ | out of reach, and the 128-bit implementation limit |

So **the exhaustive `d`-first search is linear in the size of the target, i.e. exponential
in its number of digits**: each further digit costs ten times more. A large volunteer grid
(say 10⁴ cores running continuously) exhausts the 13-digit band in weeks, the 14-digit band
in months, and stops somewhere around 15–16 digits. Twenty- and thirty-digit certificates
are not reachable by any exhaustive method, now or later; that is a property of the problem,
not of the implementation.

`xscan` has exactly the same exponential-in-digits behaviour, but per `x`: one core covers
a whole 12-digit window of `m` for one value of `x` in 1.3 h, so covering 1 000 values of
`x` to 12 digits costs ≈ 1 300 core-hours, and to 14 digits ≈ 1.3·10⁵ core-hours. It is the
better tool when one is willing to bet on `x` being small (all but two of the eleven known
solutions have `|x| ≤ 10⁸`), and the worse tool otherwise.

### 2.3 What the smooth sweep really covers

`dsmooth` is the only component that *reaches* twenty to thirty digits, and it is cheap:
extrapolating the measured shard, **the entire decade of 60-smooth certificates in
`[10²⁰, 10²¹)` costs about 130 core-hours** — one afternoon on a grid. But the coverage is
correspondingly thin. Counting exactly (this session): there are 1.999·10⁸ integers in
`[10²⁰, 10²¹)` that are 60-smooth and coprime to 6, against 1.5·10²⁰ admissible
certificates in that decade, i.e.

> the 21-digit smooth sweep inspects **1.3·10⁻¹²** of the certificates of that size.

There is a further loss inside the run: 2 008 of the 4 541 smooth certificates of the test
shard (44 %) were *skipped* because `U²` has more than the default 200 000 divisors; raising
`--maxdiv` recovers them at proportionally higher cost, since those are precisely the `U`
with the most divisor pairs.

So A′ should be understood honestly as a **lottery ticket, not a search**: it is a bet that
a solution's certificate happens to be smooth. The only evidence for the bet is that 3 of
the 11 known certificates are smooth (`−5586 = −2·3·7²·19`, one 2 273-smooth, one
2 309-smooth) — but those are *small* certificates, where smoothness is common; at 21 digits
a random certificate is 60-smooth with probability ~10⁻¹². Unless the arithmetic of this
family biases certificates towards smoothness (there is no reason known to me that it
should), the expected yield of the smooth sweep at twenty digits is essentially zero.

### 2.4 What the curve method can and cannot do

Algorithm C is the only formulation with **no bound on `n`**: for a fixed `x` it is complete
in `n`, whereas `xscan` is complete only inside its window. That is its real value —
finishing off a value of `x` once and for all, which is how the earlier runs closed
`|x| ≤ 21 800` for *all* `n`.

It is worth being precise about the amplification claim in `ALGORITHMS.md` §4: the group law
produces points of height 10²⁰ easily, but those are *rational* points, and a solution needs
an **integral** one. By Siegel's theorem each curve has only finitely many integral points,
and multiples `kP` of a generator are almost never integral. The group law therefore does
not manufacture large solutions on demand; what it does is let one enumerate the small
combinations that *could* be integral, and modern integral-point machinery (or a
`ellratpoints`-style search plus a height bound) then settles a given `x` completely.
The cost is dominated by the rank/descent computation, a few seconds to a few minutes per
`x` with `gp`, and it grows roughly with the size of `x` (the conductor involves `x³`), so
one can settle of the order of 10³–10⁴ new values of `x` per core-day — not per core-hour.
This is the only path by which a genuinely 20-digit `n` could realistically appear, and it
appears as a *by-product* of scanning many `x`, not as a targeted computation.

### 2.5 Prospects: will it eventually find a solution?

Combining the above, honestly:

* **Solutions do get found by this pipeline.** Its ancestors produced all eleven known
  solutions, including `(n, x) = (−516368250, 55022141248)` with `d =
  −14123191460839/14966022419456`. Empirically the solutions occur at roughly one or two per
  decade of `|n|`, which is the behaviour one expects of an elliptic surface, so there is
  every reason to believe 10- to 20-digit solutions exist.
* **Complete coverage is affordable only to about 13–15 digits.** Beyond that, all methods
  degrade from "search" to "sampling", and the probability of a hit per core-hour falls off
  a cliff. A grid campaign of 10⁶–10⁷ core-hours is a fair bet for a new solution in the
  10–14 digit range; it is not a plausible route to a 20-digit one in the unrestricted
  problem, let alone in the restricted family.
* **The family restriction costs about a factor 4 in density** (this estimate supersedes the
  "10–40 times rarer" guess made here earlier, see `CONSTRAINTS_TRADEOFF.md`). None of the
  eleven known solutions has `x ≡ 7 (mod 12)` — their `x` are `≡ 0, 3, 4 (mod 12)`. It is now
  *proved* (`DEquation.sat_x_mod_twelve`) that these four classes are the only ones that can
  occur at all, and a measurement of the 2- and 3-adic densities puts them within 2 % of each
  other, so the family should hold about a quarter of all solutions — against which the
  restricted sweep is 16–26× faster at equal reach. On that basis a *family* solution in the
  10–14 digit band is roughly a one-in-four-to-one-in-eight proposition per decade searched.
* **Sharpest way to spend a fixed budget.** (i) `dsweep` to `|U| ≤ 3·10¹³` — this is
  genuinely exhaustive and, by `|n| ≤ |U|`, settles every family solution with a small
  certificate up to 13 digits; (ii) `xscan` over a few thousand `x` for the 10–12 digit `m`
  bands, which is complete in the other direction; (iii) a standing fraction (say 10–20 %) of
  the budget on `xcurve`, pushing `|x|` upward one value at a time, because that is the only
  component whose reach in `n` is unbounded; (iv) `dsmooth` only with spare cycles, and with
  `--maxdiv` raised, understanding it as a lottery. Running a slice in unrestricted mode
  (`dsweep --general`) alongside is advisable: a solution outside the family is still a
  solution of the original equation, and it is 10–40× more likely to turn up.

### 2.6 Summary table

| algorithm | enumerates | complete in | measured rate | reach | blind spot |
|---|---|---|---|---|---|
| A `dsweep` | certificates `U` | everything with `\|U\|` in the interval | 1.8–2.8·10⁹ `U`/core-hour | ≈ 13–15 digits of `n` at grid scale | solutions whose `U` is larger than the sweep (`\|U\|/\|n\|` reaches 10¹³ among known solutions) |
| A′ `dsmooth` | `B`-smooth `U` | smooth certificates only | 4.7·10¹⁰ pairs/core-hour | 20–30 digits, 130 core-hours per decade | 1 − 1.3·10⁻¹² of all certificates; plus 44 % of smooth `U` skipped at default `--maxdiv` |
| B `xscan` | `m` for fixed `x` | `m` inside the window | 7.8·10¹¹ `m`/core-hour per `x` | 12-digit `m` in 1.3 h per `x` | all `x` outside the chosen list |
| C `xcurve` | integral points for fixed `x` | **all `n`**, no bound | 10³–10⁴ values of `x` per core-day | unbounded in `n` | all `x` outside the chosen list; needs rank/descent to succeed |

The four are complementary precisely because their blind spots are disjoint: A is complete
in the certificate, B and C are complete in `n` for the `x` they touch, and A′ trades
completeness for size.
