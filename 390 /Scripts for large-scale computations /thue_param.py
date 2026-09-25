#!/usr/bin/env python3
"""
thue_param.py
=============

Parameterization of d and generation of Thue equation forms.

The core equation (after algebraic manipulation) is the cubic Thue form:

    36*n^3 - 24*d*n*x^2 - 4*d*(1+d)*x^3 = 65

For rational d = p/q (in lowest terms), multiplying by q^2 gives:

    36*q^2*n^3 - 24*p*q*n*x^2 - 4*p*(q+p)*x^3 = 65*q^2

This module:
  1. Generates Thue forms for given (p, q) parameterizations of d.
  2. Produces ready-to-run PARI/GP commands.
  3. Produces ready-to-run Magma commands.
  4. Estimates the discriminant of the associated cubic field.
"""

from math import gcd, log10


def make_thue_form(p: int, q: int):
    """
    Build the integer Thue form for d = -1 - p/q  (i.e., near the d ≈ -1 root).

    With d = -1 - p/q, we have:
      -d = 1 + p/q = (q+p)/q
      -d*(1+d) = (q+p)/q * (-p/q) = -p*(q+p)/q^2

    So the form (multiplied by q^2) is:
      36*q^2*n^3 + 24*q*(q+p)*n*x^2 - 4*p*(q+p)*x^3 = 65*q^2

    Returns a dict with coefficients and metadata.
    """
    g = gcd(p, q)
    if g != 1:
        p, q = p // g, q // g

    # d = -1 - p/q
    d_num = -(q + p)
    d_den = q

    # Coefficients of the Thue form: a*n^3 + b*n*x^2 + c*x^3 = rhs
    a = 36 * q * q
    b = 24 * q * (q + p)
    c = -4 * p * (q + p)
    rhs = 65 * q * q

    # Discriminant of the associated cubic polynomial a*t^3 + b*t + c = 0
    # For depressed cubic t^3 + pt + q: discriminant = -4p^3 - 27q^2
    # Here: t^3 + (b/a)*t + (c/a) = 0
    # disc = -4*(b/a)^3 - 27*(c/a)^2  (up to a^4 factor)
    # Integer discriminant: -4*b^3*a - 27*c^2*a  ... (careful)
    # For form a*t^3 + b*t + c: disc = -4*b^3 - 27*a*c^2
    disc = -4 * b**3 - 27 * a * c**2

    return {
        "p": p,
        "q": q,
        "d": f"{d_num}/{d_den}",
        "d_num": d_num,
        "d_den": d_den,
        "a": a,       # coefficient of n^3
        "b": b,       # coefficient of n*x^2
        "c": c,       # coefficient of x^3
        "rhs": rhs,   # right-hand side
        "discriminant": disc,
        "log10_disc": log10(abs(disc)) if disc != 0 else float('inf'),
    }


def make_thue_form_near_zero(p: int, q: int):
    """
    Build the Thue form for d = p/q  (near the d ≈ 0 root).

    With d = p/q:
      -d = -p/q
      -d*(1+d) = -p*(q+p)/q^2

    So the form (multiplied by q^2) is:
      36*q^2*n^3 - 24*p*q*n*x^2 - 4*p*(q+p)*x^3 = 65*q^2

    Returns a dict with coefficients and metadata.
    """
    g = gcd(p, q)
    if g != 1:
        p, q = p // g, q // g

    d_num = p
    d_den = q

    a = 36 * q * q
    b = -24 * p * q
    c = -4 * p * (q + p)
    rhs = 65 * q * q

    disc = -4 * b**3 - 27 * a * c**2

    return {
        "p": p,
        "q": q,
        "d": f"{d_num}/{d_den}",
        "d_num": d_num,
        "d_den": d_den,
        "a": a,
        "b": b,
        "c": c,
        "rhs": rhs,
        "discriminant": disc,
        "log10_disc": log10(abs(disc)) if disc != 0 else float('inf'),
    }


