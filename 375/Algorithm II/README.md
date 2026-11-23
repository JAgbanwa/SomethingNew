# Algorithm II: exact searches of the original equation

This folder provides two self-contained search backends for the requested
equation, one common exact acceptance check, and an additional rational-`d`-first
search. The public command-line interface fixes the target at **375** and accepts
only points with

```text
n an integer,
x = X/2, y = Y/2,
X and Y odd integers, Y > 0,
gcd(X,Y) = 1.
```

Every emitted solution is rechecked in the original, unsquared equation using
exact rational arithmetic. The implementations and their finite coverage are
documented; a completed run with no solutions excludes only its recorded region.

## The equation and the corrected parameter

Write

```text
A(n) = 36n^3 + 54n^2 + 27n - 58,
B = x + 6n + 3,
y = sqrt(B^2 + A(n)/x),
A(n) = -2*d*x^2*(y-B).
```

Since `A(n) == 2 (mod 3)`, it never vanishes for integer `n`. Factoring the
radical relation gives `A(n)=x*(y-B)*(y+B)`, so the equation forces

```text
d = -(y + x + 6n + 3)/(2x),
abs(d) = abs(y + x + 6n + 3)/(2*abs(x)).
```

This implements the **agreed +3 correction**. The repeatedly quoted expression
without `+3` is not used. The signed `d` is retained in the equation; its absolute
value is a separate output field. Replacing signed `d` with `abs(d)` can change
the equation.

With `t=2n+1`, the exact change of coordinates is

```text
a = X + 3t,       b = -(X+Y)/2,       c = (Y-X)/2,
a^3+b^3+c^3 = 375,
d = (a+c)/(b+c).
```

The inverse, for every permutation of a cube triple, is

```text
n = (a+b+c-3)/6,       X = -(b+c),       Y = c-b.
```

The accepted charts satisfy `a+b+c == 3 (mod 6)`, `b+c` odd, `c>b`, and
`gcd(b,c)=1`. Opposite parity makes `gcd(b,c)=gcd(X,Y)`. Thus cube primitivity
is necessary but does not replace the stronger requested `gcd(X,Y)=1` test.
Negative `n`, negative `x`, and either sign of `d` are allowed. No additional
magnitude or sign condition is imposed unless explicitly selected as a filter.

## Install and test

Requirements:

* Python **3.10 or newer**, using only its standard library.
* For the lattice backend: a C++17 compiler and GMP development headers/libraries.
* `make` is convenient but optional.

On Debian/Ubuntu the corresponding packages are `python3`, `build-essential`,
and `libgmp-dev`. Enter this directory with quotes because its name has a space:

```sh
cd '375/Algorithm II'
make build
make test
```

The equivalent commands without Make are

```sh
python3 -c 'from elkies_jahnel import build_worker; print(build_worker())'
python3 -m unittest discover -s tests -v
```

The first lattice run can also build its worker automatically. Set `CXX` to a
compiler command if needed. The source and binary fingerprints are checked before
reuse; compilation errors fail the run. Generated binaries stay in `build/`.
The Booker and rational-`d` searches need only Python.

## 1. Booker–Sutherland search

`booker_sutherland.py` implements segmented gap factorization, complete modular
cube roots, prime-power lifting, CRT, square sieving, and exact reconstruction.
It handles the singular roots arising from `375=3*5^3` directly. Small and
equal-coordinate cases are included because this version makes no strict
coordinate-order or large-coordinate assumption.

The integer search modulus is named uppercase **D**:

```text
D = abs(u+v),    w^3 == 375 (mod D).
```

It is different from the user's signed rational `d=(a+c)/(b+c)`.

Search a finite integer-gap rectangle:

```sh
python3 search375.py booker \
  --D-min 1 --D-max 2000 --z-min -5000 --z-max 5000 \
  --output booker-run.jsonl
```

All four endpoints are inclusive. Each cube triple in this region is converted
through every possible original-equation chart. The region covers triples for
which some labeling has the specified pair sum and distinguished coordinate.
It does not claim to cover all triples with smallest coordinate at most 5000.

