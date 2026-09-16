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
* Explicit solutions `sat_sol₁ … sat_sol₁₁`.  Computer searches (see `SEARCH_NOTES.md`)
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
  | `-14123191460839/14966022419456` | `-516368250` | `55022141248` |

  the last five being the "particularly very large" solutions asked for.  (The
  *exhaustiveness* of those large searches is a computation, not a theorem proved here; each
  of the eleven solutions themselves is verified below.)
* `DEquation.sat_exhaustive_abs_n_le_100` and `DEquation.sat_d_of_abs_n_le_100` : for
  `|n| ≤ 100` the list is *complete* — the only solutions are `(n, x) = (1, -9)` and
  `(-54, -9)`, so the only admissible `d` are `-1/54` and `1583/54`.  This is proved by
  combining the bound on `|x|` with a finite computation, whose every ingredient is proved
  correct here.

This file is self-contained: apart from `Mathlib` it has no dependencies.
-/

/-!
## The computational kernel of the exhaustive check

The definitions of this section are used by the finite computation at the end of the file.
Everything here is proved correct below; nothing is trusted beyond the Lean compiler.

The task is to check, for all integers `n` with `|n| ≤ N` and all `x ≠ 0` with
`|x| ≤ 24|n| + 14n² + 100`, whether

`V(n,x) = x²(x+6n)² + x(36n³-19)`

is a perfect square.  A pair is only handed to the (slow, exact) test `chk` if it passes six
modular filters: four of them use a table, recomputed for each `n`, of the residues `x mod mᵢ`
for which `V(n,x)` is a square modulo `mᵢ` (so that the inner loop over `x` only has to look up
four array entries and increment four counters), and two more test the exact value `V(n,x)`
against the squares modulo `m₅`, `m₆`.
-/

namespace DSieve

/-- `V(n,x) = x²(x+6n)² + x(36n³-19)`, the quantity that has to be a perfect square. -/
def Vz (n x : Int) : Int := x * x * ((x + 6 * n) * (x + 6 * n)) + x * (36 * (n * n * n) - 19)

/-- A total array lookup: out-of-range indices return `true`, the conservative answer. -/
def look (t : Array Bool) (i : Nat) : Bool := if h : i < t.size then t[i] else true

/-- `sqTab m` marks the residues that are squares modulo `m`. -/
def sqTab (m : Nat) : Array Bool :=
  (List.range m).foldl (fun a k => a.set! (k * k % m) true) (Array.replicate m false)

/-- `2⁶ · 63` -/
def m₁ : Nat := 4032
/-- `5 · 11 · 13` -/
def m₂ : Nat := 715
/-- `17 · 19 · 23` -/
def m₃ : Nat := 7429
/-- `29 · 31 · 37` -/
def m₄ : Nat := 33263
/-- `41 · 43 · 47` -/
def m₅ : Nat := 82861
/-- `53 · 59 · 61` -/
def m₆ : Nat := 190747

/-- Squares modulo `m₁`, computed once. -/
def sqTab₁ : Array Bool := sqTab m₁
/-- Squares modulo `m₂`, computed once. -/
def sqTab₂ : Array Bool := sqTab m₂
/-- Squares modulo `m₃`, computed once. -/
def sqTab₃ : Array Bool := sqTab m₃
/-- Squares modulo `m₄`, computed once. -/
def sqTab₄ : Array Bool := sqTab m₄
/-- Squares modulo `m₅`, computed once. -/
def sqTab₅ : Array Bool := sqTab m₅
/-- Squares modulo `m₆`, computed once. -/
def sqTab₆ : Array Bool := sqTab m₆

/-- `resTab m tab n` marks the residues `r = x mod m` for which `V(n,x)` can be a square
modulo `m`. -/
def resTab (m : Nat) (tab : Array Bool) (n : Int) : Array Bool :=
  (Array.range m).map (fun r : Nat => look tab ((Vz n (Int.ofNat r) % (Int.ofNat m)).toNat))

/-- Increment a residue modulo `m`. -/
def stepR (m r : Nat) : Nat := if r + 1 = m then 0 else r + 1

