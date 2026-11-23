# CE375: derivation for the fixed-g primitive-point search

## 1. Search contract

Production campaigns enumerate reduced fractions `p/q`, `q > 0`, over their
assigned height interval and solve only **`g = -1` and `g = +1`**. This is a
specified restriction on the auxiliary parameter.

Either point type is acceptable:

* Integers `n, x, y`, with `x != 0` and `gcd(n, x, y) = 1`.
* Integer `n`, with `x = X/2`, `y = Y/2`, odd nonzero `X`, odd `Y`, and
  `gcd(X, Y) = 1`.

The cases are alternatives, and `desired` is the point-primitivity flag for
the applicable case. Both signs of `y` describe the same squared equation.
The target constant is `K = 375`; other odd `K = +/-3 (mod 9)` are supported
for known-answer tests.

## 2. Original equation and cube identity

Put `S = 6n+3` and

```text
N(n) = 36n^3 + 54n^2 + 27n + (27-K)/6 = (S^3-K)/6.
```

For `K = 375`, this is `36n^3 + 54n^2 + 27n - 58`. With signed square root
`s`, set

```text
A = -x+s,    B = -x-s,    C = 2x+S.
```

Direct expansion gives

```text
A^3+B^3+C^3-K = -6x * (s^2 - (x+S)^2 - N/x).
```

Thus a point of the original equation produces an integer cube
representation `A^3+B^3+C^3 = K`. In the half-integer case the cube components
are integers because `X` and `Y` are odd. Also `A+B+C = S`.

## 3. Auxiliary fraction and the two fixed-g cubics

Let

```text
u = A+B = -2x,    w = A+C = x+s+S,    v = B+C.
d = w/u = -(x+s+S)/(2x).
```

Writing `d = p/q` in lowest terms with `q > 0` gives

```text
u = qg,    w = pg,    v = 2S-(p+q)g.
```

Using `S^3-K = 3uvw` yields

```text
F(S,g) = S^3 - 6pq S g^2 + 3pq(p+q)g^3 = K.
```

For the specified production values `g = -1,+1`, this becomes the pair of
monic cubics

```text
S^3 - 6pq S + 3pq(p+q)g - K = 0.
```

For each sign, the worker finds every integer root by exact bounds and root
search on the polynomial's monotone intervals. It needs no continued-fraction
denominator range for these production calculations. Reconstruction is

```text
n = (S-3)/6,    x = -qg/2,    s = (2p+q)g/2-S,    y = abs(s).
```

Even `q` gives integer `x,y`; odd `q` gives odd half-integers. Both signs of
`g` must be tried. Since `q > 0`, they also cover both signs of `x`.

The `xy` modes accept either sign of `s`. Each point has a principal and a
conjugate fraction, obtained from `s = +y` and `s = -y`. Their reduced
fractions, and their corresponding g values, need not be equal. Certificates
therefore distinguish the displayed principal `d` from the actual
`thue_p`, `thue_q`, and `g` used to find the point. The unit-g check applies
to the latter, so a valid conjugate-branch discovery is not rejected.

## 4. Point primitivity

The exact point tests are

| Chart | Point gcd | Accepted when |
| --- | --- | --- |
| Integer | `gcd(n, x, y)` | gcd equals 1 |
| Half-integer | `gcd(X, Y)` | gcd equals 1 |

In particular, the integer test uses all three coordinates. A common factor
of `n` and `x` alone does not reject a point if it does not also divide `y`.
For example, the test target `K = 12687` has `n = 5, x = -5, y = 3`,
`p/q = 31/10`, `g = 1`: its point gcd is 1 although `gcd(n,x) = 5`.

Cube primitivity is recorded independently. From

```text
A = (p+q)g-S,    B = S-pg,    C = S-qg
```

one gets the exact identities

```text
abs(g) = gcd(A+B,A+C),    gcd(A,B,C) = gcd(S,g).
```

The fixed-g restriction therefore makes the cube gcd 1 automatically.
The unit-g restriction and the point-gcd tests remain separate parts of the
search contract; one is not used as a substitute for the other.

## 5. Necessary arithmetic filters

At `K = 375`, cubes modulo 9 force `A = B = C = -1 (mod 3)`.
Consequently `S = 3 (mod 6)`, and cubes modulo 27 further give
`n = 2 (mod 3)`. Thus reconstructed `n` is an integer.

The worker retains necessary fraction filters:

* `gcd(p,q) = 1`, `p != 0`, `q > 0`.
* `3` divides neither `p` nor `q`, and `p = q (mod 3)`.
* For primes `l = 1 (mod 3)` outside `K` dividing `p` or `q`, `K` must be a
  cubic residue modulo `l`.
* The existing local-solvability tables may reject a fraction only when no
  primitive solution exists. Since `g = +/-1` implies `gcd(S,g) = 1`, these
  necessary primitive-solution filters remain valid for the fixed-g search.
* `xy-half` additionally requires odd `q`.

The independent Python verifier checks each reported point again against
the original equation, the reconstruction, and the applicable gcd.

## 6. Coverage and run records

A completed task covers

```text
h_start <= max(abs(p),q) < h_stop,    g in {-1,+1},
```

with its chosen mode. It does not impose a guessed interval on `n` or `y`.
For every returned point, `abs(x) = q/2`; the height interval is not a claim
of complete coverage of all points below an x bound.

Version-2 tasks, statuses, checkpoints, and collection results record the
fixed set `g_values = [-1,1]`. Version-1 large-range tasks are rejected instead
of being silently reinterpreted. A finite height task is complete only after
all of its shells have finished; deadlines and interruptions leave explicit
remaining work.

Historical pilot files preserve the previous program's results and scope.
They are not edited to claim that the new program has been run. Tests on
small known targets, both y branches, and an independent divisor search on
the original equation establish the corrected behavior on those fixtures.

## 7. General raw solver retained for regression checks

The separate raw interface accepts a target `T`, explicit fractions `p/q`,
and a positive finite `G` for comparisons with PARI/GP. Its general Thue
solver uses exact root isolation and certified continued fractions, with
small denominators checked directly. This interface is not called by the
fixed-g campaign, and its results do not count as production coverage.
