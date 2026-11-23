// CE375 d-first engine: production campaigns use exactly g = -1 and g = +1.
// See DERIVATION.md for the parameterization and the scope of this search.
//
// Target: rational d with integer n and
//   N(n) = 36n^3 + 54n^2 + 27n - 58
//        = -2*d*x^2*( -(x+6n+3) + s ),   s = sqrt((x+6n+3)^2 + N(n)/x) >= 0,
// where EITHER
//   (integer chart) x and s are integers with gcd(n, x, s) = 1, OR
//   (half chart)    x = X/2 and s = Y/2 with X, Y odd and gcd(X, Y) = 1.
//
// With S = 6n+3 we have N = (S^3 - K)/6 for K = 375. The constant K is a
// parameter only so that values with KNOWN representations (K = 3, 15, 21,
// 57, ...) can exercise the identical code; production uses K = 375 = 3 * 5^3.
// Every hit is labelled with two primitivity flags (see certify()):
//   primitive_point: gcd(n, x, s) = 1 (integer chart) / gcd(X, Y) = 1 (half chart)
//   primitive_cubes: gcd(A, B, C) = 1 for the cube components
// and "desired" = primitive_point. The cube flag is informational; g = +-1
// already implies gcd(A, B, C) = gcd(S, g) = 1. Either chart can supply a result.
//
// --mode xy (the default) searches the
// y^2 equation  y^2 = (x+6n+3)^2 + N(n)/x  for DESIRED points of both charts,
// both signs of y, using the proved 5-adic filter (mod 125) and both Thue
// branches. Hits identify the point (n, X, |Y|)
// with X = 2x, Y = 2|y|, and report the principal d = -(x + 6n+3 + |y|)/(2x).
//
// --mode xy-half searches ONLY for rational (x, y)
// with integer n on  y^2 = (x+6n+3)^2 + N(n)/x,  x = X/2, y = Y/2, X, Y odd,
// gcd(X, Y) = 1, both signs of y. It uses only odd q, the 5-adic filter, and accepts the
// conjugate branch (s < 0, i.e. y = -s) as well.
// --mode both retains principal-square-root reporting for diagnostics, with
// the same fixed production values g = +-1.
//
// For d = p/q in lowest terms (q > 0) the points are exactly the integer
// solutions (S, g) of the binary cubic Thue equation
//   F_d(S, g) = S^3 - 6 p q S g^2 + 3 p q (p+q) g^3 = K
// with x = -q g / 2 and s = (2p+q) g / 2 - S >= 0. Then q*g even gives the
// integer chart and q*g odd gives the half chart.
//
// Production finds every integer root S for each of g = -1, +1 directly,
// with exact GMP arithmetic and no continued-fraction work or configurable g bound.
// The separate --raw diagnostic solver remains general: for a supplied finite
// G, it uses exact small-g root finding and certified continued fractions for
// larger g. Its floating-point values only propose exactly checked brackets.
#include <gmpxx.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <numeric>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
using Z = mpz_class;
using Q = mpq_class;
constexpr const char* VERSION = "2.0.0";
constexpr const char* PARAMETERIZATION = "ce375-dfirst-unit-g-both-charts-v2";

Z integer(const std::string& s) {
    if (s.empty()) throw std::runtime_error("empty integer");
    std::size_t i = (s[0] == '-' || s[0] == '+') ? 1 : 0;
    if (i == s.size()) throw std::runtime_error("invalid integer");
    for (; i < s.size(); ++i)
        if (s[i] < '0' || s[i] > '9') throw std::runtime_error("invalid decimal integer");
    Z z;
    if (mpz_set_str(z.get_mpz_t(), s[0] == '+' ? s.c_str() + 1 : s.c_str(), 10) != 0)
        throw std::runtime_error("invalid decimal integer");
    return z;
}

std::string quoted(const std::string& s) { return "\"" + s + "\""; }  // decimal strings only
int sgn(const Z& z) { return mpz_sgn(z.get_mpz_t()); }
Z floor_div(const Z& a, const Z& b) { Z r; mpz_fdiv_q(r.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t()); return r; }
Z ceil_div(const Z& a, const Z& b) { Z r; mpz_cdiv_q(r.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t()); return r; }

// ---------------------------------------------------------------------------
// The monic binary cubic form of one value of d.
struct Form {
    Z p, q, c1, c0;  // F(S,g) = S^3 + c1 S g^2 + c0 g^3
    Form(const Z& p_, const Z& q_) : p(p_), q(q_), c1(-6 * p_ * q_), c0(3 * p_ * q_ * (p_ + q_)) {}
    Z F(const Z& S, const Z& g) const {
        Z g2 = g * g;
        return S * S * S + c1 * S * g2 + c0 * g2 * g;
    }
    // sign(F(z, D)) = sign(z/D - alpha) for D > 0: f(t) = (t-alpha) |t-beta|^2.
    int side(const Z& z, const Z& D) const { return sgn(F(z, D)); }
};

struct Stats {
    unsigned long long convergents = 0, small_g_values = 0, thue_solutions = 0,
                       integer_chart = 0, half_chart = 0, other_branch = 0,
                       refinements = 0, exact_roots = 0;
    unsigned max_bits = 0;
};

struct Solution { Z S, g; std::string source; };

