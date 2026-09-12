import Mathlib

open scoped BigOperators
open scoped Real
open scoped Nat
open scoped Classical
open scoped Pointwise

set_option maxHeartbeats 8000000
set_option maxRecDepth 4000
set_option synthInstance.maxHeartbeats 20000
set_option synthInstance.maxSize 128

set_option relaxedAutoImplicit false
set_option autoImplicit false

set_option pp.fullNames true
set_option pp.structureInstances true
set_option pp.coercions.types true
set_option pp.funBinderTypes true
set_option pp.letVarTypes true
set_option pp.piBinderTypes true

set_option grind.warning false

/-!
# The equation `36 n³ - 19 = -2 d x² (-(x + 6n) + √((x + 6n)² + (36n³-19)/x))`

For a rational parameter `d` we look for integer solutions `(n, x)` of

`36 n³ - 19 = -2 d x² ( -(x + 6n) + √( (x + 6n)² + (36 n³ - 19)/x ) )`.

Everything is interpreted over `ℝ`, with `√` the principal (nonnegative) square root, so the
predicate `Sat` below records *both* that the radicand is nonnegative (otherwise the equation
as written is meaningless over `ℝ`) *and* that the equality holds.

Main results.

* `DEquation.sat_iff` : the equation is equivalent to the two purely rational conditions
  `36n³ - 19 = 4d²x³ + 4dx³ + 24 d n x²` and `2dx + x + 6n ≤ 0`.  The first one is the
  Thue-type equation obtained by clearing the square root, the second selects the branch of
  the square root.
* `DEquation.exists_d_iff` : a pair of integers `(n, x)` occurs in a solution for *some*
  rational `d` if and only if `x²(x+6n)² + x(36n³-19)` is a perfect square; and then
  (`DEquation.sat_unique`) the value of `d` is uniquely determined by `(n, x)`.
* `DEquation.sat_abs_x_mul_sq_le` and `DEquation.sat_abs_x_le_poly` : effective bounds
  `|x|(x+6n)² ≤ (36n³-19)²` and `|x| ≤ 24|n| + 14n² + 100`, whence
  `DEquation.sat_x_finite` : for each `n` only finitely many `x` can occur.
* Explicit solutions `sat_sol₁ … sat_sol₁₀`.  Computer searches (see `SEARCH_NOTES.md`)
  produced exactly the following admissible values of `d`:

  | `d` | `n` | `x` |
  | --- | --- | --- |
  | `-1/54` | `1` | `-9` |
  | `1583/54` | `-54` | `-9` |
  | `-414553/43904` | `909` | `784` |
  | `-25160015/2249728` | `14709` | `10816` |
  | `-15849629/24357888` | `-29317` | `507456` |
  | `-1/965662992` | `798` | `-1642284` |
  | `308597/41724656` | `-1160307` | `-10431164` |
  | `-186487860451/3639943440` | `12512774` | `2548980` |
  | `1706615972245/230860333818` | `-64722106` | `-23707161` |
  | `-336451937/111613781466` | `101116178` | `-1691117901` |

  the last four being the "particularly very large" solutions asked for.  (The
  *exhaustiveness* of those large searches is a computation, not a theorem proved here; each
  of the ten solutions themselves is verified below.  For `|n| ≤ 200` completeness *is*
  proved, in the final section of this file.)
-/

namespace DEquation

/-- The radicand `(x + 6n)² + (36n³ - 19)/x` of the equation, as a real number. -/
noncomputable def rad (n x : ℤ) : ℝ :=
  ((x : ℝ) + 6 * (n : ℝ)) ^ 2 + (36 * (n : ℝ) ^ 3 - 19) / (x : ℝ)

/-- The equation of the problem,
`36 n³ - 19 = -2 d x² (-(x+6n) + √((x+6n)² + (36n³-19)/x))`,
together with the requirement that the radicand is nonnegative, so that the square root
occurring in it is a genuine square root. -/
def Sat (d : ℚ) (n x : ℤ) : Prop :=
  0 ≤ rad n x ∧
    36 * (n : ℝ) ^ 3 - 19 =
      -2 * (d : ℝ) * (x : ℝ) ^ 2 *
        (-((x : ℝ) + 6 * (n : ℝ)) + Real.sqrt (((x : ℝ) + 6 * (n : ℝ)) ^ 2 +
          (36 * (n : ℝ) ^ 3 - 19) / (x : ℝ)))

/-- `36 n³ - 19` never vanishes at an integer `n`. -/
theorem cubic_ne_zero (n : ℤ) : 36 * (n : ℝ) ^ 3 - 19 ≠ 0 := by
  intro h
  have h' : ((36 * n ^ 3 - 19 : ℤ) : ℝ) = 0 := by push_cast; linarith
  have h'' : (36 * n ^ 3 - 19 : ℤ) = 0 := by exact_mod_cast h'
  have h3 : 36 * (n ^ 3) = 19 := by linarith
  omega

