# Native Booker–Sutherland gap search

`bs_worker.cpp` and its checked Python interface, `booker_native.py`, provide
the compiled backend for large finite gap tasks. They complement the portable
reference implementation in `booker_sutherland.py` and the separate lattice
backend. They search the integer cancellation gap; they do not enumerate a
bounded list of rational values of the original parameter `d`.

## Running and exact coverage

```python
from booker_native import iter_gap

for record in iter_gap(
    10**12, 10**12 + 2**20,
    ratio_max=1024,
    primitive=True,
    deadline_seconds=60,
):
    print(record)
```

The default target is 375. A compiler with C++17, a 64-bit `unsigned long`,
and GMP is required. `build_worker()` compiles the worker automatically into
`build/bs_worker`. `CXX` may select a compiler command; it is passed as an
argument list, not interpreted by a shell.

For each native triple `(x,y,z)`, define **the integer gap** `D=|x+y|`.
The exact region is

```text
d_start <= D < d_stop,
floor(3847*D/1000) <= |z| <= ratio_max*D,
x >= y,
(x+y)*z < 0.
```

The `D` interval is half-open, while both bounds on `|z|` are inclusive.
The pair sum and the distinguished coordinate have opposite signs. The native
implementation does **not** impose an ordering of the three absolute coordinate
magnitudes. Ties are retained: with nonprimitive hits enabled, `(20,-25,20)`
is included for target 375. This distinction matters when comparing the actual
worker region with the asymptotic ordered region in the paper.

The decimal 3.847 is implemented exactly as the integer expression
`floor(3847*D/1000)`. It is not substituted for an irrational inequality during
verification. This lower bound lies slightly below the usual asymptotic
threshold `D/(cuberoot(2)-1)`. Neither the approximation nor an assumed prior
search frontier is used to remove points inside the declared native region.

An exhausted native task excludes primitive cube triples **only in this
gap/ratio/sign region** when primitive mode is enabled. It does not establish
whole-box coverage, cover all slopes of small rational magnitude, independently
search every solution for a bounded `n`, or exclude every representation of 375.
Other coordinate choices can describe
the same unordered triple, so callers that combine backends should deduplicate
their exact cube triples or reconstructed chart points.

## Arithmetic and why the filters are safe

Write `r=|z|`, `sigma=sign(z)`, `K=sigma*k`, and `s=x+y=-sigma*D`.
The cube identity is equivalent to

```text
r^3 == K (mod D),
Delta = [4(r^3-K)-D^3]/(3D) = (x-y)^2.
```

For a nonnegative integer square `Delta=t^2` with `t` and `D` of the same
parity, reconstruction gives `x=(s+t)/2`, `y=(s-t)/2`, and `z=sigma*r`.
Every reported triple is checked with GMP against the original cube identity.
The Python wrapper independently rechecks the cube sum, gap, signs, endpoints,
coordinate order, and primitive flag using arbitrary-precision integers.

The implementation follows the Booker–Sutherland gap/root/square architecture:

1. Factor consecutive gaps with a segmented sieve, using buckets for large
   prime factors. A prime modulo which the target is not a cube eliminates
   its multiples before more expensive factorization work.
2. Compute all roots modulo each prime power and combine them with the Chinese
   remainder theorem. Unit roots at primes congruent to one modulo three use
   digit extraction in the 3-primary subgroup; they do not require a residue
   scan up to the prime.
3. Use the exact congruences modulo 3, 27, and powers of two to restrict the
   arithmetic progressions. For `k == +/-3 (mod 9)`, all cube coordinates have
   the corresponding residue `+/-1 modulo 3`, `3` does not divide the gap,
   and `9` divides `(x-y)^2`. These facts also fix `sigma` from `D modulo 3`.
4. Apply exact quadratic-residue tests at 16 odd primes. The first eight tests
   use bit masks to examine 64 progression steps together. A prime dividing
   `D` is excluded from the inverse-based test at that prime.
5. Test the survivors with GMP, reconstruct the coordinates, and verify the
   cube sum and gcd exactly.

All sieves are necessary conditions. The full residue enumeration and the
final exact test therefore cover every solution in the declared finite region,
provided the task finishes successfully. This implementation does not claim
to include every cubic-reciprocity optimization from the authors' production
software.

### The cube factor in 375

The target is kept as `375=3*5^3`. It is not divided by 125, since doing that
would discard the primitive problem. For `k=p^v*u`, with `p` not dividing `u`,
roots modulo `p^e` are constructed as follows:

* If `e<=v`, they are all multiples of `p^ceil(e/3)`.
* If `e>v` and `3` does not divide `v`, there are no roots.
* Otherwise factor `p^(v/3)` out of the root, solve the remaining unit equation,
  and include every free lift. For 375 there are 25 roots modulo `5^e` for
  every `e>=3`.

Primitive mode first rejects gaps with 5-adic valuation one or two. It also
checks **every reconstructed triple's gcd** and emits a hit only when that gcd
is one. The latter check is essential: the gap filter alone does not certify
primitivity for gaps divisible by 125.

