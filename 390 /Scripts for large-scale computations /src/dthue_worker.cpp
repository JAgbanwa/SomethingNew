// CE390 d-first half-chart engine. See D_FIRST.md for every proof used here.
//
// Target: rational d with integer n (n == 1 mod 3 when m = 65),
// x = X/2 (X odd), y = Y/2 (Y odd) and
//   36n^3 - m = -2*d*x^2*(y - (x+6n)),  y = sqrt((x+6n)^2 + (36n^3-m)/x) >= 0,
// with m = 65 for k = 390 (m is a parameter only so that k = 6m test cases
// with KNOWN half-chart points, e.g. m = 1, can exercise the identical code).
//
// For d = p/q in lowest terms (q > 0) these points are exactly the integer
// solutions (n, g) of the binary cubic Thue equation
//   F_d(n, g) = 72 n^3 - 12 p q n g^2 + p q (p+q) g^3 = 2m
// with q*g odd and Y = (2p+q) g - 12 n > 0; then x = -q g / 2, y = Y / 2.
//
// Per d, every solution with 1 <= |g| <= G is found: |g| <= g0 by exact
// integer root finding of the cubic in n, |g| > g0 via certified continued-
// fraction convergents of the unique real root (Legendre). All acceptance
// decisions use exact GMP integers/rationals; floating point is never used.
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
constexpr const char* VERSION = "1.1.0";
constexpr const char* PARAMETERIZATION = "dfirst-thue-height-shells-v1";

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
// The binary cubic form of one value of d.
struct Form {
    Z p, q, c1, c0;  // F(n,g) = 72 n^3 + c1 n g^2 + c0 g^3
    Form(const Z& p_, const Z& q_) : p(p_), q(q_), c1(-12 * p_ * q_), c0(p_ * q_ * (p_ + q_)) {}
    Z F(const Z& n, const Z& g) const {
        Z g2 = g * g;
        return 72 * n * n * n + c1 * n * g2 + c0 * g2 * g;
    }
    // sign(F(z, D)) = sign(z/D - alpha) for D > 0: f(t) = 72 (t-alpha) |t-beta|^2.
    int side(const Z& z, const Z& D) const { return sgn(F(z, D)); }
};

struct Stats {
    unsigned long long convergents = 0, small_g_values = 0, thue_solutions = 0,
                       other_chart = 0, other_branch = 0, refinements = 0, exact_roots = 0;
    unsigned max_bits = 0;
};

struct Solution { Z n, g; std::string source; };

// Integer roots n of h(n) = F(n, g) - T for one fixed g, by exact binary
// search on the (at most three) integer intervals where h is monotone.
void integer_roots_in_n(const Form& f, const Z& g, const Z& T, std::vector<Z>& out) {
    Z g2 = g * g;
    Z k1 = f.c1 * g2, k0 = f.c0 * g2 * g - T;  // h(n) = 72 n^3 + k1 n + k0
    auto h = [&](const Z& n) -> Z { return 72 * n * n * n + k1 * n + k0; };  // -> Z: never return a gmpxx expression template
    Z B = 2 + (abs(k1) + abs(k0)) / 72;  // Cauchy bound: every real root has |n| < B
    auto search = [&](Z lo, Z hi, int direction) {  // direction +1 increasing, -1 decreasing
        if (lo > hi) return;
        while (lo <= hi) {
            Z mid = floor_div(lo + hi, 2);
            int s = sgn(h(mid)) * direction;
            if (s == 0) { out.push_back(mid); return; }
            if (s < 0) lo = mid + 1; else hi = mid - 1;
        }
    };
    if (sgn(k1) >= 0) { search(-B, B, 1); return; }
    // h'(n) = 216 n^2 + k1 vanishes at n = +-r, r^2 = -k1/216. s = floor(r).
    Z r2 = floor_div(-k1, Z(216)), s;
    mpz_sqrt(s.get_mpz_t(), r2.get_mpz_t());
    search(-B, -s - 1, 1);
    search(-s, s, -1);
    search(s + 1, B, 1);
}