/-- Real-variable form of the reduction: clearing the square root. -/
theorem key_real (D X N : ℝ) (hA : 36 * N ^ 3 - 19 ≠ 0) :
    (0 ≤ (X + 6 * N) ^ 2 + (36 * N ^ 3 - 19) / X ∧
        36 * N ^ 3 - 19 =
          -2 * D * X ^ 2 * (-(X + 6 * N) +
            Real.sqrt ((X + 6 * N) ^ 2 + (36 * N ^ 3 - 19) / X))) ↔
      (36 * N ^ 3 - 19 = 4 * D ^ 2 * X ^ 3 + 4 * D * X ^ 3 + 24 * D * N * X ^ 2 ∧
        2 * D * X + X + 6 * N ≤ 0) := by
  set A : ℝ := 36 * N ^ 3 - 19 with hAdef
  rcases eq_or_ne X 0 with hX | hX
  · subst hX
    constructor
    · rintro ⟨-, h⟩; exact absurd (by simpa using h) hA
    · rintro ⟨h, -⟩; exact absurd (by simpa using h) hA
  constructor
  · rintro ⟨hrad, heq⟩
    set S : ℝ := Real.sqrt ((X + 6 * N) ^ 2 + A / X) with hSdef
    have hS0 : 0 ≤ S := Real.sqrt_nonneg _
    have hS2 : S ^ 2 = (X + 6 * N) ^ 2 + A / X := Real.sq_sqrt hrad
    have hS2' : X * S ^ 2 = X * (X + 6 * N) ^ 2 + A := by
      rw [hS2]; field_simp
    have h1 : 2 * D * X ^ 2 * S = 2 * D * X ^ 2 * (X + 6 * N) - A := by
      linear_combination heq
    have hD : D ≠ 0 := by
      intro hD0
      apply hA
      rw [hD0] at h1
      simpa using h1.symm
    have hsq : (2 * D * X ^ 2 * S) ^ 2 = (2 * D * X ^ 2 * (X + 6 * N) - A) ^ 2 := by rw [h1]
    have hkey : A * (4 * D ^ 2 * X ^ 3 + 4 * D * X ^ 2 * (X + 6 * N) - A) = 0 := by
      linear_combination hsq - 4 * D ^ 2 * X ^ 3 * hS2'
    have hpoly : A = 4 * D ^ 2 * X ^ 3 + 4 * D * X ^ 3 + 24 * D * N * X ^ 2 := by
      rcases mul_eq_zero.mp hkey with h | h
      · exact absurd h hA
      · linarith [h]
    refine ⟨hpoly, ?_⟩
    have hDX : 2 * D * X ^ 2 ≠ 0 :=
      mul_ne_zero (mul_ne_zero two_ne_zero hD) (pow_ne_zero 2 hX)
    have h3 : 2 * D * X ^ 2 * S = 2 * D * X ^ 2 * (-(2 * D * X + X + 6 * N)) := by
      rw [h1]; linear_combination -hpoly
    have h4 : S = -(2 * D * X + X + 6 * N) := mul_left_cancel₀ hDX h3
    rw [h4] at hS0
    linarith
  · rintro ⟨hpoly, hle⟩
    have hrad : (X + 6 * N) ^ 2 + A / X = (2 * D * X + (X + 6 * N)) ^ 2 := by
      field_simp
      linear_combination hpoly
    have hsqrt : Real.sqrt ((X + 6 * N) ^ 2 + A / X) = -(2 * D * X + (X + 6 * N)) := by
      rw [hrad, Real.sqrt_sq_eq_abs, abs_of_nonpos (by linarith)]
    refine ⟨by rw [hrad]; positivity, ?_⟩
    rw [hsqrt]
    linear_combination hpoly

/-- **Reduction of the equation.**  For a rational `d` and integers `n`, `x`, the equation of
the problem holds if and only if the Thue-type equation
`36n³ - 19 = 4d²x³ + 4dx³ + 24 d n x²` holds together with the branch condition
`2dx + x + 6n ≤ 0`. -/
theorem sat_iff (d : ℚ) (n x : ℤ) :
    Sat d n x ↔
      (36 * (n : ℚ) ^ 3 - 19 =
          4 * d ^ 2 * (x : ℚ) ^ 3 + 4 * d * (x : ℚ) ^ 3 + 24 * d * (n : ℚ) * (x : ℚ) ^ 2 ∧
        2 * d * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ) ≤ 0) := by
  rw [Sat, rad, key_real (d : ℝ) (x : ℝ) (n : ℝ) (cubic_ne_zero n)]
  constructor
  · rintro ⟨h1, h2⟩
    constructor
    · exact_mod_cast h1
    · exact_mod_cast h2
  · rintro ⟨h1, h2⟩
    constructor
    · exact_mod_cast h1
    · exact_mod_cast h2

/-- In a solution the integer `x` is nonzero. -/
theorem sat_x_ne_zero {d : ℚ} {n x : ℤ} (h : Sat d n x) : x ≠ 0 := by
  rintro rfl
  rw [sat_iff] at h
  have h1 := h.1
  norm_num at h1
  have h2 : ((36 * n ^ 3 - 19 : ℤ) : ℚ) = 0 := by push_cast; linarith
  have h3 : (36 * n ^ 3 - 19 : ℤ) = 0 := by exact_mod_cast h2
  have h4 : 36 * (n ^ 3) = 19 := by linarith
  omega

