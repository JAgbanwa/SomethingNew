# run9 — the half chart and integral radicals (October 2026)

Programs: `grid/` after the update (see `../../HALF_INTEGER.md` and `../../grid /README.md`).
All runs on one or two cores of the session machine; every line printed by a search was
re-checked with `grid/verify.py`.

## 1. Half chart, rational square root: `half_rational_V1e8.txt`

```
dsweep --ulo 2 --uhi 100000000 --half --rational-sqrt
```

Every certificate `2 ≤ |V| < 10⁸` (both signs), every odd divisor `X` of `V²`, no congruence
restriction: 2·10⁸ certificates, 1.81·10¹⁰ pairs `(V, X)`, 1381 s.  Five candidate lines, of
which `verify.py` confirms exactly **two solutions**, the same two that a brute force over
`|n| ≤ 300`, odd `|X| ≤ 4·10⁵` finds:

| `d` | `n` | `x` | `y` | `V` |
|---|---|---|---|---|
| `−142/4913` | `15` | `−289/2` | `1569/34` | `−2414` |
| `−9671/625` | `114` | `125/2` | `11877/10` | `−241775` |

(The other three lines are the other root of the quadratic, rejected on the branch
condition.)  Both have a rational, non-integral square root.  So in the half chart there is
no further solution with a certificate below 10⁸ — compare the integer chart, which has four
of its eleven known solutions below `|U| = 10⁸` (`U = −3, −5586, 4749, −11607484`).

## 2. Integral square root, beyond Booker–Sutherland: `xroots_{half,int}_{pos,neg}.txt`

```
xroots [--half] --X0 1 --X1 10000 --n0  1667000000000000000 --n1  1667001000000000000
xroots [--half] --X0 1 --X1 10000 --n0 -1667001000000000000 --n1 -1667000000000000000
```

Every solution with an integral square root (equivalently, every representation
`114 = A³+B³+C³` whose chart pair sum is `|A+B| = |X| < 10⁴` in the half chart, resp.
`2|x| < 2·10⁴` in the integer chart) with `1.667·10¹⁸ ≤ |n| < 1.667·10¹⁸ + 10¹²`.  In
Booker–Sutherland's coordinates that is `d < 10⁴` (resp. `< 2·10⁴`) and third cube
`|z| = |C|` just above `10¹⁹`, i.e. just outside their 2020 search region
(`d ≤ 1.85·10¹⁷`, `|z| ≤ 10¹⁹`).  Result: **no candidate at all** (not even a spurious
filter survivor).

| chart, sign of `n` | `X` with cube roots | progressions | `n` tested | time |
|---|---|---|---|---|
| half, `n > 0` | 1609 of 3333 | 76 593 | 3.79·10¹¹ | 557 s |
| half, `n < 0` | 1609 of 3333 | 76 593 | 3.79·10¹¹ | 550 s |
| integer, `n > 0` | 806 of 1666 | 630 432 | 4.06·10¹⁰ | 43 s |
| integer, `n < 0` | 806 of 1666 | 630 432 | 4.06·10¹⁰ | 42 s |

(1.46 ns per tested `n` in the half chart; the integer chart tests 9× fewer `n` per unit of
box because of its 2-adic sieve and its sparser `X`.)  This is a demonstration slice: it
covers `7·10⁻⁸` of the `n`-range of the decade `1.667·10¹⁸ ≤ |n| < 1.667·10¹⁹`, for
`|X| < 10⁴` only, out of the box that `make_jobs.py --target integral` would issue — not a
claim of meaningful coverage.

## 3. Validation: `validate_full.txt`

`grid/validate.py` (full mode): for `K ∈ {573952, −493088, 1082612, 260392, 3, 19}` and both
charts, `xroots` on `|X| < 1200`, `|n| < 4·10⁵` returns exactly the solutions of an
independent brute force (with and without the congruence sieve, and through each of its
three inner loops); every solution attached to a small triple is among them; `dsweep
--integral` and `dsmooth --integral` find every known certificate `|G| < 2·10⁵`; and the
Booker–Sutherland representations of `42` and `906` are found in all three of their charts
at sixteen-digit `n`.

## 4. Throughput: `bench.sh` → `bench.txt`

The measurements quoted in `grid/README.md` and `HALF_INTEGER.md`, re-runnable with
`./bench.sh` after `make` in `grid/`.  (They were taken while another job was running on the
second core, so they vary by about ±15 % from the quiet numbers quoted in the documents.)
Aristotle's original `dsweep` on the same box and machine: 4.5 s, against 3.1 s now.
