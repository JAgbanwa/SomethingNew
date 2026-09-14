# Corrected searches for rational y with integer m and u

The target is

```text
y^2 = 1 + (972*m^3 - 19)/((12*u + 7)*(12*u + 7 + 18*m)^2),
m,u in Z, y in Q.
```

All four searches default to **noninteger y** (`AllowIntegerY := false`).
Every reported triple is checked against the original equation using exact
rational arithmetic and must have integer m and u. No verified numerical
solution to this integer-(m,u) problem is supplied by this correction.

## What was wrong

Put `A = 12*u+7`, `B = A+18*m`, and `N = 972*m^3-19`.
The target gives `A*B^2*y^2 = A*B^2+N`. Therefore, if `Y = A*B*y`,
the correct relation is

```text
Y^2 = A*(A*B^2+N).
```

The former scripts instead used `Y^2 = A*B^2+N`, dropping the factor A.
Their printed y values consequently satisfy `A*y^2 = original RHS`, rather
than the requested equation. All seven complete triples in the historical
`folder1 /answers.folder1` fail the original equation; their original right
hand sides are negative, and their m and u values are not integers.

Also, integer m and u imply `B = 12*u+7+18*m` is an integer congruent to
1 modulo 6. The former fixed `B = -30/11` and the rank examples `B = -300`
and `B = -294/6 = -49` cannot produce integer m and u.

## Correct curve and inverse map

Writing `D = B^3-114` and substituting `m = (B-A)/18` gives

```text
6*A*B^2*y^2 = -A^3 + 3*B*A^2 + 3*B^2*A + D.
```

For `A*B != 0`, set `X = 6*D/A` and `W = 6*B*X*y`. Then

```text
E_B: W^2 = X^3 + 18*B^2*X^2 + 108*B*D*X - 216*D^2.
```

Its inverse, away from the identity point and `X = 0`, is

```text
A = 6*D/X;
m = (B-A)/18;
u = (A-7)/12;
y = W/(6*B*X).
```

Here `D != 0` for rational B, since 114 is not a rational cube.
For integer searches, the inverse additionally requires integer A with
`A = 7 (mod 12)` and `A = B (mod 18)`. These conditions, plus direct
substitution into the original equation, are enforced in `common.m`.
The low-level `RecoverPoint` helper also accepts rational B solely to permit
independent algebra checks; `CurveForB` enforces the integer-search domain.

## Running the code

