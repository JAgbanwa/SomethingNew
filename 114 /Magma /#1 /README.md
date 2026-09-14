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

## Files and usage

Run from this directory (`114 /Magma /#1 /`), so `load "common.m"` can find
the shared implementation. Directory names in this repository contain
trailing spaces; retain them in quoted paths.

```sh
cd '114 /Magma /#1 '
python3 validate_model.py
magma self_test.m
magma 'folder1 /codes.folder1'
```

At an interactive Magma prompt, use `load "self_test.m";` or, for example,
`load "folder1 /codes.folder1";` from the same directory.

| File | Purpose and default settings |
| --- | --- |
| `common.m` | Correct curve, inverse, exact verification, and mixed generator searches. |
| `folder1 /codes.folder1` | Scan admissible integer B from -29 to 31; coefficient bound 2. |
| `folder2 /codes.folder2` | Scan an explicit list of admissible B; coefficient bound 3. |
| `folder3 /codes.folder3` | Search one admissible B (default 7); coefficient bound 6. |
| `folder4 /codes.folder4` | Scan admissible B from -300 to 300 for reported rank at least 2; search detected curves with coefficient bound 2. |
| `self_test.m` | Magma regression checks for the algebra, inverse, historical error, and domain filters. |
| `validate_model.py` | Independent exact Python checks using only the standard library. |

Edit the settings at the top of an entry script to change B or the search
bound. Arbitrarily large integer B is supported by the exact arithmetic;
for example, `B := 10^30+3;` is admissible. Large B and larger generator
bounds can be computationally expensive. Set `AllowIntegerY := true` only
if integer y values should also be accepted.

Each search includes mixed sums of the returned generators, with each
coefficient between `-CoefficientBound` and `CoefficientBound`. With n
generators, up to `(2*CoefficientBound+1)^n` combinations are formed.
This is a finite search, and the scripts do not certify that returned
generators generate the full rational-point group. Finding no accepted
point in a search is **not a proof of nonexistence**. Rank or a generator
list alone does not establish a solution with integer m and u. Failed
curve computations in the scanning scripts are reported separately.

## Validation and historical outputs

The Python checks were executed successfully for this correction. They
verify the corrected identity by exact symbolic expansion, check an
independent rational fixture and inverse map, and reject all seven complete
historical false positives using exact fractions. The rational fixture
has noninteger m and is explicitly rejected as a target solution.

The corrected Magma scripts and `self_test.m` have **not been executed in
Magma** in the correction environment because a Magma runtime was not
available. The smoke test is provided for execution in Magma; Python
validation does not establish Magma syntax or runtime compatibility.

The four `answers.folderN` files retain their historical text with an
obsolete-output notice. They are not fresh output from the corrected
scripts. Their source is commit
`b2891590bcd54504e47e55e67177a36e90261374`; no new search results or ranks
have been invented or substituted.