The public application uses target 375. The interface accepts auxiliary targets
with `0<|k|<=1000000`, `k == +/-3 (mod 9)` for independent nonempty tests. This
native implementation's primitive mode additionally requires every cube-factor
prime to be congruent to two modulo three. These are implementation limits for
the auxiliary targets, not claims of mathematical impossibility.

Cube primitivity is still weaker than the user's original chart condition.
The shared chart verifier must impose integer `n`, odd `X,Y`, `gcd(X,Y)=1`,
the positive square-root branch, and the exact original equation before
accepting a point.

## Numeric limits and resource limits

The interface exposes `D_STOP_MAX=2**63//27`, `RATIO_MAX=2**40`, and
`validate_gap(d_start,d_stop,ratio_max)`. The native worker independently checks
the same arithmetic limits:

* `1 <= d_start < d_stop <= 2**63//27` keeps every active `27D` below `2**63`.
  It also bounds `18D`, modular products, and progression starts safely within
  their declared types. The unsigned wraparound used in the two-adic test is
  intentional arithmetic modulo `2**64`.
* `4 <= ratio_max <= 2**40`, together with the explicit
  `ratio_max*(d_stop-1)+18*d_stop < 2**126` guard, bounds the 128-bit progression
  arithmetic. Cubes and reconstructed coordinates themselves use GMP.
* Counters use unsigned 128-bit integers. The conservative guard
  `(ratio_max+1)*d_stop*(d_stop-d_start) < 2**128` bounds them without relying
  on a statistical estimate of the number of cube roots. Oversized intervals
  must be split into tasks. Counter values are serialized as decimal strings
  to preserve every digit in consumers with narrower numeric types.

These limits describe arithmetic safety, **not affordable running time or
memory**. Initialization sieves primes through `P=isqrt(d_stop-1)` even when
the requested interval is narrow. Its odd-composite bit table takes about
`P/16` bytes, and factor buckets and working arrays require additional memory.
Increasing `ratio_max` increases progression work. A bounded sample on the
actual machine should guide campaign sizing; short examples in this document
are not a throughput guarantee.

## Completed prefixes, deadlines, signals, and verification

The stream has four record types:

| Record | Meaning |
|---|---|
| `start` | Echoes version, method, target, exact bounds, filters, chunk request, deadline, and sieve limit. |
| `hit` | A verified integer cube triple inside the declared region. It does not mark its gap complete. |
| `chunk` | A contiguous, nonempty half-open interval of fully completed gaps, with its exact counters. |
| `end` | `state=complete` or `partial`, the first uncovered gap `d_next`, and a reason. |

Ordinary chunks are emitted after completed 65,536-gap factor blocks, once the
requested chunk size is reached. A deadline or signal can flush a shorter
chunk in the middle of a factor block, but **only after each covered gap has
finished completely**. An interrupted individual gap is never counted as
complete. Both SIGINT and SIGTERM request this safe stop. Initialization and
the current individual gap may take time before a stop is observed.

The deadline is a soft integer-second budget including native initialization.
It is checked at least every 1024 processed gaps and at factor-block ends.
A process killed externally can lack a terminal record; that is an error,
not a successful task. Resuming from the last durably recorded completed chunk
may repeat later hits, so the application must deduplicate them.

The wrapper validates the start options, every hit, contiguous chunk endpoints,
counter accounting, the number of emitted hits, and the terminal prefix. It
rejects missing starts or ends, duplicate hits, regressing coverage, malformed
records, nonzero exits, and any output following an end record. It withholds
the terminal record until EOF and a successful exit have both been observed.

The local build stamp contains the source SHA-256, compiler command, flags,
worker version, and binary SHA-256. A mismatched source or binary triggers a
rebuild. Compilation and stamp replacement are atomic. Campaign manifests
should retain their own source/binary fingerprints and exact task regions.

## Tests and provenance

Run the focused tests with:

```sh
python3 -m unittest discover -s tests -p test_booker_native.py -v
```

The tests compare full small native regions with the independent Python
reference; compare a coordinate box against direct integer-cube enumeration;
test singular roots modulo 125 and 625; recover the known large target-3
representation; and verify both primitive filters. An actual SIGINT test checks
that the completed prefix plus its resumed tail has exactly the same hits and
counters as an uninterrupted run. Another test checks a real deadline. Forged,
incomplete, contradictory, and trailing stream records are rejected.

This worker is adapted from this repository's
`375/gap-search/src/gap_worker.cpp`, version 1.2.0, whose source SHA-256 at the
time of copying was
`68f5411a81f253a22ae265b784514458b987e17745c0ff113e8192956e56f2c1`.
That source records its derivation from CE114 gap worker 1.1.0. The Algorithm II
changes preserve the arithmetic engine and add explicit protocol metadata,
128-bit counters with a checked bound, strict primitive-hit filtering, and
safe deadline/signal prefix reporting. The interface is new and self-contained.

Primary references for the underlying method are Andrew R. Booker and Andrew
V. Sutherland, [*On a question of Mordell*](https://arxiv.org/abs/2007.01209),
and the [authors' implementation](https://github.com/AndrewVSutherland/SumsOfThreeCubes).
