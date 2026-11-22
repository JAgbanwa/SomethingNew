// CE375 n-first worker. See METHOD.md for the proofs used here.
//
// Target: rational x, y with n an integer on
//
//     y^2 = (x + 6n+3)^2 + N(n)/x,      N(n) = 36n^3 + 54n^2 + 27n - 58,
//
// in either accepted form
//   (integer) n, x, y integers,                       gcd(n, x) = 1;
//   (half)    n integer, x = X/2, y = Y/2, X, Y odd,  gcd(X, Y) = 1.
//
// With S = 6n+3, N = (S^3 - K)/6 for K = 375 (K is a parameter only so that
// tests can run the identical code on other K with known solutions).
//
// For every n in [n_start, n_stop) with n = n_mod3(K) (mod 3) the worker
//   1. factors |N(n)| completely (block sieve over small primes, then
//      Miller-Rabin and Brent-Pollard rho on the 128-bit cofactor),
//   2. runs over EVERY divisor D of |N(n)| and both signs:
//        integer form  x = +-D:          y^2 = (x+S)^2 + N/x
//        half form     X = +-D, D odd:   Y^2 = (X+2S)^2 + 8N/X,
//   3. tests the right-hand side for being a perfect square (cheap residue
//      filters first, then an exact GMP test).
// Every point found is re-verified exactly in GMP before it is printed, with
// primitivity flags. If some |N(n)| could not be factored within the budget,
// the worker prints an "incomplete" record for that n: it is never skipped
// silently.
#include <gmpxx.h>
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

extern "C" {
#include "fac128.h"
}
#include <pari/pari.h>

namespace {
using Z = mpz_class;
using i128 = __int128;
using u128 = unsigned __int128;
constexpr const char* VERSION = "1.0.0";
constexpr const char* METHOD = "ce375-nfirst-divisors-v1";

std::string u128s(u128 v) {
    if (v == 0) return "0";
    std::string s;
    while (v) { s.push_back(static_cast<char>('0' + static_cast<int>(v % 10))); v /= 10; }
    std::reverse(s.begin(), s.end());
    return s;
}
std::string i128s(i128 v) { return v < 0 ? "-" + u128s(static_cast<u128>(-v)) : u128s(static_cast<u128>(v)); }
Z zi(i128 v) {
    u128 a = v < 0 ? static_cast<u128>(-v) : static_cast<u128>(v);
    uint64_t w[2] = {static_cast<uint64_t>(a), static_cast<uint64_t>(a >> 64)};  // least significant first
    Z z; mpz_import(z.get_mpz_t(), 2, -1, sizeof(uint64_t), 0, 0, w);
    return v < 0 ? Z(-z) : z;
}
std::string q(const std::string& s) { return "\"" + s + "\""; }

// ------------------------------------------------- 64-bit Montgomery arithmetic
struct Mont64 {
    uint64_t n, ninv, r2, one;
    explicit Mont64(uint64_t n_) : n(n_) {
        uint64_t inv = n;
        for (int i = 0; i < 6; ++i) inv *= 2 - n * inv;
        ninv = 0 - inv;
        one = static_cast<uint64_t>((static_cast<u128>(1) << 64) % n);
        r2 = static_cast<uint64_t>(static_cast<u128>(one) * one % n);
    }
    uint64_t redc(u128 t) const {
        uint64_t m = static_cast<uint64_t>(t) * ninv;
        u128 u = (t + static_cast<u128>(m) * n) >> 64;  // t < n * 2^64, so no overflow for n < 2^63
        return u >= n ? static_cast<uint64_t>(u - n) : static_cast<uint64_t>(u);
    }
    uint64_t mul(uint64_t a, uint64_t b) const { return redc(static_cast<u128>(a) * b); }
    uint64_t in(uint64_t a) const { return mul(a % n, r2); }
    uint64_t pow(uint64_t a, uint64_t e) const {
        uint64_t r = one;
        while (e) { if (e & 1) r = mul(r, a); a = mul(a, a); e >>= 1; }
        return r;
    }
};

uint64_t gcd64(uint64_t a, uint64_t b) { while (b) { uint64_t t = a % b; a = b; b = t; } return a; }
u128 gcd128x(u128 a, u128 b) {
    while (b) {
        if ((a >> 64) == 0 && (b >> 64) == 0) return gcd64(static_cast<uint64_t>(a), static_cast<uint64_t>(b));
        u128 t = a % b; a = b; b = t;
    }
    return a;
}

// ---------------------------------------------------------------- primality
// Strong probable-prime test to the first 13 prime bases: a PROOF of
// primality for n < 3.317e24 (Sorenson-Webster). Above that bound GMP's
// mpz_probab_prime_p (BPSW plus 30 Miller-Rabin rounds) is added; METHOD.md
// says what that means for coverage.
const unsigned SP[] = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41};

