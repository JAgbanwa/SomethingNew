# Local pilot, mode xy (both charts): k = 375, heights 4000 <= H < 20000

Run on 22 Nov 2026 on the development host (shared two-core cloud VM, one core
per task), worker version 1.0.0, default campaign mode `xy`:

```sh
python3 make_campaign.py --campaign-id ce375-xy-both-pilot --h-start 4000 --h-stop 20000 \
  --us-per-pair 1.5 --task-hours 0.16 --output-dir camp
python3 run_task.py --task camp/tasks/ce375-xy-both-pilot-0.json --output-dir res/ce375-xy-both-pilot-0
python3 run_task.py --task camp/tasks/ce375-xy-both-pilot-1.json --output-dir res/ce375-xy-both-pilot-1
python3 collect.py --results res --page camp/page.json --output-dir col
```

| Quantity | Value |
| --- | --- |
| Raw pairs `(p, q)` | 767,952,000 |
| Admissible `d` solved | 8,842,868 (1.15 %) |
| Convergents tested | 1,724,703,242 |
| Precision refinements / exact roots | 0 / 0 |
| `g` bound | `1 <= abs(g) <= 10^100` (so `abs(X) <= q * 10^100`) |
| Coverage / gaps | `[4000, 20000)` / none |
| Elapsed | 809 s + 752 s = 1561 s (2.0 us/pair, both tasks in parallel) |
| **Hits / desired hits** | **0 / 0** |

Together with the mode-`both` pilot over `H < 4000` (3 hits, all
non-primitive), this means: **no desired point of either chart has a value of
`d` of height below 20,000** (within `|g| <= 10^100`). That is, no rational `d`
with `max(|num|, den) < 20000` comes from integers `n, x, y` with
`gcd(n, x) = 1` and primitive cubes, or from `x = X/2`, `y = Y/2` with `X, Y`
odd and `gcd(X, Y) = 1`.