/-- Reformulation of the reduced equation in terms of `e = 2dx + x + 6n`: a solution amounts to
`x·e² = x(x+6n)² + (36n³ - 19)` with `e ≤ 0`. -/
theorem sat_iff_e (d : ℚ) (n x : ℤ) :
    Sat d n x ↔
      ((x : ℚ) * (2 * d * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ)) ^ 2
          = (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ)) ^ 2 + (36 * (n : ℚ) ^ 3 - 19) ∧
        2 * d * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ) ≤ 0) := by
  rw [sat_iff]
  constructor
  · rintro ⟨h1, h2⟩
    exact ⟨by linear_combination -h1, h2⟩
  · rintro ⟨h1, h2⟩
    exact ⟨by linear_combination -h1, h2⟩

/-- **Existence of a suitable `d`.**  Integers `n` and `x ≠ 0` appear in a solution for some
rational `d` exactly when `x²(x+6n)² + x(36n³-19)` is a perfect square. -/
theorem exists_d_iff (n x : ℤ) (hx : x ≠ 0) :
    (∃ d : ℚ, Sat d n x) ↔
      ∃ k : ℤ, k ^ 2 = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) := by
  have hxQ : (x : ℚ) ≠ 0 := Int.cast_ne_zero.mpr hx
  constructor
  · rintro ⟨d, hd⟩
    rw [sat_iff_e d n x] at hd
    set e : ℚ := 2 * d * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ) with he
    have hq : ((x : ℚ) * e) ^ 2 = ((x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) : ℤ) : ℚ) := by
      push_cast
      linear_combination (x : ℚ) * hd.1
    have : IsSquare (((x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) : ℤ) : ℚ)) :=
      ⟨(x : ℚ) * e, by rw [← hq]; ring⟩
    rcases Rat.isSquare_intCast_iff.mp this with ⟨k, hk⟩
    exact ⟨k, by rw [hk]; ring⟩
  · rintro ⟨k, hk⟩
    -- take the nonpositive branch `e = -|k| / |x|`
    refine ⟨(-(|(k : ℚ)| / |(x : ℚ)|) - ((x : ℚ) + 6 * (n : ℚ))) / (2 * (x : ℚ)), ?_⟩
    rw [sat_iff_e _ n x]
    have hxabs : |(x : ℚ)| ≠ 0 := abs_ne_zero.mpr hxQ
    have he : 2 * ((-(|(k : ℚ)| / |(x : ℚ)|) - ((x : ℚ) + 6 * (n : ℚ))) / (2 * (x : ℚ))) * (x : ℚ)
        + (x : ℚ) + 6 * (n : ℚ) = -(|(k : ℚ)| / |(x : ℚ)|) := by
      field_simp
      ring
    rw [he]
    constructor
    · have hk' : ((k : ℚ)) ^ 2 = (x : ℚ) ^ 2 * ((x : ℚ) + 6 * (n : ℚ)) ^ 2
          + (x : ℚ) * (36 * (n : ℚ) ^ 3 - 19) := by
        have h := congrArg (fun z : ℤ => (z : ℚ)) hk
        push_cast at h
        linear_combination h
      have hstep : (-(|(k : ℚ)| / |(x : ℚ)|)) ^ 2 = (k : ℚ) ^ 2 / (x : ℚ) ^ 2 := by
        rw [neg_sq, div_pow, sq_abs, sq_abs]
      rw [hstep]
      field_simp
      linear_combination hk'
    · have : 0 ≤ |(k : ℚ)| / |(x : ℚ)| := div_nonneg (abs_nonneg _) (abs_nonneg _)
      linarith