bool is_prime64(uint64_t n) {  // n odd, n > 41, n < 2^63
    Mont64 M(n);
    uint64_t d = n - 1; int r = 0;
    while (!(d & 1)) { d >>= 1; ++r; }
    uint64_t nm1 = M.in(n - 1);
    for (unsigned b : SP) {
        uint64_t a = M.pow(M.in(b), d);
        if (a == M.one || a == nm1) continue;
        bool ok = false;
        for (int j = 1; j < r; ++j) { a = M.mul(a, a); if (a == nm1) { ok = true; break; } }
        if (!ok) return false;
    }
    return true;
}

bool is_prime(u128 n) {
    if (n < 2) return false;
    for (unsigned p : SP) if (n % p == 0) return n == p;
    if (n < (static_cast<u128>(1) << 63)) return is_prime64(static_cast<uint64_t>(n));
    mont_t M; mont_init(&M, n);
    u128 d = n - 1; int r = 0;
    while (!(d & 1)) { d >>= 1; ++r; }
    u128 nm1 = mont_in(&M, n - 1);
    for (unsigned b : SP) {
        u128 a = mont_pow(&M, mont_in(&M, b), d);
        if (a == M.one || a == nm1) continue;
        bool ok = false;
        for (int j = 1; j < r; ++j) { a = mont_mul(&M, a, a); if (a == nm1) { ok = true; break; } }
        if (!ok) return false;
    }
    static const u128 LIMIT = static_cast<u128>(3317044064679887ULL) * 1000000000ULL;  // 3.317e24
    if (n < LIMIT) return true;
    return mpz_probab_prime_p(zi(static_cast<i128>(n)).get_mpz_t(), 30) > 0;
}

u128 isqrt128(u128 v) {
    u128 r = static_cast<u128>(std::sqrt(static_cast<long double>(v)));
    while (r > 0 && r * r > v) --r;
    while ((r + 1) * (r + 1) <= v) ++r;
    return r;
}

// ---------------------------------------------------------------- rho
// Brent's variant of Pollard rho, f(y) = y^2 + c. A zero difference counts
// (it makes the batch product 0, so the gcd is n and the batch is replayed
// one step at a time); a step-by-step gcd of n means this c failed, and the
// caller retries with another c. Returns a nontrivial factor or 0.
template <class Mul, class Gcd, class T>
T brent(T n, T c, T y0, long budget, long& used, Mul mul, Gcd gcd) {
    auto f = [&](T v) { v = mul(v, v) + c; return v >= n ? v - n : v; };
    auto dist = [](T a, T b) { return a > b ? a - b : b - a; };
    T y = y0, x = y0, ys = y0, q = 1, g = 1;
    const long m = 64;
    for (long r = 1; g == 1; r <<= 1) {
        x = y;
        for (long i = 0; i < r; ++i) y = f(y);
        for (long k = 0; k < r && g == 1; k += m) {
            ys = y;
            long lim = std::min(m, r - k);
            for (long i = 0; i < lim; ++i) { y = f(y); q = mul(q, dist(x, y)); }
            g = gcd(q, n);
            used += lim;
            if (used > budget) return 0;
        }
    }
    if (g == n) {
        do { ys = f(ys); g = gcd(dist(x, ys), n); } while (g == 1);
    }
    return g == n ? 0 : g;
}