**Each `codes.folderN` file and `self_test.m` is now self-contained.**
Copy the entire contents of one file into the
[Magma calculator](https://magma.maths.usyd.edu.au/calc/) and press Submit.
No separate `common.m` file or `load` command is needed. Start with
`self_test.m`, then try `folder3 /codes.folder3` with its default settings.
The calculator currently allows 60 seconds and 50000 input bytes; all five
standalone files are below the input limit. A computational bound is not a
promise that a calculation will finish within 60 seconds.

For an installed Magma, run the file directly. For example, from the
repository root:

```sh
magma '114 /Magma /#1 /self_test.m'
magma '114 /Magma /#1 /folder3 /codes.folder3'
```

At a Magma prompt you can instead load either standalone file by its full
path. Directory names in this repository contain trailing spaces; retain
those spaces in quoted paths. The scripts no longer depend on Magma's
working directory to locate another file.

## Compatibility and workload correction

The first algebra correction introduced `load "common.m";` dependencies in
all four entry scripts. Those files worked only when the helper was present
in the working directory; a script pasted by itself into the online
calculator could not load it. This revision embeds the helper definitions.

The former default also called `Generators(E)` before its first progress
message and materialized the entire coefficient box as a set. Both stages
could be expensive. The revised scripts print before expensive operations,
use a bounded rational-point search by default, and cap the number of seed
points and coefficient combinations used in mixed sums.

| File | Current default behavior |
| --- | --- |
| `folder1 /codes.folder1` | Scan admissible B between -5 and 7. |
| `folder2 /codes.folder2` | Scan the explicit list `[1,7,-5]`. |
| `folder3 /codes.folder3` | Search one B (default 7); recommended starting file. |
| `folder4 /codes.folder4` | Bounded searches between -5 and 7; optional rank discovery. |
| `self_test.m` | Standalone checks of the algebra, point API, filtering, and capped combinations; no rank or generator computation. |
| `common.m` | Canonical helper definitions embedded in all five runnable files. |
| `build_standalone.py` | Update or check the embedded helper copies. |
| `validate_model.py` | Independent exact Python checks using only the standard library. |

## Search settings

The settings are at the top of each entry file, before the helper definitions.

| Setting | Default | Meaning |
| --- | --- | --- |
| `PointBound` | 1000 | x-coordinate height bound for `Points(E : Bound:=PointBound)`. |
| `CoefficientBound` | 2 | Coefficients in mixed sums range from -2 to 2. |
| `UseGenerators` | false | Set true to request the potentially expensive `Generators(E)` computation instead of the bounded point search. |
| `MaxSeeds` | 3 | Maximum number of finite input points, distinct up to sign, used in mixed sums. |
| `MaxCombinations` | 1000 | Maximum coefficient tuples materialized per curve. |
| `AllowIntegerY` | false | Accept only noninteger rational y. |
| `ComputeRanks` (folder 4) | false | Set true to enable the optional rank-discovery step. |
| `RankEffort` (folder 4) | 1 | Effort passed to `Rank`; this is not a time limit. |

The default input points are **seed points, not a proved generating set**.
All returned input points and their negatives are checked directly, even if
some are omitted from mixed sums by `MaxSeeds`. Mixed coefficients are
visited in the order `0,1,-1,2,-2,...` in each coordinate. Seed omissions and
truncated coefficient boxes are reported explicitly. Each combination and
its negative are checked, so both signs of an accepted y can be reported.

With `ComputeRanks := true`, folder 4 reports both the rank value and whether
Magma proved it exact. An unproved value is labeled a lower bound. The
`MinimumRank` threshold (default 2) applies to this lower bound; if a smaller
unproved value is returned, the curve's actual rank may still exceed the
threshold. `SearchDetectedCurves` controls the subsequent solution search.

The documented APIs are in the Magma handbook:
[point searches](https://magma.maths.usyd.edu.au/magma/handbook/text/1552) and
[rank and Mordell-Weil methods](https://magma.maths.usyd.edu.au/magma/handbook/text/1570).

## Larger searches and interpretation

Extend the B range/list or increase the bounds after checking the small
example. Exact arithmetic supports arbitrarily large integer B; for example,
`B := 10^30+3;` is admissible. A small `PointBound` on that curve is still a
small point search and need not find any useful seed. Large B, larger point
bounds, and generator computations can require a long-running installed
Magma session. The combination cap limits the number of tuples; it does not
bound the size of rational coordinates or the running time of point arithmetic.

For a deeper search, `UseGenerators := true` restores the generator-based
approach, with progress output and the explicit seed/combination limits.
Increase those limits deliberately if you want more of the returned group
searched. Neither mode certifies a complete solution set.

Finding no accepted point in a finite search is **not a proof of
nonexistence**. Rank or a point list alone does not establish a solution with
integer m and u. Failed curve computations in the scanning scripts are
reported separately. No verified numerical target solution is supplied here.

## Validation and maintenance

Run these commands from this directory with Python 3:

```sh
python3 validate_model.py
python3 build_standalone.py --check
```

Both checks passed for this revision. The first verifies the curve identity
by exact symbolic expansion, checks an independent rational fixture and
inverse map, and rejects all seven complete historical false positives.
The fixture has noninteger m and is explicitly rejected as a target solution.
The second verifies synchronization of all embedded helper copies and the
calculator input-size limit. Neither command executes Magma.

**Magma execution remains unverified in the correction environment.**
No local Magma executable was available. The online calculator page could be
opened, but submitting code returned `502 Bad Gateway` (connection refused).
Consequently no successful Magma run is claimed. The expanded `self_test.m`
exercises the actual point-search and bounded-combination code paths when
run in Magma. If another runtime error occurs, retain the first error message,
its line number, the file name, and whether the online or installed version
was used.

To edit shared routines, change `common.m`, then run:

```sh
python3 build_standalone.py
python3 build_standalone.py --check
```

Edit settings or driver code outside the marked helper regions directly in
the entry files. The builder preserves those edits. Users running the Magma
files do not need Python.

The four `answers.folderN` files retain their historical text with an
obsolete-output notice. They are not fresh output from the corrected
scripts. Their historical source is commit
`b2891590bcd54504e47e55e67177a36e90261374`; no new search results or ranks
have been invented or substituted.
