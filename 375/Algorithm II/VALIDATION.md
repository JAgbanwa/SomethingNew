# Validation performed on 23 November 2026

The tests and bounded pilots below were run locally before the source was pushed.
The original repository source inspected was commit
`857adf3f89831816461641d6d4f7bbf89783304f`. The Python runtime was 3.12.14; the
native lattice worker compiled successfully with C++17 and GMP.

## Automated checks

```sh
make test
```

Result: **54 tests passed**, process exit code 0.

The suite includes independent exhaustive arithmetic oracles, not merely
recomputation by the same search code:

* Modular cube roots checked against all residues for small primes and composite
  moduli; singular 3-adic/5-adic lifts and powers of 5 through exponent 30.
* Signed Booker rectangles, equal/small/zero-coordinate cases, primitive filters,
  square-sieve necessity and exact interval partitions.
* Agreement of the Booker and lattice kernels with exhaustive small-shell
  enumeration, with both nonempty and empty controls.
* A nonempty full chart control at target 15:
  `(-46)^3+23^3+44^3=15`, mapping to
  `(n,X,Y,d)=(3,-67,21,-2/67)` for the generalized test equation.
  This is a test control, not a target-375 solution.
* Strict original-equation rejection of the known scaled375 examples, including
  huge coordinates, wrong square-root signs, wrong signed d and failed gcd.
* Exact lattice boundaries, width invariance, tile continuation, height `10^40`,
  and large polynomial roots. Invalid/missing native terminal output cannot
  assert completion.
* Direct-d enumeration against an independent numerator/denominator oracle;
  all 2,916 cubics in a small coefficient grid plus random and huge constructed
  root controls. The `d=-8,n=2` test finds integer scale `m=5` and then rejects
  `X=5,Y=45` on gcd, proving that the search does not assume `m=+/-1`.
* Public CLI fixed-target behavior, exact filter semantics, partial-run exit
  codes, preservation of existing output files, and continuation metadata that
  retains original height/d/n restrictions.

## Bounded runs of the actual public CLI

| Command | Declared region | Outcome |
| --- | --- | --- |
| `python search375.py booker-box --height-max 500 --progress-every 0` | All target375 cube triples with maximum absolute coordinate at most 500, then the strict original-equation filters | Complete; 0 accepted points |
| `python search375.py elkies --height-max 500 --progress-every 0` | Same box, using the exact low-height closure and five lattice shells | Complete; 0 accepted points |
| `python search375.py rational-d --height-min 1 --height-max 50 --n-min -100 --n-max 100 --progress-every 0` | Reduced rational heights 1 through 50 and integer n from -100 through 100, with every integer scale m examined algebraically | Complete; 0 accepted points |

The Booker box processed 1,000 integer gaps and 1,321 modular progression
candidates. The direct-d run processed 526 reduced parameters after necessary
local filters, 35,242 parameter/n combinations, and three integer-scale
candidates; none passed every original-equation condition.

The raw cube-candidate counters need not match between the two box commands:
their preliminary handling of low-height nonprimitive triples differs. Both
apply the same strict final acceptance check, and their accepted sets agree.

The exact start/end records, source SHA-256 values and counters are in
[`validation.json`](validation.json). Short local timings in those records are
diagnostic measurements; they are not a large-search performance comparison.

These runs establish completion of the stated finite regions. They neither
claim a new primitive375 representation nor establish global nonexistence.