// Integer roots S of h(S) = F(S, g) - T for one fixed g, by exact binary
// search on the (at most three) integer intervals where h is monotone.
void integer_roots_in_S(const Form& f, const Z& g, const Z& T, std::vector<Z>& out) {
    Z g2 = g * g;
    Z k1 = f.c1 * g2, k0 = f.c0 * g2 * g - T;  // h(S) = S^3 + k1 S + k0
    auto h = [&](const Z& S) -> Z { return S * S * S + k1 * S + k0; };
    Z B = 2 + abs(k1) + abs(k0);  // Cauchy bound: every real root has |S| < B
    auto search = [&](Z lo, Z hi, int direction) {
        if (lo > hi) return;
        while (lo <= hi) {
            Z mid = floor_div(lo + hi, 2);
            int s = sgn(h(mid)) * direction;
            if (s == 0) { out.push_back(mid); return; }
            if (s < 0) lo = mid + 1; else hi = mid - 1;
        }
    };
    if (sgn(k1) >= 0) { search(-B, B, 1); return; }
    // h'(S) = 3 S^2 + k1 vanishes at S = +-r, r^2 = -k1/3; s = floor(r).
    Z r2 = floor_div(-k1, Z(3)), s;
    mpz_sqrt(s.get_mpz_t(), r2.get_mpz_t());
    search(-B, -s - 1, 1);
    search(-s, s, -1);
    search(s + 1, B, 1);
}

// The production search has two fixed g values. Solve the cubic in S for
// each sign directly; the general CF solver below is only for --raw diagnostics.
std::vector<Solution> solve_unit_g(const Form& f, const Z& T, Stats& st) {
    std::vector<Solution> sols;
    std::vector<Z> roots;
    for (int sign : {-1, 1}) {
        Z g = sign;
        roots.clear();
        ++st.small_g_values;
        integer_roots_in_S(f, g, T, roots);
        for (const Z& S : roots) {
            if (f.F(S, g) != T) throw std::runtime_error("internal unit-g solution check failed");
            sols.push_back({S, g, "unit_g"});
            ++st.thue_solutions;
        }
    }
    return sols;
}

// Unique real root alpha of f(t) = t^3 + c1 t + c0, isolated as
// alpha in (z/2^bits, (z+1)/2^bits), or exactly alpha = z/2^bits.
struct Root { Z z; unsigned bits = 0; bool exact = false; };

bool fix_bracket(const Form& f, const Z& D, Z& z) {
    int s = f.side(z, D);
    if (s == 0) return true;
    Z lo, hi;
    if (s < 0) {
        lo = z;
        for (Z step = 1;; step *= 2) {
            Z t = z + step; int st = f.side(t, D);
            if (st == 0) { z = t; return true; }
            if (st > 0) { hi = t; break; }
            lo = t;
        }
    } else {
        hi = z;
        for (Z step = 1;; step *= 2) {
            Z t = z - step; int st = f.side(t, D);
            if (st == 0) { z = t; return true; }
            if (st < 0) { lo = t; break; }
            hi = t;
        }
    }
    while (hi - lo > 1) {
        Z mid = floor_div(lo + hi, 2); int st = f.side(mid, D);
        if (st == 0) { z = mid; return true; }
        if (st < 0) lo = mid; else hi = mid;
    }
    z = lo;
    return false;
}

Root isolate(const Form& f, unsigned bits) {
    // A floating-point guess is only a starting point: fix_bracket() then
    // establishes the bracket by exact sign tests, whatever the guess's error.
    Root r; r.bits = 24;
    Z D = Z(1) << 24;
    long double P = f.c1.get_d(), Qc = f.c0.get_d();  // t^3 + P t + Qc = 0
    long double disc = Qc * Qc / 4.0L + P * P * P / 27.0L;  // > 0: one real root
    long double guess = 0.0L;
    if (disc >= 0.0L) {
        long double h = -Qc / 2.0L, s = std::sqrt(disc);
        long double u = std::cbrt(h + (h >= 0.0L ? s : -s));
        guess = (u != 0.0L) ? u - P / (3.0L * u) : std::cbrt(-Qc);
        for (int it = 0; it < 3; ++it) {
            long double fv = guess * guess * guess + P * guess + Qc, dv = 3.0L * guess * guess + P;
            if (dv != 0.0L) guess -= fv / dv;
        }
    }
    if (std::isfinite(static_cast<double>(guess)) && std::fabs(static_cast<double>(guess)) < 1e15) {
        mpz_set_d(r.z.get_mpz_t(), std::floor(static_cast<double>(guess * 16777216.0L)));
        if (fix_bracket(f, D, r.z)) { r.exact = true; return r; }
    } else {
        Z R = 2 + abs(f.c1) + abs(f.c0);
        Z lo = -R * D, hi = R * D;
        while (hi - lo > 1) {
            Z mid = floor_div(lo + hi, 2); int st = f.side(mid, D);
            if (st == 0) { r.z = mid; r.exact = true; return r; }
            if (st < 0) lo = mid; else hi = mid;
        }
        r.z = lo;
    }
    while (r.bits < bits) {
        unsigned nb = std::min(bits, 2 * r.bits);
        r.z <<= (nb - r.bits);
        D = Z(1) << nb;
        Z D2 = D * D;
        for (int it = 0; it < 2; ++it) {
            Z val = f.F(r.z, D), der = 3 * r.z * r.z + f.c1 * D2;
            if (sgn(der) == 0 || sgn(val) == 0) break;
            r.z -= val / der;
        }
        r.bits = nb;
        if (fix_bracket(f, D, r.z)) { r.exact = true; return r; }
    }
    return r;
}