For a directly comparable, complete cube-height box use

```sh
python3 search375.py booker-box --height-max 500 --output booker-box.jsonl
```

This runs `1 <= D <= 2B`, `-B <= w <= B`, then retains cube height at most `B`.
Every target-375 triple in the box is covered: its pair sum has magnitude at most
`2B`, and a zero pair sum would require 375 to be a cube. The public search may
discard nonprimitive cube triples early because none can pass `gcd(X,Y)=1`.

This is a portable **reference adaptation** of the Booker–Sutherland architecture.
It does not implement the authors' full cubic-reciprocity optimization suite or
claim their native throughput. In particular, its prime table needs memory
proportional to `sqrt(D_max)` even for a narrow high-D interval. See
[BS_METHOD.md](BS_METHOD.md) for the root construction, proof and practical limits.

## 2. Elkies–Elsenhans–Jahnel search

`ej_worker.cpp` is the repository's exact GMP tangent-tile/LLL/lattice-enumeration
backend, preserved in this folder with explicit source provenance. All curve
enclosures, reduction steps and enumeration bounds use exact integers/rationals.
It is a real lattice implementation; a coordinate-pair scan is used only for the
small exceptional region below height 25.

Search the same complete cube box:

```sh
python3 search375.py elkies --height-max 500 --output elkies-box.jsonl
```

The command covers heights below 25 by a small exhaustive check, then covers
shells `[25,50)`, `[50,100)`, and so on. The final shell is searched completely
and filtered to the requested inclusive box bound. This low-height closure is
essential for a full-box statement.

Alternatively, assign a single shell or a ratio band:

```sh
python3 search375.py elkies-shell --height 100 --output shell-100.jsonl
python3 search375.py elkies-shell --height 100 \
  --index-start 100 --index-stop 400 --output band-100.jsonl
```

The shell is `H <= cube_height < 2H`. In canonical magnitudes
`0<a<=b<c`, the ratio band is

```text
index_start <= (5H)*a/c < index_stop.
```

The global endpoint `index_stop=4H` is included. Omit both indices to cover the
full proved shell. The program rejects bands outside its proved domain. For
375, `H=25` already satisfies the required inequalities. No lower height or
ratio band outside the chosen task is silently declared covered.

For a bounded amount of work:

```sh
python3 search375.py elkies-shell --height 100 \
  --max-tiles 1 --output partial-shell.jsonl
```

A tile budget can produce `complete=false`, exit status 3, and `next_index`.
Resume the unfinished band with the original `index_start` and
`index_stop=next_index`, writing a new output file. A partial box run emits a
`resume.argv` array that preserves its box cap and optional `d,n` filters; that
continuation completes only the unfinished shell. Any larger unvisited shells
remain to be run, as recorded by `remaining_larger_shells_begin`.

`--tile-scale P/Q` changes subdivision and runtime, not the coverage proof.
See [EJ_METHOD.md](EJ_METHOD.md) for the Taylor enclosure, index-nine sublattice,
exact LLL, enumeration, polynomial shortcut and interruption contract.

## 3. Search rational d first, including every integer scale

This extra command is explicitly a **different organization of the search**, not
a claim that a rational number can be substituted for the integer modulus D.
It directly addresses the request to enumerate rational parameter values.

Write `d=p/q` in lowest terms with `q>0`. The original equation forces `q|X`,
so put `X=q*m`. It becomes

```text
9t^3 - 6pq*t*m^2 - pq(p+q)*m^3 = 125,
Y = -(2p+q)*m - 6t,        n=(t-1)/2.
```

For each bounded `d,n`, the program finds **all integer roots m** of the
resulting polynomial using a proved root bound and exact monotone root isolation.
It does not assume `m=+1` or `-1`, and it needs no arbitrary cutoff on `m`.

```sh
python3 search375.py rational-d \
  --height-min 1 --height-max 50 --n-min -100 --n-max 100 \
  --output rational-d-run.jsonl
```

Here `height=max(abs(p),q)`, with both height and n endpoints inclusive. The
enumeration safely uses the necessary conditions

