# Local pilot: k = 192, heights 1 <= H < 4000

Run on 4 Nov 2026 on the development host (shared two-core cloud VM, the two
tasks in parallel), worker version 1.0.0, with the production pipeline:

```sh
python3 make_campaign.py --campaign-id ce192-local-pilot --h-stop 4000 --task-hours 0.05 --output-dir pilot
python3 run_task.py --task pilot/tasks/ce192-local-pilot-0.json --output-dir pilot-res/ce192-local-pilot-0
python3 run_task.py --task pilot/tasks/ce192-local-pilot-1.json --output-dir pilot-res/ce192-local-pilot-1
python3 collect.py --results pilot-res --page pilot/page.json --output-dir pilot-col
python3 verify_hits.py pilot-col/hits.jsonl
```

| Quantity | Value |
| --- | --- |
| Raw pairs `(p, q)` | 31,988,001 |
| Admissible `d` solved | 1,226,189 (3.83 %) |
| Convergents tested | 239,050,626 |
| Precision refinements / exact roots | 0 / 0 |
| `g` bound | `1 <= abs(g) <= 10^100` |
| Coverage / gaps | `[1, 4000)` / none |
| Elapsed | 173.9 s + 99.1 s = 273 s (8.5 us/pair) |
| **Hits** | **3** (integer chart 3, half chart 0) |

| `d` | chart | `n` | `x` | `s` | cube components |
| --- | --- | ---: | ---: | ---: | --- |
| `1` | integer | 2 | -4 | 0 | 4, 4, 4 |
| `-1/8` | integer | 2 | -16 | 0 | 16, 16, -20 |
| `-8` | integer | 2 | 2 | 18 | 16, -20, 16 |

These are exactly the `d` predicted from `192 = 4^3 * 3` and the two small
representations of 3 (DERIVATION.md §5). No other rational `d` with height
below 4000 has a point, in either chart, with `|g| <= 10^100`
(i.e. `|x| <= q * 10^100 / 2`). All three were also certified with no bound on
`g` by `tools/certify_d.gp`.

Files: `pilot-h4000-summary.json` (collector output), `pilot-h4000-hits.jsonl`
(verified hits), `pilot-h4000-d_values.txt`; task files in `examples/pilot/`.