// Lower bound L for 4*eta^2 = 3 alpha^2 - 24pq (eta = |Im beta|), from the bracket.
// Returns false if the bracket is too wide to prove positivity.
bool eta_bound(const Form& f, const Root& r, Q& lower) {
    Z D = Z(1) << r.bits;
    Z a;  // bracket endpoint of minimal |.|
    if (r.exact) a = r.z;
    else if (sgn(r.z) >= 0) a = r.z;
    else if (sgn(r.z + 1) <= 0) a = r.z + 1;
    else a = 0;
    lower = Q(3 * a * a - 24 * f.p * f.q * D * D, D * D);
    lower.canonicalize();
    return sgn(lower.get_num()) > 0;
}

std::vector<Z> cube_divisors(const Z& T) {
    std::vector<Z> e;
    Z aT = abs(T);
    for (Z c = 1; c * c * c <= aT; ++c)
        if (mpz_divisible_p(aT.get_mpz_t(), Z(c * c * c).get_mpz_t())) e.push_back(c);
    return e;
}

struct Solver {
    Z T, G;              // target K, maximal |g|
    bool skip3;          // 3 | g is impossible (proved when K = +-3 mod 9)
    unsigned bits0, max_bits;
    std::vector<Z> cubes;
    bool odd_g_only = false;  // xy-half mode: q g odd, so g odd

    std::vector<Solution> solve(const Form& f, Stats& st, Z* g0_out = nullptr) const {
        std::set<std::pair<std::string, std::string>> seen;
        std::vector<Solution> sols;
        auto add = [&](const Z& S, const Z& g, const char* src) {
            if (sgn(g) == 0 || abs(g) > G) return;
            if (f.F(S, g) != T) throw std::runtime_error("internal Thue solution check failed");
            if (seen.emplace(S.get_str(), g.get_str()).second) { sols.push_back({S, g, src}); ++st.thue_solutions; }
        };
        unsigned need = 2 * static_cast<unsigned>(mpz_sizeinbase(G.get_mpz_t(), 2)) + 64;
        unsigned bits = std::max(bits0, need);
        Root r = isolate(f, bits);
        Q lower;
        while (!r.exact && !eta_bound(f, r, lower)) {
            if (r.bits >= max_bits) throw std::runtime_error("precision cap reached while bounding eta");
            r = isolate(f, std::min(max_bits, 2 * r.bits)); ++st.refinements;
        }
        if (r.exact) eta_bound(f, r, lower);
        // Legendre holds for |g| > 2|T|/eta^2 = 8|T|/(3 alpha^2 - 24pq); L <= 3 alpha^2 - 24pq.
        Z g0 = floor_div(8 * abs(T) * lower.get_den(), lower.get_num());
        if (r.exact) {
            // alpha = a/b rational: for S/g != alpha, 1/(b|g|) <= |T|/(eta^2 |g|^3),
            // so g^2 <= |T| b / eta^2 = 4 |T| b / (3 alpha^2 - 24pq). No CF needed.
            ++st.exact_roots;
            Q alpha(r.z, Z(1) << r.bits); alpha.canonicalize();
            Z bound2 = floor_div(4 * abs(T) * alpha.get_den() * lower.get_den(), lower.get_num()), gb;
            mpz_sqrt(gb.get_mpz_t(), bound2.get_mpz_t());
            g0 = std::max(g0, Z(gb + 1));
        }
        if (g0 > G) g0 = G;
        if (g0_out) *g0_out = g0;
        std::vector<Z> roots;
        for (Z g = 1; g <= g0; ++g) {
            if (skip3 && mpz_divisible_ui_p(g.get_mpz_t(), 3)) continue;
            if (odd_g_only && mpz_even_p(g.get_mpz_t())) continue;
            for (int s : {1, -1}) {
                Z gs = s * g;
                roots.clear(); ++st.small_g_values;
                integer_roots_in_S(f, gs, T, roots);
                for (const Z& S : roots) add(S, gs, "small_g");
            }
        }
        if (r.exact || g0 >= G) return sols;
        for (;;) {
            st.max_bits = std::max(st.max_bits, r.bits);
            if (cf_pass(f, r, st, add)) return sols;
            if (r.bits >= max_bits) throw std::runtime_error("precision cap reached before CF completeness");
            r = isolate(f, std::min(max_bits, 2 * r.bits)); ++st.refinements;
            if (r.exact) return solve_exact_fallback(f, st, add);
        }
    }

    template <class Add>
    std::vector<Solution> solve_exact_fallback(const Form& f, Stats& st, Add& add) const {
        // Restart this d with the exact-root bound (discarding nothing: add() dedupes).
        ++st.exact_roots;
        Root r = isolate(f, bits0); Q lower;
        if (!r.exact) throw std::runtime_error("inconsistent exact-root detection");
        eta_bound(f, r, lower);
        Q alpha(r.z, Z(1) << r.bits); alpha.canonicalize();
        Z bound2 = floor_div(4 * abs(T) * alpha.get_den() * lower.get_den(), lower.get_num()), gb;
        mpz_sqrt(gb.get_mpz_t(), bound2.get_mpz_t());
        Z g0 = std::max(floor_div(8 * abs(T) * lower.get_den(), lower.get_num()), Z(gb + 1));
        if (g0 > G) g0 = G;
        std::vector<Z> roots;
        for (Z g = 1; g <= g0; ++g)
            for (int s : {1, -1}) { Z gs = s * g; roots.clear(); integer_roots_in_S(f, gs, T, roots);
                for (const Z& S : roots) add(S, gs, "small_g"); }
        throw std::runtime_error("exact root found only after refinement; rerun this d alone");
    }