/-- The bound `24|n| + 14n² + 100` on `|x|`, as a natural number. -/
def bnd (n : Int) : Nat := 24 * n.natAbs + 14 * (n.natAbs * n.natAbs) + 100

/-- The two filters applied to the exact value of `V(n,x)`. -/
def exactFilter (n x : Int) : Bool :=
  look sqTab₅ ((Vz n x % (Int.ofNat m₅)).toNat) && look sqTab₆ ((Vz n x % (Int.ofNat m₆)).toNat)

/-- Inner loop: runs over `fuel` consecutive values of `x`, starting at `x`, carrying the
residues of `x` modulo the four moduli `m₁, …, m₄`.  The exact test `chk` is only applied to
the pairs that survive all six filters. -/
def scanX (chk : Int → Int → Bool) (n : Int) (t₁ t₂ t₃ t₄ : Array Bool) :
    Nat → Int → Nat → Nat → Nat → Nat → Bool
  | 0, _, _, _, _, _ => true
  | fuel + 1, x, r₁, r₂, r₃, r₄ =>
    ((!(look t₁ r₁ && look t₂ r₂ && look t₃ r₃ && look t₄ r₄ && exactFilter n x)) || chk n x) &&
      scanX chk n t₁ t₂ t₃ t₄ fuel (x + 1)
        (stepR m₁ r₁) (stepR m₂ r₂) (stepR m₃ r₃) (stepR m₄ r₄)

/-- Outer loop over `fuel` consecutive values of `n`, starting at `n`. -/
def scanN (chk : Int → Int → Bool) : Nat → Int → Bool
  | 0, _ => true
  | fuel + 1, n =>
    scanX chk n (resTab m₁ sqTab₁ n) (resTab m₂ sqTab₂ n) (resTab m₃ sqTab₃ n)
        (resTab m₄ sqTab₄ n) (2 * bnd n + 1) (-(Int.ofNat (bnd n)))
        ((-(Int.ofNat (bnd n)) % (Int.ofNat m₁)).toNat)
        ((-(Int.ofNat (bnd n)) % (Int.ofNat m₂)).toNat)
        ((-(Int.ofNat (bnd n)) % (Int.ofNat m₃)).toNat)
        ((-(Int.ofNat (bnd n)) % (Int.ofNat m₄)).toNat) &&
      scanN chk fuel (n + 1)

/-- The full scan for `|n| ≤ N`. -/
def scanAll (chk : Int → Int → Bool) (N : Nat) : Bool := scanN chk (2 * N + 1) (-(Int.ofNat N))

end DSieve

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
  push_neg at hcon
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

/-- `d = -14123191460839/14966022419456` works, with `(n, x) = (-516368250, 55022141248)`:
a nine-digit `n` and an **eleven-digit** `x`.  Certified through `sat_of_U` with
`U = 2dx² = -5713884084050227342552`. -/
theorem sat_sol₁₁ :
    Sat (-14123191460839/14966022419456) (-516368250) 55022141248 := by
  have hd : (-14123191460839/14966022419456 : ℚ)
      = ((-5713884084050227342552 : ℤ) : ℚ) / (2 * ((55022141248 : ℤ) : ℚ) ^ 2) := by norm_num
  rw [hd]
  exact sat_of_U (by norm_num) (by norm_num) (by norm_num)

/-!
## Verified exhaustiveness of the list of solutions for small `|n|`

`DEquation.sat_abs_x_le_poly` bounds `|x|` by `24|n| + 14n² + 100` in any solution, so for
`|n| ≤ N` the admissible pairs `(n, x)` lie in an explicit finite set, and by
`DEquation.exists_d_iff` such a pair occurs in a solution only if

`V(n,x) = x²(x+6n)² + x(36n³-19)`

is a perfect square.  The scan of the previous section checks that condition over the whole
box; here its soundness is proved (`DEquation.look_sqTab_of_square` and
`DEquation.look_resTab` for the modular filters, `DEquation.pairOK_sound` for the exact test,
`DEquation.scanX_sound` and `DEquation.scanN_sound` for the two loops), and the scan is then
run for `N = 100` by a `native_decide` computation, which yields

