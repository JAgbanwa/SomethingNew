New solution found in this run: n = -5877899, x = 11122866225, d = -2338707218296801/2346146172839250 ≈ -0.9968292877. This is the largest |d| on record (the previous record was -913/1458 ≈ -0.6262) and by far the largest denominator (2.35·10¹⁵ against the previous 1.39·10¹⁰).

```
theorem solution_nneg5877899_x11122866225 : SatisfiesEq (-2338707218296801/2346146172839250 : ℝ) (-5877899) (11122866225) :=
  satisfiesEq_of_sq (-5877899) (11122866225) 123325878223992734490 (-2338707218296801/2346146172839250 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)
```