/-- For given integers `n`, `x` there is at most one rational `d` solving the equation. -/
theorem sat_unique {d d' : ℚ} {n x : ℤ} (h : Sat d n x) (h' : Sat d' n x) : d = d' := by
  have hx : x ≠ 0 := sat_x_ne_zero h
  have hxQ : (x : ℚ) ≠ 0 := Int.cast_ne_zero.mpr hx
  rw [sat_iff_e d n x] at h
  rw [sat_iff_e d' n x] at h'
  set e : ℚ := 2 * d * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ) with hedef
  set e' : ℚ := 2 * d' * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ) with he'def
  have hsq : (x : ℚ) * e ^ 2 = (x : ℚ) * e' ^ 2 := by rw [h.1, h'.1]
  have hee : e ^ 2 = e' ^ 2 := mul_left_cancel₀ hxQ hsq
  have hfac : (e - e') * (e + e') = 0 := by linear_combination hee
  have heq : e = e' := by
    rcases mul_eq_zero.mp hfac with h1 | h1
    · linarith
    · have h2 := h.2
      have h3 := h'.2
      linarith
  rw [hedef, he'def] at heq
  have h6 : 2 * d * (x : ℚ) = 2 * d' * (x : ℚ) := by linarith
  have h7 : 2 * d = 2 * d' := mul_right_cancel₀ hxQ h6
  linarith

/-- **Certificate form of a solution.**  If integers `n`, `x ≠ 0`, `U` satisfy the integral
equation `U² + 2Ux(x+6n) = x(36n³-19)` together with the sign condition
`(U + x(x+6n))·x ≤ 0`, then `d = U/(2x²)` solves the original equation.  (Here
`U = 2dx²`, and `U + x(x+6n) = x·e` with `e` as in `sat_iff_e`.)  This is the form in which
all the explicit solutions below are certified. -/
theorem sat_of_U {n x U : ℤ} (hx : x ≠ 0)
    (h : U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19))
    (hsign : (U + x * (x + 6 * n)) * x ≤ 0) :
    Sat ((U : ℚ) / (2 * (x : ℚ) ^ 2)) n x := by
  rw [sat_iff_e]
  have hxQ : (x : ℚ) ≠ 0 := Int.cast_ne_zero.mpr hx
  have hQ : (U : ℚ) ^ 2 + 2 * U * x * ((x : ℚ) + 6 * n) = (x : ℚ) * (36 * (n : ℚ) ^ 3 - 19) := by
    exact_mod_cast congrArg (fun z : ℤ => (z : ℚ)) h
  have hsQ : (((U + x * (x + 6 * n)) * x : ℤ) : ℚ) ≤ 0 := by exact_mod_cast hsign
  push_cast at hsQ
  have he : 2 * ((U : ℚ) / (2 * (x : ℚ) ^ 2)) * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ)
      = ((U : ℚ) + (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ))) / (x : ℚ) := by
    field_simp; ring
  have key : ((U : ℚ) + (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ))) ^ 2
      = (x : ℚ) ^ 2 * ((x : ℚ) + 6 * (n : ℚ)) ^ 2 + (x : ℚ) * (36 * (n : ℚ) ^ 3 - 19) := by
    linear_combination hQ
  refine ⟨?_, ?_⟩
  · rw [he, div_pow, key]
    field_simp
  · rw [he]
    have hx2 : (0 : ℚ) < (x : ℚ) ^ 2 := by positivity
    have hrw : ((U : ℚ) + (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ))) / (x : ℚ)
        = (((U : ℚ) + (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ))) * (x : ℚ)) / (x : ℚ) ^ 2 := by
      field_simp
    rw [hrw]
    exact div_nonpos_of_nonpos_of_nonneg hsQ hx2.le

/-- **Integrality of `2dx²`.**  In every solution the rational number `U = 2dx²` is in fact an
integer, and it satisfies the integral equation `U² + 2Ux(x+6n) = x(36n³-19)` and the sign
condition `(U + x(x+6n))·x ≤ 0`.  Conversely any such integer `U` produces a solution
(`sat_of_U`), so this is a complete integral description of the solutions. -/
theorem sat_iff_exists_U {d : ℚ} {n x : ℤ} (hx : x ≠ 0) :
    Sat d n x ↔ ∃ U : ℤ, (U : ℚ) = 2 * d * (x : ℚ) ^ 2 ∧
        U ^ 2 + 2 * U * x * (x + 6 * n) = x * (36 * n ^ 3 - 19) ∧
        (U + x * (x + 6 * n)) * x ≤ 0 := by
  have hxQ : (x : ℚ) ≠ 0 := Int.cast_ne_zero.mpr hx
  constructor
  · intro hsat
    rw [sat_iff_e] at hsat
    obtain ⟨heq, hle⟩ := hsat
    set e : ℚ := 2 * d * (x : ℚ) + (x : ℚ) + 6 * (n : ℚ) with hedef
    have hq2 : ((x : ℚ) * e) ^ 2
        = ((x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) : ℤ) : ℚ) := by
      push_cast
      linear_combination (x : ℚ) * heq
    obtain ⟨m, hm⟩ : ∃ m : ℤ, (x : ℚ) * e = (m : ℚ) := by
      have hden : (((x : ℚ) * e) ^ 2).den = 1 := by rw [hq2]; exact Rat.den_intCast _
      rw [Rat.den_pow] at hden
      have h1 : ((x : ℚ) * e).den = 1 := by nlinarith [((x : ℚ) * e).den_pos, hden]
      exact ⟨((x : ℚ) * e).num, by
        rw [← Rat.num_div_den ((x : ℚ) * e), h1]; simp⟩
    refine ⟨m - x * (x + 6 * n), ?_, ?_, ?_⟩
    · push_cast
      rw [← hm, hedef]; ring
    · have hQ : ((m : ℚ) - (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ))) ^ 2
          + 2 * ((m : ℚ) - (x : ℚ) * ((x : ℚ) + 6 * (n : ℚ))) * (x : ℚ)
              * ((x : ℚ) + 6 * (n : ℚ))
          = (x : ℚ) * (36 * (n : ℚ) ^ 3 - 19) := by
        have := hq2
        rw [hm] at this
        push_cast at this
        linear_combination this
      exact_mod_cast hQ
    · have hmx : (m : ℚ) * (x : ℚ) ≤ 0 := by
        rw [← hm]
        have : (x : ℚ) * e * (x : ℚ) = (x : ℚ) ^ 2 * e := by ring
        rw [this]
        exact mul_nonpos_of_nonneg_of_nonpos (by positivity) hle
      have : ((m * x : ℤ) : ℚ) ≤ 0 := by push_cast; linarith
      have hmx' : m * x ≤ 0 := by exact_mod_cast this
      simpa using hmx'
  · rintro ⟨U, hU, heq, hsign⟩
    have hd : d = (U : ℚ) / (2 * (x : ℚ) ^ 2) := by
      rw [hU]; field_simp
    rw [hd]
    exact sat_of_U hx heq hsign

