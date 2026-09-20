This project was edited by [Aristotle](https://aristotle.harmonic.fun).

To cite Aristotle:
- Tag @Aristotle-Harmonic on GitHub PRs/issues
- Add as co-author to commits:
```
Co-authored-by: Aristotle (Harmonic) <aristotle-harmonic@harmonic.fun>
```


# Verified solutions

Each row is an exact solution of

```
36 n^3 - 65 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36 n^3 - 65)/x ) )
```

with `n, x` integers and `d` rational; `T = sqrt(D)`,
`D = x^2 (x+6n)^2 + x (36 n^3 - 65)`, and `d = (-x(x+6n) - sgn(x) T)/(2 x^2)`.
Every row is re-verified in exact rational arithmetic and machine-checked in
`RequestProject/Solutions.lean`.

| # | n | x | d | d (decimal) | denominator of d |
|---|---|---|---|---|---|
| 1 | -5 | 81 | `-913/1458` | -0.626200274348 | 1458 |
| 2 | -2960189 | 34556096 | `-262121371/552897536` | -0.474086704919 | 552897536 |
| 3 | 46219 | -394731 | `-144791/2368386` | -0.061134882574 | 2368386 |
| 4 | 1847965 | -16010260 | `-761139263/13896905680` | -0.0547704129629 | 13896905680 |
| 5 | 166 | -2500 | `-1103/250000` | -0.004412 | 250000 |
| 6 | 2047 | -45972 | `-599/551664` | -0.00108580585284 | 551664 |

### the radical value at each solution

| n | x | sqrt((x+6n)^2 + (36n^3-65)/x) | T |
|---|---|---|---|
| -5 | 81 | `454/9` | 4086 |
| -2960189 | 34556096 | `127761675/8` | 551868088302600 |
| 46219 | -394731 | `207460/3` | 27296964420 |
| 1847965 | -16010260 | `1375212717/434` | 50731597130130 |
| 166 | -2500 | `74097/50` | 3704850 |
| 2047 | -45972 | `201541/6` | 1544207142 |