    // One certified CF pass over the open bracket. Returns true when every
    // convergent with denominator <= G has been tested.
    template <class Add>
    bool cf_pass(const Form& f, const Root& r, Stats& st, Add& add) const {
        Z D = Z(1) << r.bits;
        Z ln = r.z, ld = D, hn = r.z + 1, hd = D;  // alpha in (ln/ld, hn/hd)
        Z pm2 = 0, pm1 = 1, qm2 = 1, qm1 = 0;
        for (;;) {
            Z cmin = floor_div(ln, ld), cmax = ceil_div(hn, hd) - 1;
            if (sgn(qm1) > 0 && cmin * qm1 + qm2 > G) return true;
            if (cmin != cmax) return false;
            const Z& c = cmin;
            Z pk = c * pm1 + pm2, qk = c * qm1 + qm2;
            if (qk > G) return true;
            ++st.convergents;
            Z value = f.F(pk, qk);
            for (const Z& e : cubes) {
                Z t = T / (e * e * e);
                if (value == t) add(e * pk, e * qk, "convergent");
                else if (value == -t) add(-e * pk, -e * qk, "convergent");
            }
            pm2 = pm1; pm1 = pk; qm2 = qm1; qm1 = qk;
            Z lr = ln - c * ld, hr = hn - c * hd;
            if (sgn(lr) == 0) return false;
            if (sgn(lr) < 0 || sgn(hr) <= 0) throw std::runtime_error("internal CF interval invariant failed");
            Z nln = hd, nld = hr, nhn = ld, nhd = lr;
            ln = std::move(nln); ld = std::move(nld); hn = std::move(nhn); hd = std::move(nhd);
        }
    }
};

// ---------------------------------------------------------------------------
// Admissibility of d = p/q (all conditions are proved in DERIVATION.md):
//  gcd(p,q) = 1, p != 0, q > 0;  3 !| pq;  p == q (mod 3);
//  every prime l >= 5 dividing pq:
//    l | K with v_l(K) <= 2  ->  v_l(pq) <= v_l(K);
//    l !| K, l == 1 (mod 3)  ->  K must be a cube modulo l;
//  for each prime l >= 5 dividing K: (p mod l, q mod l) must make
//    F_d(S,g) == K (mod l) solvable with (S,g) != (0,0) (mod l).
// No condition is placed on 2: both parities of q are needed (two charts).
struct Admissibility {
    long long K;
    bool half = false;   // xy-half mode: q odd
    bool cube_tables = false;  // xy and xy-half modes: the l^3 tables below
    // xy-half mode, primes l with v_l(K) >= 3 (l = 5 at K = 375): a primitive
    // point has (S, g) != (0, 0) mod l, so F_d(S, g) = K must be solvable mod
    // l^3 with that restriction. F depends on d only via a = pq, b = pq(p+q).
    struct Cube { long long l, m; std::vector<uint8_t> ab; };  // ab[a*m + b]
    std::vector<Cube> cube_local;
    std::vector<uint32_t> spf;
    std::vector<uint8_t> ok;
    struct Local { long long l; std::vector<uint8_t> allowed; };  // allowed[(p%l)*l + q%l]
    std::vector<Local> local;

    static long long powmod(long long b, long long e, long long mod) {
        long long r = 1 % mod; b %= mod; if (b < 0) b += mod;
        while (e) { if (e & 1) r = r * b % mod; b = b * b % mod; e >>= 1; }
        return r;
    }
    static int vval(long long a, long long l) { int v = 0; if (a == 0) return 99; while (a % l == 0) { a /= l; ++v; } return v; }

    int cap_for_prime(long long l) const {
        if (l == 2) return 255;
        if (l == 3) return 0;
        int vk = vval(std::llabs(K), l);
        if (vk > 0) return vk <= 2 ? vk : 255;
        if (l % 3 == 2) return 255;
        // l == 1 mod 3, l !| 3K: S^3 == K solvable iff K^((l-1)/3) == 1 (mod l).
        return powmod(K, (l - 1) / 3, l) == 1 ? 255 : 0;
    }

