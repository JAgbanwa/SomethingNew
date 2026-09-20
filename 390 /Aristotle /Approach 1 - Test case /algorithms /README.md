# Searching for rational `d` with integer solutions `(n, x)`

Target equation:

```
36 n^3 - 65  =  -2 d x^2 ( -(x + 6n) + sqrt( (x + 6n)^2 + (36 n^3 - 65)/x ) )
```

with `n, x ∈ ℤ`, `x ≠ 0`, `d ∈ ℚ`.

Everything below is derived rigorously; the key steps are machine-checked in
`RequestProject/DSearch.lean` and `RequestProject/Prune.lean`.

---

## 1. Kill the radical: `d` is *determined* by `(n, x)`

Write

```
K = 36 n^3 - 65 ,    S = x + 6n ,    A = x·S = x(x+6n) ,
D = A^2 + xK = x^4 + 12n x^3 + 36 n^2 x^2 + K x .
```

Multiplying the equation by the conjugate of the radical (`√(S²+K/x) + S`) and
using `(√(S²+K/x))² - S² = K/x` the radical disappears and one gets the
**closed formula**

```
        d  =  ( -A - sgn(x)·T ) / (2 x^2) ,     T = +√D ,
```

and, equivalently, the purely polynomial form of the equation

```
        36 n^3 - 65  =  4 d (d+1) x^3  +  24 d n x^2 .
```

Consequently:

> **`d` is rational  ⟺  `D = x²(x+6n)² + x(36n³-65)` is a perfect square.**

(⇐ is `DSearch.satisfiesEq_of_sq`, ⇒ is `DSearch.exists_sq_of_satisfiesEq`.)

So one never has to "guess" `d`: **every** admissible `d` is produced by a pair
`(n,x)` that makes `D` a square, its denominator always divides `2x²`, and its
size is
```
        |d|  ≈  3 |n|^{3/2} / |x|^{3/2}      (when |x| ≪ |n|),
        |d|  ≈  |x + 6n| / |x|  or  ≈ 0      (when |x| ≫ |n|).
```
Large `|d|` therefore lives in the regime `|x| ≪ |n|`, large *denominators*
need `|x|` with many prime factors, and a genuinely non-integer `d` needs
`|x| ≥ 2`.

An equivalent "Mordell" shape of the same condition, useful for theory
(`S = 3n + x`):

```
        3 T^2 = x ( 4 (3n + x)^3 - x^3 - 195 ) ,
```
i.e. for fixed `x` the integer points of the Mordell curve
`Y² = V³ - 432x³(x³+195)` with `V = 12x(3n+x)`, `Y = 36xT`.

## 2. The `m`-parameter: turning squares into divisors

Put `m = T - A`.  Then `T² = A² + xK` becomes

```
        2 m x^2 + (12 m n - K) x + m^2 = 0 ,        (Q)
        equivalently   K = 2m(x+6n) + m²/x .
```

Two decisive consequences:

* **(Q) is a *quadratic in x*.**  Any integer triple `(n,x,m)` solving (Q)
  automatically makes `D = (A+m)²` a square — *no square test, no luck needed*.
  The discriminant condition of (Q) is `P² - 8m³ = R²` with `P = 12mn - K`, i.e.

  ```
        (P - R)(P + R) = 8 m^3 ,
  ```
  a **factorisation** problem: choose `m`, factor `8m³`, and every divisor pair
  proposes a `P`, hence (by solving the cubic `36n³ - 12mn + (P-65) = 0`) a
  candidate `n`, hence `x = (K - 12mn ± R)/(4m)`.

* **`x | m²`** (because `m² = x(K - 2(x+6n)m)`).  Writing `x = s·t²` with `s`
  squarefree this gives `st | m`, `m = str`, and
  ```
        K = s ( 2 t r (x + 6n) + r² )   ⟹   s | 36 n³ - 65 .
  ```

## 3. The pruning theorem (this is what makes the search fast)

`36n³ - 65` is always **odd** and always `≡ 1 (mod 3)`.  Combined with
`s | 36n³-65`:

* the exponent of `2` and the exponent of `3` in `x` are **even**
  (`Prune.even_padicValInt_two/three`), so
  `x = ±2, ±3, ±6, ±8, ±12, ±18, ±24, ±27, …` are **impossible**;
* for every other `x`, `n` is confined to the roots of the cubic congruence
  ```
        36 n^3 ≡ 65   (mod s),      s = squarefree kernel of x,
  ```
  which is typically **one residue class out of `s`**.

That is a speed-up factor of `s` (up to `|x|` itself) over any scan in `(n,x)`.

## 3½. The complete engine: solving *all* `x` for a given `n`

Combining §2 and §3 gives an algorithm that is **complete in `x` with no search
window at all**.  Write `x = s t²` (`s` squarefree, `s | K`), `K = s K'`.  Then

```
        D = x²(x+6n)² + xK = s² t² ( t²(x+6n)² + K' ) ,
```

so `D` is a perfect square **iff**

```
        K'  =  G² - W²  =  (G-W)(G+W) ,        W = t (s t² + 6n) .
```

So for a fixed `n`:

1. factor `K = 36n³ - 65` (Pollard rho);
2. for each squarefree divisor `s` of `K` (both signs) put `K' = K/s`;
3. for each factorisation `K' = u·v` put `W = (v-u)/2`;
4. solve the cubic `s t³ + 6n t - W = 0` for an integer `t` (exact binary search
   on its monotone branches);
5. each root gives `x = s t²`, and **every** solution for this `n` arises this way.

