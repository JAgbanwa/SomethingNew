/*
  Exact Magma smoke tests. Run from this directory:

      magma self_test.m

  Or at the Magma prompt:

      load "self_test.m";

  These tests check algebra and filtering; they do not perform a rank search.
*/

load "common.m";
Q := Rationals();

// Reject the first historical false positive and reproduce its precise error.
old_u := Q!(-1108096585330175597) / 121246798630112100;
old_m := Q!504906597765762061 / 90935098972584075;
old_y := Q!715851085517318857008053743 / 492569026891726810138930800;
old_a := 12*old_u + 7;
old_b := old_a + 18*old_m;
old_rhs := 1 + (972*old_m^3 - 19)/(old_a*old_b^2);
assert old_b eq -Q!30/11;
assert old_rhs eq old_a*old_y^2;
assert old_rhs lt 0;
assert not OriginalEquation(old_m, old_u, old_y);
assert not IsRequestedSolution(old_m, old_u, old_y, false);
assert not IsRequestedSolution(old_m, old_u, old_y, true);

// Positive algebra fixture: the equation holds, but m is not an integer.
fixture_m := Q!10891036/1440747;
fixture_u := Q!(-21);
fixture_y := -Q!78246760204/84593013813;
assert OriginalEquation(fixture_m, fixture_u, fixture_y);
assert OriginalEquation(fixture_m, fixture_u, -fixture_y);
assert not OriginalEquation(fixture_m, fixture_u, fixture_y + 1);
assert not IsRequestedSolution(fixture_m, fixture_u, fixture_y, false);
assert not IsRequestedSolution(fixture_m, fixture_u, fixture_y, true);

fixture_a := 12*fixture_u + 7;
fixture_b := fixture_a + 18*fixture_m;
fixture_d := fixture_b^3 - 114;
fixture_x := 6*fixture_d/fixture_a;
fixture_w := 6*fixture_b*fixture_x*fixture_y;
// A rational B is intentional in this map-only fixture. CurveForB enforces the
// integer-search restriction, so construct this auxiliary curve directly.
fixture_E := EllipticCurve([Q| 0, 18*fixture_b^2, 0,
                            108*fixture_b*fixture_d, -216*fixture_d^2]);
fixture_P := fixture_E![fixture_x, fixture_w, 1];
assert RecoverPoint(fixture_b, fixture_P) eq
       [Q| fixture_m, fixture_u, fixture_y];
assert RecoverPoint(fixture_b, -fixture_P) eq
       [Q| fixture_m, fixture_u, -fixture_y];

// An exact polynomial identity verifies the model for every nonzero A.
R<a,b,t> := PolynomialRing(Q, 3);
d := b^3 - 114;
// Both sides below are A^3 times the curve residual after substituting
// X=6D/A and W=6BXY. Clearing denominators makes this a polynomial identity.
curve_cleared := 1296*a*b^2*d^2*t^2 - 216*d^3
                 - 648*a*b^2*d^2 - 648*a^2*b*d^2 + 216*a^3*d^2;
original_cleared := 6*a*b^2*t^2 - 6*a*b^2 - (b-a)^3 + 114;
assert curve_cleared eq 216*d^2*original_cleared;

// Undefined denominators and the elliptic identity point must be rejected.
assert not OriginalEquation(Q!0, -Q!7/12, Q!0);
assert not OriginalEquation(-Q!7/18, Q!0, Q!0);
E1 := CurveForB(1);
assert #RecoverPoint(1, E1!0) eq 0;

// Every integer-(m,u) solution has B=12u+7+18m congruent to 1 modulo 6.
for bad_b in [Q| -30/11, -300, -49] do
    rejected := false;
    try
        bad_E := CurveForB(bad_b);
    catch err
        rejected := true;
    end try;
    assert rejected;
end for;

print "PASS: historical regression, exact curve identity, map, and domain filters.";
print "No search completeness or new integer-(m,u) solution is claimed.";