    Admissibility(long long K_, uint32_t limit, bool half_ = false, bool tables_ = false)
        : K(K_), half(half_), cube_tables(tables_ || half_), spf(limit + 1, 0), ok(limit + 1, 1) {
        for (uint64_t i = 2; i <= limit; ++i)
            if (!spf[i]) for (uint64_t j = i; j <= limit; j += i) if (!spf[j]) spf[j] = static_cast<uint32_t>(i);
        std::vector<uint32_t> rest(limit + 1, 1), expo(limit + 1, 0);
        for (uint32_t v = 2; v <= limit; ++v) {
            uint32_t l = spf[v], w = v / l;
            if (w > 1 && spf[w] == l) { expo[v] = expo[w] + 1; rest[v] = rest[w]; }
            else { expo[v] = 1; rest[v] = w; }
            int cap = (l == 3) ? 255 : cap_for_prime(l);  // 3 is checked separately
            ok[v] = ok[rest[v]] && static_cast<int>(expo[v]) <= cap;
        }
        long long a = std::llabs(K);
        for (long long l = 5; l <= a && l <= 4000; ++l) {
            bool prime = l > 1; for (long long t = 2; t * t <= l; ++t) if (l % t == 0) { prime = false; break; }
            if (!prime || a % l) continue;
            Local loc{l, std::vector<uint8_t>(static_cast<std::size_t>(l * l), 0)};
            long long Kl = ((K % l) + l) % l;
            for (long long pr = 0; pr < l; ++pr) for (long long qr = 0; qr < l; ++qr) {
                long long pq = pr * qr % l, c1 = (l - 6 * pq % l) % l, c0 = 3 * pq % l * ((pr + qr) % l) % l;
                bool found = false;
                for (long long S = 0; S < l && !found; ++S) for (long long g = 0; g < l && !found; ++g) {
                    if (S == 0 && g == 0) continue;  // gcd(S,g) = 1 needs K cube-free at l; see below
                    long long v = (S * S % l * S + c1 * S % l * g % l * g + c0 * g % l * g % l * g) % l;
                    if (v == Kl) found = true;
                }
                loc.allowed[static_cast<std::size_t>(pr * l + qr)] = found;
            }
            // The primitivity (S,g) != (0,0) mod l is valid only when l^3 !| K.
            if (vval(a, l) >= 3) {
                if (cube_tables && l * l * l <= 4000) {
                    long long m = l * l * l, Km = ((K % m) + m) % m;
                    Cube cu{l, m, std::vector<uint8_t>(static_cast<std::size_t>(m * m), 0)};
                    for (long long S = 0; S < m; ++S) for (long long g = 0; g < m; ++g) {
                        if (S % l == 0 && g % l == 0) continue;
                        long long S3 = S * S % m * S % m, Sg2 = S * g % m * g % m, g3 = g * g % m * g % m;
                        for (long long aa = 0; aa < m; ++aa) {
                            long long base = (S3 - 6 * aa % m * Sg2 % m + 6 * m) % m;
                            for (long long bb = 0; bb < m; ++bb)
                                if ((base + 3 * bb % m * g3) % m == Km) cu.ab[static_cast<std::size_t>(aa * m + bb)] = 1;
                        }
                    }
                    cube_local.push_back(std::move(cu));
                }
                continue;
            }
            local.push_back(std::move(loc));
        }
    }
    bool q_ok(uint32_t q) const { return q % 3 != 0 && (!half || (q & 1u)) && ok[q]; }
    bool p_ok(int64_t p, uint32_t q) const {
        if (p == 0) return false;
        uint64_t a = static_cast<uint64_t>(p < 0 ? -p : p);
        if (a % 3 == 0) return false;
        if (((p % 3) + 3) % 3 != q % 3) return false;
        if (a >= ok.size() || !ok[a]) return false;
        for (const auto& loc : local) {
            long long pr = ((p % loc.l) + loc.l) % loc.l, qr = q % loc.l;
            if (!loc.allowed[static_cast<std::size_t>(pr * loc.l + qr)]) return false;
        }
        for (const auto& cu : cube_local) {
            long long pr = ((p % cu.m) + cu.m) % cu.m, qr = q % cu.m;
            long long aa = pr * qr % cu.m, bb = aa * ((pr + qr) % cu.m) % cu.m;
            if (!cu.ab[static_cast<std::size_t>(aa * cu.m + bb)]) return false;
        }
        return std::gcd(a, static_cast<uint64_t>(q)) == 1;
    }
};

// n (mod 3) forced by K (DERIVATION.md section 5): cube components are all
// 1 (K = 3 mod 9) or all -1 (K = 6 mod 9) mod 3, which fixes S mod 9; with
// S = 3 (mod 6) that fixes S mod 18, hence n = (S-3)/6 mod 3. K = 375 gives 2.
int n_mod3(long long K) {
    long long r9 = ((K % 9) + 9) % 9;
    long long s9 = r9 == 3 ? (((K + 6) / 3) % 9 + 9) % 9 : (((K - 6) / 3) % 9 + 9) % 9;
    for (int v = 3; v < 18; v += 6) if (v % 9 == s9) return (v - 3) / 6;
    throw std::runtime_error("internal n (mod 3) derivation failed");
}

Z zgcd(const Z& a, const Z& b) { Z r; mpz_gcd(r.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t()); return r; }