Cost: one factorisation plus `O(3^ω(K) · τ(K))` O(1)-steps — a few milliseconds,
independent of how large `|x|` is.  This is `engine_full.py`, and it is what
lets us say *"for every `n` in the scanned range there is no other `x`
whatsoever"* rather than *"no other `x` below some bound"*.

## 4. The engines

| file | idea | best for | cost |
|---|---|---|---|
| `scan_box.c` (**B**) | for each `n`, run over `x` using 4th-order finite differences of the quartic `D(x)` (four 128-bit additions, no multiplications) + mod 64/63/65/11 square filter | exhaustive sweeps of a box | `3·10⁸` pairs/s/core |
| `scan_curve.c` (**A**) | for each `x`, run over `n` using 3rd-order finite differences of the cubic `D(n)` | deep sweeps of one "elliptic curve per `x`" | `3·10⁸` pairs/s/core |
| `engine_m.c` (**C**) | the divisor method of §2: factor `8m³`,each divisor pair gives `P`, solve the cubic for `n`, read off `x` | reaching **huge** `\|x\|` (`~m²` and beyond, e.g. `10¹²–10¹⁴`) that no scan can enumerate | `τ(8m³)` cubic solves per `m` |
| `engine_sqfree.c` (**E**) | §3: enumerate `x = ±s t²` with `s` odd squarefree, `3∤s`, solve `36n³ ≡ 65 (mod s)` (cube roots mod `p` via `a^((2p-1)/3)` for `p≡2 mod 3`, cubic-residue test + search for `p≡1 mod 3`), CRT, then walk **only** that residue class with finite differences | the **large-`\|d\|` regime** `\|x\| ≪ \|n\|`; fastest overall | covers `\|x\|≤X, \|n\|≤N` in `≈3.2·N·√X` tests instead of `4NX` |
| `engine_full.py` (**F**) | §3½: factor `K`, run over squarefree divisors `s` and over factorisations of `K/s`, solve a cubic for `t`, output `x = s t²` | **complete for each `n`, over all `x ∈ ℤ` — no bound at all**; the strongest engine | one factorisation of `K` per `n` (≈1 ms) |
| `engine_divK.py` (**D**) | `x \| K` sub-family: factor `K = 36n³-65` (Pollard rho) and test every divisor `x` — reaches `\|x\|` up to `\|K\| ~ 10¹⁶`| structured solutions with very large `\|x\|` | one factorisation per `n` |
| `verify.py` | exact rational re-verification of every hit (including the radical itself) and computation of `d` | — | — |

All six engines independently rediscover the same solutions — a useful
cross-check.

*Note on engine E*: for a prime `p ≡ 1 (mod 3)` that passes the cubic-residue
test it locates the three roots of `36n³ ≡ 65 (mod p)` by a direct search of
cost `O(p)` (only about one prime in six needs it).  That is why `XMAX ≤ 10⁶`
is the sweet spot for engine E; beyond that use engine F, which has no bound on
`|x|` at all.

### Building and running on macOS

```sh
cd algorithms
clang -O3 -march=native -o scan_box      scan_box.c      -lm
clang -O3 -march=native -o scan_curve    scan_curve.c    -lm
clang -O3 -march=native -o engine_m      engine_m.c      -lm
clang -O3 -march=native -o engine_sqfree engine_sqfree.c -lm

# THE COMPLETE SEARCH: every x whatsoever, for every n in the range
python3 engine_full.py 1 1000000 8 | tee hits_F_pos.txt
python3 engine_full.py -1000000 -1 8 | tee hits_F_neg.txt

# the sieve workhorse: |x| <= 10^6, |n| <= 10^8, split over 8 cores
for i in 0 1 2 3 4 5 6 7; do
  ./engine_sqfree 1000000 100000000 8 $i > hits_E_$i.txt &
done; wait
cat hits_E_*.txt | python3 verify.py

# huge |x| via the divisor method, 8 cores
for i in 0 1 2 3 4 5 6 7; do ./engine_m 10000000 8 $i > hits_M_$i.txt & done; wait
cat hits_M_*.txt | python3 verify.py

# the x | K family
python3 engine_divK.py -200000 200000 8 | tee hits_D.txt
```

`run_all.sh` does all of this for you.

## 5. Why the solution set is thin (and what that means for "many" solutions)

For a "random" `D` of size `D` the chance of being a perfect square is
`1/(2√D)`.  Summing that heuristic over the whole search region gives

* `|x| ≫ |n|`:  `D ≈ x⁴`, mass `≈ Σ_x 1/(2x²) = O(1/|n|)`;
* `|x| ≲ |n|`:  `D ≈ 36|x||n|³`, mass `≈ Σ 1/(12√x |n|^{3/2}) = O(1/|n|)`;

so the expected number of solutions with `|n| ≤ N` grows only like
`c · log N` (with a small constant coming from the local densities).  This is
*confirmed* by the data: exhausting `|n| ≤ 2·10⁴, |x| ≤ 10⁶` (8·10¹⁰ pairs)
yields 3 solutions, and pushing to `|x| ≤ 10⁷`, `|n| ≤ 10⁸` adds one more.

In other words: solutions exist, but each additional one costs roughly a
*decade* of extra search — which is exactly why engines C/D/E (which buy whole
decades of `|x|` or `|n|` for a nearly constant price) matter so much more than
raw brute force.

## 6. Solutions found

See `../SOLUTIONS.md` (regenerated by `verify.py`); every entry there is also
machine-checked in `../RequestProject/Solutions.lean`.
