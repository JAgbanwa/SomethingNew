/*
  Standalone Magma smoke tests. Paste this entire file into the calculator,
  or run from this directory:

      magma self_test.m

  Or at the Magma prompt:

      load "self_test.m";

  These tests check algebra, filtering, bounded point search, and capped
  combinations. They do not perform rank or generator computations.
*/

// BEGIN SHARED HELPERS (generated from common.m)
/*
Canonical exact helpers for the four searches in this directory.
build_standalone.py embeds these helpers in each executable script.

Target: y^2 = 1 + (972*m^3-19)/((12*u+7)*(12*u+7+18*m)^2),
        with m,u integers and y rational (nonintegral by default).

A=12*u+7, B=A+18*m, D=B^3-114 give
  6*A*B^2*y^2 = -A^3+3*B*A^2+3*B^2*A+D.
Set X=6*D/A and W=6*B*X*y. The correct elliptic curve is
  W^2 = X^3+18*B^2*X^2+108*B*D*X-216*D^2.
Inverse: A=6*D/X, m=(B-A)/18, u=(A-7)/12, y=W/(6*B*X).

The former model omitted A from (A*B*y)^2=A*(A*B^2+972*m^3-19).
Only integer B congruent to 1 modulo 6 can yield integer m,u.
The default uses bounded point searches, without computing generators.
Optional generator computations and finite combinations are not exhaustive.
*/

Q := Rationals();
Z := Integers();

function OriginalEquation(m,u,y)
    m := Q!m; u := Q!u; y := Q!y;
    A := 12*u+7;
    B := A+18*m;
    if A*B eq 0 then
        return false;
    end if;
    return y^2 eq 1+(972*m^3-19)/(A*B^2);
end function;

function IsRequestedSolution(m,u,y,allow_integer_y)
    if Denominator(Q!m) ne 1 or Denominator(Q!u) ne 1 then
        return false;
    end if;
    if not allow_integer_y and Denominator(Q!y) eq 1 then
        return false;
    end if;
    return OriginalEquation(m,u,y);
end function;

function CurveForB(B)
    assert Denominator(Q!B) eq 1;
    B := Z!B;
    assert B mod 6 eq 1;
    D := B^3-114;
    return EllipticCurve([Q | 0,18*B^2,0,108*B*D,-216*D^2]);
end function;

// Low-level inverse: also supports rational B for algebraic checks.
// Empty sequence denotes an exceptional point with no finite inverse.
function RecoverPoint(B,P)
    B := Q!B;
    if B eq 0 or P[3] eq 0 then
        return [Q | ];
    end if;
    X := P[1]; W := P[2];
    D := B^3-114;
    if X eq 0 or D eq 0 then
        return [Q | ];
    end if;
    A := 6*D/X;
    m := (B-A)/18;
    u := (A-7)/12;
    y := W/(6*B*X);
    assert OriginalEquation(m,u,y);
    return [Q | m,u,y];
end function;

// Materialize at most max_combinations points, including the identity first.
// Coefficients are ordered 0,1,-1,2,-2,... so a truncated box starts centrally.
function BoundedPointCombinations(E,G,H,max_combinations)
    assert H ge 1 and max_combinations ge 1;
    width := 2*H+1;
    total := width^#G;
    count := Minimum(total,max_combinations);
    points := [E!0];
    for j in [1..count-1] do
        digits := j;
        P := E!0;
        for S in G do
            digit := digits mod width;
            if digit mod 2 eq 1 then
                k := (digit+1) div 2;
            else
                k := -(digit div 2);
            end if;
            digits := digits div width;
            if k ne 0 then
                P := P+k*S;
            end if;
        end for;
        Append(~points,P);
    end for;
    return points,total gt count;
end function;

procedure RecordPoint(~found,B,P,allow_integer_y)
    if P[3] eq 0 or P[1] eq 0 then
        return;
    end if;
    A := 6*(B^3-114)/P[1];
    if Denominator(A) ne 1 then
        return;
    end if;
    Ai := Z!A;
    if (Ai-7) mod 12 ne 0 or (B-Ai) mod 18 ne 0 then
        return;
    end if;
    values := RecoverPoint(B,P);
    if #values eq 0 then
        return;
    end if;
    m := values[1]; u := values[2]; y := values[3];
    if not IsRequestedSolution(m,u,y,allow_integer_y) then
        return;
    end if;
    sol := <Z!m,Z!u,Q!y>;
    if sol notin found then
        Include(~found,sol);
        printf "VERIFIED m=%o, u=%o, y=%o\n",sol[1],sol[2],sol[3];
    end if;
