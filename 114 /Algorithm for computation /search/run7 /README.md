# run7 — continuation of the elliptic-curve scan over `x`

`search/ec_scan.py` fixes `x` and looks for the integers `n` with `V(n,x)` a square by
computing Mordell–Weil generators of the Mordell curve

```
Y² = Z³ - 432 x³ (x³ + 57),      Z = 36 x n + 12 x²,  Y = 36 x t,
```

with PARI (through `cypari`) and enumerating small combinations of the generators, keeping the
points whose `n` is an integer.  Unlike the divisor search over `n`, this can in principle
produce solutions with an arbitrarily large `n` for a moderate `x`.

The earlier run covered `|x| ≤ 12000` contiguously, plus `15001 ≤ |x| ≤ 16550`, and re-found
`(1,-9)`, `(-54,-9)` and `(909,784)`.  `launch_ec2.sh` starts the two ranges that were left
open:

| tag | range of `\|x\|` | outcome |
| --- | --- | --- |
| `a_p`, `a_m` | `[12001 , 15000]` | nothing new |
| `b_p`, `b_m` | `[16551 , 20000]` | nothing new |
| `c_p`, `c_m` | `[20001 , 21800]` (stopped there) | nothing new |

(`ec_*.txt` hold the hits, `ecerr_*.txt` the progress and the curves whose rank computation
failed.  The scan is a search, not a proof: `ellrank` is used with a bounded effort, only
small combinations of the generators are enumerated, and the ranges above are the ones
completed when the run was stopped.)