// Unique real root alpha of f(t) = 72 t^3 + c1 t + c0, isolated as
// alpha in (z/2^bits, (z+1)/2^bits), or exactly alpha = z/2^bits.
struct Root {
    Z z; unsigned bits = 0; bool exact = false;
};

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
    // Coarse bracket by bisection at 64 bits, then exact-checked Newton doubling.
    // A floating-point guess is only a starting point: fix_bracket() then
    // establishes the bracket by exact sign tests, whatever the guess's error.
    Root r; r.bits = 24;
    Z D = Z(1) << 24;
    long double P = f.c1.get_d() / 72.0L, Qc = f.c0.get_d() / 72.0L;  // t^3 + P t + Qc = 0
    long double disc = Qc * Qc / 4.0L + P * P * P / 27.0L;  // > 0: one real root
    long double guess = 0.0L;
    if (disc >= 0.0L) {
        long double h = -Qc / 2.0L, s = std::sqrt(disc);
        long double u = std::cbrt(h + (h >= 0.0L ? s : -s));  // larger-magnitude branch: no cancellation
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
        Z R = 2 + (abs(f.c1) + abs(f.c0)) / 72;
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
            Z val = f.F(r.z, D), der = 216 * r.z * r.z + f.c1 * D2;
            if (sgn(der) == 0 || sgn(val) == 0) break;
            r.z -= val / der;
        }
        r.bits = nb;
        if (fix_bracket(f, D, r.z)) { r.exact = true; return r; }
    }
    return r;
}