def gen_pari_commands(form: dict) -> str:
    """
    Generate PARI/GP commands to solve the Thue equation.

    PARI/GP uses thue() which takes a binary form (a*x^3 + b*x^2*y + ...).
    Our form is: a*n^3 + b*n*x^2 + c*x^3 = rhs
    In PARI notation: a*X^3 + 0*X^2*Y + b*X*Y^2 + c*Y^3 = rhs
    """
    a, b, c, rhs = form["a"], form["b"], form["c"], form["rhs"]
    return f"""\\ PARI/GP commands for d = {form['d']}
\\ Thue form: {a}*n^3 + {b}*n*x^2 + {c}*x^3 = {rhs}
\\ Associated polynomial: {a}*t^3 + {b}*t + {c} = 0

T = thueinit(thuepoly(({a})*t^3 + ({b})*t + ({c})));
solutions = thue(T, {rhs});
print("Solutions: ", solutions);
"""


def gen_magma_commands(form: dict) -> str:
    """
    Generate Magma commands to solve the Thue equation.
    """
    a, b, c, rhs = form["a"], form["b"], form["c"], form["rhs"]
    return f"""// Magma commands for d = {form['d']}
// Thue form: {a}*n^3 + {b}*n*x^2 + {c}*x^3 = {rhs}

Q := RationalField();
R := PolynomialRing(Q);
f := {a}*t^3 + {b}*t + {c};
K := NumberField(RootOf(f));
O := MaximalOrder(K);
F := BinaryQuadraticForm(...);  // Use Thue() in Magma
// For cubic Thue forms, use:
// Thue({a}, {b}, {c}, {rhs});
print "Solving Thue equation...";
// solutions := Thue({a}, {b}, {c}, {rhs});
// print solutions;
"""


def estimate_field_difficulty(form: dict) -> str:
    """
    Provide a qualitative estimate of the computational difficulty
    of solving this Thue equation, based on the discriminant size.
    """
    log_disc = form["log10_disc"]

    if log_disc < 20:
        level = "Trivial — solvable in milliseconds."
    elif log_disc < 40:
        level = "Moderate — solvable in seconds to minutes."
    elif log_disc < 60:
        level = "Hard — may require hours to days. Use PARI/GP or Magma."
    elif log_disc < 100:
        level = "Very hard — requires significant computational resources."
    else:
        level = "Extremely hard — at the frontier of current methods."

    return (f"  Discriminant ~ 10^{log_disc:.1f}\n"
            f"  Difficulty: {level}")


def scan_parameters(p_range=range(1, 21), q_values=None):
    """
    Scan over small p values and representative q values,
    generating Thue forms and difficulty estimates.

    For the d ≈ -1 root: d = -1 - p/q, q ~ 10^11
    For the d ≈ 0 root:  d = p/q, q ~ 10^32

    We test with small q for validation, then extrapolate.
    """
    if q_values is None:
        # Small q for testing; real q ~ 10^11 (near -1) or ~ 10^32 (near 0)
        q_values = [10**11, 10**11 + 1, 10**11 + 7, 10**11 + 13]

    print("=" * 70)
    print("THUE EQUATION PARAMETER SCAN")
    print("=" * 70)
    print("\n--- Root d ≈ -1 (d = -1 - p/q) ---\n")

    for p in p_range:
        for q in q_values:
            if gcd(p, q) != 1:
                continue
            form = make_thue_form(p, q)
            print(f"  p={p}, q={q} -> d={form['d']}")
            print(f"  Form: {form['a']}*n^3 + {form['b']}*n*x^2 + {form['c']}*x^3 = {form['rhs']}")
            print(estimate_field_difficulty(form))
            print()

    print("\n--- Root d ≈ 0 (d = p/q) ---\n")

    q_large = [10**32, 10**32 + 1, 10**32 + 3]
    for p in [1, 2, 3]:
        for q in q_large:
            if gcd(p, q) != 1:
                continue
            form = make_thue_form_near_zero(p, q)
            print(f"  p={p}, q={q} -> d={form['d']}")
            print(f"  Form: {form['a']}*n^3 + {form['b']}*n*x^2 + {form['c']}*x^3 = {form['rhs']}")
            print(estimate_field_difficulty(form))
            print()


if __name__ == "__main__":
    scan_parameters()