* the only solutions with `|n| ≤ 100` are `(n, x) = (1, -9)` and `(-54, -9)`
  (`DEquation.sat_exhaustive_abs_n_le_100`), and hence
* the only admissible values of `d` there are `-1/54` and `1583/54`
  (`DEquation.sat_d_of_abs_n_le_100`).

The scan for `N = 100` examines about `2·10⁷` pairs `(n, x)` and takes under a minute.  The
statements are proved for a general `N` (`DEquation.sat_exhaustive_of_scan`), so a larger
range can be obtained simply by running the computation for a larger `N`: with `N = 1000`
(about `2·10¹⁰` pairs, feasible only with the kernel compiled ahead of time to native code)
one gets that the only solutions with `|n| ≤ 1000` are `(1,-9)`, `(-54,-9)`, `(909,784)` and
`(798,-1642284)`, so that the only admissible `d` there are `-1/54`, `1583/54`,
`-414553/43904` and `-1/965662992`.

The range covered here is the range in which the completeness of the list of solutions is
*proved*; the much larger searches recorded in `SEARCH_NOTES.md` are computations only.
-/

open DSieve

/-- The kernel's `V` is the quantity appearing in `DEquation.exists_d_iff`. -/
theorem Vz_eq (n x : ℤ) : Vz n x = x ^ 2 * (x + 6 * n) ^ 2 + x * (36 * n ^ 3 - 19) := by
  rw [Vz]; ring

/-- Setting an entry of a table preserves the entries that are already set. -/
theorem look_set_of_look {a : Array Bool} {i j : ℕ} (h : look a j = true) :
    look (a.set! i true) j = true := by
  have hsz : (a.set! i true).size = a.size := Array.size_set! a i true
  rw [look] at h ⊢
  by_cases hj : j < a.size
  · rw [dif_pos (by rw [hsz]; exact hj)]
    rw [dif_pos hj] at h
    simp only [Array.set!_eq_setIfInBounds, Array.getElem_setIfInBounds hj]
    split <;> simp_all
  · rw [dif_neg (by rw [hsz]; exact hj)]

/-- Setting an entry of a table marks it. -/
theorem look_set_self {a : Array Bool} {i : ℕ} (hi : i < a.size) :
    look (a.set! i true) i = true := by
  have hsz : (a.set! i true).size = a.size := Array.size_set! a i true
  rw [look, dif_pos (by rw [hsz]; exact hi)]
  simp [Array.set!_eq_setIfInBounds, Array.getElem_setIfInBounds hi]

/-- The size of the table built by the fold. -/
theorem foldl_set_size (m : ℕ) (l : List ℕ) (a : Array Bool) :
    (l.foldl (fun a k => a.set! (k * k % m) true) a).size = a.size := by
  induction l generalizing a with
  | nil => simp
  | cons k t ih => rw [List.foldl_cons, ih, Array.size_set!]

theorem sqTab_size (m : ℕ) : (sqTab m).size = m := by
  rw [sqTab, foldl_set_size]
  simp

/-- Entries already marked stay marked along the fold. -/
theorem look_foldl_of_look (m : ℕ) (l : List ℕ) {a : Array Bool} {j : ℕ} (h : look a j = true) :
    look (l.foldl (fun a k => a.set! (k * k % m) true) a) j = true := by
  induction l generalizing a with
  | nil => simpa using h
  | cons k t ih => exact ih (look_set_of_look h)

/-- Every `k` in the list gets its square marked. -/
theorem look_foldl_mem (m : ℕ) (hm : 0 < m) (l : List ℕ) :
    ∀ {a : Array Bool}, a.size = m → ∀ {k : ℕ}, k ∈ l →
      look (l.foldl (fun a k => a.set! (k * k % m) true) a) (k * k % m) = true := by
  induction l with
  | nil => intro a _ k hk; exact absurd hk (by simp)
  | cons k' t ih =>
    intro a ha k hk
    have hsz : (a.set! (k' * k' % m) true).size = m := by rw [Array.size_set!]; exact ha
    rcases List.mem_cons.mp hk with rfl | hk'
    · refine look_foldl_of_look m t (look_set_self ?_)
      rw [ha]; exact Nat.mod_lt _ hm
    · exact ih hsz hk'