// Lower bound for 36*eta^2 = 27 alpha^2 - 6pq (eta = |Im beta|), from the bracket.
// Returns false if the bracket is too wide to prove positivity.
bool eta_bound(const Form& f, const Root& r, Q& lower) {
    Z D = Z(1) << r.bits;
    Z a;  // endpoint of minimal |.|
    if (r.exact) a = r.z;
    else if (sgn(r.z) >= 0) a = r.z;
    else if (sgn(r.z + 1) <= 0) a = r.z + 1;
    else a = 0;
    lower = Q(27 * a * a - 6 * f.p * f.q * D * D, D * D);
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
    Z T, G;              // target 2m (or raw target), maximal |g|
    bool half_only;      // only odd g and 3 !| g in the exhaustive range
    unsigned bits0, max_bits;
    std::vector<Z> cubes;

    // Returns every (n, g) with F_d(n,g) = T and 1 <= |g| <= G (subject to
    // half_only for |g| <= g0; convergent solutions are all reported).
    std::vector<Solution> solve(const Form& f, Stats& st, Z* g0_out = nullptr) const {
        std::set<std::pair<std::string, std::string>> seen;
        std::vector<Solution> sols;
        auto add = [&](const Z& n, const Z& g, const char* src) {
            if (sgn(g) == 0 || abs(g) > G) return;
            if (f.F(n, g) != T) throw std::runtime_error("internal Thue solution check failed");
            if (seen.emplace(n.get_str(), g.get_str()).second) { sols.push_back({n, g, src}); ++st.thue_solutions; }
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
        // g0 = floor(|T| / (27 alpha^2 - 6pq)) >= |T|/(36 eta^2): Legendre holds for |g| > g0.
        Z g0 = floor_div(abs(T) * lower.get_den(), lower.get_num());
        if (r.exact) {
            // alpha = a/b rational: for n/g != alpha, 1/(b|g|) <= |T|/(72 eta^2 |g|^3),
            // so g^2 <= |T| b / (72 eta^2) = 2 |T| b / (36 eta^2). No CF needed.
            ++st.exact_roots;
            Q alpha(r.z, Z(1) << r.bits); alpha.canonicalize();
            Z bound2 = floor_div(2 * abs(T) * alpha.get_den() * lower.get_den(), lower.get_num()), gb;
            mpz_sqrt(gb.get_mpz_t(), bound2.get_mpz_t());
            g0 = std::max(g0, Z(gb + 1));
        }
        if (g0 > G) g0 = G;
        if (g0_out) *g0_out = g0;
        // Exhaustive small |g|.
        std::vector<Z> roots;
        for (Z g = 1; g <= g0; ++g) {
            if (half_only && (mpz_even_p(g.get_mpz_t()) || mpz_divisible_ui_p(g.get_mpz_t(), 3))) continue;
            for (int s : {1, -1}) {
                Z gs = s * g;
                roots.clear(); ++st.small_g_values;
                integer_roots_in_n(f, gs, T, roots);
                for (const Z& n : roots) add(n, gs, "small_g");
            }
        }
        if (r.exact || g0 >= G) return sols;
        // Certified convergents of alpha with denominators in (g0, G].
        for (;;) {
            st.max_bits = std::max(st.max_bits, r.bits);
            if (cf_pass(f, r, st, add)) return sols;
            if (r.bits >= max_bits) throw std::runtime_error("precision cap reached before CF completeness");
            r = isolate(f, std::min(max_bits, 2 * r.bits)); ++st.refinements;
            if (r.exact) {  // Extremely unlikely: redo with the exact-root bound.
                return solve_exact_fallback(f, st, sols, seen, add);
            }
        }
    }

    template <class Add>
    std::vector<Solution> solve_exact_fallback(const Form& f, Stats& st, std::vector<Solution>& sols,
                                               std::set<std::pair<std::string, std::string>>&, Add& add) const {
        ++st.exact_roots;
        Root r = isolate(f, bits0); Q lower;
        if (!r.exact) throw std::runtime_error("inconsistent exact-root detection");
        eta_bound(f, r, lower);
        Q alpha(r.z, Z(1) << r.bits); alpha.canonicalize();
        Z bound2 = floor_div(2 * abs(T) * alpha.get_den() * lower.get_den(), lower.get_num()), gb;
        mpz_sqrt(gb.get_mpz_t(), bound2.get_mpz_t());
        Z g0 = std::max(floor_div(abs(T) * lower.get_den(), lower.get_num()), Z(gb + 1));
        if (g0 > G) g0 = G;
        std::vector<Z> roots;
        for (Z g = 1; g <= g0; ++g)
            for (int s : {1, -1}) { Z gs = s * g; roots.clear(); integer_roots_in_n(f, gs, T, roots);
                for (const Z& n : roots) add(n, gs, "small_g"); }
        return sols;
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
// Admissibility of d = p/q (all conditions are proved in D_FIRST.md):
//  q odd; 3 !| pq; p == q (mod 3); gcd(p,q) = 1; p != 0;
//  every prime l >= 5 dividing pq: if l | m (with v_l(m) <= 2) then v_l(pq) <= v_l(m);
//  if l !| m then l == 2 (mod 3) or 36 t^3 == m (mod l) is solvable;
//  if m is odd then 4 !| p.
struct Admissibility {
    long long m;
    std::vector<uint32_t> spf;
    std::vector<uint8_t> ok;  // ok[v]: every prime power of v is allowed (2 and 3 handled separately)
    std::vector<uint8_t> prime_cap;  // cap on the exponent of a prime (255 = unlimited, 0 = forbidden)

    static long long powmod(long long b, long long e, long long mod) {
        long long r = 1 % mod; b %= mod; if (b < 0) b += mod;
        while (e) { if (e & 1) r = r * b % mod; b = b * b % mod; e >>= 1; /* mod < 2^28: no overflow */ }
        return r;
    }
    static int vval(long long a, long long l) { int v = 0; if (a == 0) return 99; while (a % l == 0) { a /= l; ++v; } return v; }

    int cap_for_prime(long long l) const {
        if (l == 2) return (m % 2 != 0) ? 1 : 255;
        if (l == 3) return 0;
        int vm = vval(std::llabs(m), l);
        if (vm > 0) return vm <= 2 ? vm : 255;
        if (l % 3 == 2) return 255;
        // l == 1 mod 3, l !| 6m: 36 t^3 == m solvable iff m^((l-1)/3) == 36^((l-1)/3) (mod l).
        long long e = (l - 1) / 3;
        return powmod(m, e, l) == powmod(36, e, l) ? 255 : 0;
    }

    Admissibility(long long m_, uint32_t limit) : m(m_), spf(limit + 1, 0), ok(limit + 1, 1) {
        for (uint64_t i = 2; i <= limit; ++i)
            if (!spf[i]) for (uint64_t j = i; j <= limit; j += i) if (!spf[j]) spf[j] = static_cast<uint32_t>(i);
        std::vector<uint32_t> rest(limit + 1, 1), expo(limit + 1, 0);
        for (uint32_t v = 2; v <= limit; ++v) {
            uint32_t l = spf[v], w = v / l;
            if (w > 1 && spf[w] == l) { expo[v] = expo[w] + 1; rest[v] = rest[w]; }
            else { expo[v] = 1; rest[v] = w; }
            int cap = (l == 2 || l == 3) ? 255 : cap_for_prime(l);  // 2 and 3 checked separately
            ok[v] = ok[rest[v]] && static_cast<int>(expo[v]) <= cap;
        }
    }
    bool q_ok(uint32_t q) const { return (q & 1u) && q % 3 != 0 && ok[q]; }
    bool p_ok(int64_t p, uint32_t q) const {
        if (p == 0) return false;
        uint64_t a = static_cast<uint64_t>(p < 0 ? -p : p);
        if (a % 3 == 0) return false;
        if (((p % 3) + 3) % 3 != q % 3) return false;
        // For odd m and odd q,g, F(n,g) == 2m == 2 (mod 4) requires
        // p(p+q) == 2 (mod 4). This also rejects odd p with p != q (mod 4).
        // Normalize the SIGNED p residue and multiply only residues, so no
        // signed-remainder mistake or overflow in p*(p+q) can remove a point.
        if (m % 2 != 0) {
            uint32_t p4 = static_cast<uint32_t>((p % 4 + 4) % 4);
            if ((p4 * ((p4 + q % 4) % 4)) % 4 != 2) return false;
        }
        if (!ok[a]) return false;
        return std::gcd(a, static_cast<uint64_t>(q)) == 1;
    }
};

// Exact verification of a half-chart point against the ORIGINAL equation.
std::string certify(long long m, const Z& p, const Z& q, const Z& n, const Z& g, const char* source) {
    // From the integer cube sum 390 modulo 9 and 27, n == 1 (mod 3).
    // Keep this explicit production invariant separate from generic-m tests.
    if (m == 65 && mpz_fdiv_ui(n.get_mpz_t(), 3) != 1)
        throw std::runtime_error("internal production n == 1 (mod 3) check failed");
    Q x(-q * g, 2), y((2 * p + q) * g - 12 * n, 2), d(p, q);
    x.canonicalize(); y.canonicalize(); d.canonicalize();
    Q S = x + 6 * n, A = 36 * n * n * n - Z(static_cast<long>(m));
    if (x.get_den() != 2 || y.get_den() != 2 || sgn(y.get_num()) <= 0)
        throw std::runtime_error("internal half-chart denominator check failed");
    if (y * y != S * S + A / x || A != -2 * d * x * x * (y - S))
        throw std::runtime_error("internal original-equation verification failed");
    Q Ap = -x + y, Bm = -x - y, C = 2 * x + 6 * n;
    Ap.canonicalize(); Bm.canonicalize(); C.canonicalize();
    if (Ap.get_den() != 1 || Bm.get_den() != 1 || C.get_den() != 1)
        throw std::runtime_error("internal cube-component integrality failed");
    Z a = Ap.get_num(), b = Bm.get_num(), c = C.get_num();
    if (a * a * a + b * b * b + c * c * c != Z(static_cast<long>(6 * m)))
        throw std::runtime_error("internal cube-sum verification failed");
    Q gap = y - S; gap.canonicalize();
    std::ostringstream o;
    o << "{\"type\":\"hit\",\"chart\":\"half\",\"source\":" << quoted(source)
      << ",\"m\":" << quoted(std::to_string(m))
      << ",\"d_num\":" << quoted(d.get_num().get_str()) << ",\"d_den\":" << quoted(d.get_den().get_str())
      << ",\"g\":" << quoted(g.get_str())
      << ",\"n_num\":" << quoted(n.get_str()) << ",\"n_den\":\"1\""
      << ",\"x_num\":" << quoted(x.get_num().get_str()) << ",\"x_den\":\"2\""
      << ",\"y_num\":" << quoted(y.get_num().get_str()) << ",\"y_den\":\"2\""
      << ",\"gap_num\":" << quoted(gap.get_num().get_str()) << ",\"gap_den\":" << quoted(gap.get_den().get_str())
      << ",\"cube_plus\":" << quoted(a.get_str()) << ",\"cube_minus\":" << quoted(b.get_str())
      << ",\"cube_third\":" << quoted(c.get_str()) << ",\"cube_sum\":" << quoted(std::to_string(6 * m)) << "}";
    return o.str();
}

struct Config {
    long long m = 65;
    uint32_t h_start = 1, h_stop = 0;  // shells h_start <= H < h_stop
    Z G;                                // max |g|
    unsigned g_digits = 100;
    double deadline = 0;                // seconds; 0 = none
    unsigned bits0 = 128, max_bits = 1u << 18;
    bool raw = false; Z raw_target, raw_gmax; bool have_raw_target = false, have_raw_gmax = false;
};

void usage() {
    std::cout <<
        "Usage (campaign): dthue_worker --h-start H0 --h-stop H1 [--m 65] [--g-max-digits 100]\n"
        "                  [--deadline-seconds S] [--precision-bits 128] [--max-precision-bits 262144]\n"
        "  Sweeps every admissible d = p/q with H0 <= max(|p|,q) < H1 (one height shell at a time)\n"
        "  and reports every half-chart point with 1 <= |g| <= 10^digits (|x| = q|g|/2).\n"
        "Usage (raw test mode): dthue_worker --raw --target T --g-max G  (reads 'p q' lines)\n"
        "  Reports ALL integer solutions of F_d(n,g) = T with 1 <= |g| <= G; no filters.\n";
}

Config arguments(int argc, char** argv) {
    Config c;
    bool have_start = false, have_stop = false;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--version") { std::cout << "ce390-dthue-worker " << VERSION << "\n"; std::exit(0); }
        if (a == "--help") { usage(); std::exit(0); }
        if (a == "--raw") { c.raw = true; continue; }
        if (i + 1 == argc) throw std::runtime_error("missing value for " + a);
        std::string v = argv[++i];
        if (a == "--m") { Z z = integer(v); if (z == 0 || abs(z) > Z("1000000000")) throw std::runtime_error("m out of range"); c.m = z.get_si(); }
        else if (a == "--h-start") { Z z = integer(v); if (z < 1 || z > Z("200000000")) throw std::runtime_error("h-start out of range"); c.h_start = static_cast<uint32_t>(z.get_ui()); have_start = true; }
        else if (a == "--h-stop") { Z z = integer(v); if (z < 2 || z > Z("200000001")) throw std::runtime_error("h-stop out of range"); c.h_stop = static_cast<uint32_t>(z.get_ui()); have_stop = true; }
        else if (a == "--g-max-digits") { Z z = integer(v); if (z < 1 || z > 100000) throw std::runtime_error("g-max-digits out of range"); c.g_digits = static_cast<unsigned>(z.get_ui()); }
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
    if (!have_start || !have_stop || c.h_stop <= c.h_start) throw std::runtime_error("need --h-start < --h-stop");
    if (c.m % 3 == 0) throw std::runtime_error("m must not be divisible by 3 (integrality of n is proved only then)");
    mpz_ui_pow_ui(c.G.get_mpz_t(), 10, c.g_digits);
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
            return a.g != b.g ? a.g < b.g : a.n < b.n; });
        std::cout << "{\"p\":" << quoted(p.get_str()) << ",\"q\":" << quoted(q.get_str())
                  << ",\"g0\":" << quoted(g0.get_str()) << ",\"convergents\":" << st.convergents
                  << ",\"exact_root\":" << (st.exact_roots ? "true" : "false") << ",\"solutions\":[";
        for (std::size_t i = 0; i < sols.size(); ++i)
            std::cout << (i ? "," : "") << "[" << quoted(sols[i].n.get_str()) << "," << quoted(sols[i].g.get_str())
                      << "," << quoted(sols[i].source) << "]";
        std::cout << "]}\n" << std::flush;
    }
    return 0;
}

