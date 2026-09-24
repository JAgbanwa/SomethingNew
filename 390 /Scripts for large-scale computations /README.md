# Diophantine Equation Solver

## Problem

Find rational (non-integer) values of `d` such that the pair `(n, x)`
consists of integers, and the expression

```
sqrt((x + 6n)^2 + (36n^3 - 65) / x)
```

is also an integer, satisfying the equation:

```
36n^3 - 65 = -2d * x^2 * (-(x + 6n) + sqrt((x + 6n)^2 + (36n^3 - 65)/x))
```

### Constraints

- `n ≡ 1 (mod 3)`
- `x ≡ 5 (mod 12)`
- `x ≢ 0 (mod 7)`
- Asymptotically: `|n| ~ 10^43`, `x ~ n^(5/4)`

### Key Result: Reduction to a Thue Equation

After algebraic manipulation, the equation reduces to the cubic Thue form:

```
36*n^3 - 24*d*n*x^2 - 4*d*(1+d)*x^3 = 65
```

For rational `d = p/q`, multiplying by `q^2` gives an integer Thue equation.

### Key Result: CM Elliptic Curve (j = 0)

The associated elliptic curve has j-invariant 0, giving it complex
multiplication by Z[omega] (ring of integers of Q(sqrt(-3))).

---

## File Structure

| File | Purpose |
|------|---------|
| `modular_sieve.py` | Modular sieve: filter (n, x) by primes, estimate density, CRT combination |
| `thue_param.py` | Parameterize d = -1 - p/q, generate Thue forms, produce PARI/GP and Magma commands |
| `factorization_search.py` | Factorization search via (y-w)(y+w) = (36n^3-65)*x, with modular pre-filter |
| `mw_sieve.py` | Mordell-Weil sieve: elliptic curve arithmetic over F_p, local filtering |
| `cm_descent.py` | 3-descent on CM curve j=0: Z[omega] arithmetic, factorization, Selmer group |
| `lll_search.py` | LLL reduction and Coppersmith's method for small root finding |
| `verify.py` | Full solution verification: all conditions, integrality, original equation |
| `main.py` | Orchestrator: `--mode demo/sieve/factor/search-small/search-large/verify` |
| `README.md` | This file |

---

## Usage

### Demo (all algorithms)
```bash
python main.py --mode demo
```

### Modular sieve report
```bash
python main.py --mode sieve
```

### Factorization search (small n)
```bash
python main.py --mode factor
```

### Small solution search (|n| <= 10^6)
```bash
python main.py --mode search-small
```

### Large solution parameters (~10^43)
```bash
python main.py --mode search-large
```

### Verify a specific solution
```bash
python main.py --mode verify <n> <x> [<d_num> <d_den>]
```

---

## Recommended Strategy

For the target scale |n| ~ 10^43, a hybrid approach is recommended:

| Step | Method | Module | Purpose |
|------|--------|--------|---------|
| 1 | Parameterize d = -1 - p/q (small p) | `thue_param.py` | Narrow d space |
| 2 | Modular sieve (30-50 primes) | `modular_sieve.py` | Narrow (n, x) mod M |
| 3 | 3-descent on CM curve (j=0) | `cm_descent.py` | Find E(Q) for fixed x |
| 4 | Mordell-Weil sieve | `mw_sieve.py` | Compress candidates to O(1) |
| 5 | Tzanakis-de Weger (PARI/Magma) | `thue_param.py` | Exact solution for final d |
| 6 | Factorization check | `factorization_search.py` | Validate found (n, x) |
| 7 | Full verification | `verify.py` | Confirm all conditions |

### Why start with d ≈ -1?

For the root d ≈ -1, the denominator q ~ 10^11, which is significantly
smaller than q ~ 10^32 for the root d ≈ 0. This makes the associated
cubic field discriminant more tractable and the 3-descent more feasible.

---

## External Tools

For the actual large-scale computations, these Python modules serve as
pre-processing, command generation, and verification tools. The heavy
lifting should be done in:

- **PARI/GP**: `thue()` for solving Thue equations
- **Magma**: `Thue()`, `RankBounds()`, `IntegralPoints()`, `HeegnerPoint()`
- **SageMath**: `EllipticCurve()`, `integral_points()`, `descent()`
- **fpLLL**: BKZ reduction for large lattices

---

## Complexity Estimates

| Component | Complexity | Notes |
|-----------|-----------|-------|
| Modular sieve (per prime) | O(p^2) | Small primes, parallelizable |
| Thue equation (Tzanakis-de Weger) | O(sqrt(|Delta|)) | Delta ~ 10^46 for d ≈ -1 |
| 3-descent (j=0) | Polynomial in |k| | k ~ x^3 ~ 10^159 (hard) |
| Mordell-Weil sieve | O(|E(F_p)| * num_primes) | Parallelizable across primes |
| LLL/BKZ | O(n^6 * log B) | n = lattice dimension, B = entry size |
| Factorization check | O(|K|^{1/2}) | K = 36n^3 - 65 |

### Parallelization

The modular sieve and Mordell-Weil sieve are embarrassingly parallel:
each prime can be processed independently. The Thue equation solving
and 3-descent are sequential per parameter set, but different parameter
sets (different p values) can be distributed across cores.

---

## Dependencies

- Python 3.8+
- `sympy` (for prime generation, factorization, modular arithmetic)
- Standard library: `math`, `fractions`, `argparse`, `collections`

No additional packages required for core functionality.
