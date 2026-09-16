

This project was edited by [Aristotle](https://aristotle.harmonic.fun).

To cite Aristotle:
- Tag @Aristotle-Harmonic on GitHub PRs/issues
- Add as co-author to commits:
```
Co-authored-by: Aristotle (Harmonic) <aristotle-harmonic@harmonic.fun>
```
---

# `36n³ - 19 = -2d·x²·(-(x+6n) + √((x+6n)² + (36n³-19)/x))`

Which rational `d` admit integer solutions `(n, x)`?

* `SEARCH_NOTES.md` — the mathematical derivation, the list of admissible `d` found so far
  (eleven values, the largest with a nine-digit `n` and an eleven-digit `x`), the searches
  carried out and what is proved versus computed.
* `RequestProject/Main.lean` — the whole Lean development, in a single self-contained file
  (its only dependency is `Mathlib`, so it can be pasted into an online Lean editor): the
  reduction of the equation to two rational conditions, the perfect-square criterion,
  uniqueness of `d`, effective bounds on `x`, a proof of each of the eleven explicit
  solutions, the computational kernel of the exhaustive check together with the proof that
  every one of its filters and loops is sound, and completeness for `|n| ≤ 100`: the only
  solutions there are `(1,-9)` and `(-54,-9)`, so the only admissible `d` are `-1/54` and
  `1583/54`.  Completeness is proved for a general bound (`sat_exhaustive_of_scan`); running
  the same scan for `N = 1000` (which needs the kernel compiled to native code ahead of time)
  adds `(909,784)` and `(798,-1642284)`, i.e. `d = -414553/43904` and `d = -1/965662992`.
* `ALGORITHMS.md` — the algorithms designed for a large grid (Charity Engine): the d-first
  sweep over the certificate `U = 2dx²`, its smooth-certificate variant, the per-`x` scan
  and the Mordell-curve phase, with their measured throughputs, the work-unit sizing for
  one- to two-hour tasks and the digit-band escalation schedule.
* `grid/` — those programs (`dsweep.c`, `dsmooth.c`, `xscan.c`, `xcurve.gp`, `xcurve.py`),
  the exact verifier `verify.py`, the work-unit generator `make_jobs.py` and the node
  wrapper `run_task.sh`.
* `RequestProject/Algorithm.lean` — the Lean proofs the grid search relies on: correctness
  and completeness of the d-first sweep, the bound `|n| ≤ |U|` that calibrates the digit
  bands, the `mod 12` sieve for `x = 12u+7`, and the Mordell-curve correspondence.
* `search/` — the C and Python search programs of the earlier runs and their logs.
# Searching for rational `d`: algorithms for a large grid

Target equation, with `n, x` integers and `d` rational:

```
36 n³ − 19 = −2 d x² ( −(x + 6n) + √( (x + 6n)² + (36n³ − 19)/x ) )        (E)
```

and the family asked for: `n = 3m`, `x = 12u + 7`.

This note describes the algorithms, why they are the right ones, what each of them costs,
how the work is cut into one‑ to two‑hour tasks, and — honestly — how far each of them can
reach.  The programs are in [`grid/`](grid/); the mathematical facts they rely on are
proved in Lean in [`RequestProject/Algorithm.lean`](https://github.com/JAgbanwa/SomethingNew/blob/main/114%20/Algorithm%20for%20computation%20/RequestProject%20/Algorithm.lean) and
[`RequestProject/Main.lean`](https://github.com/JAgbanwa/SomethingNew/blob/main/114%20/Algorithm%20for%20computation%20/RequestProject%20/Main.lean), so the search can be trusted not to
miss solutions inside the range it claims to cover.

---

## 1. What "searching for `d`" means

`d` is *not* an independent unknown: for a given pair `(n, x)` with `x ≠ 0`, equation (E)
has a solution `d` if and only if

```
x²(x + 6n)² + x(36n³ − 19)   is a perfect square,                          (⋆)
```

and then `d` is **unique** (`DEquation.exists_d_iff`, `DEquation.sat_unique`).  So a search
"over `d`" has to be a search over a parameter that determines `d` and lets `n` or `x` be
*solved for* rather than enumerated.  That parameter is

```
U = 2 d x²   —   always an integer   (`DEquation.sat_iff_exists_U`),
```

the numerator of `d = U / (2x²)`.  In terms of `U` equation (E) becomes purely integral:

```
U² + 2 U x (x + 6n) = x (36 n³ − 19).                                      (★)
```

Three facts make `U` the right thing to enumerate (all proved):

| fact | statement | consequence for the search |
|---|---|---|
| `DEquation.sat_U_dvd` | `x ∣ U²` | for a given `U`, only the divisors of `U²` can be `x` |
| `DEquation.cubic_in_n` | writing `U² = c·x`, (★) is `36n³ − 12Un = c + 2Ux + 19` | `n` is **solved** by one cube root, not enumerated |
| `DEquation.abs_n_le_abs_U` | `\|n\| ≤ \|U\|` | a `D`-digit `n` needs a `D`-digit certificate `U` |

and, for the requested family,

| `DEquation.sat_U_mod_twelve` | `x ≡ 7 (mod 12)` forces `U ≡ 5` or `11 (mod 12)` | 10 of every 12 values of `U` are skipped; `U` is then coprime to 6, so all divisors of `U²` are automatically coprime to 6, as `x` must be |

The extra condition `n = 3m` turns out to cost nothing and to add nothing to the sieve, so
the sweep accepts every `n` and the verifier reports which hits have `3 ∣ n`.

The whole of Algorithm A below is exactly the statement

```
DEquation.sat_iff_dSweep :
  Sat d n x  ↔  ∃ U c, U = 2dx²  ∧  U² = c·x  ∧  36n³ − 12Un = c + 2Ux + 19
                       ∧  (U + x(x+6n))·x ≤ 0
```

read as a program: enumerate `U`, enumerate `x ∣ U²`, solve the cubic, check the branch.

---

## 2. Algorithm A — the d‑first sweep (`grid/dsweep.c`)

```
for each |U| in the work unit’s interval, with U ≡ 5 or 11 (mod 12):
    factor U                                  (segmented sieve + Pollard rho)
    for each divisor D of U² with ±D ≡ 7 (mod 12):
        x  = ±D                               (the sign is forced mod 12)
        c  = U²/x                             (exact: x | U²)
        K  = c + 2Ux + 19
        solve 36 n³ − 12 U n = K for a real root, round it, and test the
        three neighbours exactly                → report (U, x, n)
```

*Cost.* One value of `U` costs an amortised factorisation plus about five divisor
candidates, each a cube root and a couple of 128‑bit operations.  Measured on one core:

| `|U|` | values of `U` per core‑hour |
|---|---|
| 10⁹ | 2.4 × 10⁹ |
| 10¹² | 1.9 × 10⁹ |
| 10¹⁴ | 1.6 × 10⁹ |

(Each `(U, x)` pair is first passed through a one‑sided modular filter — `K = c + 2Ux + 19`
must lie in the image of `t ↦ 36t³ − 12Ut` modulo `7, 13, 19, 31, 37, 43`, which rejects
about 94 % of the pairs at a fraction of the cost of the cube root, and can never reject a
genuine solution.)

*Completeness.* Everything with `|U|` in the swept interval is found — including solutions
with an arbitrarily large `x` — and nothing else is produced.  This is the theorem
`sat_iff_dSweep` above; the floating‑point root finding and the two 61‑bit modular tests
are only filters, and every hit is re‑checked exactly by `grid/verify.py`.

*Reach.* `|n| ≤ |U|` is a theorem, so this algorithm can never produce an `n` larger than
the largest `|U|` it sweeps: reaching a `D`-digit `m` requires sweeping `|U| ≥ 3·10^{D−1}`.
That is the honest statement of what the d‑first search can and cannot do — see the budget
table in §5.

*Validation.* Run in unrestricted mode (`--general`) over `|U| ≤ 2·10⁴`, it re‑discovers
the three smallest known solutions, `d = −1/54` at `(n,x) = (1,−9)`, `d = 1583/54` at
`(−54,−9)` and `d = −1/965662992` at `(798,−1642284)` — the last one has a seven‑digit `x`
although its certificate is only `U = −5586`, which illustrates why sweeping `U` is much
better than sweeping `x`.

---

## 2b. Algorithm A′ — smooth certificates (`grid/dsmooth.c`)

Algorithm A is exhaustive but, by `|n| ≤ |U|`, it cannot get past about thirteen digits on
a realistic budget: there are simply too many `U`.  Algorithm A′ keeps the same inner loop
and enumerates only the `U` that are **`B`‑smooth** (every prime factor `≤ B`).  Those can
be listed directly, in factored form, for `U` of twenty, thirty or more digits — the count
of `B`‑smooth numbers below `10^k` is smaller than `10^k` by many orders of magnitude — and
they are exactly the `U` that have the *most* divisors, i.e. the most candidate `x` per unit
of work.

Why this is a sensible bet rather than an arbitrary restriction: among the eleven
certificates known for this equation,

```
U = −5586 = −2·3·7²·19,     U = −335124555576  (2273‑smooth),
U = −665761661810070  (sixteen digits, 2309‑smooth)
```

are smooth, i.e. roughly a third of the known solutions would have been caught by a smooth
sweep, at a cost far below that of the exhaustive one.  A solution whose certificate has a
large prime factor is invisible to A′ — that is the price, and it is why A and A′ should
both be run.

Implementation: the `B`‑smooth `U` in a box `[lo, hi)` are produced by a depth‑first
product enumeration (so their factorisation is free), work is split into independent shards
by a counter, the divisor pairs `(x, c = U²/x)` are built multiplicatively so that `U²` is
never formed, the same modular pre‑filter is applied, and the cubic is solved in
`__float128` (113‑bit mantissa: enough to pin `n` to within one unit for `n` beyond 10³⁰)
and confirmed modulo two 61‑bit primes.  Measured: about 7 × 10⁵ pairs per second, i.e.
2.5 × 10⁹ pairs per core‑hour; with `B = 60` a twenty‑digit `U` offers some 10⁴ divisor
pairs each.

Validation: run with `--test` (which drops the family restrictions) over `|U| ≤ 2·10⁴`, it
reproduces exactly the same five certificates as `dsweep --general`, through a completely
different enumeration and a different floating point path.

---

## 3. Algorithm B — the per‑`x` scan (`grid/xscan.c`)

For a *fixed* `x`, (⋆) says that

```
F_x(n) = x²(x + 6n)² + x(36n³ − 19)
```

must be a perfect square.  `F_x` is a cubic in `n`, so this is an elliptic curve; a work
unit fixes a block of `x = 12u+7` and a window of `m` (with `n = 3m`) and filters the
window by the condition that `F_x(3m)` is a quadratic residue modulo forty primes.  The
first six primes are applied through a precomputed bit wheel of modulus
`5·7·11·13·17·19 = 1616615` (one bit test per `m`), the remaining thirty‑four only to the
survivors; the amortised cost is about one memory access per value of `m`, and what comes
out (expected: nothing spurious in 10¹⁰ work units) is confirmed exactly by
`verify.py --nx`.

Measured: **5.4 × 10¹¹ values of `m` per core‑hour and per `x`** — i.e. one core covers the
whole 10‑digit band for ninety values of `x` in 1.5 h, or the whole 12‑digit band for one
value of `x` in about 1.5 h.

This unit type is *complete in `m`* inside its window: if the requested family has a
solution with a 10‑, 11‑ or 12‑digit `m` and a small `u`, this is the unit type that will
find it.

---

## 4. Algorithm C — the Mordell curve of `x` (`grid/xcurve.gp`, `grid/xcurve.py`)

The same fixed‑`x` problem, written as an elliptic curve in Weierstrass form
(`DEquation.mordell_of_sat`, proved as an algebraic identity):

```
V² = Z³ − 432 x³ (x³ + 57),      Z = 12x(3n + x),   V = 36xY,
```

with `Y² = F_x(n)`, and conversely (`DEquation.sat_of_mordell`) every integral point of
that shape yields a genuine solution and the explicit value
`d = (Y − x(x+6n)) / (2x²)`.

This is the only view of the problem that is **not bounded in `n`**: rational points form a
group, and the naive height multiplies by `k²` under `P ↦ kP`, so a generator of height
10⁵ already produces points of height 10²⁰ at its fourth multiple.  A work unit therefore

1. computes the rank / some generators of `E_x` (PARI/GP `ellrank`, `ellratpoints`, or a
   brute‑force point search in the Python reference implementation),
2. walks through small linear combinations `aP + bQ + …` of the generators,
3. keeps those whose `Z` is `≡ 12x² (mod 36x)` and whose `V` is divisible by `36x`; these
   are exactly the ones that come from an integer `n`.

Measured on the known data: the Python reference implementation reproduces the Mordell
point, the recovery map and the group law for all eleven known solutions
(`./xcurve.py --selftest`).  Throughput depends on the rank and is best measured on the
grid itself; a block of 64 values of `u` per work unit is a reasonable starting point.

**This is where the 10–20 digit and 20–30 digit bands have to come from.**  No uniform
search — over `n`, over `x`, or over `U` — can cover 10²⁰ candidates; the group law is the
only mechanism that produces solutions of that size from computations of moderate size.

---

## 5. What to run, in what order: the digit‑band escalation

Band `D` = the targets with a `D`-digit `m`.  Work units are sized for 1.5 core‑hours.

| band `D` (digits of `m`) | A: `dsweep` over `|U| ∈ [3·10^{D−1}, 3·10^{D+1})` | B: `xscan`, whole band, per `x` | C: `xcurve` |
|---|---|---|---|
| 10 | 200 units | 90 values of `x` per unit | any number of units, 64 `x` each |
| 11 | 2 000 units | 9 values of `x` per unit | " |
| 12 | 20 000 units | 1 value of `x` per unit | " |
| 13 | 2 × 10⁵ units | 11 units per `x` | " |
| 14 | 2 × 10⁶ units | 110 units per `x` | " |
| 15 | 2 × 10⁷ units | 1 100 units per `x` | " |
| 16–19 | 10⁸ … 10¹¹ units (out of reach) | 10⁴ … 10⁷ units per `x` | " |
| 20–30 | out of reach exhaustively; use A′ (`dsmooth`) instead | out of reach | " |

Recommended schedule, exactly in the escalating form asked for:

1. **Band 10–12 first.**  Issue the `dsweep` units for `|U| ≤ 3·10¹³` (≈ 22 000 units,
   ≈ 33 000 core‑hours) *together with* `xscan` units covering bands 10–12 completely for
   the first few thousand values of `u` (one unit covers 90 `x` at 10 digits).  Everything
   in that range is then genuinely exhausted from two independent directions.
2. **If nothing is found, band 13–15.**  The `dsweep` side becomes the dominant cost
   (2 × 10⁵ … 2 × 10⁷ units); the `xscan` side stays affordable if the list of `x` is kept
   short (a few hundred).  Run both, plus a growing number of `xcurve` units.
3. **From band 16 on: A′ and C.**  Exhaustive sweeps stop here.  Issue `dsmooth` units for
   the box `[3·10¹⁵, 3·10²⁰)` with `B = 60`, then `[3·10²⁰, 3·10³⁰)` with `B = 40…60` —
   these are the units that can actually return a twenty‑ or thirty‑digit `(m, u)` — and at
   the same time shift a growing share of the budget to Algorithm C: many values of `u`,
   deeper rank computations, larger multiples `kP`.  A 20‑digit solution, if one exists in
   this family, will come out of a smooth certificate or a curve of positive rank, not out
   of an exhaustive sweep.

Every unit is independent, takes its whole input from its command line, writes one output
file, and can be re‑issued or duplicated for validation; see `grid/README.md` for the
manifest format and the wrapper script.

---

## 6. Expected yield — an honest estimate

* The eleven solutions known so far have `|n| = 1, 54, 798, 909, 14709, 29317, 1.2·10⁶,
  1.3·10⁷, 6.5·10⁷, 1.0·10⁸, 5.2·10⁸`: roughly **one or two per decade of `|n|`**, which is
  the behaviour expected of an elliptic surface.  There is therefore every reason to
  believe that solutions with 10‑ to 20‑digit `n` exist; the difficulty is entirely one of
  finding them.
* **None of the eleven is in the requested family**: their `x` are `≡ 0, 3, 4 (mod 12)`,
  never `7`; in particular every known `x` is divisible by 2 or by 3, while `x = 12u+7` is
  coprime to 6.  There is no local obstruction to the family (the congruences are solvable
  modulo every prime power tested), but restricting to it plausibly costs a factor of
  around 10–40 in the density of solutions.  It is worth running a fraction of the grid
  budget in the unrestricted mode (`dsweep --general`) alongside the family search.
* The certificate ratios `|U|/|n|` of the known solutions range from 3 to 10¹³.  A sweep of
  `|U|` up to `3·10^{D+1}` therefore catches band `D` solutions whose `d` has a "small"
  numerator, which is precisely the kind of `d` the question asks for, but not those with a
  very large one; the per‑`x` and curve units are the complement that has no such bias.
* Searches already performed (this project): all `|n| ≤ 8·10⁹` with *every* `x`
  (divisor method, earlier runs), all `|x| ≤ 21800` with every `n` (curve method, earlier
  runs), and now, with `x ≡ 7 (mod 12)`: all certificates `|U| < 2·10¹⁰` (the exhaustive
  d‑first sweep) and all 50‑smooth certificates with `10¹⁰ ≤ |U| < 10¹⁸` (the smooth sweep),
  together about 5·10¹¹ pairs `(U, x)`.  No solution of the family has appeared yet.

---

## 7. Summary of the proved ingredients

| Lean name | role in the algorithms |
|---|---|
| `DEquation.sat_iff` / `sat_iff_e` | (E) ⇔ two rational conditions |
| `DEquation.exists_d_iff`, `sat_unique` | `(n,x)` admits a `d` iff (⋆); `d` is then unique |
| `DEquation.sat_iff_exists_U`, `sat_of_U` | the integral certificate `U = 2dx²` |
| `DEquation.sat_U_dvd`, `sat_abs_x_le_U_sq` | `x ∣ U²`, `\|x\| ≤ U²` — the divisor loop |
| `DEquation.cubic_in_n`, `eq_of_cubic_in_n` | the cubic that is solved for `n` |
| `DEquation.sat_iff_dSweep` | soundness **and** completeness of Algorithms A and A′ |
| `DEquation.abs_n_le_abs_U` | `\|n\| ≤ \|U\|` — the digit‑band calibration |
| `DEquation.sat_U_mod_twelve` | the `mod 12` sieve for `x = 12u+7` |
| `DEquation.mordell_of_sat`, `sat_of_mordell` | the Mordell curve view and the map back to `d` |
| `DEquation.sat_abs_x_le_poly`, `sat_x_finite` | `\|x\| ≤ 24\|n\| + 14n² + 100`: finiteness for fixed `n` |
