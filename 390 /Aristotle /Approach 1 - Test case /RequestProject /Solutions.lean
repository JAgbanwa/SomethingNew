/-
# Machine-checked verification of every solution found by the search

Each theorem below states that the given rational `d` together with the given
integers `(n, x)` satisfies the original radical equation, in the reals.
They are produced by `algorithms/make_report.py` from the output of the search
engines and proved by `DSearch.satisfiesEq_of_sq`.
-/
import Mathlib
import RequestProject.DSearch

namespace DSearch

/-- `n = -5`, `x = 81`, `d = -913/1458`. -/
theorem solution_nneg5_x81 : SatisfiesEq (-913/1458 : ℝ) (-5) (81) :=
  satisfiesEq_of_sq (-5) (81) 4086 (-913/1458 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)

/-- `n = -2960189`, `x = 34556096`, `d = -262121371/552897536`. -/
theorem solution_nneg2960189_x34556096 : SatisfiesEq (-262121371/552897536 : ℝ) (-2960189) (34556096) :=
  satisfiesEq_of_sq (-2960189) (34556096) 551868088302600 (-262121371/552897536 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)

/-- `n = 46219`, `x = -394731`, `d = -144791/2368386`. -/
theorem solution_n46219_xneg394731 : SatisfiesEq (-144791/2368386 : ℝ) (46219) (-394731) :=
  satisfiesEq_of_sq (46219) (-394731) 27296964420 (-144791/2368386 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)

/-- `n = 1847965`, `x = -16010260`, `d = -761139263/13896905680`. -/
theorem solution_n1847965_xneg16010260 : SatisfiesEq (-761139263/13896905680 : ℝ) (1847965) (-16010260) :=
  satisfiesEq_of_sq (1847965) (-16010260) 50731597130130 (-761139263/13896905680 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)

/-- `n = 166`, `x = -2500`, `d = -1103/250000`. -/
theorem solution_n166_xneg2500 : SatisfiesEq (-1103/250000 : ℝ) (166) (-2500) :=
  satisfiesEq_of_sq (166) (-2500) 3704850 (-1103/250000 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)

/-- `n = 2047`, `x = -45972`, `d = -599/551664`. -/
theorem solution_n2047_xneg45972 : SatisfiesEq (-599/551664 : ℝ) (2047) (-45972) :=
  satisfiesEq_of_sq (2047) (-45972) 1544207142 (-599/551664 : ℝ) (by norm_num) (by norm_num)
    (by norm_num [Disc]) (by norm_num)

end DSearch