end procedure;

function SearchGeneratorBox(B,E,G,H,allow_integer_y :
                            MaxSeeds:=3,MaxCombinations:=1000)
    assert Denominator(Q!B) eq 1;
    B := Z!B;
    assert B mod 6 eq 1;
    assert H ge 1 and MaxSeeds ge 1 and MaxCombinations ge 1;
    found := {};
    seeds := [E!0];
    Remove(~seeds,1);
    seen_x := { Q | };
    omitted := 0;

    // Check every input point directly, even if it is omitted from mixed sums.
    // Our model has a1=a3=0, so P and -P have the same x-coordinate.
    for P in G do
        RecordPoint(~found,B,P,allow_integer_y);
        RecordPoint(~found,B,-P,allow_integer_y);
        if P[3] eq 0 then
            continue;
        end if;
        if P[1] in seen_x then
            continue;
        end if;
        Include(~seen_x,P[1]);
        if #seeds lt MaxSeeds then
            Append(~seeds,P);
        else
            omitted +:= 1;
        end if;
    end for;
    printf "B=%o: %o seeds for mixed sums; %o omitted by MaxSeeds.\n",
           B,#seeds,omitted;
    if #seeds eq 0 then
        print "No finite seed points were found at the current search bound.";
        return found;
    end if;
    printf "B=%o: forming at most %o coefficient combinations.\n",
           B,Minimum((2*H+1)^#seeds,MaxCombinations);
    points,truncated := BoundedPointCombinations(E,seeds,H,MaxCombinations);
    if truncated then
        print "Combination limit reached: this coefficient box is truncated.";
    end if;
    for P in points do
        RecordPoint(~found,B,P,allow_integer_y);
        RecordPoint(~found,B,-P,allow_integer_y);
    end for;
    return found;
end function;

function SearchB(B,H,allow_integer_y : PointBound:=1000,
                 UseGenerators:=false,MaxSeeds:=3,MaxCombinations:=1000)
    assert PointBound ge 1;
    printf "Starting B=%o.\n",B;
    E := CurveForB(B);
    if UseGenerators then
        print "Computing generators; this optional step can take a long time.";
        G := Generators(E);
    else
        printf "Bounded rational-point search, x-height bound=%o.\n",PointBound;
        G := [P : P in Points(E : Bound:=PointBound)];
    end if;
    printf "B=%o: %o input points; coefficient bound=%o.\n",B,#G,H;
    found := SearchGeneratorBox(B,E,G,H,allow_integer_y :
                  MaxSeeds:=MaxSeeds,MaxCombinations:=MaxCombinations);
    printf "B=%o: %o verified triples in this finite search.\n",B,#found;
    return found;
end function;
// END SHARED HELPERS
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

// Exercise Magma's actual point-search API on a curve with known points.
toy := EllipticCurve([Q| 0,-2]);
toy_p := toy![3,5,1];
assert toy![6,10,2] eq toy_p;
toy_points := Points(toy : Bound:=10);
assert toy_p in toy_points;
assert -toy_p in toy_points;

// Mixed sums, central ordering, and the explicit combination limit.
box,cut := BoundedPointCombinations(toy,[toy_p,2*toy_p],1,9);
assert #box eq 9 and not cut;
assert box[1] eq toy!0 and box[2] eq toy_p and box[3] eq -toy_p;
assert box[5] eq 3*toy_p;
small_box,cut := BoundedPointCombinations(toy,[toy_p,2*toy_p],1,5);
assert cut and small_box eq box[1..5];
identity_box,cut := BoundedPointCombinations(toy,[toy_p],1,1);
assert cut and identity_box eq [toy!0];
// The cap must also prevent allocating an array of 2*H+1 coefficients.
huge_bound_box,cut := BoundedPointCombinations(toy,[toy_p],10^12,3);
assert cut and huge_bound_box eq [toy!0,toy_p,-toy_p];

// Run the real bounded-search path, including the no-seed case.
assert #SearchGeneratorBox(1,E1,[E1!0],1,false :
    MaxSeeds:=1,MaxCombinations:=2) eq 0;
assert #SearchB(1,1,false : PointBound:=10,UseGenerators:=false,
    MaxSeeds:=1,MaxCombinations:=2) eq 0;

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

print "PASS: algebra, historical regression, filters, point API, and bounded combinations.";
print "No search completeness or new integer-(m,u) solution is claimed.";