u128 find_factor(u128 n, long budget, unsigned& seed) {
    long used = 0;
    for (int attempt = 0; attempt < 64 && used <= budget; ++attempt) {
        seed = seed * 1103515245u + 12345u;
        uint64_t c = 1 + (seed >> 4) % 1000003u, y0 = 2 + (seed >> 12) % 9973u;
        if (n < (static_cast<u128>(1) << 63)) {
            uint64_t n64 = static_cast<uint64_t>(n);
            Mont64 M(n64);
            uint64_t d = brent<>(n64, M.in(c), M.in(y0), budget, used,
                                 [&](uint64_t a, uint64_t b) { return M.mul(a, b); },
                                 [](uint64_t a, uint64_t b) { return gcd64(a, b); });
            if (d) return d;
        } else {
            mont_t M; mont_init(&M, n);
            u128 d = brent<>(n, mont_in(&M, c), mont_in(&M, y0), budget, used,
                             [&](u128 a, u128 b) { return mont_mul(&M, a, b); },
                             [](u128 a, u128 b) { return gcd128x(a, b); });
            if (d) return d;
        }
    }
    return 0;
}

struct Factors {
    std::vector<std::pair<u128, int>> pe;
    void add(u128 p, int e = 1) {
        for (auto& t : pe) {
            if (t.first == p) { t.second += e; return; }
        }
        pe.push_back({p, e});
    }
};

// PARI fallback for cofactors rho does not split quickly. PARI's factors are
// re-checked by is_prime() and their product by the caller, so PARI is only
// trusted to propose a factorisation.
bool pari_factor(u128 c, std::vector<u128>& out) {
    pari_sp av = avma;
    GEN z = addii(shifti(utoi(static_cast<ulong>(c >> 64)), 64), utoi(static_cast<ulong>(c)));
    GEN F = Z_factor(z), P = gel(F, 1), E = gel(F, 2);
    bool ok = true;
    for (long i = 1; i < lg(P); ++i) {
        GEN pr = gel(P, i);
        if (expi(pr) >= 126) { ok = false; break; }
        u128 v = (static_cast<u128>(itou(shifti(pr, -64))) << 64) | static_cast<u128>(itou(remi2n(pr, 64)));
        for (long e = 0; e < itos(gel(E, i)); ++e) out.push_back(v);
    }
    set_avma(av);
    return ok;
}

// Factor a cofactor c >= 1 that has no prime factor <= the sieve limit;
// sieved2 = (sieve limit)^2, so 1 < c < sieved2 means c is prime.
bool split(u128 c, u128 sieved2, long budget, unsigned& seed, Factors& f, unsigned long long& rho_calls) {
    if (c == 1) return true;
    if (c < sieved2 || is_prime(c)) { f.add(c); return true; }
    u128 s = isqrt128(c);
    if (s * s == c) {
        Factors g;
        if (!split(s, sieved2, budget, seed, g, rho_calls)) return false;
        for (auto& t : g.pe) f.add(t.first, 2 * t.second);
        return true;
    }
    ++rho_calls;
    // Rho first (cheap when c has a smallish factor); for c >= 2^63 only a short
    // budget, then PARI.
    const bool big = c >= (static_cast<u128>(1) << 63);
    u128 d = (c & 1) ? find_factor(c, big ? std::min(budget, 1L << 11) : std::min(budget, 1L << 18), seed) : 2;
    if (d > 1 && d < c && c % d == 0)
        return split(d, sieved2, budget, seed, f, rho_calls) && split(c / d, sieved2, budget, seed, f, rho_calls);
    std::vector<u128> pr;
    if (!pari_factor(c, pr)) return false;
    u128 prod = 1;
    for (u128 v : pr) { if (!is_prime(v)) return false; prod *= v; }
    if (prod != c) return false;
    for (u128 v : pr) f.add(v);
    return true;
}

