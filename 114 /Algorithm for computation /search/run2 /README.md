# Search run extending the range to `|n| ≤ 8·10⁹`

Program: `../search_sv.c` (compiled as `../sv_new`), the sieve-accelerated divisor search; for
each `n` it considers **all** integers `x` allowed by the bound `|x| ≲ 13n²`
(`DEquation.sat_abs_x_le_poly`).

Ranges covered in this run (both signs, contiguous, joining the earlier runs which had reached
`n ≤ 3.583·10⁹` and `n ≥ -3.835·10⁹`):

| file | `n` range |
| --- | --- |
| `gap_p.txt` | `3.583·10⁹ … 3.590·10⁹` |
| `p_0.txt` … `p_3.txt` | `3.590·10⁹ … 7.010·10⁹` |
| `p_4.txt`, `p_5.txt` | `7.000·10⁹ … 8.000·10⁹` |
| `gap_m.txt` | `-3.840·10⁹ … -3.835·10⁹` |
| `m_0.txt` … `m_3.txt` | `-7.000·10⁹ … -3.840·10⁹` |
| `m_4.txt`, `m_5.txt` | `-8.000·10⁹ … -7.000·10⁹` |

**Result: no new solutions.** All the output files are empty; the list of ten solutions in
`../../SEARCH_NOTES.md` is unchanged.

`skipped_n.txt` lists the 699 984 values of `n` (about one in 12 000 of the ≈8.6·10⁹ values
scanned) for which `36n³-19` had more than 2·10⁶ divisor combinations and which were therefore
skipped; those values remain unchecked. For large `n` the sieve (primes up to 3·10⁷) can also
leave an unfactored cofactor, so the run is thorough but not provably exhaustive.