/-- **The squarefree part of `x` divides `36n³ - 19`.**  Concretely: if a prime `p` divides `x`
exactly once, then `p` divides `36n³ - 19`.  (This is what makes an exhaustive search over all
`x` for a fixed `n` feasible: `x` must be of the form `± e y²` with `e` a squarefree divisor
of `36n³ - 19`.) -/
theorem sat_prime_dvd {d : ℚ} {n x : ℤ} (h : Sat d n x) {p : ℤ} (hp : Prime p)
    (hpx : p ∣ x) (hpx2 : ¬ p ^ 2 ∣ x) : p ∣ 36 * n ^ 3 - 19 := by
  have hx := sat_x_ne_zero h
  obtain ⟨k, hk⟩ := (exists_d_iff n x hx).mp ⟨d, h⟩
  obtain ⟨x', rfl⟩ := hpx
  have hpx' : ¬ p ∣ x' := by
    rintro ⟨c, rfl⟩
    exact hpx2 ⟨c, by ring⟩
  have hp0 : p ≠ 0 := hp.ne_zero
  have hpp : p ∣ p * x' := ⟨x', rfl⟩
  have h1 : p ∣ k ^ 2 := by
    rw [hk]
    exact dvd_add (dvd_mul_of_dvd_left (dvd_pow hpp two_ne_zero) _)
      (dvd_mul_of_dvd_left hpp _)
  have h2 : p ∣ k := hp.dvd_of_dvd_pow h1
  have h3 : p ^ 2 ∣ k ^ 2 := pow_dvd_pow_of_dvd h2 2
  have h4 : p ^ 2 ∣ (p * x') ^ 2 * ((p * x') + 6 * n) ^ 2 :=
    dvd_mul_of_dvd_left (pow_dvd_pow_of_dvd hpp 2) _
  have h5 : p ^ 2 ∣ (p * x') * (36 * n ^ 3 - 19) := by
    have : (p * x') * (36 * n ^ 3 - 19)
        = k ^ 2 - (p * x') ^ 2 * ((p * x') + 6 * n) ^ 2 := by rw [hk]; ring
    rw [this]
    exact dvd_sub h3 h4
  obtain ⟨c, hc⟩ := h5
  have h6 : p * (x' * (36 * n ^ 3 - 19)) = p * (p * c) := by
    rw [← mul_assoc]; rw [hc]; ring
  have h7 : x' * (36 * n ^ 3 - 19) = p * c := mul_left_cancel₀ hp0 h6
  rcases hp.dvd_mul.mp ⟨c, h7⟩ with hcase | hcase
  · exact absurd hcase hpx'
  · exact hcase

/-! ### An effective bound on `x` in terms of `n`

The quadratic `V² + 2Vx(x+6n) = x(36n³-19)` satisfied by `U = 2dx²` has a second integral root
`U' = -U - 2x(x+6n)`, with `U·U' = -x(36n³-19)`, and `x` divides both `U²` and `U'²`.  Since
`|U| + |U'| ≥ |U + U'| = 2|x(x+6n)|`, the larger of the two is at least `|x(x+6n)|`, so the
smaller one `m` satisfies `|x| ≤ m² ≤ (x(36n³-19))²/(x(x+6n))²`.  This gives the bound
`|x|(x+6n)² ≤ (36n³-19)²`, hence `|x| ≲ 13n²` once `|x| ≥ 24|n|`, and in particular for each
`n` only finitely many `x` can occur. -/

/-- `36n³ - 19` never vanishes at an integer `n` (integral version of `cubic_ne_zero`). -/
theorem int_cubic_ne_zero (n : ℤ) : 36 * n ^ 3 - 19 ≠ 0 := by
  obtain ⟨m, hm⟩ : ∃ m : ℤ, n ^ 3 = m := ⟨_, rfl⟩
  rw [hm]
  omega

/-- Arithmetic core of the bound: if `U·V = -xA`, if `|x|` is at most both `U²` and `V²`, and
if `2|xs| ≤ |U| + |V|`, then `|x|s² ≤ A²`. -/
theorem abs_x_mul_sq_le_of_roots {x s A U V : ℤ} (hx : x ≠ 0)
    (hprod : U * V = -(x * A)) (hU : |x| ≤ U ^ 2) (hV : |x| ≤ V ^ 2)
    (hsum : 2 * |x * s| ≤ |U| + |V|) : |x| * s ^ 2 ≤ A ^ 2 := by
  have hx2 : (0 : ℤ) < x ^ 2 := by positivity
  have key : ∀ P Q : ℤ, P * Q = -(x * A) → |x| ≤ Q ^ 2 → |x * s| ≤ |P| →
      |x| * s ^ 2 ≤ A ^ 2 := by
    intro P Q hPQ hQ hP
    have h1 : (x * s) ^ 2 ≤ P ^ 2 := by
      nlinarith [hP, abs_nonneg (x * s), abs_nonneg P, sq_abs (x * s), sq_abs P]
    have h2 : |x| * (x * s) ^ 2 ≤ Q ^ 2 * P ^ 2 :=
      mul_le_mul hQ h1 (by positivity) (by positivity)
    have h3 : Q ^ 2 * P ^ 2 = (x * A) ^ 2 := by
      have : (P * Q) ^ 2 = (x * A) ^ 2 := by rw [hPQ]; ring
      linarith [this, (by ring : (P * Q) ^ 2 = Q ^ 2 * P ^ 2)]
    have h4 : x ^ 2 * (|x| * s ^ 2) ≤ x ^ 2 * A ^ 2 := by nlinarith [h2, h3]
    exact le_of_mul_le_mul_left h4 hx2
  rcases le_total |V| |U| with hle | hle
  · exact key U V hprod hV (by linarith)
  · exact key V U (by rw [← hprod]; ring) hU (by linarith)

/-- **Bound on `x`.**  In every solution, `|x|·(x+6n)² ≤ (36n³-19)²`. -/
theorem sat_abs_x_mul_sq_le {d : ℚ} {n x : ℤ} (h : Sat d n x) :
    |x| * (x + 6 * n) ^ 2 ≤ (36 * n ^ 3 - 19) ^ 2 := by
  have hx := sat_x_ne_zero h
  obtain ⟨U, -, heq, -⟩ := (sat_iff_exists_U hx).mp h
  have hA0 : 36 * n ^ 3 - 19 ≠ 0 := int_cubic_ne_zero n
  have hxA : x * (36 * n ^ 3 - 19) ≠ 0 := mul_ne_zero hx hA0
  set s : ℤ := x + 6 * n with hs
  set A : ℤ := 36 * n ^ 3 - 19 with hA
  set V : ℤ := -U - 2 * x * s with hV
  have hprod : U * V = -(x * A) := by rw [hV]; linear_combination -heq
  have hU0 : U ≠ 0 := by
    rintro rfl
    exact hxA (by linear_combination -heq)
  have hV0 : V ≠ 0 := by
    intro h0
    apply hxA
    have : U * V = 0 := by rw [h0, mul_zero]
    rw [hprod] at this
    linarith
  have hUsq : |x| ≤ U ^ 2 := by
    refine Int.le_of_dvd (by positivity) ((abs_dvd _ _).mpr ⟨A - 2 * U * s, ?_⟩)
    linear_combination heq
  have hVsq : |x| ≤ V ^ 2 := by
    refine Int.le_of_dvd (by positivity) ((abs_dvd _ _).mpr ⟨A + 2 * U * s + 4 * x * s ^ 2, ?_⟩)
    rw [hV]; linear_combination heq
  refine abs_x_mul_sq_le_of_roots hx hprod hUsq hVsq ?_
  have hUV : U + V = -(2 * (x * s)) := by rw [hV]; ring
  have habs := abs_add_le U V
  rw [hUV, abs_neg, abs_mul, abs_two] at habs
  linarith

/-- **Explicit size bound.**  In every solution either `|x| ≤ 24|n|`, or
`|x|³ ≤ 2(36n³-19)²` (so that `|x| ≤ 13n²` up to the lower-order terms). -/
theorem sat_abs_x_le {d : ℚ} {n x : ℤ} (h : Sat d n x) :
    |x| ≤ 24 * |n| ∨ |x| ^ 3 ≤ 2 * (36 * n ^ 3 - 19) ^ 2 := by
  rcases le_or_gt |x| (24 * |n|) with hle | hlt
  · exact Or.inl hle
  refine Or.inr ?_
  have hmain := sat_abs_x_mul_sq_le h
  have h6 : |x| - 6 * |n| ≤ |x + 6 * n| := by
    have : |x| ≤ |x + 6 * n| + |(6 : ℤ) * n| := by
      simpa using abs_sub (x + 6 * n) (6 * n)
    have h6n : |(6 : ℤ) * n| = 6 * |n| := by rw [abs_mul]; norm_num
    linarith [this, h6n.le, h6n.ge]
  have hs0 : 0 ≤ |x + 6 * n| := abs_nonneg _
  have ha0 : 0 ≤ |x| := abs_nonneg x
  have hsq : (x + 6 * n) ^ 2 = |x + 6 * n| ^ 2 := (sq_abs _).symm
  have hmain' : |x| * |x + 6 * n| ^ 2 ≤ (36 * n ^ 3 - 19) ^ 2 := by rwa [hsq] at hmain
  have h7 : 3 * |x| ≤ 4 * |x + 6 * n| := by linarith
  have h8 : 9 * |x| ^ 2 ≤ 16 * |x + 6 * n| ^ 2 := by nlinarith
  have h10 := mul_le_mul_of_nonneg_left h8 ha0
  nlinarith [h10, hmain', sq_nonneg (36 * n ^ 3 - 19)]

/-- **Uniform bound on `x`.**  In every solution `|x| ≤ 24|n| + 14n² + 100`; in particular `x`
is at most quadratic in `n`. -/
theorem sat_abs_x_le_poly {d : ℚ} {n x : ℤ} (h : Sat d n x) :
    |x| ≤ 24 * |n| + 14 * n ^ 2 + 100 := by
  rcases sat_abs_x_le h with h1 | h1
  · nlinarith [sq_nonneg n]
  by_contra hcon
  push Not at hcon
  have hm : (0 : ℤ) ≤ |n| := abs_nonneg n
  have hB : (0 : ℤ) ≤ 24 * |n| + 14 * n ^ 2 + 100 := by positivity
  have hcube : (24 * |n| + 14 * n ^ 2 + 100) ^ 3 < |x| ^ 3 :=
    pow_lt_pow_left₀ hcon hB (by norm_num)
  have hA : |36 * n ^ 3 - 19| ≤ 36 * |n| ^ 3 + 19 := by
    calc |36 * n ^ 3 - 19| ≤ |36 * n ^ 3| + |(19 : ℤ)| := abs_sub _ _
      _ = 36 * |n| ^ 3 + 19 := by rw [abs_mul, abs_pow]; norm_num
  have hA2 : (36 * n ^ 3 - 19) ^ 2 ≤ (36 * |n| ^ 3 + 19) ^ 2 := by
    nlinarith [sq_abs (36 * n ^ 3 - 19), abs_nonneg (36 * n ^ 3 - 19), pow_nonneg hm 3]
  have hkey : 2 * (36 * |n| ^ 3 + 19) ^ 2 ≤ (24 * |n| + 14 * |n| ^ 2 + 100) ^ 3 := by
    nlinarith [pow_nonneg hm 3, pow_nonneg hm 4, pow_nonneg hm 5, pow_nonneg hm 6, hm,
      mul_nonneg hm hm, sq_nonneg (|n| - 1)]
  rw [sq_abs] at hkey
  linarith

/-- For each `n`, only finitely many integers `x` occur in a solution. -/
theorem sat_x_finite (n : ℤ) : {x : ℤ | ∃ d : ℚ, Sat d n x}.Finite := by
  set B : ℤ := 24 * |n| + 14 * n ^ 2 + 100 with hB
  refine Set.Finite.subset (Set.finite_Icc (-B) B) ?_
  rintro x ⟨d, hd⟩
  obtain ⟨h1, h2⟩ := abs_le.mp (sat_abs_x_le_poly hd)
  exact Set.mem_Icc.mpr ⟨h1, h2⟩

/-! ### Explicit solutions

The solutions below are the complete list produced by the searches described in
`SEARCH_NOTES.md`. -/

/-- `d = -1/54` works, with `(n, x) = (1, -9)`. -/
theorem sat_sol₁ : Sat (-1/54) 1 (-9) := by
  rw [sat_iff]; norm_num

/-- `d = 1583/54` works, with `(n, x) = (-54, -9)`. -/
theorem sat_sol₂ : Sat (1583/54) (-54) (-9) := by
  rw [sat_iff]; norm_num

/-- `d = -414553/43904` works, with `(n, x) = (909, 784)`. -/
theorem sat_sol₃ : Sat (-414553/43904) 909 784 := by
  rw [sat_iff]; norm_num

/-- `d = -25160015/2249728` works, with the large values `(n, x) = (14709, 10816)`. -/
theorem sat_sol₄ : Sat (-25160015/2249728) 14709 10816 := by
  rw [sat_iff]; norm_num

/-- `d = -15849629/24357888` works, with the very large values `(n, x) = (-29317, 507456)`. -/
theorem sat_sol₅ : Sat (-15849629/24357888) (-29317) 507456 := by
  rw [sat_iff]; norm_num

/-- `d = -1/965662992` works, with the very large values `(n, x) = (798, -1642284)`. -/
theorem sat_sol₆ : Sat (-1/965662992) 798 (-1642284) := by
  rw [sat_iff]; norm_num

/-- `d = 308597/41724656` works, with the very large values `(n, x) = (-1160307, -10431164)`
(a seven-digit `n` and an eight-digit `x`).  Certified through `sat_of_U` with
`U = 2dx² = 1609512958454`. -/
theorem sat_sol₇ : Sat (308597/41724656) (-1160307) (-10431164) := by
  have hd : (308597/41724656 : ℚ)
      = ((1609512958454 : ℤ) : ℚ) / (2 * ((-10431164 : ℤ) : ℚ) ^ 2) := by norm_num
  rw [hd]
  exact sat_of_U (by norm_num) (by norm_num) (by norm_num)

/-- `d = -186487860451/3639943440` works, with the very large values
`(n, x) = (12512774, 2548980)` (an eight-digit `n`).  Certified through `sat_of_U` with
`U = 2dx² = -665761661810070`. -/
theorem sat_sol₈ : Sat (-186487860451/3639943440) 12512774 2548980 := by
  have hd : (-186487860451/3639943440 : ℚ)
      = ((-665761661810070 : ℤ) : ℚ) / (2 * ((2548980 : ℤ) : ℚ) ^ 2) := by norm_num
  rw [hd]
  exact sat_of_U (by norm_num) (by norm_num) (by norm_num)

/-- `d = 1706615972245/230860333818` works, with `(n, x) = (-64722106, -23707161)`: **both**
values have eight digits.  Certified through `sat_of_U` with `U = 2dx² = 8309513168860905`. -/
theorem sat_sol₉ : Sat (1706615972245/230860333818) (-64722106) (-23707161) := by
  have hd : (1706615972245/230860333818 : ℚ)
      = ((8309513168860905 : ℤ) : ℚ) / (2 * ((-23707161 : ℤ) : ℚ) ^ 2) := by norm_num
  rw [hd]
  exact sat_of_U (by norm_num) (by norm_num) (by norm_num)

/-- `d = -336451937/111613781466` works, with `(n, x) = (101116178, -1691117901)`: a nine-digit
`n` and a **ten-digit** `x`.  Certified through `sat_of_U` with
`U = 2dx² = -17241814954146189`. -/
theorem sat_sol₁₀ : Sat (-336451937/111613781466) 101116178 (-1691117901) := by
  have hd : (-336451937/111613781466 : ℚ)
      = ((-17241814954146189 : ℤ) : ℚ) / (2 * ((-1691117901 : ℤ) : ℚ) ^ 2) := by norm_num
  rw [hd]
  exact sat_of_U (by norm_num) (by norm_num) (by norm_num)

end DEquation

/-!
# Verified exhaustiveness of the list of solutions for `|n| ≤ 200`

`DEquation.sat_abs_x_le_poly` bounds `|x|` by `24|n| + 14n² + 100` in any solution, so for
`|n| ≤ 200` the admissible pairs `(n, x)` lie in an explicit finite set.  Over that set the
perfect-square criterion `DEquation.exists_d_iff` is checked by computation
(`DEquation.square_check_abs_n_le_200`, a `native_decide` over about 1.5·10⁸ pairs), with the
result that

* the only solutions with `|n| ≤ 200` are `(n, x) = (1, -9)` and `(n, x) = (-54, -9)`
  (`DEquation.sat_exhaustive_abs_n_le_200`), and hence
* the only admissible values of `d` there are `-1/54` and `1583/54`
  (`DEquation.sat_d_of_abs_n_le_200`).

This is the range in which the completeness of the list of solutions is *proved*; the much
larger searches recorded in `SEARCH_NOTES.md` are computations only.
-/

namespace DEquation

set_option maxRecDepth 4000000

/-- The finite computation behind `sat_exhaustive_abs_n_le_200`: for `|n| ≤ 200` and
`0 < |x| ≤ 24|n| + 14n² + 100`, the number `x²(x+6n)² + x(36n³-19)` is a perfect square only
for `(n, x) = (1, -9)` and `(n, x) = (-54, -9)`. -/
theorem square_check_abs_n_le_200 :
    ∀ n ∈ Finset.Icc (-200 : ℤ) 200,
      ∀ x ∈ Finset.Icc (-(24 * |n| + 14 * n ^ 2 + 100)) (24 * |n| + 14 * n ^ 2 + 100), x ≠ 0 →
      Int.sqrt (x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19))
          * Int.sqrt (x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19))
        = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) →
      (n = 1 ∧ x = -9) ∨ (n = -54 ∧ x = -9) := by
  native_decide

