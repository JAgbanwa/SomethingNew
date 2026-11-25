# Elkies / Elsenhans–Jahnel search for the rational-y equation

This package applies the **projective three-dimensional lattice method** to

$$
y^2=1+\frac{36n^3+54n^2+27n-58}{x(6n+3+x)^2},
\qquad n,x\in\mathbb Z.
$$

Its main target is a rational value of y that yields a **primitive integer
triple of cubes summing to 375**. It uses tangent tiles near the normalized
cubic curve, rank-three LLL reduction and exact lattice enumeration. Every
accepted point is then independently checked in the original equation.

The earlier experiments used three different algorithms. In particular,
Experiment #3 used fixed-n factor pairs, not the algorithm in the attached
`Elkies_allg.tar`. This package corrects that missing connection. It reuses
the exact GMP backend already present in this repository's `375/Algorithm II`
at commit `624acc970c5968a63baf684b02d062e98d701099`, with a new equation
adapter, interval planner, checked resumable campaigns and Matplotlib views.

The attached historical source is the algorithmic reference; this package
is **not a claim to reproduce the authors' optimized executable or its speed**.
Its exact-arithmetic implementation avoids raising the historical program's
fixed-width constants beyond their safe range. See [SOURCE_AUDIT.md](SOURCE_AUDIT.md).

## 1. Install and run on macOS

Download the entire `elkies375` directory, or clone the repository and enter it:

```bash
cd "SomethingNew/375/Matplotlib/Experiment /elkies375"
```

Use the same Python interpreter for installation and execution. With the
interpreter used in the earlier experiments:

```bash
/usr/local/bin/python3 -m pip install -r requirements.txt
```

The native search additionally needs a C++17 compiler and GMP with its C++
headers/library. If Apple's command-line developer tools are missing, install
them using `xcode-select --install`. If Homebrew is already installed:

```bash
brew install gmp
export GMP_PREFIX="$(brew --prefix gmp)"
export CXX=c++
```