// --------------------------------------------------------------- squares
struct SquareFilter {
    // v is a square only if v mod m is a square mod m, for m = 64, 63, 65, 11.
    bool r64[64]{}, r63[63]{}, r65[65]{}, r11[11]{};
    SquareFilter() {
        for (int i = 0; i < 64; ++i) r64[(i * i) % 64] = true;
        for (int i = 0; i < 63; ++i) r63[(i * i) % 63] = true;
        for (int i = 0; i < 65; ++i) r65[(i * i) % 65] = true;
        for (int i = 0; i < 11; ++i) r11[(i * i) % 11] = true;
    }
    static uint64_t mod(i128 a, uint64_t m) { i128 r = a % static_cast<i128>(m); return static_cast<uint64_t>(r < 0 ? r + m : r); }
    // v = U^2 + W with U, W exact 128-bit integers (|U| < 2^126).
    bool maybe(i128 U, i128 W) const {
        const uint64_t M = 64ULL * 63 * 65 * 11;
        uint64_t u = mod(U, M), w = mod(W, M);
        uint64_t v = static_cast<uint64_t>((static_cast<u128>(u) * u + w) % M);
        return r64[v % 64] && r63[v % 63] && r65[v % 65] && r11[v % 11];
    }
};

int n_mod3(long long K) {
    long long r9 = ((K % 9) + 9) % 9;
    long long s9 = r9 == 3 ? (((K + 6) / 3) % 9 + 9) % 9 : (((K - 6) / 3) % 9 + 9) % 9;
    for (int v = 3; v < 18; v += 6) if (v % 9 == s9) return (v - 3) / 6;
    throw std::runtime_error("internal n (mod 3) derivation failed");
}

// Exact verification of one point and the output record.
std::string certify(long long K_, long long n_, const Z& X, const Z& Y, bool integer_form) {
    const Z K(static_cast<long>(K_)), n(static_cast<long>(n_));
    Z S = 6 * n + 3;
    Z N = (S * S * S - K) / 6;
    if (N * 6 != S * S * S - K) throw std::runtime_error("internal N check failed");
    // x = X/2, y = Y/2 with X, Y even (integer form) or odd (half form).
    if (integer_form != (mpz_even_p(X.get_mpz_t()) != 0) || integer_form != (mpz_even_p(Y.get_mpz_t()) != 0))
        throw std::runtime_error("internal parity check failed");
    if (sgn(Y) < 0 || X == 0) throw std::runtime_error("internal sign check failed");
    mpq_class x(X, 2), y(Y, 2); x.canonicalize(); y.canonicalize();
    mpq_class U = x + S;
    if (y * y != U * U + mpq_class(N) / x) throw std::runtime_error("internal equation verification failed");
    if (integer_form && (x.get_den() != 1 || y.get_den() != 1)) throw std::runtime_error("internal integrality failed");
    mpq_class A = -x + y, B = -x - y, C = 2 * x + S;
    A.canonicalize(); B.canonicalize(); C.canonicalize();
    Z a = A.get_num(), b = B.get_num(), c = C.get_num();
    if (A.get_den() != 1 || B.get_den() != 1 || C.get_den() != 1 || a * a * a + b * b * b + c * c * c != K)
        throw std::runtime_error("internal cube identity failed");
    Z gp, gc;
    if (integer_form) mpz_gcd(gp.get_mpz_t(), n.get_mpz_t(), x.get_num().get_mpz_t());
    else mpz_gcd(gp.get_mpz_t(), X.get_mpz_t(), Y.get_mpz_t());
    mpz_gcd(gc.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t());
    mpz_gcd(gc.get_mpz_t(), gc.get_mpz_t(), c.get_mpz_t());
    bool pp = gp == 1, pc = gc == 1;
    std::ostringstream o;
    o << "{\"type\":\"hit\",\"form\":" << q(integer_form ? "integer" : "half")
      << ",\"desired\":" << (pp && pc ? "true" : "false")
      << ",\"primitive_point\":" << (pp ? "true" : "false") << ",\"primitive_cubes\":" << (pc ? "true" : "false")
      << ",\"point_gcd\":" << q(gp.get_str()) << ",\"cube_gcd\":" << q(gc.get_str())
      << ",\"k\":" << q(K.get_str()) << ",\"n\":" << q(n.get_str())
      << ",\"x_num\":" << q(x.get_num().get_str()) << ",\"x_den\":" << q(x.get_den().get_str())
      << ",\"y_num\":" << q(y.get_num().get_str()) << ",\"y_den\":" << q(y.get_den().get_str())
      << ",\"X\":" << q(X.get_str()) << ",\"Y\":" << q(Y.get_str())
      << ",\"cube_a\":" << q(a.get_str()) << ",\"cube_b\":" << q(b.get_str()) << ",\"cube_c\":" << q(c.get_str()) << "}";
    return o.str();
}

