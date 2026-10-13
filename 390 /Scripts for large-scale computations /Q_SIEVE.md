# Integer-radical denominator sieve (worker 3.2.1)

This revision integrates the sieve into `run_task.py`, `src/cf_worker.cpp`,
`collector.py` and the container build. Candidate enumeration and task identities
are unchanged. This is not the earlier standalone add-on.

## Mathematical certificate

For integer y, the identity

    y^2 = (x + 6*n)^2 + (36*n^3 - 65)/x

implies x divides 36*n^3-65. The reduced auxiliary denominator q divides |x|.
Thus every prime p dividing q must permit a root of 36*n^3 = 65 modulo p,
regardless of the signs of n and x.

For prime p == 1 (mod 3), excluding 5 and 13, a root exists exactly when

```python
pow(65, (p - 1) // 3, p) == pow(36, (p - 1) // 3, p)
```

There are 733 additional obstructing primes strictly below 20,000, starting
7, 19, 31, 37, 43, 67, 73, 79, 97, 127. The implementations generate them from
this criterion and reject q when its gcd with their product exceeds one.
All arithmetic is exact, including production-size denominators. No denominator
factorization is required. The finite prime cutoff can only weaken the sieve.
Primes 5 and 13 have the root zero and are not rejected. Existing filters for
2 and 3 and non-coprime a,q remain unchanged.

## Modes and accounting

The supervisor checks the sieve before dispatching a fibre to the native worker.
A rejection advances the original index once and uses the common checkpoint
path. Neither selected-numerator nor general-a/q enumeration is renumbered.

The diagnostic counter `q_sieve_excluded` is a SUBSET of `congruence_excluded`,
not an additional coverage category. The updated collector accepts this optional
counter, checks its parent category and rejects nonzero sieve counts in rational
mode. Historical outputs without this counter remain readable. Use the updated
collector with new outputs: the old collector rejects unknown counter keys.

The native worker independently checks the same obstruction after input
validation. An obstructed fibre produces a normal successful, empty reply with
`excluded_by_q_sieve=true`, `excluded_by_congruence=true`, and zero convergents.
The equation still implies this obstruction under `--relax-congruences` when an
integer radical is required.

The sieve is NEVER applied in rational-root mode. Historical schema-v2 tasks
without `require_integer_sqrt` still mean rational roots are allowed. The known
rational-root solution n=-5877899, x=11122866225 has an auxiliary denominator
containing obstructing prime 79; a regression test preserves that solution.

## Build and validation

From this directory:

```sh
sha256sum --check SHA256SUMS
make clean
make -j2
make test
```

The Makefile tracks `src/q_sieve.hpp`. The Docker runtime includes `q_sieve.py`;
the build stage includes Dockerfile for the packaging regression test. Rebuild
the executable and image; do not reuse an older binary or container.

The additional tests cover independent exhaustive residue classification,
Python/C++ agreement, huge denominators, special primes, all sign selectors,
rational mode, pre-dispatch rejection, unchanged ranks, resumed coverage,
collector counters and packaging. Two pre-existing precision tests now use
10000000009 instead of 10000000001: the latter contains obstructing prime 3541
and is correctly proved empty before continued fractions. A new test retains
that old denominator specifically to check the successful-empty shortcut.

The PR workflow runs the full suite and a Docker build/runtime check and retains
source and validation evidence. It publishes no release and submits no Charity
Engine work. Historical records under `validation/` are not results of this
revision; consult its actual test and CI logs.

## Existing campaigns

Worker SHA256 pins and checkpoint validation remain enforced. Continuations
pinned to an old worker will reject the rebuilt binary. Finish them with their
original image or use an explicitly audited campaign transition. Do not remove
hash checks to force a resume. Candidate indices themselves remain stable.

A reduction in denominator count is not a measured runtime speedup: existing
filters, numerator counts and per-fibre costs affect the saving. Calibrate the
rebuilt image with a small CE pilot before scaling up.