// Exact verification against the ORIGINAL, unsquared equation.
std::string certify(long long K, const Z& p, const Z& q, const Z& S, const Z& g, const char* source) {
    if (abs(g) != 1) throw std::runtime_error("campaign hit must have g = -1 or +1");
    if (mpz_fdiv_ui(S.get_mpz_t(), 6) != 3) throw std::runtime_error("internal S == 3 (mod 6) check failed");
    Z n = (S - 3) / 6;
    if (static_cast<int>(mpz_fdiv_ui(n.get_mpz_t(), 3)) != n_mod3(K))
        throw std::runtime_error("internal n (mod 3) invariant check failed");
    Q x(-q * g, 2), s((2 * p + q) * g - 2 * S, 2), d(p, q);
    x.canonicalize(); s.canonicalize(); d.canonicalize();
    if ((27 - K) % 6 != 0) throw std::runtime_error("K must be 3 (mod 6)");
    Z c(static_cast<long>((27 - K) / 6));  // -58 for K = 375
    Z Nn = 36 * n * n * n + 54 * n * n + 27 * n + c;
    Q U = x + S;  // x + 6n + 3
    if (sgn(s.get_num()) < 0) throw std::runtime_error("internal s >= 0 check failed");
    if (s * s != U * U + Q(Nn) / x || Q(Nn) != -2 * d * x * x * (-U + s))
        throw std::runtime_error("internal original-equation verification failed");
    std::string chart;
    if (x.get_den() == 1 && s.get_den() == 1) chart = "integer";
    else if (x.get_den() == 2 && s.get_den() == 2) chart = "half";  // canonical den 2 => odd numerators
    else throw std::runtime_error("internal chart check failed");
    Q A = -x + s, B = -x - s, C = 2 * x + S;
    A.canonicalize(); B.canonicalize(); C.canonicalize();
    if (A.get_den() != 1 || B.get_den() != 1 || C.get_den() != 1)
        throw std::runtime_error("internal cube-component integrality failed");
    Z a = A.get_num(), b = B.get_num(), cc = C.get_num();
    if (a * a * a + b * b * b + cc * cc * cc != Z(static_cast<long>(K)))
        throw std::runtime_error("internal cube-sum verification failed");
    // Either chart can qualify independently. Cube primitivity is reported
    // separately; g = +-1 already forces gcd(A, B, C) = gcd(S, g) = 1.
    Z X = x.get_num() * (2 / x.get_den()), Y = s.get_num() * (2 / s.get_den());
    Z gp = chart == "integer" ? zgcd(zgcd(n, x.get_num()), s.get_num()) : zgcd(X, Y);
    Z gc = zgcd(zgcd(a, b), cc);
    bool prim_point = gp == 1, prim_cubes = gc == 1;
    std::ostringstream o;
    o << "{\"type\":\"hit\",\"chart\":" << quoted(chart) << ",\"source\":" << quoted(source)
      << ",\"desired\":" << (prim_point ? "true" : "false")
      << ",\"primitive_point\":" << (prim_point ? "true" : "false")
      << ",\"primitive_cubes\":" << (prim_cubes ? "true" : "false")
      << ",\"point_gcd\":" << quoted(gp.get_str()) << ",\"cube_gcd\":" << quoted(gc.get_str())
      << ",\"k\":" << quoted(std::to_string(K))
      << ",\"d_num\":" << quoted(d.get_num().get_str()) << ",\"d_den\":" << quoted(d.get_den().get_str())
      << ",\"g\":" << quoted(g.get_str()) << ",\"n\":" << quoted(n.get_str())
      << ",\"x_num\":" << quoted(x.get_num().get_str()) << ",\"x_den\":" << quoted(x.get_den().get_str())
      << ",\"s_num\":" << quoted(s.get_num().get_str()) << ",\"s_den\":" << quoted(s.get_den().get_str())
      << ",\"cube_a\":" << quoted(a.get_str()) << ",\"cube_b\":" << quoted(b.get_str())
      << ",\"cube_c\":" << quoted(cc.get_str()) << "}";
    return o.str();
}

// xy and xy-half modes: verify y^2 = (x+S)^2 + N/x exactly for x = X/2,
// y = |Y|/2 (either branch of the Thue solution), and report the point with
// y >= 0 and its principal d = -(x + S + y)/(2x). X even: integer chart.
std::string certify_xy(long long K, const Z& p, const Z& q, const Z& S, const Z& g, const char* source,
                       const std::string& mode) {
    if (abs(g) != 1) throw std::runtime_error("campaign hit must have g = -1 or +1");
    if (mpz_fdiv_ui(S.get_mpz_t(), 6) != 3) throw std::runtime_error("internal S == 3 (mod 6) check failed");
    Z n = (S - 3) / 6;
    if (static_cast<int>(mpz_fdiv_ui(n.get_mpz_t(), 3)) != n_mod3(K))
        throw std::runtime_error("internal n (mod 3) invariant check failed");
    Z X = -q * g, Ys = (2 * p + q) * g - 2 * S, Y = abs(Ys);
    const bool integer_chart = mpz_even_p(X.get_mpz_t());
    if (integer_chart != static_cast<bool>(mpz_even_p(Y.get_mpz_t())))
        throw std::runtime_error("internal X, Y parity check failed");
    Q x(X, 2), y(Y, 2);
    x.canonicalize(); y.canonicalize();  // GMP needs canonical rationals (X, Y even in the integer chart)
    Z c(static_cast<long>((27 - K) / 6));
    Z Nn = 36 * n * n * n + 54 * n * n + 27 * n + c;
    Q U = x + S;
    if (y * y != U * U + Q(Nn) / x) throw std::runtime_error("internal y^2 verification failed");
    Q d = -(x + S + y) / (2 * x); d.canonicalize();
    if (Q(Nn) != -2 * d * x * x * (-U + y)) throw std::runtime_error("internal original-equation verification failed");
    Q A = -x + y, B = -x - y, C = 2 * x + S;
    A.canonicalize(); B.canonicalize(); C.canonicalize();
    if (A.get_den() != 1 || B.get_den() != 1 || C.get_den() != 1)
        throw std::runtime_error("internal cube-component integrality failed");
    Z a = A.get_num(), b = B.get_num(), cc = C.get_num();
    if (a * a * a + b * b * b + cc * cc * cc != Z(static_cast<long>(K)))
        throw std::runtime_error("internal cube-sum verification failed");
    // Point primitivity decides success; cube primitivity remains informational.
    Z gp = integer_chart ? zgcd(zgcd(n, X / 2), Y / 2) : zgcd(X, Y), gc = zgcd(zgcd(a, b), cc);
    bool pp = gp == 1, pc = gc == 1;
    std::ostringstream o;
    o << "{\"type\":\"hit\",\"mode\":" << quoted(mode) << ",\"chart\":" << quoted(integer_chart ? "integer" : "half")
      << ",\"source\":" << quoted(source)
      << ",\"branch\":" << quoted(sgn(Ys) >= 0 ? "principal" : "conjugate")
      << ",\"desired\":" << (pp ? "true" : "false")
      << ",\"primitive_point\":" << (pp ? "true" : "false") << ",\"primitive_cubes\":" << (pc ? "true" : "false")
      << ",\"point_gcd\":" << quoted(gp.get_str()) << ",\"cube_gcd\":" << quoted(gc.get_str())
      << ",\"k\":" << quoted(std::to_string(K))
      << ",\"n\":" << quoted(n.get_str()) << ",\"X\":" << quoted(X.get_str()) << ",\"Y\":" << quoted(Y.get_str())
      << ",\"x_num\":" << quoted(X.get_str()) << ",\"x_den\":\"2\""
      << ",\"y_num\":" << quoted(Y.get_str()) << ",\"y_den\":\"2\""
      << ",\"d_num\":" << quoted(d.get_num().get_str()) << ",\"d_den\":" << quoted(d.get_den().get_str())
      << ",\"thue_p\":" << quoted(p.get_str()) << ",\"thue_q\":" << quoted(q.get_str()) << ",\"g\":" << quoted(g.get_str())
      << ",\"cube_a\":" << quoted(a.get_str()) << ",\"cube_b\":" << quoted(b.get_str())
      << ",\"cube_c\":" << quoted(cc.get_str()) << "}";
    return o.str();
}