struct Config {
    long long K = 375;
    long long n_start = 0, n_stop = 0;
    bool have_start = false, have_stop = false;
    long long block = 1 << 15;
    long sieve_limit = 1 << 14;
    long rho_budget = 1L << 27;
    double deadline = 0;
};

struct Counters { unsigned long long ns = 0, divisors = 0, candidates = 0, exact_checks = 0, hits = 0,
                  incomplete = 0, rho_calls = 0; };

long long parse_ll(const std::string& v, const std::string& name) {
    std::size_t i = 0; long long r = 0;
    try { r = std::stoll(v, &i); } catch (...) { throw std::runtime_error("invalid " + name); }
    if (i != v.size()) throw std::runtime_error("invalid " + name);
    return r;
}

void usage() {
    std::cout <<
        "Usage: xy375_worker --n-start A --n-stop B [--k 375] [--deadline-seconds S]\n"
        "                    [--block 32768] [--sieve-limit 16384] [--rho-budget 134217728]\n"
        "  Finds every rational x, y with A <= n < B on y^2 = (x+6n+3)^2 + N(n)/x,\n"
        "  N(n) = (S^3 - k)/6, S = 6n+3, in the integer form (x, y integers) and the\n"
        "  half form (x = X/2, y = Y/2, X, Y odd); prints one JSON line per point.\n";
}

Config arguments(int argc, char** argv) {
    Config c;
    for (int i = 1; i < argc; ++i) {
        std::string a = argv[i];
        if (a == "--version") { std::cout << "ce375-xy-worker " << VERSION << "\n"; std::exit(0); }
        if (a == "--help") { usage(); std::exit(0); }
        if (i + 1 == argc) throw std::runtime_error("missing value for " + a);
        std::string v = argv[++i];
        if (a == "--k") c.K = parse_ll(v, a);
        else if (a == "--n-start") { c.n_start = parse_ll(v, a); c.have_start = true; }
        else if (a == "--n-stop") { c.n_stop = parse_ll(v, a); c.have_stop = true; }
        else if (a == "--block") c.block = parse_ll(v, a);
        else if (a == "--sieve-limit") c.sieve_limit = static_cast<long>(parse_ll(v, a));
        else if (a == "--rho-budget") c.rho_budget = static_cast<long>(parse_ll(v, a));
        else if (a == "--deadline-seconds") c.deadline = static_cast<double>(parse_ll(v, a));
        else throw std::runtime_error("unknown option: " + a);
    }
    if (!c.have_start || !c.have_stop || c.n_stop <= c.n_start) throw std::runtime_error("need --n-start < --n-stop");
    // |N| < 2^126 needs |S| < ~2^43.3; keep |n| <= 10^12.
    const long long LIM = 1000000000000LL;
    if (c.n_start < -LIM || c.n_stop > LIM + 1) throw std::runtime_error("n range limited to |n| <= 10^12");
    long long r9 = ((c.K % 9) + 9) % 9;
    if (c.K % 2 == 0 || (r9 != 3 && r9 != 6) || std::llabs(c.K) > 1000000000LL)
        throw std::runtime_error("k must be odd, +-3 (mod 9) and |k| <= 10^9");
    if (c.block < 1 || c.block > (1 << 22)) throw std::runtime_error("block out of range");
    if (c.sieve_limit < 100 || c.sieve_limit > (1 << 22)) throw std::runtime_error("sieve-limit out of range");
    if (c.rho_budget < 1000) throw std::runtime_error("rho-budget too small");
    return c;
}

