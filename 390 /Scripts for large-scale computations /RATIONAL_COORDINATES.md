# Equal reduced rational coordinate denominators

This is an opt-in extension to CE390. The old integer-coordinate programs,
integer task identities, and the default container entrypoint remain unchanged.
Use `rational_campaign.py`, `run_rational_task.py`, `collect_rational.py`,
`verify_rational.py`, and `bin/rational_cf_worker` for the new task schema.

## Scope and explicit policies

The requested equation is unchanged:

```
36*n^3-65 = -2*d*x^2*(sqrt((x+6*n)^2+(36*n^3-65)/x)-(x+6*n)).
```

For an explicitly selected positive integer b, search rational d and

```
n=N/b, x=X/b, gcd(abs(N),b)=gcd(abs(X),b)=1, b>=1.
```

These are equal denominators AFTER reduction. Merely writing 2/6 and 3/6 with
the same displayed denominator would not qualify: their reduced denominators
are 3 and 2. Checking only gcd(N,X,b)=1 is insufficient. The implementation
checks the two coprimality conditions individually. b=1 includes integers.
The coordinate denominator b is different from the auxiliary slope denominator q.

The generator requires all three choices explicitly:

| Argument | Meaning |
| --- | --- |
| `--denominator B` | Both reduced coordinate denominators must equal this positive integer. |
| `--sqrt-policy integer` | Preserve the earlier requirement that the original principal radical y is an integer. |
| `--sqrt-policy rational` | Allow all nonnegative rational principal radicals, including nonintegers. This is a broader target. |
| `--congruence-policy none` | No residue restrictions on the rational coordinates or their numerators. |
| `--congruence-policy numerators` | Apply the old residues to signed N,X: N=1 mod 3, X=5 mod 12, X!=0 mod 7. |
| `--congruence-policy rational-mod` | Require gcd(b,84)=1 and interpret rational residues using inverses of b. Equivalently N=b mod 3, X=5b mod 12, X!=0 mod 7. |

An incompatible `rational-mod` denominator, such as 2 or 51, is rejected as a
configuration error; it is not silently reinterpreted or skipped. At b=1 the
two residue conventions agree. All four coordinate signs are allowed by default;
`--signs` can restrict them. All rational d are eligible; `--noninteger-d`
optionally excludes integer d.

Bounds still apply to the VALUES |n| and |x|. Defaults are
`10^43 <= |n| <= 10^45` and `10^54 <= |x| <= 10^55`; numerator intervals are
multiplied by b. Custom bound endpoints are positive integer strings, as in the
old program. The slope enclosure requires n_min>=2, x_min>6*n_max and the derived
upper slope below 1. Unsupported custom rectangles produce an error, not an
empty-complete result. The original production bounds satisfy these conditions.

Fractional-coordinate solutions are not automatically solutions of the earlier
integer-coordinate problem or integer cubes summing to 390. Any back-transformation
must still establish that problem's original integrality conditions.

## Exact change of variables and independent verification

Let N,X be signed, Y=b*y, A_b=36*N^3-65*b^3, and S_b=X+6*N. Direct substitution gives

```
Y^2 = S_b^2 + A_b/X,
d = -(Y+S_b)/(2*X).
```

The constant is now **65*b^3**, not 65. Dividing an old solution's coordinates
by b without changing this numerator equation is wrong. The supported bounds
ensure 36*n^3-65 is nonzero, justifying the cancellation used for d.

The independent verifier uses only the original equation and the integer

```
M = X^2*(X+6*N)^2 + (36*N^3-65*b^3)*X.
```

A rational principal radical exists exactly when M is a nonnegative exact square
m^2; then y=m/(b*abs(X)). This follows because b*abs(X)*y is rational with integer
square, hence is an integer. The verifier also checks the original unsquared
equation, the exact d and gap, magnitudes, signs, policies and reduced denominators.
All acceptance decisions use GMP/Python integers and rationals, not floats.

**Integer Y is not sufficient for integer y.** Integer-root mode checks y's own
reduced denominator, equivalently b*abs(X) divides m. The weaker q|abs(X) filter
is necessary, not sufficient.

## Fixed-denominator parameter coverage

Put U=abs(N), V=abs(X), tau=sign(N*X), and

```
a/q = abs(y/abs(x)-1+6*n/x), gcd(a,q)=1.
```

In the supported rectangles, with Delta=Y-abs(X+6*N), sign(Delta)=tau and
`a/q=(12*U+abs(Delta))/V`. Using scaled bounds U_min,U_max,V_min,V_max,

```
K = (36*U_max^3+65*b^3)/(V_min*(V_min-6*U_max))
```

bounds abs(Delta). For integral y, Delta is a nonzero integer: the conservative
slope limits are L=(12*U_min+1)/V_max and T=(12*U_max+floor(K))/V_min. K<1 excludes
the integer-root region. For rational y use L=12*U_min/V_max and
T=(12*U_max+K)/V_min. The generator requires 0<L<=T<1 and enumerates every
integer numerator `ceil(L*q) <= a <= floor(T*q)`.

No old oddness or coprimality-to-6 rule is assumed for a,q. Noncoprime pairs stay
indexed and are rejected before dispatch. Exact affine floor sums provide
logarithmic prefix counts and ranking; no enormous parameter array is allocated.

For integral y, q divides V and q<=V_max. For rational Y=u/v in lowest terms,
v^2 divides V, and q divides v*V; therefore a sufficient bound is
`q<=V_max*floor(sqrt(V_max))`. The old q<=V_max bound is unsafe for rational roots.
A restricted q window requires `--allow-q-window` and covers only that window.

