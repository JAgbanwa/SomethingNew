# run4 / run5 — the large-`x` sweeps

All runs use `search/search_xl.c` (`search_xl`, and `search_xlf` for the list mode), the
divisor-pair search *without* the 128-bit cut-off on `|x|`.  `launch2.sh` is the driver:

```
[K=..] [BUDGET=..] [CHUNK=..] [NW=..] ./launch2.sh <lo> <hi> <tag>
```

It runs `NW` workers per sign over `|n| ∈ [lo,hi]` in interleaved chunks, so that stopping
early still leaves a nearly contiguous covered prefix.  `K` is the ratio bound
(`|x| ≤ min(13n², K|n|)`), `BUDGET` the Pollard-rho budget used to split the cofactor that
the line sieve (primes `≤ 3·10⁷`) leaves behind.

| tag | range of `\|n\|` | `x`-range | outcome |
| --- | --- | --- | --- |
| `d`, `d2`, `g`, `g2`/`g3` | `[3·10⁷ , 1.486·10⁹]` (contiguous, both signs) | full (`\|x\| ≤ 13n²`) | re-found `(-516368250,55022141248)`; nothing new |
| `f` | `[10⁶ , 3·10⁷]` | full | re-found `(-1160307,-10431164)` and `(12512774,2548980)`; nothing new |
| `e` | `[1.1·10⁹ , 1.33·10⁹]` | `\|x\| ≤ 10⁴\|n\|` | nothing |
| `sk` (run5) | all `n` skipped by every earlier run with `\|n\| ≤ 1.07·10⁹` (83 500 values) | full, rho budget 2·10⁵, combination cap 2·10⁷ | nothing |

Together with the earlier runs the covered region is now

* `|n| ≤ 1.486·10⁹` with the **complete** `x`-range `|x| ≤ 13n²` (tags `f`, `d`, `d2`, `g`, `g3`),
* `|n| ≤ 8·10⁹` with the much smaller range `|x| ≤ 2¹²⁵/|A|` of the earlier programs,
* every `n` that the earlier runs skipped because `36n³-19` had more than 2·10⁶ divisor
  combinations, for `|n| ≤ 1.07·10⁹`, with the complete `x`-range and with the sieve
  cofactor factored completely (run5).

The only solution in `10⁶ ≤ |n| ≤ 1.486·10⁹` is the one found in the previous run,
`d = -14123191460839/14966022419456`, `(n,x) = (-516368250, 55022141248)`; the sweeps
re-found it, which is one of the consistency checks of the program.

Caveat that remains: with `BUDGET=0` the sweeps treat the unsieved cofactor of `36n³-19` as
one opaque factor, which costs roughly 15% of the divisor combinations at `|n| ≈ 10⁸`
(`search/facstat.c`).  The run5 pass had the cofactor split completely, but only for the
skipped `n`.