struct Config {
    long long K = 375;
    std::string mode = "xy";
    uint32_t h_start = 1, h_stop = 0;
    double deadline = 0;
    unsigned bits0 = 128, max_bits = 1u << 18;
    bool raw = false; Z raw_target, raw_gmax; bool have_raw_target = false, have_raw_gmax = false;
};

void usage() {
    std::cout <<
        "Usage (campaign): thue375_worker --h-start H0 --h-stop H1 [--k 375] [--mode xy]\n"
        "                  [--deadline-seconds S]\n"
        "  Sweeps every admissible d = p/q with H0 <= max(|p|,q) < H1 (one height shell at a time)\n"
        "  using exactly g = -1 and +1; there is no configurable campaign g bound.\n"
        "  --mode xy (default): both charts and both signs of y; either primitive chart is a result.\n"
        "  --mode xy-half: only rational x = X/2, y = Y/2 (X, Y odd, gcd(X,Y) = 1), both signs of y.\n"
        "  --mode both: principal-square-root reporting for both charts, still with g = -1 and +1.\n"
        "  Integer-chart primitivity is gcd(n,x,y) = 1; cube flags are informational.\n"
        "Usage (raw test mode): thue375_worker --raw --target T --g-max G  (reads 'p q' lines)\n"
        "                      [--precision-bits 128] [--max-precision-bits 262144]\n"
        "  Reports ALL integer solutions of F_d(S,g) = T with 1 <= |g| <= G; no filters.\n";
}

Config arguments(int argc, char** argv) {
    Config c;
    bool have_start = false, have_stop = false;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--version") { std::cout << "ce375-thue-worker " << VERSION << "\n"; std::exit(0); }
        if (a == "--help") { usage(); std::exit(0); }
        if (a == "--raw") { c.raw = true; continue; }
        if (a == "--g-max-digits")
            throw std::runtime_error("--g-max-digits is no longer supported: campaigns use exactly g = -1 and +1; use --raw --g-max G only for diagnostics");
        if (i + 1 == argc) throw std::runtime_error("missing value for " + a);
        std::string v = argv[++i];
        if (a == "--mode") { if (v != "both" && v != "xy" && v != "xy-half") throw std::runtime_error("mode must be both, xy or xy-half"); c.mode = v; }
        else if (a == "--k") { Z z = integer(v); if (z == 0 || abs(z) > Z("1000000000")) throw std::runtime_error("k out of range"); c.K = z.get_si(); }
        else if (a == "--h-start") { Z z = integer(v); if (z < 1 || z > Z("200000000")) throw std::runtime_error("h-start out of range"); c.h_start = static_cast<uint32_t>(z.get_ui()); have_start = true; }
        else if (a == "--h-stop") { Z z = integer(v); if (z < 2 || z > Z("200000001")) throw std::runtime_error("h-stop out of range"); c.h_stop = static_cast<uint32_t>(z.get_ui()); have_stop = true; }
        else if (a == "--deadline-seconds") { Z z = integer(v); if (z < 0) throw std::runtime_error("deadline must be >= 0"); c.deadline = z.get_d(); }
        else if (a == "--precision-bits") { Z z = integer(v); if (z < 64 || z > (1 << 20)) throw std::runtime_error("precision out of range"); c.bits0 = static_cast<unsigned>(z.get_ui()); }
        else if (a == "--max-precision-bits") { Z z = integer(v); if (z < 64 || z > (1 << 24)) throw std::runtime_error("max precision out of range"); c.max_bits = static_cast<unsigned>(z.get_ui()); }
        else if (a == "--target") { c.raw_target = integer(v); c.have_raw_target = true; }
        else if (a == "--g-max") { c.raw_gmax = integer(v); c.have_raw_gmax = true; if (c.raw_gmax < 1) throw std::runtime_error("g-max must be positive"); }
        else throw std::runtime_error("unknown option: " + a);
    }
    if (c.raw) {
        if (!c.have_raw_target || !c.have_raw_gmax || c.raw_target == 0) throw std::runtime_error("--raw needs nonzero --target and --g-max");
        return c;
    }
    if (c.have_raw_target || c.have_raw_gmax)
        throw std::runtime_error("--target and --g-max require --raw; campaigns use exactly g = -1 and +1");
    if (!have_start || !have_stop || c.h_stop <= c.h_start) throw std::runtime_error("need --h-start < --h-stop");
    long long r9 = ((c.K % 9) + 9) % 9;
    if ((c.K % 2 == 0) || (r9 != 3 && r9 != 6))
        throw std::runtime_error("k must be odd and +-3 (mod 9) (needed for S = 6n+3 and the 3-adic filter)");
    if (c.bits0 > c.max_bits) throw std::runtime_error("initial precision exceeds maximum precision");
    return c;
}