/-- Soundness of `sqTab`: every square modulo `m` is marked. -/
theorem look_sqTab (m k : ℕ) (hm : 0 < m) : look (sqTab m) (k * k % m) = true := by
  have hk : k % m ∈ List.range m := List.mem_range.mpr (Nat.mod_lt _ hm)
  have h := look_foldl_mem m hm (List.range m) (a := Array.replicate m false)
    (by simp) hk
  rwa [show (k % m) * (k % m) % m = k * k % m from by
    conv_rhs => rw [Nat.mul_mod]] at h

/-- Soundness of the square tables: if `v` is a perfect square, its residue modulo `m` is
marked in `sqTab m`. -/
theorem look_sqTab_of_square (m : ℕ) (hm : 0 < m) (v : ℤ) (hv : ∃ z : ℤ, v = z * z) :
    look (sqTab m) ((v % (m : ℤ)).toNat) = true := by
  have hm' : (0 : ℤ) < (m : ℤ) := by exact_mod_cast hm
  have hmne : (m : ℤ) ≠ 0 := ne_of_gt hm'
  obtain ⟨z, hz⟩ := hv
  set k : ℕ := (z % (m : ℤ)).toNat with hk
  have hk0 : (0 : ℤ) ≤ z % (m : ℤ) := Int.emod_nonneg _ hmne
  have hkz : ((k : ℤ)) = z % (m : ℤ) := Int.toNat_of_nonneg hk0
  have hmod : v % (m : ℤ) = ((k * k % m : ℕ) : ℤ) := by
    rw [hz, Int.mul_emod, ← hkz]
    push_cast
    ring
  rw [hmod, Int.toNat_natCast]
  exact look_sqTab m k hm

theorem resTab_size (m : ℕ) (tab : Array Bool) (n : ℤ) : (resTab m tab n).size = m := by
  simp [resTab]

/-- `V(n, ·)` only depends on its argument modulo `m`. -/
theorem Vz_emod (m : ℕ) (n x : ℤ) :
    Vz n (x % (m : ℤ)) % (m : ℤ) = Vz n x % (m : ℤ) := by
  have h : x % (m : ℤ) ≡ x [ZMOD (m : ℤ)] := Int.emod_emod_of_dvd _ dvd_rfl
  simp only [Vz_eq]
  exact (((h.pow 2).mul ((h.add_right (6 * n)).pow 2)).add (h.mul_right (36 * n ^ 3 - 19)))

/-- **Soundness of the per-`n` modular filter.**  If `V(n,x)` is a perfect square then the
residue of `x` modulo `m` is marked in `resTab m (sqTab m) n`. -/
theorem look_resTab (m : ℕ) (hm : 0 < m) {tab : Array Bool} (htab : tab = sqTab m) (n x : ℤ)
    (hsq : ∃ z : ℤ, Vz n x = z * z) :
    look (resTab m tab n) ((x % (m : ℤ)).toNat) = true := by
  subst htab
  have hm' : (0 : ℤ) < (m : ℤ) := by exact_mod_cast hm
  have hmne : (m : ℤ) ≠ 0 := ne_of_gt hm'
  set r : ℕ := (x % (m : ℤ)).toNat with hr
  have hr0 : (0 : ℤ) ≤ x % (m : ℤ) := Int.emod_nonneg _ hmne
  have hrz : ((r : ℤ)) = x % (m : ℤ) := Int.toNat_of_nonneg hr0
  have hrlt : r < m := by
    have := Int.emod_lt_of_pos x hm'
    omega
  rw [look, dif_pos (by rw [resTab_size]; exact hrlt)]
  simp only [resTab, Array.getElem_map, Array.getElem_range]
  have hV : Vz n (Int.ofNat r) % (m : ℤ) = Vz n x % (m : ℤ) := by
    rw [show (Int.ofNat r) = ((r : ℕ) : ℤ) from rfl, hrz]
    exact Vz_emod m n x
  rw [show (Int.ofNat m) = ((m : ℕ) : ℤ) from rfl, hV]
  exact look_sqTab_of_square m hm _ hsq