The [official Homebrew GMP formula](https://formulae.brew.sh/formula/gmp)
documents the package. The script builds its local worker automatically on
the first actual search. `CXX`, `CPPFLAGS`, `CXXFLAGS`, `LDFLAGS` and
`GMP_PREFIX` are supported and included in the build fingerprint. Compiler
arguments are passed directly to a process, without a shell.

Python 3.10 or newer is required. Matplotlib and NumPy draw the figures;
SymPy supports the separate rational mode. The exact lattice search itself
uses Python's standard library and GMP. Compilation and the test suite were
verified on Linux; a macOS execution has not been observed in this development
session. Plotting existing records and individual `--check` operations do not
require a compiler.

### First: a small complete control

```bash
/usr/local/bin/python3 elkies375_lab.py --preset demo
```

This searches `1 <= n <= 5`, includes nonprimitive integer cube lifts, and
opens the real-geometry and coverage figures. It should recover these two
canonical cube triples:

| n | x | y | Cube coordinates, up to permutation | gcd | Marker |
|---:|---:|---:|---|---:|---|
| 2 | -5 | 0 | (5, 5, 5) | 5 | Orange circle |
| 2 | -20 | 0 | (20, 20, -25) | 5 | Orange circle |

They are controls, not primitive solutions. A green star is reserved for a
verified gcd-1 solution. The second triple tests the native search's included
global ratio endpoint; the first tests the separate height-below-25 fallback.

To save the figures without opening windows:

```bash
/usr/local/bin/python3 elkies375_lab.py --preset demo --save-prefix demo
```

### Then: the requested large n interval

```bash
/usr/local/bin/python3 elkies375_lab.py \
  --n-min 100000000000000000 \
  --n-max 100000000000000000000 \
  --target primitive \
  --max-tasks 12 \
  --max-tiles 64 \
  --geometry-slices 64 \
  --out elkies375-results
```

This performs actual native work in up to 12 height/ratio tasks and then opens
the figures. Its finite work budget is explicit. Repeating the command with
the same output directory resumes incomplete tasks and then selects more
unstarted work. An interrupted attempt does not become certified coverage.

The `spread` scheduler distributes initial tasks among the height shells.
Use `--schedule sequential --task-offset INTEGER` for deterministic paging
through logical tasks. `--max-tiles 0` removes the tile limit for an attempted
task; it does not remove the `--max-tasks` bound. A difficult tile can itself
take a long time: these are work limits, not wall-clock guarantees.

To inspect the full finite plan without running the worker:

```bash
/usr/local/bin/python3 elkies375_lab.py --plan-only --out elkies375-plan
```

To reopen a campaign without repeating search work:

```bash
/usr/local/bin/python3 elkies375_lab.py --plot-only elkies375-results
```

To search without windows and later save the plots:

```bash
/usr/local/bin/python3 elkies375_lab.py --out elkies375-results --no-window
/usr/local/bin/python3 elkies375_lab.py --plot-only elkies375-results --save-prefix large
```

All large integer bounds must be written as decimal integers, not Python
expressions such as `10**20`. Quote directory names that contain spaces.

## 2. How the original equation enters the lattice search

Set

$$
S=6n+3,\qquad T=S+x,\qquad
N=36n^3+54n^2+27n-58=\frac{S^3-375}{6},\qquad t=yT.
$$

Define

$$
(A,B,C)=(-x-t,-x+t,S+2x).
$$

The exact identity is

$$
A+B+C=S,\qquad
A^3+B^3+C^3=375-6R,\qquad
R=x(t^2-T^2)-N.
$$

Thus `R = 0` is exactly the original equation, provided `x != 0` and
`T != 0`. The cube lift is integral exactly when t is integral. A rational y
with a denominator is allowed: `y = t/T` is recovered as an exact fraction.

The native worker searches integer cube triples near

$$
u^3+v^3=1,\qquad u=a/c,\quad v=b/c.
$$

Its geometric engine covers this curve with rigorous tangent tiles, applies
rank-three lattice reduction and enumerates a proved enclosing region. It
tests the cube residual exactly. For every hit with sum of cubes 375, the
adapter recovers

$$
n=\frac{A+B+C-3}{6},\quad
x=-\frac{A+B}{2},\quad
t=\frac{B-A}{2},\quad
y=\frac{t}{6n+3+x}.
$$

It tries **every distinct same-parity pair** for A and B, rather than keeping
one arbitrary permutation. One canonical cube triple can yield several
distinct equation points. The two signs of y are counted together.

The n interval is enforced through the cube-coordinate sum. For the native
positive-n sign pattern `(a,b,-c)`, the condition is

$$
6n_{\min}+3\le a+b-c\le6n_{\max}+3.
$$

This gives a collective search region for all n in the requested interval.
It does not run separate searches at the n values chosen for drawing curves.
The planner uses additional proved inequalities to discard impossible ratio
bands, and the adapter checks each accepted triple against the exact interval.

## 3. Modular conditions and green stars

Every integer cube lift must satisfy

$$
n\bmod27\in\{2,5,14,20,23\},\qquad x\equiv1\pmod3,
\qquad t\equiv0\pmod3.
$$

The native cube lattice also uses the corresponding modulo-3 sublattice
restriction. Necessary conditions prune impossible integer lifts; satisfying
them does not establish a solution. They do **not** exclude rational-only
points, because t need not be an integer there.

The plotting layer recomputes classifications from exact values. Its symbols
have these meanings:

| Symbol | Meaning |
|---|---|
| Blue real curves/surfaces | Continuous real geometry; includes irrational y |
| Green star | Exact rational y, integral cube lift, cube sum 375 and gcd 1 |
| Orange circle | Exact integral cube lift with gcd 5 |
| Purple diamond | Exact rational-only point, without an integral cube lift |

For an integer triple with cube sum 375, a common coordinate divisor g must
have `g^3 | 375`, so the only possible positive gcds are 1 and 5. The backend
emits exact hits and coverage records; this implementation does not invent a
cloud of near-solutions to make an unsuccessful search look productive.

## 4. Rational-only y is a separate search problem

The integer lattice finds the part relevant to primitive integer cube triples.
It cannot enumerate rational-y points with nonintegral t. The earlier exact
factor-pair method remains available under an explicit engine name:

```bash
/usr/local/bin/python3 elkies375_lab.py --engine rational --n 13
```

This control gives

$$
n=13,\qquad x=-144,\qquad y=\pm\frac{695}{756}.
$$

It is an exact rational point, but `t = -695/12` for the positive-y branch;
its cube coordinates are nonintegral. It must be purple, not a primitive
green star. This example also shows why the integer-lift n congruences cannot
be applied to a general rational-only search.

`--engine rational --help` lists that engine's independent options. Its
factorization and pair-enumeration budgets can leave an n slice partial.
It covers all integer x at a selected n only when both stages finish. It
does not search every n in a displayed interval.

For an individual exact rationality check, without factoring or compiling:

```bash
/usr/local/bin/python3 elkies375_lab.py --check 13 -144
```

The exact criterion is that the integer

$$
Q=x^2(S+x)^2+xN
$$

is nonnegative and a perfect square; then `|y| = sqrt(Q)/|x(S+x)|`.
No floating-point tolerance is used to accept a solution.

## 5. The true scale of 10^17 through 10^20

A bound on n restricts the coordinate sum, not each cube coordinate. The
derived complete canonical height envelope for this interval is

```text
minimum c: 1021448630351589166
maximum c: 6000000000000000000075000000001
dyadic height shells: 43
logical native tasks at band width 1000: 100763245124579414319
```

The upper bound follows from

$$
c\le1+\left\lfloor\sqrt{(S+1)^2+(S^3-375)/6}\right\rfloor,
$$

rounded down to `c = 1 (mod 3)`. The lower bound uses the necessary inequality
`(S+c)^3 <= 4(c^3+375)`. See [METHOD.md](METHOD.md) for the derivations and
the outward-rounded quadratic ratio bounds.

These task counts describe the chosen partition of a mathematically finite
region. They are not the number of solutions, not a runtime estimate and not
completed work. A short local run cannot finish this entire plan. Changing
`--band-width` changes the partition; it does not eliminate the underlying
search volume. `--height-max` below the proved bound imposes a restricted
search and is reported as such.

## 6. Reading the figures

The viewer produces three figures:

1. **Original equation, 2D.** An exact selected n slice, with the real branches
   and any verified equation points at that n. Enter an exact n to inspect
   geometry or an exact x to perform the rationality check.
2. **Original equation, 3D.** Selected geometry slices across the interval,
   plus all n values containing recorded hits. `--geometry-slices` controls
   rendering density only. These samples are explicitly labelled as geometry.
3. **Native coverage.** The actual planned height/ratio regions and the
   completed recorded portions. An exact-offset detail view shows small
   searched intervals that would be invisible on the global scale.

At these enormous n values, many real curves are visually indistinguishable.
Matplotlib positions are floating-point approximations for display, while
search, interval bounds, rationality tests and point labels use exact integer
or rational arithmetic. Large local origins are subtracted before drawing
small coverage details. Display precision cannot create a certified hit.

Every integer n can be requested in the viewer; showing every integer slice
simultaneously would require about 10^20 separate curves. Neither a surface
nor 64 displayed slices is labelled as completion of that arithmetic search.

## 7. Checkpoints, coverage and resuming

The output directory contains:

- `manifest.json`: exact scope, algorithm settings, task count and source hashes;
- `tasks/*.json`: task bounds, verified points, completed tiles and attempt history;
- `low_height.json`: the separate finite check below coordinate height 25;
- `summary.json`: actual completed, partial, error and unstarted counts;
- `points.json` / `points.csv`: exact equation points;
- `coverage.csv`: materialized native-task coverage.

A native attempt is accepted only after its start/progress/hit/end contract
and successful process exit are verified. Missing terminal output, malformed
records or native failure cannot mark a task complete. Previously validated
coverage survives a failed continuation. Checkpoint reloads validate scope,
source hashes, tile continuity, attempt history and exact point classifications.

`complete_target_search_in_n_interval` becomes true only after all required
native regions and the small-height fallback finish, with full derived height
scope. `general_rational_y_search_complete` remains false for the integer-cube
engine. A nonzero lattice counter includes integer points in intervals handled
by exact cubic root isolation; it must not be read as that many individually
tested cube triples.

One active writer is allowed per output directory. A `run.lock` prevents
concurrent checkpoint overwrites. If a process is forcibly killed, remove a
stale lock only after confirming that process has stopped. Source changes
invalidate old campaign compatibility; use a new output directory after
updating arithmetic/search code.

## 8. Recorded runs

The [examples directory](examples/README.md) contains actual saved campaigns,
figures, exact CSV/JSON records and logs. The complete small control recovered
both nonprimitive n=2 triples. The large pilot completed 43 assigned bands
across all 43 height shells: 551 tangent tiles and 12,571 lattice points, with
zero primitive hits. Its full interval search is explicitly unfinished. A
separate n=13 factor-pair control verifies the rational-only case.

## 9. Code and verification

| File | Responsibility |
|---|---|
| `elkies375_lab.py` | Terminal interface and explicit engine selection |
| `ej_worker.cpp` | GMP tangent tiles, rank-three LLL and lattice enumeration |
| `ej_backend.py` | Portable compilation and strict native-output validation |
| `equation.py` | Exact equation, cube mapping, rationality and gcd checks |
| `region.py` | Proven finite scope, sum-strip pruning and lazy task planning |
| `campaign.py` | Execution, checkpoints, resume and coverage validation |
| `plotting.py` | Equation geometry, independently checked markers and coverage |
| `rational_core.py` | Preserved Experiment #3 fixed-n factor-pair engine |

Run the meaningful mathematical and failure-path tests from this directory:

```bash
/usr/local/bin/python3 -m unittest discover -s tests -v
```

Tests cover the native enclosure/enumeration against small brute-force
controls, malformed worker output, exact cube-to-equation conversion,
rational-only separation, arbitrary-size interval planning and boundaries,
checkpoint tampering/failure/resume behavior, and coverage/marker plotting.

## References and provenance

- S. G. Huisman, [Newer sums of three cubes](https://arxiv.org/abs/1604.07746),
  methodology section: the projective tangent-tile/lattice search.
- N. D. Elkies, [Rational points near curves and small nonzero |x^3-y^2| via
  lattice reduction](https://arxiv.org/abs/math/0005139).
- A.-S. Elsenhans and J. Jahnel, *New sums of three cubes*, Mathematics of
  Computation 78 (2009), 1227–1230, and the user-supplied historical source.
- Attachment SHA-256:
  `f3d19470122b494a59081ad93aca3a5994a1c481b7b1cf39d111a8142686d4f7`.
- [SOURCE_AUDIT.md](SOURCE_AUDIT.md), [METHOD.md](METHOD.md) and
  [EJ_METHOD.md](EJ_METHOD.md) distinguish historical source, reused backend
  and new equation-specific work.
