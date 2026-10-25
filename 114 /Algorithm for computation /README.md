

This project was edited by [Aristotle](https://aristotle.harmonic.fun).

To cite Aristotle:
- Tag @Aristotle-Harmonic on GitHub PRs/issues
- Add as co-author to commits:
```
Co-authored-by: Aristotle (Harmonic) <aristotle-harmonic@harmonic.fun>
```
---

# `36n³ - 19 = -2d·x²·(-(x+6n) + √((x+6n)² + (36n³-19)/x))`

Which rational `d` admit integer solutions `(n, x)`?  Most ideally with an **integral**
square root — and, as a second case, with `x = X/2` and `√(…) = Y/2` for odd `X`, `Y` (the
*half chart*).

> **Update (October 2026) — the half chart and integral radicals.**  Every program in
> `grid/` now runs in two charts — the integer chart (`x` an integer, Aristotle's setting)
> and the half chart (`x = X/2`, `X` odd, flag `--half`, certificate `V = dX²`) — and for two
> targets: any rational square root, or an *integral* one (`y` an integer, resp. `y = Y/2`
> with `Y` odd).  The integral solutions are exactly the representations
> `114 = A³+B³+C³` with `A = −x+y`, `B = −x−y`, `C = 2x+6n`: each representation gives one
> integer-chart and two half-chart solutions, and Aristotle's family `n = 3m, x = 12u+7` is
> precisely the integer chart's forced congruence.  Because Booker–Sutherland have excluded
> every representation of 114 with `min(|A|,|B|,|C|) ≤ 10¹⁷`, an integral solution needs
> `|n| ≥ 9.8·10¹⁵` and a ≥ 25-digit certificate, out of reach of the certificate sweeps; a new
> engine, `grid/xroots.c` (Algorithm D, §2c), searches it by cube roots modulo `X`.  The
> half chart also has rational-radical solutions, e.g. `d = −142/4913` at `(n, x) =
> (15, −289/2)` and `d = −9671/625` at `(114, 125/2)`.  Details and proofs:
> [`HALF_INTEGER.md`](https://github.com/JAgbanwa/SomethingNew/blob/main/114%20/Algorithm%20for%20computation%20/HALF_INTEGER.md);
> runs: `search/run9/`.  Also fixed along the way: `dsmooth` silently capped `--B` at 3671,
> `xscan` covered only `x > 0, n ≥ 0`, `xcurve.gp` defaulted `KMAX` to 0, and `dsweep` is
> 1.5× faster.

* `HALF_INTEGER.md` — **new**: the half chart (`x = X/2`), the certificate `V = dX²` and its
  cubic, the equivalence of integral radicals (in either chart) with `114 = A³+B³+C³`, the
  2‑/3‑adic congruences of both charts, what the Booker–Sutherland searches already exclude,
  and Algorithm D with its measured throughput.
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
* The section *Searching for rational `d`* below (formerly referred to as `ALGORITHMS.md`,
  which is not a separate file) — the algorithms designed for a large grid (Charity Engine):
  the d-first sweep over the certificate `U = 2dx²` (or `V = dX²`), its smooth-certificate
  variant, the cube-root engine for integral radicals, the per-`x` scan and the
  Mordell-curve phase, with their measured throughputs, the work-unit sizing for one- to
  two-hour tasks and the escalation schedules.
* `grid/` — those programs (`dsweep.c`, `dsmooth.c`, `xroots.c`, `xscan.c`, `xcurve.gp`,
  `xcurve.py`), the shared filters `filter.h` and `local.h`, the exact verifier `verify.py`,
  the work-unit generator `make_jobs.py`, the node wrapper `run_task.sh`, and the tests
  `selftest.sh` / `validate.py` (`make test`).  See `grid/README.md`.
* `HOW_IT_WORKS.md` — how the search works and how efficient it is (with an addendum on the
  half chart and Algorithm D).
* `RequestProject/Algorithm.lean` — the Lean proofs the grid search relies on: correctness
  and completeness of the d-first sweep, the bound `|n| ≤ |U|` that calibrates the digit
  bands, the `mod 12` sieve for `x = 12u+7`, and the Mordell-curve correspondence.
* `search/` — the C and Python search programs of the earlier runs and their logs;
  `search/run9/` holds the runs of the half-chart / integral-radical session.

# Searching for rational `d`: algorithms for a large grid

Target equation, with `n, x` integers and `d` rational:

```
36 n³ − 19 = −2 d x² ( −(x + 6n) + √( (x + 6n)² + (36n³ − 19)/x ) )        (E)
```

and the family asked for: `n = 3m`, `x = 12u + 7`.  Since the update, also the **half
chart** `x = X/2` with `X` odd, and the **integral** target in which the square root is an
integer (integer chart) or `Y/2` with `Y` odd (half chart); the family above is exactly the
set of congruences forced on an integral integer-chart solution (§1, `HALF_INTEGER.md` §3).

This note describes the algorithms, why they are the right ones, what each of them costs,
how the work is cut into one‑ to two‑hour tasks, and — honestly — how far each of them can
reach.  The programs are in [`grid/`](https://github.com/JAgbanwa/SomethingNew/tree/main/114%20/Algorithm%20for%20computation%20/grid%20); the mathematical facts they rely on are
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

**The half chart** (`x = X/2`, `X` odd; `HALF_INTEGER.md` §1).  `DEquation.sat_iff` does not
use that `x` is an integer, and with `V = dX²` it gives

```
V² + V X (X + 12n) = 2X (36n³ − 19),    (2V + X(X+12n))·X ≤ 0,                   (★½)
```

so `V` is always an integer (a root of a monic integer quadratic), `X ∣ V²`, and with
`V² = c·X` the cubic is `72n³ − 12Vn = c + VX + 38`; again `|n| ≤ |V|`.  Every d‑first
program runs in this chart with `--half` (output lines `HHIT V X n`); `d = V/X²`.

**Integral radicals.**  The square root is `y = −(x + 6n + 2dx)` and `2dx = U/x = V/X`, so
`y` is an integer (integer chart) iff `x ∣ U`, and `y = Y/2` with `Y` odd (half chart) iff
`X ∣ V`.  In that case only the divisors of `|U|` (resp. `|V|`) — not of `U²` — need to be
tried (`--integral`; the default in the half chart).  With `A = −x+y`, `B = −x−y`,
`C = 2x+6n` one has identically `A³+B³+C³ − 114 = −6x(y² − (x+6n)² − (36n³−19)/x)`, so these
are exactly the representations of 114 as a sum of three cubes; the chart is the parity of
`A+B = −2x`.  For them the 2‑ and 3‑adic conditions are computed exactly (`grid/local.h`):
integer chart `x ≡ 7 (mod 12)`, `n ≡ 0 (mod 3)`, `U ≡ 5, 11 (mod 12)` (the requested family
and `sat_U_mod_twelve`), plus joint conditions on `(x mod 16, n mod 4)` and
`(x mod 243, n mod 243)`; half chart `X ≡ 5, 11 (mod 12)`, `n ≡ 0 (mod 3)`, `V ≡ 1, 10
(mod 12)`.

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

| `\|U\|` | values of `U` per core‑hour |
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

*Half chart and integral radicals.*  `--half` sweeps `|V|` with the cubic of (★½) over the
odd divisors of `V²` (`--rational-sqrt`) or of `V` (integral, the default there);
`--integral` does the same in the integer chart; `--K k` replaces 19 by `k` for validation.
Re-measured on this session's machine (about 1.6× slower than Aristotle's): the original
mode now runs at 2.5·10⁹ `|U|` per core‑hour at `|U| ~ 10⁹`, 1.5× faster than before on the
same machine (a cofactor left prime by the sieve is no longer re-tested by Miller–Rabin);
the integral modes at 3.4–3.6·10⁹ `|G|` per core‑hour; `--half --rational-sqrt` (no family
restriction is known there) at 2.5·10⁸ `|V|` per core‑hour at `|V| ~ 10⁸`.  Validation:
`--half --rational-sqrt` over `|V| < 2.5·10⁵` returns exactly the two half-chart solutions
that a brute force over `|n| ≤ 300`, odd `|X| ≤ 4·10⁵` finds (§6), and `--integral` finds
every known certificate on equations with known integral solutions (`grid/validate.py`).
For `K = 19` an integral certificate has at least 25 digits (`HALF_INTEGER.md` §5), so
`dsweep` cannot meet one; integral solutions are the job of Algorithm D.

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
different enumeration and a different floating point path.  (Correction: the original
program kept only the first 512 primes, so `--B 20000` really meant `B = 3671`; in this
validation it skipped 15 % of the certificates.  It now honours any `B`, and the pair count
matches `dsweep --general` exactly.  Production runs with `B = 60` were not affected.)
`dsmooth` takes the same `--half`, `--integral`, `--rational-sqrt`, `--K` flags as `dsweep`.

---

## 2c. Algorithm D — integral radicals by cube roots (`grid/xroots.c`, new)

For an integral radical, `X ∣ 36n³ − 19` in both charts (integer chart: `y² − (x+6n)² =
(36n³−19)/x` must be an integer; half chart: `Y² − (X+12n)² = 8(36n³−19)/X`, `X` odd).
So for a fixed `X` the admissible `n` lie in the classes `n ≡ r (mod |X|)` with
`36r³ ≡ 19` — about one class on average instead of all `|X|` — and only there is
`(x+6n)² + (36n³−19)/x` (resp. `(X+12n)² + 8(36n³−19)/X`) tested for being a square.  This is
the Booker–Sutherland algorithm written in the coordinates of (E): their `d = |x+y|` is our
pair sum `|A+B|` (= `|X|` in the half chart, `2|x|` in the integer chart; odd ↔ half chart)
and their `z` is our `C = X + 6n` (resp. `2x + 6n`).  The search fixes the denominator side
of `d = (A+C)/(A+B)` and solves for the rest.

```
for each |X| in the unit's range (both signs), factored by a segmented sieve:
    roots r of 36 r³ ≡ 19 modulo each prime power of X, combined by the CRT
    fold in the 2-adic / 3-adic classes of n allowed for this X (local.h), by the CRT
    for each progression n ≡ ρ (mod |X|·L) inside the window of n:
        wheel over t mod 5005 (primes 5, 7, 11, 13), jump between passing positions,
        residues mod 17 … 29 carried along, then 70 more primes on demand
        → "ICAND chart X n", confirmed exactly by verify.py (prints d, y and (A, B, C))
```

A work unit is a range of `|X|` times a window of `n` (128‑bit), and it is **complete** for
that box.  Validation (`grid/validate.py`): identical output to an independent brute force on
boxes `|X| < 1200`, `|n| < 4·10⁵` for six values of `K` with known representations, in both
charts and through all three inner loops; and the Booker–Sutherland solutions of `42` and
`906` are found in all three of their charts at sixteen‑digit `n`.  Throughput at
`n ≈ 2·10¹⁸`, window 10¹⁰, one core: half chart `|X| < 10³` in 5.2 s (3·10⁹ `n` tested,
1.7 ns each), `[10³, 10⁵)` in 5.6 s, `[10⁵, 10⁶)` in 10.5 s; integer chart 0.5, 2.2, 5.2 s.

Where to point it: for small `|X|` the Booker–Sutherland searches stop at `|C| = 10¹⁹`, i.e.
`|n| = 1.667·10¹⁸`.  `make_jobs.py --target integral` tiles `|X| < 10⁶`,
`1.667·10¹⁸ ≤ |n| < 1.667·10¹⁹` (both signs, both charts) into 1.5‑hour units, epoch by
epoch; the whole box is about `9.5·10⁶` core‑hours, 90 % of it in the half chart.

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

Since the update: `--half` scans `X = 6u+5` with `F_X(n) = X²(X+12n)² + 8X(36n³−19)`;
`--xneg` / `--nneg` scan `x = −(12u+5)` (resp. `X = −(6u+1)`) and `n = −3m` — the original
covered only `x > 0` and `n ≥ 0`, although the known solutions have every sign pattern
(`make_jobs.py --signs all`, the default, issues all four).  For an *integral* radical
Algorithm D is the right tool: it visits about one `n` in `|x|` instead of all.

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
(`HOW_IT_WORKS.md` §2.4 qualifies this: only *integral* points give solutions, and multiples
`kP` are almost never integral.)

Half chart: the curve is `V² = Z³ − 432X³(X³ + 456)` with `Z = 12X(6n + X)`, `V = 36X·W`,
`W² = X²(X+12n)² + 8X(36n³−19)` — the integer-chart curve at `x = X/2` after
`(Z, V) → (4Z, 8V)`.  `xcurve.py --half`, `XCURVE_HALF=1 gp -q xcurve.gp`; the self test now
checks 14 solutions in both charts, including the integral one coming from 42.

---

## 5. What to run, in what order: the digit‑band escalation

Band `D` = the targets with a `D`-digit `m`.  Work units are sized for 1.5 core‑hours.

| band `D` (digits of `m`) | A: `dsweep` over `\|U\| ∈ [3·10^{D−1}, 3·10^{D+1})` | B: `xscan`, whole band, per `x` | C: `xcurve` |
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

**The same plan in the half chart** (rational radicals): `make_jobs.py --chart half` (or
`--chart both`) issues `dsweep --half --rational-sqrt`, `xscan --half`, `dsmooth --half
--rational-sqrt` and `xcurve --half` units over the same bands; `|n| ≤ |V|` calibrates them
exactly as `|n| ≤ |U|` does in the integer chart.

**The integral target** (the square root an integer, resp. `Y/2`, i.e. 114 = A³+B³+C³):

1. Nothing below `|n| ≈ 10¹⁶` is worth searching — Booker–Sutherland's complete search
   (`min(|A|,|B|,|C|) ≤ 10¹⁷`) already covers it (`HALF_INTEGER.md` §5).
2. `make_jobs.py --target integral` (Algorithm D, both charts): `|X| < 10⁶` and
   `1.667·10¹⁸ ≤ |n| < 1.667·10¹⁹`, the first decade beyond their 2020 search for small pair
   sums, about `9.5·10⁶` core‑hours in 1.5‑hour units; a prefix of the manifest is always a
   complete box.  Raise `--x-max` or move the `n` window outward as budget allows.
3. `dsmooth --integral` (either chart) for 25–35 digit smooth certificates only with spare
   cycles: a lottery, as in the rational case.

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
  *Why the family looks empty:* `n = 3m, x = 12u+7` is exactly the set of congruences
  forced on a solution whose square root is an integer, and such a solution is a
  representation of 114 as a sum of three cubes — of which none is known.  All eleven known
  solutions have a non-integral rational square root (`y = 8/3` at `(1, −9)`, for instance).
  Within the family a rational-radical solution is still possible, but the family no longer
  has any special status for it.
* **Integral radicals (either chart).**  Every representation of 114 gives one
  integer-chart and two half-chart solutions; Booker–Sutherland exclude all with
  `min(|A|,|B|,|C|) ≤ 10¹⁷`, so `|n| ≥ 9.8·10¹⁵` and the certificate has ≥ 25 digits.
  Heuristically 114 does have representations (Heath-Brown's conjecture predicts infinitely
  many for every `k ≢ ±4 mod 9`, their number up to height `B` growing like `c_k·log B`), but
  they are sparse, so a hit in any finite campaign remains a lottery.
* The certificate ratios `|U|/|n|` of the known solutions range from 3 to 10¹³.  A sweep of
  `|U|` up to `3·10^{D+1}` therefore catches band `D` solutions whose `d` has a "small"
  numerator, which is precisely the kind of `d` the question asks for, but not those with a
  very large one; the per‑`x` and curve units are the complement that has no such bias.
* Searches already performed (this project): all `|n| ≤ 8·10⁹` with *every* `x`
  (divisor method, earlier runs), all `|x| ≤ 21800` with every `n` (curve method, earlier
  runs), and now, with `x ≡ 7 (mod 12)`: all certificates `|U| < 2·10¹⁰` (the exhaustive
  d‑first sweep) and all 50‑smooth certificates with `10¹⁰ ≤ |U| < 10¹⁸` (the smooth sweep),
  together about 5·10¹¹ pairs `(U, x)`.  No solution of the family has appeared yet.
  Half chart / integral target (`search/run9/`): see the README there.

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

Used by the half-chart and integral modes — elementary algebra and finite residue
enumeration, checked symbolically (sympy), by `grid/local.h` and by `grid/validate.py`, **not
yet formalised in Lean** (suggested statements in `HALF_INTEGER.md` §7):

| statement | role |
|---|---|
| (★½) with `V = dX²` integral, `X ∣ V²`, `72n³ − 12Vn = c + VX + 38`, `\|n\| ≤ \|V\|` | Algorithms A, A′ in the half chart |
| `A³+B³+C³ − 114 = −6x(y² − (x+6n)² − (36n³−19)/x)`, `A = −x+y`, `B = −x−y`, `C = 2x+6n` | integral radicals ⇔ representations of 114 |
| integral ⇔ `x ∣ U` (integer chart) ⇔ `X ∣ V` (half chart) ⇒ `X ∣ 36n³ − 19` | `--integral`; the cube-root classes of Algorithm D |
| the 2‑/3‑adic tables of `local.h` (e.g. `x ≡ 7`, `X ≡ 5, 11`, `V ≡ 1, 10 (mod 12)`, `n ≡ 0 (mod 3)`) | sieves of the integral modes |
| `V² = Z³ − 432X³(X³+456)`, `Z = 12X(6n+X)`, `V = 36X·W` | Algorithm C in the half chart |
