/*
Shared exact helpers for the four searches in this directory.
Run from this directory so that load "common.m" resolves correctly.

Target: y^2 = 1 + (972*m^3-19)/((12*u+7)*(12*u+7+18*m)^2),
        with m,u integers and y rational (nonintegral by default).

A=12*u+7, B=A+18*m, D=B^3-114 give
  6*A*B^2*y^2 = -A^3+3*B*A^2+3*B^2*A+D.
Set X=6*D/A and W=6*B*X*y. The correct elliptic curve is
  W^2 = X^3+18*B^2*X^2+108*B*D*X-216*D^2.
Inverse: A=6*D/X, m=(B-A)/18, u=(A-7)/12, y=W/(6*B*X).

The former model omitted A from (A*B*y)^2=A*(A*B^2+972*m^3-19).
Only integer B congruent to 1 modulo 6 can yield integer m,u.
These routines search finite combinations of returned generators.
They do not claim that the returned generators or search are exhaustive.
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

function SearchGeneratorBox(B,E,G,H,allow_integer_y)
    assert Denominator(Q!B) eq 1;
    B := Z!B;
    assert B mod 6 eq 1;
    assert H ge 1;
    D := B^3-114;

    // Include mixed sums of generators, with each coefficient in [-H,H].
    // At most (2*H+1)^#G combinations are formed; keep H modest.
    points := { E!0 };
    for P in G do
        points := { R+k*P : R in points, k in [-H..H] };
    end for;

    found := {};
    for P in points do
        if P[3] eq 0 then
            continue;
        end if;
        X := P[1];
        if X eq 0 then
            continue;
        end if;

        // Filter integer m,u using the corrected inverse A=6*D/X.
        A := 6*D/X;
        if Denominator(A) ne 1 then
            continue;
        end if;
        Ai := Z!A;
        if (Ai-7) mod 12 ne 0 or (B-Ai) mod 18 ne 0 then
            continue;
        end if;

        values := RecoverPoint(B,P);
        if #values eq 0 then
            continue;
        end if;
        m := values[1]; u := values[2]; y := values[3];
        if not IsRequestedSolution(m,u,y,allow_integer_y) then
            continue;
        end if;
        sol := <Z!m,Z!u,Q!y>;
        if sol notin found then
            Include(~found,sol);
            printf "VERIFIED m=%o, u=%o, y=%o\n", sol[1],sol[2],sol[3];
        end if;
    end for;
    return found;
end function;

function SearchB(B,H,allow_integer_y)
    E := CurveForB(B);
    G := Generators(E);
    printf "B=%o; returned generators=%o; coefficient bound=%o\n",B,#G,H;
    found := SearchGeneratorBox(B,E,G,H,allow_integer_y);
    printf "B=%o: %o verified triples in this finite generator box.\n",B,#found;
    return found;
end function;
