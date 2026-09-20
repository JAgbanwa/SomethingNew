#!/usr/bin/env python3
"""
Collect every hit produced by the engines, verify it exactly, and regenerate

    SOLUTIONS.md                      (human-readable table)
    RequestProject/Solutions.lean     (machine-checked Lean instances)

usage:  cat hits*.txt | python3 make_report.py  [project_root]
"""
import sys, re, os
from math import isqrt
from fractions import Fraction

def K(n): return 36*n**3 - 65

def data(n, x):
    A = x*(x+6*n); D = A*A + x*K(n)
    if D < 0: return None
    T = isqrt(D)
    if T*T != D: return None
    d = Fraction(-A - (1 if x > 0 else -1)*T, 2*x*x)
    # exact check of the original radical equation
    inner = Fraction((x+6*n)**2) + Fraction(K(n), x)
    num, den = inner.numerator, inner.denominator
    sn, sd = isqrt(num), isqrt(den)
    assert sn*sn == num and sd*sd == den
    assert -2*d*x*x*(-(x+6*n) + Fraction(sn, sd)) == K(n)
    return T, d

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else "."
    text = sys.stdin.read()
    pairs = sorted({(int(a), int(b)) for a, b in re.findall(r"n=(-?\d+)\s+x=(-?\d+)", text)})
    rows = []
    for (n, x) in pairs:
        got = data(n, x)
        if got is None:
            print(f"REJECT n={n} x={x}", file=sys.stderr); continue
        T, d = got
        rows.append((n, x, T, d))
    rows.sort(key=lambda r: -abs(r[3]))

    md = ["# Verified solutions",
          "",
          "Each row is an exact solution of",
          "",
          "```",
          "36 n^3 - 65 = -2 d x^2 ( -(x+6n) + sqrt( (x+6n)^2 + (36 n^3 - 65)/x ) )",
          "```",
          "",
          "with `n, x` integers and `d` rational; `T = sqrt(D)`,",
          "`D = x^2 (x+6n)^2 + x (36 n^3 - 65)`, and `d = (-x(x+6n) - sgn(x) T)/(2 x^2)`.",
          "Every row is re-verified in exact rational arithmetic and machine-checked in",
          "`RequestProject/Solutions.lean`.",
          "",
          "| # | n | x | d | d (decimal) | denominator of d |",
          "|---|---|---|---|---|---|"]
    for i, (n, x, T, d) in enumerate(rows, 1):
        md.append(f"| {i} | {n} | {x} | `{d}` | {float(d):.12g} | {d.denominator} |")
    md += ["", "### the radical value at each solution", "",
           "| n | x | sqrt((x+6n)^2 + (36n^3-65)/x) | T |", "|---|---|---|---|"]
    for (n, x, T, d) in rows:
        md.append(f"| {n} | {x} | `{Fraction(T, abs(x))}` | {T} |")
    open(os.path.join(root, "SOLUTIONS.md"), "w").write("\n".join(md) + "\n")

    lean = ['''/-
# Machine-checked verification of every solution found by the search

Each theorem below states that the given rational `d` together with the given
integers `(n, x)` satisfies the original radical equation, in the reals.
They are produced by `algorithms/make_report.py` from the output of the search
engines and proved by `DSearch.satisfiesEq_of_sq`.
-/
import Mathlib
import RequestProject.DSearch

namespace DSearch
''']
    names = []
    for i, (n, x, T, d) in enumerate(rows, 1):
        nm = "solution_n{}_x{}".format(str(n).replace("-", "neg"), str(x).replace("-", "neg"))
        names.append(nm)
        dd = f"({d.numerator}/{d.denominator} : ℝ)"
        lean.append(f"""/-- `n = {n}`, `x = {x}`, `d = {d}`. -/
theorem {nm} : SatisfiesEq {dd} ({n}) ({x}) :=
  satisfiesEq_of_sq ({n}) ({x}) {T} {dd} (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)
""")
    lean.append("end DSearch\n")
    open(os.path.join(root, "RequestProject", "Solutions.lean"), "w").write("\n".join(lean))
    print(f"{len(rows)} verified solutions written to SOLUTIONS.md and Solutions.lean")

if __name__ == "__main__":
    main()