/-- **Exhaustiveness for `|n| ≤ 200`.**  Every solution of the equation with `|n| ≤ 200` is one
of the two small ones, `(n, x) = (1, -9)` or `(n, x) = (-54, -9)`. -/
theorem sat_exhaustive_abs_n_le_200 {d : ℚ} {n x : ℤ} (h : Sat d n x) (hn : |n| ≤ 200) :
    (n = 1 ∧ x = -9) ∨ (n = -54 ∧ x = -9) := by
  have hx := sat_x_ne_zero h
  obtain ⟨k, hk⟩ := (exists_d_iff n x hx).mp ⟨d, h⟩
  obtain ⟨hn1, hn2⟩ := abs_le.mp hn
  obtain ⟨hx1, hx2⟩ := abs_le.mp (sat_abs_x_le_poly h)
  refine square_check_abs_n_le_200 n (Finset.mem_Icc.mpr ⟨hn1, hn2⟩) x
    (Finset.mem_Icc.mpr ⟨hx1, hx2⟩) hx ?_
  exact (Int.exists_mul_self _).mp ⟨k, by rw [← hk]; ring⟩

/-- **The admissible `d` for `|n| ≤ 200`.**  For `|n| ≤ 200` the only rational values of `d`
for which the equation has an integer solution are `-1/54` and `1583/54`. -/
theorem sat_d_of_abs_n_le_200 {d : ℚ} {n x : ℤ} (h : Sat d n x) (hn : |n| ≤ 200) :
    d = -1/54 ∨ d = 1583/54 := by
  rcases sat_exhaustive_abs_n_le_200 h hn with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
  · exact Or.inl (sat_unique h sat_sol₁)
  · exact Or.inr (sat_unique h sat_sol₂)

end DEquation