int run_campaign(const Config& c) {
    auto t0 = std::chrono::steady_clock::now();
    Admissibility adm(c.m, c.h_stop);
    Z T = Z(static_cast<long>(2 * c.m));
    Solver solver{T, c.G, true, c.bits0, c.max_bits, cube_divisors(T)};
    std::cout << "{\"type\":\"start\",\"version\":" << quoted(VERSION) << ",\"parameterization\":" << quoted(PARAMETERIZATION)
              << ",\"m\":" << quoted(std::to_string(c.m)) << ",\"target\":" << quoted(T.get_str())
              << ",\"g_max_digits\":" << c.g_digits << ",\"h_start\":" << c.h_start << ",\"h_stop\":" << c.h_stop << "}\n" << std::flush;
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
            for (const auto& s : solver.solve(f, st)) {
                if (mpz_even_p(s.g.get_mpz_t())) { ++st.other_chart; continue; }        // x integral: not this chart
                if (sgn((2 * P + Qd) * s.g - 12 * s.n) <= 0) { ++st.other_branch; continue; }  // belongs to the conjugate d
                std::cout << certify(c.m, P, Qd, s.n, s.g, s.source.c_str()) << "\n" << std::flush;
            }
        };
        // Shell H: q = H with -H <= p <= H, then 1 <= q < H with p = -H, +H.
        for (int64_t p = -static_cast<int64_t>(H); p <= static_cast<int64_t>(H); ++p) handle(p, H);
        for (uint32_t q = 1; q < H; ++q) { handle(-static_cast<int64_t>(H), q); handle(H, q); }
        double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - s0).count();
        std::cout << "{\"type\":\"shell\",\"h\":" << H << ",\"pairs\":" << pairs << ",\"admissible\":" << admissible
                  << ",\"convergents\":" << st.convergents << ",\"small_g_values\":" << st.small_g_values
                  << ",\"thue_solutions\":" << st.thue_solutions << ",\"other_chart\":" << st.other_chart
                  << ",\"other_branch\":" << st.other_branch << ",\"refinements\":" << st.refinements
                  << ",\"exact_roots\":" << st.exact_roots << ",\"max_bits\":" << st.max_bits
                  << ",\"seconds\":" << secs << "}\n" << std::flush;
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
        std::cerr << "ce390-dthue-worker: " << e.what() << '\n';
        return 2;
    }
}
