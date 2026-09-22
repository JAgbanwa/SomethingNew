### These are excerpts from a Lean task (by Harmonic's Aristotle).

New solution found in this run: n = -5877899, x = 11122866225, d = -2338707218296801/2346146172839250 ≈ -0.9968292877. This is the largest |d| on record (the previous record was -913/1458 ≈ -0.6262) and by far the largest denominator (2.35·10¹⁵ against the previous 1.39·10¹⁰).

```
theorem solution_nneg5877899_x11122866225 : SatisfiesEq (-2338707218296801/2346146172839250 : ℝ) (-5877899) (11122866225) :=
  satisfiesEq_of_sq (-5877899) (11122866225) 123325878223992734490 (-2338707218296801/2346146172839250 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)
```


Complete classification of where |d| > 1 can occur. (1) If n ≥ 1 and x ≥ 1 then every solution has d < -1, so |d| > 1 automatically. (2) If n ≤ -1 < 1 ≤ x then |d| < 1. (3) If n ≥ 3 and x ≤ -1 then |d| < 1. (4) If n ≤ -1 and x ≤ -1 then |d| > 1 holds exactly when 8x³ + 24nx² - 36n³ + 65 > 0, i.e. roughly when |x| < 1.13·|n|. Consequently |d| > 1 requires n and x to have the same sign — which is why all solutions on record (all of which have n, x of opposite signs) satisfy |d| < 1, and why 1 is the exact supremum for the type n < 0 < x that gives the current record |d| ≈ 0.9968.

```
theorem d_lt_neg_one_of_pos_pos (n x d : ℝ) (hn : 1 ≤ n) (hx : 1 ≤ x)
    (hK : 36 * n ^ 3 - 65 ≠ 0) (h : SatisfiesEq d n x) : d < -1

theorem d_lt_neg_one_of_pos_pos_int (n x : ℤ) (d : ℝ) (hn : 1 ≤ n) (hx : 1 ≤ x)
    (h : SatisfiesEq d (n : ℝ) (x : ℝ)) : d < -1

theorem abs_d_lt_one_of_neg_pos (n x d : ℝ) (hn : n ≤ -1) (hx : 1 ≤ x)
    (hrad : 0 ≤ Rad n x) (h : SatisfiesEq d n x) : |d| < 1

theorem abs_d_lt_one_of_pos_neg (n x d : ℝ) (hn : 3 ≤ n) (hx : x ≤ -1)
    (hrad : 0 ≤ Rad n x) (h : SatisfiesEq d n x) : |d| < 1

theorem one_lt_abs_d_iff_neg_neg (n x d : ℝ) (hn : n ≤ -1) (hx : x ≤ -1)
    (hrad : 0 ≤ Rad n x) (h : SatisfiesEq d n x) :
    1 < |d| ↔ 0 < 8 * x ^ 3 + 24 * n * x ^ 2 - 36 * n ^ 3 + 65
```