```text
q odd, p == q != 0 (mod 3), n == 2 (mod 3).
```

The other parity, positivity and gcd conditions are verified after reconstruction.
`rational_d.py` documents the exact polynomial reduction. A real bound on
`abs(d)` alone would leave infinitely many rational candidates; the rational
height bound is what makes this parameter enumeration finite.

## Optional d and n filters

All search commands support exact signed parameter filters:

```sh
python3 search375.py booker-box --height-max 500 \
  --d-min=-10 --d-max=10 --d-height=1000 --n-min=-100 --n-max=100

python3 search375.py rational-d --height-max 100 \
  --n-min=-100 --n-max=100 --d=-8 --d=-4/11
```

Repeated `--d` selects a finite set of rational values. The minus sign is easiest
to pass with `--d=-4/11`. Fractions are parsed exactly, with no decimal tolerance.
Filters intersect the backend's finite region; they do not enlarge it. Both
signs are searched unless a chosen filter excludes one.

## Verification and output

To check proposed data independently:

```sh
python3 search375.py verify-point --n 2 --X 5 --Y 45 --signed-d=-8
python3 search375.py verify-cubes 20 -25 20
```

The first command deliberately fails `gcd(X,Y)=1`; the second verifies the cube
triple but emits no accepted solution. These known values are regression controls,
not discoveries. A primitive cube triple can also fail the chosen chart's gcd
condition, so all relevant permutations are checked separately.

JSONL output consists of `start`, zero or more `solution` records, and one `end`
record. The start records the exact region, optional filters, strict acceptance
requirements and source SHA-256 values. A solution contains `n,X,Y,x,y,d,abs_d`,
the reduced numerator/denominator and the cube triple. Large mathematical integers
and rationals are serialized as decimal/fraction strings to avoid JSON consumer
rounding. Timing fields are informational and are not used in mathematical tests.

The original equation is checked without a numerical radical: `Y>0` together
with exact equality of the rational squares proves that `Y/2` is the principal
square root. The original unsquared equation is then checked independently.

Exit status:

| Code | Meaning |
| --- | --- |
| 0 | Requested finite region completed, or explicit verification completed |
| 2 | Invalid input, invalid candidate, failed build, or failed worker contract |
| 3 | Lattice task stopped at a tile budget/signal before its region completed |
| 130 | Python process interrupted; no completed-region claim |

Progress is written to stderr. Booker progress marks only whole completed D
values; restart at the reported `next_D` with the original remaining bounds and
filters. A hit does not mark an unfinished interval complete. Files supplied to
`--output` must not already exist, so earlier evidence is not overwritten.

## Validation and scientific scope

The suite compares both kernels to independent exhaustive searches in small
regions and includes nonempty controls at other targets. General target arguments
are available to the **internal mathematical test APIs**; the public CLI always
uses the user's exact target 375. Tests also cover singular roots modulo powers
of 5, large exact integers, wrong radical signs, signed d, nonunit m, tile
boundaries, resume, invalid native output and strict rejection of scaled375 hits.

The validation report records the finite runs performed when this folder was
added. No primitive375 discovery or global nonexistence result is asserted.
The Python Booker backend prioritizes inspectable correctness; the exact-rational
lattice backend prioritizes rigorous bounds. Neither file is a claim to reproduce
the performance of the authors' historical optimized executables.

## Files and sources

* `search375.py`: fixed-375 CLI, finite scopes, strict output and status handling.
* `equation375.py`: shared original-equation verification and chart conversion.
* `booker_sutherland.py`, `BS_METHOD.md`: modular-root/CRT/square search and proof.
* `ej_worker.cpp`, `elkies_jahnel.py`, `EJ_METHOD.md`: exact lattice search and proof.
* `rational_d.py`: direct rational-parameter search with all integer scales.
* `tests/`: independent arithmetic, coverage and integration controls.
* `VALIDATION.md`: actual local validation and bounded-run results.
* `PROVENANCE.md`: source relationship and paper references.

All required source is contained in this directory; no sibling Python modules,
Magma installation, network access, or remote compute service is needed at runtime.