## Continued-fraction completeness and the changed fallback

The native worker solves

```
H_tau(U,V) = 36*q^2*U^3+12*q*(2*q+tau*a)*U*V^2-a*(2*q+tau*a)*V^3
          = sign(N)*65*b^3*q^2.
```

The positive root alpha of H_tau(t,1)=0 is the same as in the original engine;
its derivative exceeds 12*q^2. Consequently
`abs(U/V-alpha)<65*b^3/(12*V^3)`. With g=gcd(U,V), Legendre's sufficient condition
holds when `65*b^3<6*g^2*V`, in particular when `V>65*b^3/6`. Certified convergents
are tested using exact cube recovery from `65*b^3*q^2/abs(H_tau(u,v))`.

For every smaller V up to floor(65*b^3/6), the worker performs an exact binary
search in U for each signed target. Keeping the old fallback V<=10 would miss
solutions. The tests include a genuine fractional solution that is not a
convergent and is recovered by this enlarged fallback. Redundant CF work is
skipped when the fallback already covers the whole requested V interval.

For extremely large b the fallback can be impractically expensive. The deadline
still stops a job, but an unfinished fiber is replayed rather than marked complete.
No practical throughput guarantee is made for arbitrary b. Precision limits and
interrupted fibers never produce empty-complete certificates.

## The 733-prime sieve

It is disabled in unrestricted rational-root mode. In integer-root mode, integral
Y implies q|V and V|(36*N^3-65*b^3). Because gcd(V,b)=1, a prime p|q cannot divide b.
Reducing modulo p then implies `36*(N/b)^3=65 mod p`, so the original obstructing
prime list remains a valid necessary exclusion. This argument depends on the
reduced-coordinate conditions; it does not pretend the rational coordinates
are integers. Both runner and native worker enforce the mode guard. Rejections
preserve original indices; `q_sieve_excluded` is a subset of congruence exclusions.

## Generate and run a finite campaign

Build and test from the package directory:

```sh
make -j2
make test
```

Example preserving integer-root integrality and modular-inverse residues, at b=5:

```sh
python3 rational_campaign.py --campaign-id ce390-rational-b5-pilot \
  --denominator 5 --sqrt-policy integer --congruence-policy rational-mod \
  --candidates-per-task 30000 --task-count 1 --seconds 3600 \
  --output-dir rational-b5-tasks
python3 run_rational_task.py --task rational-b5-tasks/task-000000000000-*.json \
  --output-dir rational-b5-output
```

For the broader rational equation, `examples/rational-pilot/` uses b=2,
`--sqrt-policy rational --congruence-policy none`, the original huge magnitude
bounds, and 30,000 indices. This is an example denominator, not a predicted one.
Each campaign binds one exact b. Generate separate campaigns for other positive
b values, including b=1, and use separate output directories. Infinitely many
b>=1 cannot be exhausted by a finite pilot. Completed prefixes cover only those
indices at their selected b, not all fractions or the full region. Generating
pages never submits CE jobs or commits to the manifest's total workload.

Use new tools to validate rational results:

```sh
python3 collect_rational.py --page rational-b5-tasks/page-000000000000.json \
  --results-dir rational-b5-output --output-dir rational-b5-collected
python3 verify_rational.py rational-b5-collected/hits.jsonl \
  --task rational-b5-tasks/task-000000000000-*.json
```

The collector can combine pages and new-host continuations; the standalone
verifier above checks certificates under one task. Preserve all returned output
batches. `continuation.task.json` pins both the native worker and relevant Python
sources. Never remove these checks to force a resume. The legacy integer
collector/verifier reject the new schemas rather than reinterpret fractions.

## Docker and Charity Engine

The Dockerfile builds both workers and includes the new Python tools. The legacy
entrypoint remains unchanged. After building and publishing a NEW tested image,
the explicit CE command for a staged file named task.json is:

```text
python3 /app/run_rational_task.py --task /local/input/task.json --output-dir /local/output
```

The old published image does not acquire new functionality automatically. Rebuild
with `docker build -t ce390:rational-common .` and test before publication. Keep
the exact image for all continuations. Use the existing deployment convention of
a two-hour external allowance for a 3,600-second internal budget. This extension
does not submit or change a CE job. Native test success, Docker validation and
actual CE execution are separate claims.

## Nonempty diagnostic test, not a production hit

A verified example of the broader rational equation is

```
n=110/51, x=-2341/51, y=1676/51, d=-5/4682.
```

Both coordinate fractions are reduced with denominator 51. Its radical is NOT
an integer; it also does not meet the original residues or huge magnitude bounds.
It is a correctness fixture, not an integer 390 solution or production result.
`examples/rational-smoke/` selects n magnitudes [2,3], x magnitudes [40,50], q=2341,
rational roots, no residues, and 1,052 indices. Run it with

```sh
python3 run_rational_task.py --task examples/rational-smoke/task-*.json \
  --output-dir rational-smoke-output
```

The test suite checks exact original-equation oracles, large parameter ranks,
legacy b=1 compatibility, all sign policies, both radical modes, the nonconvergent
fallback fixture, sieve safety, input validation, source and binary pins,
checkpoint recovery, actual deadline interruption, and gap-free collection.
The PR workflow also runs this nonempty job in the built Docker runtime and
independently verifies its returned certificate. Consult the actual CI evidence
for the result, not merely the existence of these instructions.