/-- Soundness of the two filters applied to the exact value of `V(n,x)`. -/
theorem exactFilter_of_square {n x : ℤ} (hsq : ∃ z : ℤ, Vz n x = z * z) :
    exactFilter n x = true := by
  rw [exactFilter, Bool.and_eq_true]
  exact ⟨look_sqTab_of_square m₅ (by norm_num [m₅]) _ hsq,
    look_sqTab_of_square m₆ (by norm_num [m₆]) _ hsq⟩

/-- The four pairs `(n, x)` with `|n| ≤ 1000` that occur in a solution; only the first two
have `|n| ≤ 100`. -/
def KnownPair (n x : ℤ) : Prop :=
  (n = 1 ∧ x = -9) ∨ (n = -54 ∧ x = -9) ∨ (n = 909 ∧ x = 784) ∨ (n = 798 ∧ x = -1642284)

/-- The exact test applied to the pairs that survive the modular filters. -/
def pairOK (n x : ℤ) : Bool :=
  if x = 0 then true
  else if Int.sqrt (Vz n x) * Int.sqrt (Vz n x) = Vz n x then
    (n = 1 && x = -9) || (n = -54 && x = -9) || (n = 909 && x = 784) ||
      (n = 798 && x = -1642284)
  else true

/-- Soundness of `pairOK`. -/
theorem pairOK_sound {n x : ℤ} (h : pairOK n x = true) (hx : x ≠ 0)
    (hsq : ∃ z : ℤ, Vz n x = z * z) : KnownPair n x := by
  obtain ⟨z, hz⟩ := hsq
  have hsqrt : Int.sqrt (Vz n x) * Int.sqrt (Vz n x) = Vz n x := by
    rw [hz, Int.sqrt_eq z, Int.natAbs_mul_self']
  rw [pairOK, if_neg hx, if_pos hsqrt] at h
  simp only [Bool.or_eq_true, Bool.and_eq_true, decide_eq_true_eq] at h
  rcases h with ((h1 | h1) | h1) | h1
  · exact Or.inl h1
  · exact Or.inr (Or.inl h1)
  · exact Or.inr (Or.inr (Or.inl h1))
  · exact Or.inr (Or.inr (Or.inr h1))

/-- Correctness of the residue counters of the inner loop. -/
theorem stepR_spec (m : ℕ) (hm : 0 < m) (x : ℤ) :
    stepR m ((x % (m : ℤ)).toNat) = ((x + 1) % (m : ℤ)).toNat := by
  have hm' : (0 : ℤ) < (m : ℤ) := by exact_mod_cast hm
  have hmne : (m : ℤ) ≠ 0 := ne_of_gt hm'
  have h0 : (0 : ℤ) ≤ x % (m : ℤ) := Int.emod_nonneg _ hmne
  have h1 : x % (m : ℤ) < (m : ℤ) := Int.emod_lt_of_pos x hm'
  have hmm : x % (m : ℤ) ≡ x [ZMOD (m : ℤ)] := Int.emod_emod_of_dvd x dvd_rfl
  have hadd : (x + 1) % (m : ℤ) = (x % (m : ℤ) + 1) % (m : ℤ) := (hmm.add_right 1).symm
  rcases eq_or_lt_of_le (by omega : x % (m : ℤ) + 1 ≤ (m : ℤ)) with heq | hlt
  · have hz : (x + 1) % (m : ℤ) = 0 := by rw [hadd, heq]; simp
    rw [hz, stepR, if_pos]
    · simp
    · omega
  · have hz : (x + 1) % (m : ℤ) = x % (m : ℤ) + 1 := by
      rw [hadd, Int.emod_eq_of_lt (by omega) hlt]
    rw [hz, stepR, if_neg (by omega)]
    omega

/-- Soundness of the inner loop. -/
theorem scanX_sound (n : ℤ) :
    ∀ (fuel : ℕ) (x : ℤ) (r₁ r₂ r₃ r₄ : ℕ),
      r₁ = (x % (m₁ : ℤ)).toNat → r₂ = (x % (m₂ : ℤ)).toNat →
      r₃ = (x % (m₃ : ℤ)).toNat → r₄ = (x % (m₄ : ℤ)).toNat →
      scanX pairOK n (resTab m₁ sqTab₁ n) (resTab m₂ sqTab₂ n) (resTab m₃ sqTab₃ n)
          (resTab m₄ sqTab₄ n) fuel x r₁ r₂ r₃ r₄ = true →
      ∀ y : ℤ, x ≤ y → y < x + (fuel : ℤ) → y ≠ 0 → (∃ z : ℤ, Vz n y = z * z) →
        KnownPair n y := by
  intro fuel
  induction fuel with
  | zero => intro x r₁ r₂ r₃ r₄ _ _ _ _ _ y hy1 hy2; exfalso; simp at hy2; omega
  | succ fuel ih =>
    intro x r₁ r₂ r₃ r₄ h₁ h₂ h₃ h₄ hscan y hy1 hy2 hy0 hsq
    rw [scanX, Bool.and_eq_true] at hscan
    obtain ⟨hhead, htail⟩ := hscan
    rcases eq_or_lt_of_le hy1 with rfl | hlt
    · -- the current value of `x`
      have hcond : (look (resTab m₁ sqTab₁ n) r₁ && look (resTab m₂ sqTab₂ n) r₂ &&
          look (resTab m₃ sqTab₃ n) r₃ && look (resTab m₄ sqTab₄ n) r₄ &&
          exactFilter n x) = true := by
        rw [h₁, h₂, h₃, h₄]
        simp only [Bool.and_eq_true]
        exact ⟨⟨⟨⟨look_resTab m₁ (by norm_num [m₁]) rfl n x hsq,
          look_resTab m₂ (by norm_num [m₂]) rfl n x hsq⟩,
          look_resTab m₃ (by norm_num [m₃]) rfl n x hsq⟩,
          look_resTab m₄ (by norm_num [m₄]) rfl n x hsq⟩,
          exactFilter_of_square hsq⟩
      rw [hcond] at hhead
      simp only [Bool.not_true, Bool.false_or] at hhead
      exact pairOK_sound hhead hy0 hsq
    · refine ih (x + 1) _ _ _ _ ?_ ?_ ?_ ?_ htail y (by omega) (by omega) hy0 hsq
      · rw [h₁]; exact stepR_spec m₁ (by norm_num [m₁]) x
      · rw [h₂]; exact stepR_spec m₂ (by norm_num [m₂]) x
      · rw [h₃]; exact stepR_spec m₃ (by norm_num [m₃]) x
      · rw [h₄]; exact stepR_spec m₄ (by norm_num [m₄]) x

theorem bnd_cast (n : ℤ) : ((bnd n : ℕ) : ℤ) = 24 * |n| + 14 * n ^ 2 + 100 := by
  unfold bnd
  push_cast
  rw [abs_mul_abs_self]
  ring

/-- Soundness of the outer loop. -/
theorem scanN_sound :
    ∀ (fuel : ℕ) (n : ℤ), scanN pairOK fuel n = true →
      ∀ (ν x : ℤ), n ≤ ν → ν < n + (fuel : ℤ) → x ≠ 0 → |x| ≤ ((bnd ν : ℕ) : ℤ) →
        (∃ z : ℤ, Vz ν x = z * z) → KnownPair ν x := by
  intro fuel
  induction fuel with
  | zero => intro n _ ν x _ h2; exfalso; simp at h2; omega
  | succ fuel ih =>
    intro n hscan ν x hn1 hn2 hx hxb hsq
    rw [scanN, Bool.and_eq_true] at hscan
    obtain ⟨hhead, htail⟩ := hscan
    rcases eq_or_lt_of_le hn1 with rfl | hlt
    · refine scanX_sound n (2 * bnd n + 1) (-((bnd n : ℕ) : ℤ)) _ _ _ _ rfl rfl rfl rfl hhead x
        ?_ ?_ hx hsq
      · have := abs_le.mp hxb; omega
      · have := abs_le.mp hxb; omega
    · exact ih (n + 1) htail ν x (by omega) (by push_cast at hn2 ⊢; omega) hx hxb hsq

/-- Soundness of the full scan, in the form in which it is used below. -/
theorem scanAll_sound {N : ℕ} (h : scanAll pairOK N = true) {n x : ℤ} (hn : |n| ≤ (N : ℤ))
    (hx : x ≠ 0) (hxb : |x| ≤ 24 * |n| + 14 * n ^ 2 + 100) (hsq : ∃ z : ℤ, Vz n x = z * z) :
    KnownPair n x := by
  obtain ⟨hn1, hn2⟩ := abs_le.mp hn
  refine scanN_sound (2 * N + 1) (-(N : ℤ)) h n x (by omega) (by push_cast; omega) hx ?_ hsq
  rw [bnd_cast]; exact hxb

/-- **Exhaustiveness from a completed scan.**  If the scan succeeds for `N`, every solution
of the equation with `|n| ≤ N` is one of the four known pairs. -/
theorem sat_exhaustive_of_scan {N : ℕ} (hscan : scanAll pairOK N = true) {d : ℚ} {n x : ℤ}
    (h : Sat d n x) (hn : |n| ≤ (N : ℤ)) : KnownPair n x := by
  have hx := sat_x_ne_zero h
  obtain ⟨k, hk⟩ := (exists_d_iff n x hx).mp ⟨d, h⟩
  refine scanAll_sound hscan hn hx (sat_abs_x_le_poly h) ⟨k, ?_⟩
  rw [Vz_eq]
  linear_combination -hk

/-- The finite computation: the scan succeeds for `N = 100`.  (The same computation runs for
larger `N`, at a cost growing like `N³`; `scanAll pairOK 1000 = true` also holds, but checking
it takes hours unless the definitions of the kernel above are compiled to native code
beforehand.) -/
theorem scanAll_100 : scanAll pairOK 100 = true := by native_decide

/-- **Exhaustiveness for `|n| ≤ 100`.**  The only solutions of the equation with `|n| ≤ 100`
are `(n, x) = (1, -9)` and `(n, x) = (-54, -9)`. -/
theorem sat_exhaustive_abs_n_le_100 {d : ℚ} {n x : ℤ} (h : Sat d n x) (hn : |n| ≤ 100) :
    (n = 1 ∧ x = -9) ∨ (n = -54 ∧ x = -9) := by
  rcases sat_exhaustive_of_scan scanAll_100 h (by exact_mod_cast hn) with h1 | h1 | h1 | h1
  · exact Or.inl h1
  · exact Or.inr h1
  · exact absurd hn (by rw [h1.1]; decide)
  · exact absurd hn (by rw [h1.1]; decide)

/-- **The admissible `d` for `|n| ≤ 100`.**  For `|n| ≤ 100` the only rational values of `d`
for which the equation has an integer solution are `-1/54` and `1583/54`. -/
theorem sat_d_of_abs_n_le_100 {d : ℚ} {n x : ℤ} (h : Sat d n x) (hn : |n| ≤ 100) :
    d = -1/54 ∨ d = 1583/54 := by
  rcases sat_exhaustive_abs_n_le_100 h hn with ⟨rfl, rfl⟩ | ⟨rfl, rfl⟩
  · exact Or.inl (sat_unique h sat_sol₁)
  · exact Or.inr (sat_unique h sat_sol₂)

/-- **The answer for `|n| ≤ 100`.**  A rational `d` admits an integer solution with `|n| ≤ 100`
if and only if it is `-1/54` or `1583/54`. -/
theorem exists_sat_abs_n_le_100_iff (d : ℚ) :
    (∃ n x : ℤ, |n| ≤ 100 ∧ Sat d n x) ↔ d = -1/54 ∨ d = 1583/54 := by
  constructor
  · rintro ⟨n, x, hn, h⟩
    exact sat_d_of_abs_n_le_100 h hn
  · rintro (rfl | rfl)
    · exact ⟨1, -9, by decide, sat_sol₁⟩
    · exact ⟨-54, -9, by decide, sat_sol₂⟩

end DEquation
