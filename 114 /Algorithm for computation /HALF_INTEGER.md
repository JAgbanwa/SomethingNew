# The half-integer chart and integral radicals

This note adds to the search for rational `d` the case requested after Aristotle's runs:

> at a given rational `d`, `x = X/2` with `X` odd and `√((x+6n)² + (36n³−19)/x) = Y/2` with `Y` odd,

and explains how it relates to the integer case that Aristotle's programs search, what it
means for the problem, and which algorithm is the right one for it.  Throughout, `K = 19`
is the constant of the original equation; the programs take `--K k` so that everything can
be validated on equations whose solutions are known.

```
36n³ − K = −2d·x²·( −(x+6n) + y ),      y = √( (x+6n)² + (36n³−K)/x ) ≥ 0,      n ∈ ℤ.     (E_K)
```

## 0. Summary

* **Two charts.** *Integer chart*: `x` an integer (Aristotle's setting).  *Half chart*: `x = X/2`,
  `X` odd (new).  In both, `d` is determined by `(n, x)` and has an **integral certificate**:
  `U = 2dx²` in the integer chart, `V = dX²` in the half chart.
* **The half chart has the same algebra as the integer chart**: `V² + VX(X+12n) = 2X(36n³−K)`,
  `X | V²`, a cubic in `n` once `(V, X)` is fixed, `|n| ≤ |V|` — so every d-first program
  (`dsweep`, `dsmooth`) runs in it unchanged apart from constants (`--half`).
* **Integral radicals are sums of three cubes.**  With `A = −x+y`, `B = −x−y`, `C = 2x+6n`,
  `A³+B³+C³ − 6K = −6x·(y² − (x+6n)² − (36n³−K)/x)` identically.  So a solution with `y`
  an integer (integer chart) or `y = Y/2`, `Y` odd (half chart) is exactly an integer
  representation `6K = A³+B³+C³` with `A+B+C = 6n` — for `K = 19`, of **114**.  The chart
  is the parity of the pair sum `A+B = −2x`: even → integer chart, odd → half chart.  Every
  representation of 114 gives **one integer-chart and two half-chart solutions**, all with
  the same `n = (A+B+C)/6`, and `d = (A+C)/(A+B)`.
* **Aristotle's family is the integer-chart congruence of 114.**  `n = 3m, x = 12u+7` are
  precisely the conditions every integral integer-chart solution must satisfy (and for
  `K = 65`, i.e. 390, the same computation gives `n ≡ 1 (mod 3)`, `x ≡ 5 (mod 12)`).  The
  half-chart analogue is `n ≡ 0 (mod 3)`, `X ≡ 5 or 11 (mod 12)`, `V ≡ 1 or 10 (mod 12)`.
* **What is already known.**  Booker and Sutherland's search excludes every representation of
  114 with `min(|A|,|B|,|C|) ≤ 10¹⁷` (conditionally on error-free computation).  This forces
  `|n| ≥ 9.8·10¹⁵` and certificates of at least 25 digits for any integral solution, so the
  certificate sweeps cannot reach one; the right tool is a new per-`X` **cube-root** engine,
  `grid/xroots.c` (Algorithm D), which works in both charts.
* **Rational radicals in the half chart** exist and are found by `dsweep --half
  --rational-sqrt`: `d = −142/4913` at `(n, x) = (15, −289/2)` and `d = −9671/625` at
  `(n, x) = (114, 125/2)` are the only two with `|V| < 10⁸` (`search/run9/`).

## 1. The half chart

Write `x = X/2` with `X` odd.  Aristotle's reduction `DEquation.sat_iff` does not use that
`x` is an integer: (E_K) is equivalent to

```
36n³ − K = 4d²x³ + 4dx³ + 24dnx²,      2dx + x + 6n ≤ 0.
```

Put `V = dX²` (so `d = V/X²`).  Substituting `x = X/2` and multiplying by `2X`:

```
V² + V·X·(X+12n) = 2X·(36n³ − K),       (2V + X(X+12n))·X ≤ 0.                  (H)
```

* `V` is a rational root of the monic integer polynomial `t² + X(X+12n)t − 2X(36n³−K)`, hence
  an **integer**.
* From (H), `X | V²`; writing `V² = cX`,

  ```
  72n³ − 12Vn = c + VX + 2K,                                                    (H′)
  ```

  a cubic in `n` alone, so for a given `(V, X)` the `n` is *solved* (cube root), not
  enumerated — exactly as for `U` in the integer chart.
* The radical is `y = −(X² + 12nX + 2V)/(2X)`, and `d = −(y + x + 6n)/(2x)`.
* **`|n| ≤ |V|`** (for `K = 19`): `|c| ≤ V²`, `|X| ≤ V²`, so `72|n|³ − 12|V||n| ≤ V² + |V|³ + 38`,
  which fails for `|n| ≥ |V| + 1 ≥ 2` exactly as in `DEquation.abs_n_le_abs_U`.
* Fixed `X`: `W² = X²(X+12n)² + 8X(36n³−K)` must be a square; this is the Mordell curve

  ```
  V_E² = Z³ − 432·X³·(X³ + 24K),     Z = 12X(6n + X),   V_E = 36X·W,
  ```

  i.e. the integer-chart curve `Z³ − 432x³(x³+3K)` at `x = X/2` after `(Z, V) → (4Z, 8V)`.

These identities were checked symbolically (sympy) and on random data; they are not yet in
Lean (§7).

## 2. Integral radicals: both charts are the sum of three cubes

**Identity.** For `A = −x+y`, `B = −x−y`, `C = 2x+6n` (any rational `x ≠ 0`, `y`, `n`):

```
A³ + B³ + C³ − 6K = −6x · ( y² − (x+6n)² − (36n³−K)/x ).
```

So the radical identity `y² = (x+6n)² + (36n³−K)/x` *is* `A³+B³+C³ = 6K`.

**Integrality.** `2x = −(A+B)` and `2y = A−B` have the same parity, so `A, B` are integers
exactly when *either* `x, y` are both integers *or* both are halves of odd integers — the
two cases asked for, and no others.  Then `C = 2x+6n` is an integer too.  In terms of the
certificates: `y` is integral iff `x | U` (integer chart), resp. `X | V` (half chart), since
`2dx = U/x = V/X` and `y = −(x + 6n + 2dx)`.  Conversely an integer triple with
`A³+B³+C³ = 6K` and `6 | A+B+C` gives

```
n = (A+B+C)/6,   x = −(A+B)/2,   y = (A−B)/2  (take A ≥ B),   d = (A+C)/(A+B),
U = (A+C)(A+B)/2  (integer chart)   or   V = (A+C)(A+B)  (half chart).
```

For `6K = 114` the congruences force `A ≡ B ≡ C ≡ 2 (mod 3)`, `A+B+C ≡ 0 (mod 18)` (so `n ≡ 0
(mod 3)`) and exactly one of `A, B, C` even.  Choosing which cube is `C` (the "third" cube):
`C` even gives the **integer chart** (`A+B`, the sum of the two odd cubes, is `≡ 2 (mod 8)`,
whence `x ≡ 7 (mod 12)`); `C` odd gives the **half chart** (two ways).  So:

> every representation `114 = A³+B³+C³` produces exactly three solutions of (E): one with
> integer `x` and integer `y`, two with `x = X/2`, `y = Y/2`, `X, Y` odd — all with the same `n`.

The half-integer case is therefore not a new source of solutions for 114, but a second (and
third) coordinate chart on the same set; what changes is which `d`, which `X` and which
certificate a search has to hit, and that matters for the cost of finding it (§5).

**Worked example (validated by the programs).**  The Booker–Sutherland solution
`42 = (−80538738812075974)³ + 80435758145817515³ + 12602123297335631³` (`6K = 42`, `K = 7`)
gives, with `n = 2083190438512862` in all three:

| chart | `x` | `y` | `d` |
|---|---|---|---|
| half | `102980666258459/2` | `160974496957893489/2` | `−93037881443153146/102980666258459` |
| half | `67936615514740343/2` | `93140862109411605/2` | `−93037881443153146/67936615514740343` |
| integer | `−46518940721576573` | `33916817424240942` | `−102980666258459/93037881443153146` |

`./verify.py --K 7 --triple -80538738812075974 80435758145817515 12602123297335631` prints
them; `grid/xroots` finds all three (and the three of `906 = 6·151`) in milliseconds when
pointed at the right `X` (`grid/validate.py`).

## 3. The congruences (`grid/local.h`)

`local.h` enumerates all triples modulo `2⁸` and `3⁶` with `A³+B³+C³ ≡ 6K` and records which
residues of `X` (the chart coordinate), `n` and the certificate `G` occur.  These are
necessary conditions for integral solutions, computed for any `K`.  For `K = 19`:

| | integer chart (`X = x`, `G = U`) | half chart (`X = 2x`, `G = V`) |
|---|---|---|
| `X` | `≡ 7 (mod 12)`; `x ≡ 3 (mod 4)` | `≡ 5, 11 (mod 12)` (odd, `≡ 2 mod 3`) |
| `n` | `≡ 0 (mod 3)` | `≡ 0 (mod 3)` |
| `G` | `≡ 5, 11 (mod 12)` (Aristotle's `sat_U_mod_twelve`) | `≡ 1, 10 (mod 12)` |
| joint 2-adic | `x ≡ 3 (16) ⇒ n ≡ 2 (4)`; `x ≡ 15 (16) ⇒ n ≡ 0 (4)`; `x ≡ 7 (16) ⇒ 4 ∤ n`; `x ≡ 11 (16) ⇒ n ≢ 2 (4)` | none |
| joint 3-adic (`X`, `n` mod 243) | 2673 of 6561 admissible pairs (0.41) | 2673 of 6561 (0.41) |
| `n` visited by `xroots` | 3.4 % | 13.6 % |

The first three rows of the integer chart are exactly Aristotle's family `n = 3m, x = 12u+7`
and `U ≡ 5, 11 (mod 12)`.  For `K = 65` (`6K = 390`) the same tables give `x ≡ 5 (mod 12)`,
`n ≡ 1 (mod 3)`, matching the CE390 family.

## 4. Rational radicals in the half chart

Dropping integrality, the half chart is a natural sibling of Aristotle's problem: rational `d`
with `n` an integer and `x` a half-odd-integer.  `dsweep --half --rational-sqrt` (all odd `X`,
both signs of `V`, no congruence restriction is known here) and a brute force over
`|n| ≤ 300`, odd `|X| ≤ 4·10⁵` agree on the small solutions

| `d` | `n` | `x` | `y` | `V = dX²` |
|---|---|---|---|---|
| `−142/4913` | `15` | `−289/2` | `1569/34` | `−2414` |
| `−9671/625` | `114` | `125/2` | `11877/10` | `−241775` |

and the run recorded in `search/run9/` extends the certificate sweep to every `|V| < 10⁸`
(2·10⁸ certificates, 1.8·10¹⁰ pairs `(V, X)`, 23 minutes on one core) **without finding a
third**: in the half chart these two are the only solutions with a certificate below 10⁸,
whereas the integer chart has four of its eleven known solutions there.  Neither has an
integral radical — as expected, since an integral one would be a representation of 114.

## 5. What is already known, and what it implies for the search

Booker and Sutherland (*On a question of Mordell*, PNAS 2021) searched, on Charity Engine,
every solution of `x³+y³+z³ = k` with `min(|x|,|y|,|z|) ≤ 10¹⁷` for the open `k` (their
algorithm fixes `d = |x+y|` and runs over `z` with `z³ ≡ k (mod d)`; complete for
`d ≤ α·z_max`, `α = 2^{1/3} − 1`, `z_max = 10¹⁷`), and in 2020 ran a further search with
`z_max = 10¹⁹`, `d_max = z_max/54` for the eight values still open, 114 among them.
114 remains without a known representation (as of July 2026).  Their negative results are
conditional on the absence of undetected computing errors.  Consequences, for any integral
solution of (E):

* **`|n| ≥ 9.8·10¹⁵`.**  With `s = A+B+C = 6n`, `(s−A)(s−B)(s−C) = (s³−114)/3`.  If every
  `|A|, |B|, |C| > M = 10¹⁷` and `|s| < M`, then `(M − |s|)³ ≤ (|s|³ + 114)/3`, i.e.
  `|s| ≥ M/(1 + 3^{−1/3}) = 0.59·M`, so `|n| ≥ 0.098·M`.
* **Certificates of at least 25 digits.**  `V·R = 72n³ − 38` where `R` is the third pair sum
  and `P + Q + R = 12n`; minimising `max((|R| − 12|n|)/2, 72|n|³/|R|)` gives
  `|V| ≳ 6|n|^{3/2} ≥ 5.8·10²⁴` (and `|U| ≳ 2.9·10²⁴`).  So `dsweep` (`|G| < 10¹⁸`) can never
  produce an integral solution for `K = 19`, and `dsmooth` only with a ≥ 25-digit smooth
  certificate.  Their `--integral` modes are kept (they are exact and fast, and are validated
  on other `K`), but they are not where 114 can come from.
* **Dictionary with Booker–Sutherland.**  Their `d = |x+y|` is our pair sum `|A+B|` — `|X|`
  in the half chart, `2|x|` in the integer chart — and their `z` is our third cube
  `C = X + 6n` resp. `2x + 6n`.  So their 2020 rectangle is `|X| ≤ 1.85·10¹⁷`, `|C| ≤ 10¹⁹`, and
  **for small `|X|` the region they have not searched begins at `|n| = 10¹⁹/6 ≈ 1.667·10¹⁸`.**
  Odd `d` is our half chart; even `d` (always `≡ 2 mod 8` for 114) our integer chart.

## 6. Algorithm D: `grid/xroots.c`

For an integral radical, `X | 36n³ − K` in both charts (integer chart: `y² − (x+6n)² =
(36n³−K)/x ∈ ℤ`; half chart: `Y² − (X+12n)² = 8(36n³−K)/X ∈ ℤ` with `X` odd).  So for a fixed
`X`, `n` lies in the classes `r (mod |X|)` with `36r³ ≡ K` — at most `3^ω(X)`, about one on
average — instead of all `n`.  A work unit is a range of `|X|` (both signs) times a window of
`n`, and it is complete for that box.  Per `X`:

1. factor `|X|` (segmented sieve over the unit's range of `X`, as in `dsweep`);
2. cube roots of `K/36` modulo each prime power (Adleman–Manders–Miller style for
   `p ≡ 1 (mod 3)`, one exponentiation for `p ≡ 2`, Hensel lifting, brute force for `p | 6K`),
   combined by the CRT;
3. fold the 2-adic and 3-adic conditions of §3 into the progressions by the CRT, so excluded
   classes are never visited;
4. test `T(n) = (x+6n)² + (36n³−K)/x` resp. `(X+12n)² + 8(36n³−K)/X` for squareness modulo
   78 primes: the first four through a precomputed wheel of the positions `t (mod 5005)` that
   pass `5, 7, 11, 13` (the loop jumps from one such position to the next, carrying the
   residues mod `17…29` along), the rest on demand.  A non-square survives with probability
   about `2⁻⁷⁰`;
5. print `ICAND <chart> X n`; `verify.py` confirms it exactly and prints `(A, B, C)`.

**Validation** (`grid/validate.py`, part of `grid/selftest.sh`): on boxes `|X| < 1200`,
`|n| < 4·10⁵` for six values of `K` with many known representations, `xroots` returns exactly
the solutions of an independent brute force (every `n`, no roots, no sieves) — in both charts,
with and without the congruences, through each of its three inner loops; `dsweep --integral`
and `dsmooth --integral` find every known certificate below their bound; and the
Booker–Sutherland solutions of 42 and 906 are found in all three charts at sixteen-digit `n`.

**Throughput** (one core of the machine used here, `n ≈ 2·10¹⁸`, window `10¹⁰`):

| `\|X\|` range | half chart | integer chart |
|---|---|---|
| `[1, 10³)` | 5.2 s (3.1·10⁹ `n` tested, 1.7 ns each) | 0.5 s |
| `[10³, 10⁵)` | 5.6 s | 2.2 s |
| `[10⁵, 10⁶)` | 10.5 s | 5.2 s |

so the cost of a box is about `κ·W·ln(X₁/X₀)` with `κ ≈ 7.5·10⁻¹¹ s` (half) and `7·10⁻¹²
s` (integer) plus about 3 µs (half) / 0.4 µs (integer) per progression, which dominates once
`|X|` is large compared with the window.  Exhausting the next decade beyond
Booker–Sutherland for small pair sums — `|X| < 10⁶`, `1.667·10¹⁸ ≤ |n| < 1.667·10¹⁹`, both
signs, both charts — is about `9.5·10⁶` core-hours by this model (`make_jobs.py --target
integral` writes the manifest, epoch by epoch, so any prefix is a complete sub-box).  The
half chart carries 90 % of that cost: it holds two of the three charts of every
representation, has no 2-adic sieve, and twice as many admissible `X` classes.  As a first slice of
that box, `search/run9/` covers `|X| < 10⁴`, `1.667·10¹⁸ ≤ |n| < 1.667·10¹⁸ + 10¹²` (both
signs, both charts; 8.4·10¹¹ values of `n` tested in 20 core-minutes): no candidate.  The
engine is designed for this skewed region (small pair sum, huge third cube); covering
`d` up to `z_max/54` as Booker–Sutherland did would need their sieve-based root
computation for large `d`, where the per-`X` overhead here (≈ 10–20 µs) dominates.

## 7. Status of the new statements

All of §1–§3 is elementary algebra and finite residue enumeration.  It has been checked by
exact symbolic computation (`sympy`), by the exhaustive enumeration in `local.h`, and by the
validation runs; it is **not** yet formalised in Lean.  Natural targets for Aristotle,
mirroring `RequestProject/Algorithm.lean`:

```
-- half chart: x = X/2, V = d X^2
theorem half_sat_iff_dSweep  : Sat d n (X/2) ↔ ∃ V c : ℤ, V = d X² ∧ V² = c X ∧
                                72 n³ − 12 V n = c + V X + 38 ∧ (2V + X(X+12n)) X ≤ 0
theorem half_abs_n_le_abs_V  : … → |n| ≤ |V|
theorem cube_identity         : A³+B³+C³ − 6K = −6x (y² − (x+6n)² − (36n³−K)/x)
theorem integral_iff_triple   : (integral radical in either chart) ↔ ∃ A B C : ℤ, A³+B³+C³ = 114 ∧ …
theorem half_V_mod_twelve     : … → V % 12 = 1 ∨ V % 12 = 10
```