int run(const Config& c) {
    auto t0 = std::chrono::steady_clock::now();
    const int r3 = n_mod3(c.K);
    // primes up to the sieve limit, and the roots of 6N(t) = (6t+3)^3 - K mod p
    std::vector<long> primes;
    {
        std::vector<char> comp(c.sieve_limit + 1, 0);
        for (long i = 2; i <= c.sieve_limit; ++i) {
            if (comp[i]) continue;
            primes.push_back(i);
            for (long j = i * i; j <= c.sieve_limit; j += i) comp[j] = 1;
        }
    }
    // N(t) mod p for the polynomial N(t) = 36t^3 + 54t^2 + 27t + (27-K)/6.
    const long long c0 = (27 - c.K) / 6;
    std::vector<std::vector<long>> roots(primes.size());
    for (std::size_t i = 0; i < primes.size(); ++i) {
        long p = primes[i];
        long long a0 = ((c0 % p) + p) % p;
        for (long t = 0; t < p; ++t) {
            long long v = ((36LL * t % p * t % p * t + 54LL * t % p * t + 27LL * t + a0) % p + p) % p;
            if (v == 0) roots[i].push_back(t);
        }
    }
    const u128 sieved2 = static_cast<u128>(c.sieve_limit) * static_cast<u128>(c.sieve_limit);
    SquareFilter sq;
    unsigned seed = 12345u;

    std::cout << "{\"type\":\"start\",\"version\":" << q(VERSION) << ",\"method\":" << q(METHOD)
              << ",\"k\":" << q(std::to_string(c.K)) << ",\"n_start\":" << q(std::to_string(c.n_start))
              << ",\"n_stop\":" << q(std::to_string(c.n_stop)) << ",\"n_mod3\":" << r3 << "}\n" << std::flush;

    std::vector<u128> cof;
    std::vector<Factors> fac;
    for (long long b0 = c.n_start; b0 < c.n_stop; ) {
        auto s0 = std::chrono::steady_clock::now();
        long long b1 = std::min(c.n_stop, b0 + c.block);
        std::size_t L = static_cast<std::size_t>(b1 - b0);
        cof.assign(L, 0); fac.assign(L, Factors());
        for (std::size_t i = 0; i < L; ++i) {
            i128 n = b0 + static_cast<long long>(i);
            i128 N = 36 * n * n * n + 54 * n * n + 27 * n + c0;
            cof[i] = static_cast<u128>(N < 0 ? -N : N);
        }
        for (std::size_t j = 0; j < primes.size(); ++j) {
            long p = primes[j];
            for (long r : roots[j]) {
                long long first = ((r - b0) % p + p) % p;
                for (std::size_t i = static_cast<std::size_t>(first); i < L; i += static_cast<std::size_t>(p)) {
                    int e = 0;
                    while (cof[i] % static_cast<u128>(p) == 0) { cof[i] /= static_cast<u128>(p); ++e; }
                    if (e) fac[i].add(static_cast<u128>(p), e);
                }
            }
        }
        Counters k;
        std::ostringstream out;
        for (std::size_t i = 0; i < L; ++i) {
            long long n = b0 + static_cast<long long>(i);
            if (((n % 3) + 3) % 3 != r3) continue;  // METHOD.md section 2
            ++k.ns;
            Factors& f = fac[i];
            if (cof[i] > 1 && !split(cof[i], sieved2, c.rho_budget, seed, f, k.rho_calls)) {
                ++k.incomplete;
                i128 nn = n;
                i128 N = 36 * nn * nn * nn + 54 * nn * nn + 27 * nn + c0;
                out << "{\"type\":\"incomplete\",\"k\":" << q(std::to_string(c.K)) << ",\"n\":" << q(std::to_string(n))
                    << ",\"N\":" << q(i128s(N)) << "}\n";
                continue;
            }
            i128 nn = n;
            const i128 S = 6 * nn + 3;
            const i128 N = 36 * nn * nn * nn + 54 * nn * nn + 27 * nn + c0;
            // enumerate divisors
            std::vector<u128> divs{1};
            for (auto& [p, e] : f.pe) {
                std::size_t m = divs.size();
                u128 pk = 1;
                for (int t = 1; t <= e; ++t) { pk *= p; for (std::size_t s = 0; s < m; ++s) divs.push_back(divs[s] * pk); }
            }
            k.divisors += divs.size();
            for (u128 D : divs) {
                const i128 Di = static_cast<i128>(D);
                const i128 W = N / Di;  // exact
                for (int sign : {1, -1}) {
                    // integer form: x = sign*D, y^2 = (x+S)^2 + N/x
                    const i128 x = sign * Di, U = x + S, Wx = sign * W;
                    ++k.candidates;
                    if (sq.maybe(U, Wx)) {
                        ++k.exact_checks;
                        Z v = zi(U) * zi(U) + zi(Wx);
                        if (sgn(v) >= 0 && mpz_perfect_square_p(v.get_mpz_t())) {
                            Z y; mpz_sqrt(y.get_mpz_t(), v.get_mpz_t());
                            out << certify(c.K, n, 2 * zi(x), 2 * y, true) << "\n"; ++k.hits;
                        }
                    }
                    // half form: X = sign*D odd, Y^2 = (X+2S)^2 + 8N/X
                    if (D & 1) {
                        const i128 UX = x + 2 * S, WX = 8 * Wx;
                        ++k.candidates;
                        if (sq.maybe(UX, WX)) {
                            ++k.exact_checks;
                            Z v = zi(UX) * zi(UX) + zi(WX);
                            if (sgn(v) >= 0 && mpz_perfect_square_p(v.get_mpz_t())) {
                                Z Y; mpz_sqrt(Y.get_mpz_t(), v.get_mpz_t());
                                out << certify(c.K, n, zi(x), Y, false) << "\n"; ++k.hits;
                            }
                        }
                    }
                }
            }
        }
        double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - s0).count();
        std::cout << out.str()
                  << "{\"type\":\"block\",\"n_start\":" << q(std::to_string(b0)) << ",\"n_stop\":" << q(std::to_string(b1))
                  << ",\"ns\":" << k.ns << ",\"divisors\":" << k.divisors << ",\"candidates\":" << k.candidates
                  << ",\"exact_checks\":" << k.exact_checks << ",\"hits\":" << k.hits << ",\"incomplete\":" << k.incomplete
                  << ",\"rho_calls\":" << k.rho_calls << ",\"seconds\":" << secs << "}\n" << std::flush;
        b0 = b1;
        double total = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (c.deadline > 0 && total >= c.deadline && b0 < c.n_stop) {
            std::cout << "{\"type\":\"end\",\"state\":\"partial\",\"next_n\":" << q(std::to_string(b0)) << "}\n" << std::flush;
            return 0;
        }
    }
    std::cout << "{\"type\":\"end\",\"state\":\"complete\",\"next_n\":" << q(std::to_string(c.n_stop)) << "}\n" << std::flush;
    return 0;
}
}  // namespace

int main(int argc, char** argv) {
    try {
        Config c = arguments(argc, argv);
        pari_init(16000000, 0);
        int rc = run(c);
        return std::cout ? rc : 3;
    } catch (const std::exception& e) {
        std::cout << std::flush;
        std::cerr << "ce375-xy-worker: " << e.what() << '\n';
        return 2;
    }
}
