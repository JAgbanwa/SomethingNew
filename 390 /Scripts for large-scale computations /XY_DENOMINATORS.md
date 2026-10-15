# Corrected target: sixths for n, equal reduced denominators for x and y

This supersedes the earlier n/x common-denominator proposal (PR #3), which
addressed an incorrectly stated requirement. Do not use that proposal's task
schema for this target. The original integer-search files remain unchanged.

## Target and scope

Search rational d satisfying the original unsquared equation

```
36*n^3-65 = -2*d*x^2*(y-(x+6*n)),
y = sqrt((x+6*n)^2+(36*n^3-65)/x), y >= 0.
```

The corrected requirements IN LOWEST TERMS are

```
den(n) in {1,2,3,6}, den(x) = den(y) = b, b >= 1.
```

There is no requirement that den(n)=b; b is not restricted to 1,2,3,6. Write
k=6*n (an integer), x=X/b and y=Y/b, with gcd(|X|,b)=gcd(Y,b)=1. The output n=k/6
is reduced. All four n denominators are searched inside every fiber by default;
a deliberately selected subset is part of task identity. All four signs of n,x
are allowed by default; y is always nonnegative. Every rational d is eligible
unless --noninteger-d is selected. There is no independent square-root policy:
b=1 forces integral x,y; b>1 forces both to be nonintegral with denominator b.

Bounds apply to the rational VALUES. Defaults remain 10^43 <= |n| <= 10^45 and
10^54 <= |x| <= 10^55. The internal k bounds are SIX times the n bounds; the X
bounds are b times the x bounds. The fast enclosure supports positive integer
endpoints with n_min>=2, x_min>6*n_max and derived slope upper bound below 2.
Unsupported rectangles are rejected, not reported as an empty complete search.
The original production rectangle satisfies these conditions.

Fractional certificates are not automatically integer sums of three cubes.
Any transformation back to that problem still needs its integrality checks.

## Exact equation and independent verification

Substitution without approximation gives

```
6*X*(Y^2-(X+b*k)^2) = b^3*(k^3-390),
d = -(Y+X+b*k)/(2*X).
```

Since 390 is not an integer cube, k^3-390 is nonzero, justifying rationalization
for d. The independent Python verifier uses the ORIGINAL rational radicand,
checks exact squares of its reduced numerator and denominator, reconstructs the
principal root, and verifies the original unsquared equation, d, gap, denominators,
bounds and signs. Each supplied fraction must already be reduced. Floating point
is used only for timing, never for acceptance.

## Complete slope enclosure for a fixed b

Put K=|k|, V=|X|, tau=sign(k*X), and

```
a/q = abs(y/abs(x)-1+6*n/x), gcd(a,q)=1.
```

Because Y,V,b*k are integers, q divides V and q<=V_max=b*x_max. Coprimality of
X and b also implies gcd(q,b)=1. Let Delta=Y-|X+b*k|. In the supported bounds,
sign(Delta)=tau, Delta is a nonzero integer, and

```
a/q = (2*b*K+abs(Delta))/V.
```

Set K_min=6*n_min, K_max=6*n_max, V_min=b*x_min, V_max=b*x_max and

```
G = floor(b^3*(K_max^3+390)/(6*V_min*(V_min-b*K_max))),
M_min = 2*b*K_min+1, M_max = 2*b*K_max+G.
```

The identity for Y^2 bounds |Delta| between 1 and G. Every target slope is
therefore in the following enclosure, which the generator enumerates:

```
1 <= q <= V_max,
ceil(M_min*q/V_max) <= a <= min(floor(M_max*q/V_min), M_max).
```

G=0 proves the rectangle empty. The generator requires M_max/V_min<2; the
production bound is much smaller than 1. Supporting slopes between 1 and 2
also permits genuine small correctness fixtures, without losing the positive
cubic derivative. No old a/q parity or modulo-3 shortcut is inherited.

Rows are ordered by q, then a. Noncoprime pairs and sieved denominators remain
indexed and advance through the common checkpoint path. Exact affine floor
sums provide counts, ranking and streaming without allocating the parameter
space. Completing a prefix covers only that prefix at the selected b.

## Safe reuse of the 733-prime sieve

The cleared equation and gcd(X,b)=1 imply X divides k^3-390. Thus every prime
p dividing q requires k^3=390 (mod p). For p>3 the substitution k=6*t identifies
this with 36*t^3=65 (mod p). The same 733 obstructing primes below 20,000 are
safe here, INCLUDING fractional y. Separate helpers reuse the prime list under
this NEW proof; the original integer-y guard is not reinterpreted as safe for
arbitrary rational radicals. Primes 5 and 13 remain allowed by this sieve, and
2 and 3 are not rejected indiscriminately. gcd(q,b)>1 has a separate counter.

X divides k^3-390 also gives a necessary finite ceiling for b within the bounded
rectangle:

```
b <= floor(((6*n_max)^3+390)/x_min).
```

This is a mathematical ceiling, not an arbitrary small cutoff. The program does
not claim it has processed all b below it. Each finite campaign selects ONE b;
other b values need separate campaigns. All four requested n denominators are
covered inside each completed fiber, not in four overlapping index sequences.

## Native cubic and continued-fraction completeness

For each slope the GMP worker considers allowed sign branches and solves

```
F_tau(K,V) = b^3*q^2*K^3 + 12*b*q*(2*q+tau*a)*K*V^2
             - 6*a*(2*q+tau*a)*V^3
           = sign(k)*390*b^3*q^2.
```

For f(t)=F_tau(t,1), c1=12*b*q*(2*q+tau*a) and T=390*b^3*q^2, the assumption
0<a<2q ensures c1>0. There is a unique positive root alpha, with f'(t)>=c1>0
for t>=0. At a target point the mean value theorem gives

```
|K/V-alpha| < T/(c1*V^3).
```

Writing K=g*u,V=g*v with gcd(u,v)=1 gives the Legendre criterion
|u/v-alpha|<1/(2*v^2) whenever V>2*T/c1, because g^3*v=g^2*V>=V.
The worker therefore scans the exceptional physical numerator values exactly:

```
V <= floor(2*T/c1) = floor(65*b^2*q/(2*q+tau*a)).
```

It visits only multiples of q coprime to b inside the task bounds and uses
binary search in K. Beyond the threshold every solution must be recovered by
certified continued-fraction convergents, with the common scale g reconstructed
by an exact perfect-cube test. Nonprimitive k,X are included. An unfinished
fallback or insufficient precision is NEVER certified as empty and complete.
For very large b the fallback can be expensive; runtime must be piloted.

## Explicit optional congruences

The corrected target defaults to --congruence-policy none. It does not silently
apply old integer congruences to fractions. Two optional, narrower searches are
available. For REDUCED n=N/r and x=X/b:

* numerators: N=1 mod3, X=5 mod12 and X!=0 mod7.
* rational-mod: require gcd(r,3)=gcd(b,84)=1; then N=r mod3,
  X=5b mod12 and X!=0 mod7. Explicitly choose only n denominators 1 and/or2.

Incompatible inverse-denominator policies produce configuration errors. These
restricted modes do not cover the entire corrected target. Historical integer
tasks retain their own original schemas, policies and entrypoint unchanged.

## Build, generate, run and verify

From this directory, with Python 3.10+, a C++17 compiler, make and GMP installed:

```
make -j2
make test
python3 xy_campaign.py --campaign-id ce390-xy-b84-pilot --xy-denominator 84 \
  --n-denominators 1,2,3,6 --congruence-policy none \
  --candidates-per-task 30000 --task-count 1 --seconds 3600 \
  --output-dir xy-tasks
python3 run_xy_task.py --task xy-tasks/task-000000000000-*.json --output-dir xy-output
python3 collect_xy.py --page xy-tasks/page-000000000000.json \
  --results-dir xy-output --output-dir xy-collected
python3 verify_xy.py xy-collected/hits.jsonl --task xy-tasks/task-000000000000-*.json
```

84 is an example x/y denominator, not a predicted solution location. There is no
need for four jobs to cover the four n denominators. For another page keep the
campaign settings fixed and change --page-start (a task ordinal). To change b,
choose a different campaign ID and output directory. No script submits jobs.

examples/xy-pilot is a 30,000-index slice at b=84 in the original huge bounds.
examples/xy-diagnostic is a deliberately small restricted-q correctness check:
its 111 indices recover n=-65, x=5785/6, y=3391/6, d=-3418/5785. This is outside
the production bounds and is not a claimed integer 390 solution. Regression
fixtures also recover reduced n denominators 2,3 and6, with distinct b values.

## Checkpoints and Charity Engine

Use the corrected runner/collector/verifier, not the old integer tools or PR3
n/x tools. Output includes task.json, status.json, checkpoint.json, hits.jsonl,
run.log, and continuation.task.json when work remains. Preserve earlier output
batches. Continuations pin both the C++ binary and relevant Python sources. A
new host does not claim an earlier host's unreturned prefix.

The coverage categories are search_fibers_completed (CF OR exact fallback),
non_coprime_skipped, denominator_excluded, congruence_excluded, bounds_excluded.
q_sieve_excluded is a SUBSET of congruence_excluded, never an extra category.
fibers_completed counts worker replies. Exit zero can mean an intentional
partial result; inspect status.json and retain the continuation.

The Dockerfile builds both workers and includes the new tools. The old default
entrypoint stays unchanged. A NEW image containing this code is required for CE:

```
python3 /app/run_xy_task.py --task /local/input/task.json --output-dir /local/output
```

Use the existing operational guidance: allow two external hours for a task with
a 3,600-second internal budget. Do not reuse an image without run_xy_task.py.
No existing reservation or published image is modified by these source changes.
Build/test/deployment claims require actual evidence, not this document alone.
