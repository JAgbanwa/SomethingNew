# run6 — extending the divisor search above `|n| = 1.486·10⁹`

All runs use `search/search_xl.c` (binary `search_xl`) through `launch2.sh`, exactly as in
`run4`:

```
[K=..] [BUDGET=..] [CHUNK=..] [NW=..] ./launch2.sh <lo> <hi> <tag>
```

`K` is the ratio bound (`|x| ≤ min(13n², K|n|)`), so `K = 10¹¹` means the **complete** `x`
range in this region; `BUDGET = 0` leaves the cofactor that the line sieve (primes `≤ 3·10⁷`)
returns unsplit, as in the earlier sweeps.

| tag | range of `\|n\|` | `x`-range | outcome |
| --- | --- | --- | --- |
| `h` | `[1.502·10⁹ , 1.610·10⁹]`, both signs, contiguous | full | nothing |
| `gap` | `[1.486·10⁹ , 1.502·10⁹]`, both signs | full | nothing |
| `gap2` | `[1.610·10⁹ , 1.616·10⁹]`, both signs | full | nothing |
| `c` | `[1.616·10⁹ , 1.744·10⁹]`, both signs | `\|x\| ≤ 10⁴\|n\|` | nothing |

Together with `run4`/`run5` the complete-`x` sweep is therefore contiguous for
`|n| ≤ 1.616·10⁹` (both signs), and the `c` run covers `1.616·10⁹ ≤ |n| ≤ 1.744·10⁹` in the band
`|x| ≤ 10⁴|n|`, which contains every solution known (their ratios `|x|/|n|` lie between
`0.17` and `2058`).  As always the `n` for which `36n³-19` has more than `2·10⁶` divisor
combinations are skipped and listed in the `err_*.txt` logs, and the unsieved cofactor of
`36n³-19` is treated as a single factor, so these runs are thorough searches rather than
proofs.  The contiguous prefix actually finished by each worker can be read off the
`prog_*.txt` files (one line per completed chunk).