int run_raw(const Config& c) {
    Solver solver{c.raw_target, c.raw_gmax, false, c.bits0, c.max_bits, cube_divisors(c.raw_target)};
    std::string line;
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        std::istringstream in(line); std::string sp, sq, extra;
        if (!(in >> sp >> sq) || (in >> extra)) throw std::runtime_error("expected 'p q'");
        Z p = integer(sp), q = integer(sq);
        if (sgn(q) <= 0 || sgn(p) == 0) throw std::runtime_error("need q > 0 and p != 0");
        Stats st; Z g0;
        auto sols = solver.solve(Form(p, q), st, &g0);
        std::sort(sols.begin(), sols.end(), [](const Solution& a, const Solution& b) {
            return a.g != b.g ? a.g < b.g : a.S < b.S; });
        std::cout << "{\"p\":" << quoted(p.get_str()) << ",\"q\":" << quoted(q.get_str())
                  << ",\"g0\":" << quoted(g0.get_str()) << ",\"convergents\":" << st.convergents
                  << ",\"exact_root\":" << (st.exact_roots ? "true" : "false") << ",\"solutions\":[";
        for (std::size_t i = 0; i < sols.size(); ++i)
            std::cout << (i ? "," : "") << "[" << quoted(sols[i].S.get_str()) << "," << quoted(sols[i].g.get_str())
                      << "," << quoted(sols[i].source) << "]";
        std::cout << "]}\n" << std::flush;
    }
    return 0;
}

int run_campaign(const Config& c) {
    auto t0 = std::chrono::steady_clock::now();
    const bool half = c.mode == "xy-half", xy = c.mode == "xy" || half;
    Admissibility adm(c.K, c.h_stop, half, xy);
    Z T = Z(static_cast<long>(c.K));
    std::cout << "{\"type\":\"start\",\"version\":" << quoted(VERSION) << ",\"parameterization\":" << quoted(PARAMETERIZATION)
              << ",\"k\":" << quoted(std::to_string(c.K)) << ",\"mode\":" << quoted(c.mode)
              << ",\"g_values\":[-1,1],\"h_start\":" << c.h_start << ",\"h_stop\":" << c.h_stop << "}\n" << std::flush;
    for (uint32_t H = c.h_start; H < c.h_stop; ++H) {
        auto s0 = std::chrono::steady_clock::now();
        unsigned long long pairs = 0, admissible = 0;
        Stats st;
        auto handle = [&](int64_t p, uint32_t q) {
            ++pairs;
            if (!adm.q_ok(q) || !adm.p_ok(p, q)) return;
            ++admissible;
            Z P(static_cast<long>(p)), Qd(static_cast<unsigned long>(q));
            Form f(P, Qd);
            for (const auto& s : solve_unit_g(f, T, st)) {
                if (xy) {
                    bool even = mpz_even_p(Z(Qd * s.g).get_mpz_t());
                    if (half && even) continue;  // not the half chart
                    if (sgn((2 * P + Qd) * s.g - 2 * s.S) < 0) ++st.other_branch;
                    if (even) ++st.integer_chart; else ++st.half_chart;
                    std::cout << certify_xy(c.K, P, Qd, s.S, s.g, s.source.c_str(), c.mode) << "\n" << std::flush;
                    continue;
                }
                // s >= 0 required; s < 0 belongs to the conjugate value of d.
                if (sgn((2 * P + Qd) * s.g - 2 * s.S) < 0) { ++st.other_branch; continue; }
                if (mpz_even_p(Z(Qd * s.g).get_mpz_t())) ++st.integer_chart; else ++st.half_chart;
                std::cout << certify(c.K, P, Qd, s.S, s.g, s.source.c_str()) << "\n" << std::flush;
            }
        };
        // Shell H covers each pair once. Odd q (the half chart for unit g)
        // is visited first, followed by even q (the integer chart).
        for (uint32_t parity : {1u, 0u}) {
            if ((H & 1u) == parity)
                for (int64_t p = -static_cast<int64_t>(H); p <= static_cast<int64_t>(H); ++p) handle(p, H);
            for (uint32_t q = parity ? 1u : 2u; q < H; q += 2) {
                handle(-static_cast<int64_t>(H), q);
                handle(H, q);
            }
        }
        double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - s0).count();
        std::cout << "{\"type\":\"shell\",\"h\":" << H << ",\"pairs\":" << pairs << ",\"admissible\":" << admissible
                  << ",\"convergents\":" << st.convergents << ",\"small_g_values\":" << st.small_g_values
                  << ",\"thue_solutions\":" << st.thue_solutions << ",\"integer_chart\":" << st.integer_chart
                  << ",\"half_chart\":" << st.half_chart << ",\"other_branch\":" << st.other_branch
                  << ",\"refinements\":" << st.refinements << ",\"exact_roots\":" << st.exact_roots
                  << ",\"max_bits\":" << st.max_bits << ",\"seconds\":" << secs << "}\n" << std::flush;
        double total = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (c.deadline > 0 && total >= c.deadline && H + 1 < c.h_stop) {
            std::cout << "{\"type\":\"end\",\"state\":\"partial\",\"next_h\":" << (H + 1) << "}\n" << std::flush;
            return 0;
        }
    }
    std::cout << "{\"type\":\"end\",\"state\":\"complete\",\"next_h\":" << c.h_stop << "}\n" << std::flush;
    return 0;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        Config c = arguments(argc, argv);
        int rc = c.raw ? run_raw(c) : run_campaign(c);
        return std::cout ? rc : 3;
    } catch (const std::exception& e) {
        std::cout << std::flush;
        std::cerr << "ce375-thue-worker: " << e.what() << '\n';
        return 2;
    }
}
