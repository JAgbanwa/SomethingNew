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
    d_den //= g

    # Форма Туэ: 36q^2 * n^3 + 24q(q+p) * n * x^2 - 4p(q+p) * x^3 = 65q^2
    A = 36 * q * q           # коэффициент при n^3
    B = 0                     # коэффициент при n^2 * x (нет в нашем случае)
    C = 24 * q * (q + p)      # коэффициент при n * x^2
    D = -4 * p * (q + p)      # коэффициент при x^3
    rhs = 65 * q * q

    # Ассоциированный полином: A*t^3 + C*t - D = 0 (полагая x = t*n)
    # Точнее: 36q^2 * t^3 + 24q(q+p) * t - 4p(q+p) = 0
    poly_coeffs = [A, 0, C, -(-D)]  # [t^3, t^2, t, const] — приводим к виду A*t^3 + 0*t^2 + C*t + (-D) = 0
    # Но D = -4p(q+p), так что -D = 4p(q+p)
    poly_coeffs = [A, 0, C, 4 * p * (q + p)]

    return {
        'd': (d_num, d_den),
        'd_float': d_num / d_den,
        'coefficients': {'A': A, 'B': B, 'C': C, 'D': D},
        'rhs': rhs,
        'polynomial': poly_coeffs,  # A*t^3 + C*t + 4p(q+p) = 0
        'p': p,
        'q': q,
    }


def parametrize_d_near_zero(p: int, q: int) -> Dict:
    """
    Параметризация d = p/q (корень вблизи 0).

    Форма Туэ: 36q^2 * n^3 - 24pq * n * x^2 - 4p(q+p) * x^3 = 65q^2
    """
    A = 36 * q * q
    C = -24 * p * q
    D = -4 * p * (q + p)
    rhs = 65 * q * q

    poly_coeffs = [A, 0, C, -D]  # A*t^3 + C*t + (-D) = 0

    return {
        'd': (p, q),
        'd_float': p / q,
        'coefficients': {'A': A, 'B': 0, 'C': C, 'D': D},
        'rhs': rhs,
        'polynomial': poly_coeffs,
        'p': p,
        'q': q,
    }


def estimate_q_for_n(n_magnitude: int, root: str = 'near_minus_one') -> Dict:
    """
    Оценивает параметры q для заданного порядка n.

    Для корня d ≈ -1: q ~ C * n^{1/4} (C — константа из асимптотики x ~ C*n^{5/4})
    Для корня d ≈ 0:  q ~ (9/C^3) * n^{3/4}

    Параметры:
      n_magnitude: порядок n (например, 10^43)
      root: 'near_minus_one' или 'near_zero'
    """
    # Оценка C: из x ~ n^{5/4} и условий задачи
    # C ~ x / n^{5/4}; при n ~ 10^43, x ~ 10^53 (при C ~ 10^53/10^{53.75} ~ 10^{-0.75} ~ 0.18)
    # Точнее: x ~ n^{5/4} означает C ~ 1, q ~ n^{1/4}

    n_log10 = len(str(n_magnitude)) - 1 if isinstance(n_magnitude, int) else int(n_magnitude)

    if root == 'near_minus_one':
        # q ~ n^{1/4}, p — малое (1..20)
        q_estimate = 10 ** (n_log10 / 4)
        p_range = list(range(1, 21))
        d_estimate = -1 - 1 / q_estimate  # для p=1
    else:
        # q ~ n^{3/4}
        q_estimate = 10 ** (3 * n_log10 / 4)
        p_range = list(range(1, 10))
        d_estimate = 1 / q_estimate

    return {
        'q_estimate': int(q_estimate),
        'q_bits': int(q_estimate).bit_length(),
        'p_range': p_range,
        'd_estimate': d_estimate,
        'root': root,
    }


def generate_parithue_command(p: int, q: int, root: str = 'near_minus_one') -> str:
    """
    Генерирует команду для PARI/GP thue() для решения уравнения Туэ.

    Форма: A*n^3 + C*n*x^2 + D*x^3 = rhs
    PARI/GP требует полином от двух переменных.
    """
    if root == 'near_minus_one':
        params = parametrize_d_near_minus_one(p, q)
    else:
        params = parametrize_d_near_zero(p, q)

    A = params['coefficients']['A']
    C = params['coefficients']['C']
    D = params['coefficients']['D']
    rhs = params['rhs']

    # PARI/GP: thue(Thue([A,0,C,D], rhs))
    # Полином: A*X^3 + C*X*Y^2 + D*Y^3
    return f"thue(thueinit({A}*X^3 + {C}*X*Y^2 + {D}*Y^3), {rhs})"


def generate_magma_command(p: int, q: int, root: str = 'near_minus_one') -> str:
    """
    Генерирует команду для Magma Thue().
    """
    if root == 'near_minus_one':
        params = parametrize_d_near_minus_one(p, q)
    else:
        params = parametrize_d_near_zero(p, q)

    A = params['coefficients']['A']
    C = params['coefficients']['C']
    D = params['coefficients']['D']
    rhs = params['rhs']

    return f"Thue({A}*n^3 + {C}*n*x^2 + {D}*x^3, {rhs});"


def run_parametrization_demo():
    """Демонстрация параметризации."""
    print("=" * 60)
    print("ДЕМО: Параметризация d")
    print("=" * 60)

    # Оценка для n ~ 10^43
    n_mag = 10**43
    for root in ['near_minus_one', 'near_zero']:
        est = estimate_q_for_n(n_mag, root)
        print(f"\nКорень {root}:")
        print(f"  Оценка q: ~10^{int(est['q_bits'] * 0.301)} ({est['q_bits']} бит)")
        print(f"  Диапазон p: {est['p_range']}")
        print(f"  Оценка d: {est['d_estimate']:.6e}")

        # Пример для p=1, q=100 (демонстрационный)
        if root == 'near_minus_one':
            params = parametrize_d_near_minus_one(1, 100)
        else:
            params = parametrize_d_near_zero(1, 100)

        print(f"  Пример (p=1, q=100):")
        print(f"    d = {params['d'][0]}/{params['d'][1]} = {params['d_float']:.6f}")
        print(f"    Коэффициенты: A={params['coefficients']['A']}, "
              f"C={params['coefficients']['C']}, D={params['coefficients']['D']}")
        print(f"    RHS = {params['rhs']}")

        # PARI/GP команда
        gp_cmd = generate_parithue_command(1, 100, root)
        print(f"    PARI/GP: {gp_cmd[:80]}...")

        # Magma команда
        magma_cmd = generate_magma_command(1, 100, root)
        print(f"    Magma:   {magma_cmd[:80]}...")


if __name__ == "__main__":
    run_parametrization_demo()
