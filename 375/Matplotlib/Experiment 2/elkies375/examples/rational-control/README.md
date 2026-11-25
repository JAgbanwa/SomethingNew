# Rational-only control at n = 13

Actual command:

```bash
python3 elkies375_lab.py --engine rational --n 13 --search-only \
  --backend sympy --factor-seconds 10 --csv examples/rational-control/points.csv
```

The separate fixed-n factor-pair engine proved the factorization
`N(13) = 61 * 1451`, completed its five factor-pair cases, and found one
`(n,x,|y|)` representation:

$$
n=13,\qquad x=-144,\qquad y=\pm\frac{695}{756}.
$$

For the positive-y branch, `S=81`, `S+x=-63` and `t=-695/12`. Its cube lift is

$$
\left(\frac{2423}{12},\frac{1033}{12},-207\right),
$$

whose cube sum is exactly 375. These are not all integers. This is a valid
rational point of the equation, not a primitive integer-cube solution.

This control deliberately has `n mod 27 = 13`, outside the integer-cube
admissibility classes. It demonstrates why those modular restrictions must
not be used to discard general rational-only points.

[points.csv](points.csv) preserves the exact fractions and classifications;
[points-coverage.csv](points-coverage.csv) records this fixed-n all-x
completion; [run.log](run.log) is the terminal output. This fixed-n completion
is separate from every native Elkies height/ratio coverage record.
