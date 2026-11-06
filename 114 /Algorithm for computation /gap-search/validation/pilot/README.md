# Gap-search pilot, k = 114 (6 Nov 2026)

Development host, 2 cores, worker 1.0.0, R = 64, through the production pipeline
(plan, run, collect `--require-complete`, audit 5%, `to_d.py`). Task files are in `../../examples/pilot/`.

| Quantity | Value |
| --- | --- |
| Covered | `δ = |a+b|` in [185185185185185186, 185185187185185186), `3.847δ <= |c| <= 64δ` |
| `δ` values | 2,000,000,000 (gaps: none) |
| Worker time | 0.173 core-hours (0.31 µs per `δ`; the host was shared during the run) |
| Audit | 6/6 sampled chunks reproduce exactly |
| Representations of 114 found | 0, so no `d` of result 1 or 2 from this slice |

Heuristic expectation for this slice: 4.8e-10.
