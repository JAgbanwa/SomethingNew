# Search for Solutions to a Diophantine Equation

## Equation

```
36n³ - 65 = -2d · x² · (-(x + 6n) + √((x + 6n)² + (36n³ - 65)/x))
```

## Conditions

- **n, x** — integers
- **d** — rational (most likely non-integer)
- √(...) — an integer
- n ≡ 1 (mod 3)
- x ≡ 5 (mod 12)
- x ≢ 0 (mod 7)
- Asymptotically: |n| ~ 10⁴³, x ~ n^{5/4}

## Project Structure

| File | Purpose |
|------|---------|
| `modular_sieve.py` | Modular sieve: filtering (n, x) modulo primes |
| `thue_param.py` | Parameterization d = -1 - p/q and generation of Thue equations |
| `factorization_search.py` | Factorization-based search using (y-w)(y+w) = (36n³-65)·x |
| `mw_sieve.py` | Mordell–Weil sieve on an elliptic curve |
| `cm_descent.py` | 3-descent on a CM curve with j=0 (arithmetic in Z[ω]) |
| `lll_search.py` | LLL/BKZ search and Coppersmith's method |
| `verify.py` | Full verification of solutions |
| `main.py` | Orchestration of all modules |

## Quick Start

### Demonstration of All Modules

```bash
python main.py --mode demo
```

### Modular Sieve Only

```bash
python main.py --mode sieve
```

### Search for Small Solutions (|n| ≤ 10⁶)

```bash
python main.py --mode search-small
```

### Search Setup for Large n (~10⁴³)

```bash
python main.py --mode search-large
```

### Verification of a Specific Solution

```bash
python main.py --mode verify <n> <x> <d_num> <d_den>
```

## Algorithmic Strategy

### Stage 1: Modular Sieve

For each prime p, the admissible classes (n mod p, x mod p) are computed,
satisfying all modular conditions and the condition that (36n³-65)·x is a quadratic residue modulo p.
Combining them via CRT reduces the search space.

**Estimate:** 100 primes yield a reduction factor of ~10^{-100}; 200 primes yield ~10^{-200}.

### Stage 2: Parameterization of d

Root d ≈ -1: d = -1 - p/q, where p is small (1..20), q ~ n^{1/4} ~ 10^{11}.

Root d ≈ 0: d = p/q, where q ~ n^{3/4} ~ 10^{32} (considerably worse).

**Recommendation:** start with d ≈ -1.

### Stage 3: Thue Equation

For fixed d = -1 - p/q, the equation reduces to a cubic Thue form:

```
36q²n³ + 24q(q+p)·n·x² - 4p(q+p)·x³ = 65q²
```

It is solved using the Tzanakis–de Weger algorithm (PARI/GP `thue()`, Magma `Thue()`).

### Stage 4: 3-Descent on a CM Curve

For fixed x, the equation reduces to the elliptic curve Y² = N³ + k
with j = 0 (complex multiplication by Z[ω]). 3-descent uses factorization
in Z[ω] to compute the Selmer group.

### Stage 5: Mordell–Weil Sieve

Combines local information (E(F_p)) with the group structure of E(Q)
to narrow down the candidates without exhaustive search.

### Stage 6: LLL Search

In the asymptotic regime (x = C·n^{5/4} + δ), Coppersmith's method
finds the small correction δ through LLL lattice reduction.

### Stage 7: Verification

Full checks: integrality, modular conditions, divisibility, the perfect-square condition,
and the original equation.

## External Tools

| Tool | Purpose |
|------|---------|
| **PARI/GP** | `thue()` — solving Thue equations; `ellheegner()` — Heegner points |
| **Magma** | `Thue()`, `RankBounds()`, `IntegralPoints()`, `HeegnerPoint()` |
| **SageMath** | `EllipticCurve()`, `integral_points()`, `descent()` |
| **fplll** | BKZ reduction of large lattices (block_size 30–40) |
| **GMP** | Exact arithmetic with large numbers |

## Parallelization

- **By q:** each value of q is an independent task (embarrassingly parallel)
- **By primes:** the modular sieve is parallelized over primes p
- **By x:** for fixed n, the search over x is parallelized

Recommended structure: master–worker, with q as the task parameter.

## Complexity Estimates

| Component | Complexity | Practical Estimate |
|-----------|------------|--------------------|
| Modular sieve (100 primes) | O(100 · p²) | ~seconds |
| Unit group of a cubic field | O(√\|Δ\| · polylog) | ~10^{23} operations |
| 3-descent (j=0) | polynomial | ~minutes–hours |
| LLL reduction | O(d⁵ · log B) | ~minutes |
| thue() in PARI/GP | depends on the field | ~hours–days |

## References

1. Tzanakis, de Weger. "Practical solution of Thue equations" — the Tzanakis–de Weger algorithm
2. Bilu, Hanrot. "Solving Thue equations without the full unit group" — a simplified method
3. Cremona, et al. "Mordell-Weil Sieve" — a sieve on elliptic curves
4. Coppersmith. "Small solutions to polynomial equations" — the small-roots method
5. Cohen. "Advanced Topics in Computational Number Theory" — 3-descent, Heegner points
