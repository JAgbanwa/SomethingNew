// Primitive-375 search, adapted from the CE114 Booker-Sutherland gap worker.
// Optional primitive and height restrictions are exact; see README.md.
//
// Every solution of x^3 + y^3 + Z^3 = k with |x| > |y| > |Z| > sqrt(k) has
//   d = |x + y|,  0 < d < alpha |Z|,  alpha = 2^(1/3) - 1,
//   z = |Z|,  z^3 == K (mod d),  K = k * sign(Z),
//   Delta = (4 (z^3 - K)/d - d^2)/3 = (x - y)^2,
// and for k == 3 eps (mod 9), eps = +-1: x == y == Z == eps (mod 3), which fixes
//   z == d (mod 3), and K = k if d == eps (mod 3), K = -k if d == -eps (mod 3).
// Conversely every (d, z) in such a progression with Delta = t^2, t == d (mod 2)
// gives the solution  s = -sign(Z) d,  x = (s + t)/2,  y = (s - t)/2.
//
// For each d in [d_start, d_stop) this worker
//   1. factors d with a segmented (small primes direct, large primes bucketed) sieve,
//   2. computes every cube root of K modulo d (prime roots, Hensel lifting, CRT),
//   3. walks z == root (mod d), z == d (mod 3) through [z_lo(d), z_hi(d)],
//      z_lo = floor(3847 d / 1000) <= d/alpha,  z_hi = ratio_max * d,
//   4. rejects candidates with an exact 2-adic test and 16 exact odd-prime
//      quadratic-residue tests on Delta, and
//   5. decides survivors exactly with GMP and verifies x^3 + y^3 + Z^3 = k.
// The filters are necessary conditions, so no solution in the region is lost.
#include <gmp.h>
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

namespace {
using u64 = uint64_t;
using u32 = uint32_t;
__extension__ typedef unsigned __int128 u128;
__extension__ typedef __int128 i128;
constexpr const char* VERSION = "1.2.0";
constexpr const char* METHOD = "booker-sutherland-primitive-v1";
constexpr u32 BLOCK = 1u << 16;            // d values per sieve block (per-d arrays stay cache-resident)
constexpr int MAXF = 16;                   // distinct prime factors of d < 2^63 is at most 15

// ------------------------------------------------------------ arithmetic
// a, b < m: the 128-bit product has high word < m, so one hardware divide gives the remainder.
inline u64 mulmod(u64 a, u64 b, u64 m) {
#if defined(__x86_64__) && defined(__GNUC__)
    u64 hi, lo, q, r;
    __asm__("mulq %3" : "=a"(lo), "=d"(hi) : "a"(a % m), "rm"(b % m) : "cc");
    __asm__("divq %4" : "=a"(q), "=d"(r) : "a"(lo), "d"(hi), "rm"(m) : "cc");
    (void)q;
    return r;
#else
    return static_cast<u64>(static_cast<u128>(a) * b % m);
#endif
}
u64 powmod(u64 a, u64 e, u64 m) {
    u64 r = 1 % m; a %= m;
    while (e) { if (e & 1) r = mulmod(r, a, m); a = mulmod(a, a, m); e >>= 1; }
    return r;
}
// Montgomery arithmetic for odd moduli < 2^63 (used for exponentiations mod large primes).
struct Mont {
    u64 n, ninv, r2;  // ninv = -n^{-1} mod 2^64, r2 = 2^128 mod n
    explicit Mont(u64 n_) : n(n_) {
        u64 inv = n;                                 // Newton: inverse of n mod 2^64
        for (int i = 0; i < 6; ++i) inv *= 2 - n * inv;
        ninv = ~inv + 1;
        u128 r = (static_cast<u128>(1) << 64) % n;
        r2 = static_cast<u64>(r * r % n);
    }
    u64 reduce(u128 t) const {
        u64 m = static_cast<u64>(t) * ninv;
        u128 s = t + static_cast<u128>(m) * n;
        u64 r = static_cast<u64>(s >> 64);
        // t < n^2 < 2^126 and m*n < 2^127, so s cannot overflow 128 bits.
        return r >= n ? r - n : r;
    }
    u64 to(u64 a) const { return reduce(static_cast<u128>(a % n) * r2); }
    u64 from(u64 a) const { return reduce(a); }
    u64 mul(u64 a, u64 b) const { return reduce(static_cast<u128>(a) * b); }
    u64 pow(u64 a, u64 e) const {  // a, result in normal form
        u64 x = to(a), r = to(1);
        while (e) { if (e & 1) r = mul(r, x); x = mul(x, x); e >>= 1; }
        return from(r);
    }
};
u64 pw(u64 a, u64 e, u64 m) {  // a^e mod m for any m >= 1
    if (m == 1) return 0;
    if ((m & 1) && m < (1ull << 63)) return Mont(m).pow(a % m, e);
    return powmod(a, e, m);
}
u64 invmod(u64 a, u64 m) {  // a^{-1} mod m, gcd(a, m) = 1, m < 2^63 (Bezout coefficients stay below m)
    if (m == 1) return 0;
    long long t = 0, nt = 1; u64 r = m, nr = a % m;
    while (nr) { u64 q = r / nr; long long tmp = t - static_cast<long long>(q) * nt; t = nt; nt = tmp; u64 tr = r - q * nr; r = nr; nr = tr; }
    if (r != 1) throw std::runtime_error("internal: non-invertible residue");
    if (t < 0) t += static_cast<long long>(m);
    return static_cast<u64>(t);
}
// u with 3u == 1 (mod t), 3 !| t, t >= 1
inline u64 inv3mod(u64 t) { if (t == 1) return 0; return (t % 3 == 1) ? (2 * (t / 3) + 1) : ((t / 3) + 1); }
u64 mod_signed(long long k, u64 m) { long long r = k % static_cast<long long>(m); return static_cast<u64>(r < 0 ? r + static_cast<long long>(m) : r); }

// ------------------------------------------------------------ cube roots
// Every z mod p with z^3 == a (mod p), for a prime p, p != 3, p !| a.
// One Montgomery context per call (p is odd and < 2^63 here except p = 2).
void cube_roots_prime(u64 a, u64 p, std::vector<u64>& out, bool known_residue = false) {
    out.clear();
    a %= p;
    if (p == 2) { out.push_back(a & 1); return; }
    const bool mont = (p & 1) && p < (1ull << 63);
    std::unique_ptr<Mont> mo; if (mont) mo.reset(new Mont(p));
    auto P = [&](u64 x, u64 e) -> u64 { return mont ? mo->pow(x % p, e) : powmod(x, e, p); };
    if (p % 3 == 2) { out.push_back(P(a, (2 * p - 1) / 3)); return; }
    u64 t = p - 1; int s = 0;
    while (t % 3 == 0) { t /= 3; ++s; }
    if (s == 1) {
        // p == 4, 7 (mod 9): t = (p-1)/3 is prime to 3. If a is a cube, a^t = 1 and r = a^u with
        // 3u == 1 (mod t) is a root; conversely r^3 == a shows a is a cube. So the residue test is
        // r^3 == a itself and costs no extra exponentiation. Any b with zeta = b^t != 1 gives the
        // primitive cube root of unity zeta.
        u64 u = inv3mod(t);
        u64 r = P(a, u);
        if (mulmod(mulmod(r, r, p), r, p) != a) {
            if (known_residue) throw std::runtime_error("internal: cube root check failed");
            return;                                   // not a cubic residue
        }
        u64 zeta = 1;
        for (u64 b = 2; zeta == 1; ++b) zeta = P(b, t);
        out.push_back(r); out.push_back(mulmod(r, zeta, p)); out.push_back(mulmod(r, mulmod(zeta, zeta, p), p));
        return;
    }
    if (!known_residue && P(a, (p - 1) / 3) != 1) return;  // not a cubic residue
    u64 b = 2;
    while (P(b, (p - 1) / 3) == 1) ++b;
    u64 g = P(b, t);                          // generator of the 3-Sylow subgroup (order 3^s)
    u64 zeta = g; for (int i = 1; i < s; ++i) zeta = P(zeta, 3);   // primitive cube root of 1
    u64 u = inv3mod(t);                       // 3u == 1 (mod t)
    u64 r0 = P(a, u);
    u64 w = mulmod(P(r0, 3), invmod(a, p), p);   // in the 3-Sylow subgroup
    u64 y = invmod(w, p), x = 0, p3 = 1, ginv = invmod(g, p);
    for (int i = 0; i < s; ++i) {             // Pohlig-Hellman: g^x = w^{-1}
        u64 c = mulmod(y, P(ginv, x), p);
        u64 e = 1; for (int j = 0; j < s - 1 - i; ++j) e *= 3;
        c = P(c, e);
        u64 digit = (c == 1) ? 0 : (c == zeta ? 1 : 2);
        if (digit == 2 && c != mulmod(zeta, zeta, p)) throw std::runtime_error("internal: cube-root discrete log");
        x += digit * p3; p3 *= 3;
    }
    if (x % 3 != 0) throw std::runtime_error("internal: cube-root residue class");
    u64 r = mulmod(r0, P(g, x / 3), p);
    if (P(r, 3) != a) throw std::runtime_error("internal: cube root check failed");
    out.push_back(r); out.push_back(mulmod(r, zeta, p)); out.push_back(mulmod(r, mulmod(zeta, zeta, p), p));
}

// Lift each root mod p to mod q = p^e (p !| 3a): Newton z <- z - (z^3-a)/(3z^2).
void hensel(u64 a, u64 q, std::vector<u64>& roots) {
    a %= q;
    for (u64& z : roots) {
        for (int it = 0; it < 80; ++it) {
            u64 f = (mulmod(mulmod(z, z, q), z, q) + q - a) % q;
            if (f == 0) break;
            u64 fp = mulmod(3, mulmod(z, z, q), q);
            z = (z + q - mulmod(f, invmod(fp, q), q)) % q;
        }
        if (mulmod(mulmod(z, z, q), z, q) != a) throw std::runtime_error("internal: Hensel lift failed");
    }
}

// ------------------------------------------------------------ the search
struct Counters {
    u64 d_total = 0, d_skipped_mod3 = 0, d_skipped_primitive = 0, d_no_roots = 0, d_live = 0, roots = 0, candidates = 0,
        pass_2adic = 0, pass_residue = 0, exact_checks = 0, hits = 0;
    std::string json() const {
        std::ostringstream o;
        o << "{\"d_total\":" << d_total << ",\"d_skipped_mod3\":" << d_skipped_mod3 << ",\"d_no_roots\":" << d_no_roots
          << ",\"d_skipped_primitive\":" << d_skipped_primitive
          << ",\"d_live\":" << d_live << ",\"roots\":" << roots << ",\"candidates\":" << candidates
          << ",\"pass_2adic\":" << pass_2adic << ",\"pass_residue\":" << pass_residue
          << ",\"exact_checks\":" << exact_checks << ",\"hits\":" << hits << "}";
        return o.str();
    }
    void add(const Counters& c) {
        d_total += c.d_total; d_skipped_mod3 += c.d_skipped_mod3; d_no_roots += c.d_no_roots; d_live += c.d_live;
        d_skipped_primitive += c.d_skipped_primitive;
        roots += c.roots; candidates += c.candidates; pass_2adic += c.pass_2adic; pass_residue += c.pass_residue;
        exact_checks += c.exact_checks; hits += c.hits;
    }
};

constexpr std::array<u32, 16> FP = {5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61};

// Delta == A_p z^3 + B_p (mod p) must be a square mod p (0 included). Constant moduli: no divisions.
// Filter primes J in [J, E). z only needs to be correct modulo the product of those primes.
constexpr std::size_t NBIT = 8;                       // primes 5..29: bit-parallel stage
constexpr u64 P1 = 5ull * 7 * 11 * 13 * 17 * 19 * 23 * 29;            // 2156564410
constexpr std::array<u32, 8> ADV = {64 % 5, 64 % 7, 64 % 11, 64 % 13, 64 % 17, 64 % 19, 64 % 23, 64 % 29};
constexpr u64 P2 = 31ull * 37 * 41 * 43 * 47 * 53 * 59 * 61;          // 18128893780549
template <std::size_t J, std::size_t E>
inline bool residue_ok(u64 z, const u32* Ap, const u32* Bp, const bool* use, const u64* qrmask) {
    if constexpr (J == E) { return true; }
    else {
        constexpr u32 p = FP[J];
        if (use[J]) {
            u32 zr = static_cast<u32>(z % p);
            u32 v = (Ap[J] * (zr * zr % p * zr % p) + Bp[J]) % p;
            if (!((qrmask[J] >> v) & 1)) return false;
        }
        return residue_ok<J + 1, E>(z, Ap, Bp, use, qrmask);
    }
}
// All 16 primes for a 128-bit z.
inline bool residue_all(u128 z, const u32* Ap, const u32* Bp, const bool* use, const u64* qrmask) {
    return residue_ok<0, NBIT>(static_cast<u64>(z % P1), Ap, Bp, use, qrmask)
        && residue_ok<NBIT, FP.size()>(static_cast<u64>(z % P2), Ap, Bp, use, qrmask);
}
std::string u128str(u128 v) {
    if (!v) return "0";
    std::string s;
    while (v) { s.push_back(static_cast<char>('0' + static_cast<int>(v % 10))); v /= 10; }
    std::reverse(s.begin(), s.end());
    return s;
}

void set_mpz_u128(mpz_t out, u128 value) {
    const u64 words[2] = {static_cast<u64>(value), static_cast<u64>(value >> 64)};
    mpz_import(out, 2, -1, sizeof(u64), 0, 0, words);
}

u128 get_mpz_u128(const mpz_t value) {
    if (mpz_sgn(value) < 0 || mpz_sizeinbase(value, 2) > 128)
        throw std::runtime_error("internal: integer does not fit in 128 bits");
    u64 words[2] = {0, 0};
    std::size_t count = 0;
    mpz_export(words, &count, -1, sizeof(u64), 0, 0, value);
    return static_cast<u128>(words[0]) | (static_cast<u128>(words[1]) << 64);
}

struct Config {
    long long k = 375;
    u64 d_start = 0, d_stop = 0, ratio_max = 64;   // |z| <= ratio_max * d, z held in 128 bits
    u128 height_min = 0;                         // report only max(|x|, |y|, |z|) > height_min
    u64 chunk = 1ull << 24;      // d values per progress/checkpoint record
    double deadline = 0;
    bool no_filter = false, dump_factors = false, dump_roots = false, primitive_only = false;
    u64 dump_candidates = 0;     // test mode: print filter verdicts for the first N candidates
};

struct Search {
    Config c;
    int eps3;                                    // eps mod 3 (1 or 2)
    std::vector<u32> small_p;                    // primes 2 <= p < BLOCK, p != 3
    std::vector<u64> small_next;                 // next multiple offset (relative to d_start)
    struct SmallInfo { bool kdiv, killer; std::vector<u64> roots; };
    std::vector<SmallInfo> sinfo;
    struct Entry { u32 p, off; };                // off: bits 0..30 offset in block, bit 31 = killer
    static constexpr u32 KILL = 1u << 31;
    // Buckets are singly linked lists of fixed-size pages drawn from one free pool, so memory
    // stays ~ (pending entries + one partial page per bucket) instead of every bucket keeping
    // the capacity of its fullest moment.
    static constexpr u32 PAGE = 1024;
    struct Page { Entry e[PAGE]; u32 n; Page* next; };
    std::vector<Page*> head;           // head[b]: page being filled (newest first)
    std::vector<Page*> pool;           // free pages
    std::vector<std::unique_ptr<Page>> owned;
    Page* new_page() {
        if (pool.empty()) { owned.emplace_back(new Page); return owned.back().get(); }
        Page* p = pool.back(); pool.pop_back(); return p;
    }
    inline void push(u64 bucket, Entry e) {
        Page*& h = head[bucket];
        if (!h || h->n == PAGE) { Page* np = new_page(); np->n = 0; np->next = h; h = np; }
        h->e[h->n++] = e;
    }
    u64 nblocks = 0, nb = 0, P = 0;
    std::map<std::pair<u64, int>, std::vector<u64>> kdiv_cache;  // roots of k mod p^e, p | k
    // per-block arrays
    std::vector<u64> cof; std::vector<uint8_t> nf, dead; std::vector<std::array<u32, MAXF>> fp; std::vector<std::array<uint8_t, MAXF>> fe;
    std::array<u64, FP.size()> qrmask{};
    std::array<std::array<u32, 64>, FP.size()> invtab{};
    std::array<u32, FP.size()> kmod_pos{}, kmod_neg{};   // k and -k modulo each filter prime
    // zmask[J][A*p+B]: bit z (0 <= z < p) set iff A z^3 + B is a square mod p.
    std::array<std::vector<u64>, FP.size()> zmask;
    // pat0[J][(A*p+B)*p+st] (J < NBIT): bit t set iff residue t*st (mod p) is allowed by zmask[J][A*p+B].
    std::array<std::vector<u64>, NBIT> pat0;
    u128 block_height_lower = 0;   // safe lower bound on |z| for this entire sieve block

    // A_p = 4/(3d), B_p = -4K/(3d) - d^2/3 (mod p); p | d disables the filter at p.
    template <std::size_t J>
    inline void filter_consts(u64 d, const u32* kp, u32* Ap, u32* Bp, bool* use) const {
        if constexpr (J < FP.size()) {
            constexpr u32 p = FP[J];
            u32 dp = static_cast<u32>(d % p);
            use[J] = dp != 0;
            if (dp) {
                u32 inv3d = invtab[J][(3 * dp) % p], inv3 = invtab[J][3 % p];
                Ap[J] = (4 * inv3d) % p;
                Bp[J] = (2 * p * p - (4 * kp[J] % p) * inv3d % p - (dp * dp % p) * inv3 % p) % p;
            }
            filter_consts<J + 1>(d, kp, Ap, Bp, use);
        }
    }

    explicit Search(const Config& cfg) : c(cfg) {
        long long r9 = ((c.k % 9) + 9) % 9;
        if (r9 != 3 && r9 != 6) throw std::runtime_error("k must be +-3 (mod 9)");
        eps3 = (r9 == 3) ? 1 : 2;
        for (std::size_t i = 0; i < FP.size(); ++i) {
            u32 p = FP[i]; u64 m = 0;
            for (u32 x = 0; x < p; ++x) m |= 1ull << (x * x % p);
            qrmask[i] = m;
            for (u32 x = 1; x < p; ++x) invtab[i][x] = static_cast<u32>(invmod(x, p));
            kmod_pos[i] = static_cast<u32>(mod_signed(c.k, p)); kmod_neg[i] = static_cast<u32>(mod_signed(-c.k, p));
            zmask[i].assign(static_cast<std::size_t>(p) * p, 0);
            for (u32 A = 0; A < p; ++A) for (u32 B = 0; B < p; ++B) {
                u64 zm = 0;
                for (u32 z = 0; z < p; ++z) if ((m >> ((A * (z * z % p * z % p) + B) % p)) & 1) zm |= 1ull << z;
                zmask[i][static_cast<std::size_t>(A) * p + B] = zm;
            }
            if (i < NBIT) {
                pat0[i].assign(static_cast<std::size_t>(p) * p * p, 0);
                for (u32 AB = 0; AB < p * p; ++AB) for (u32 st = 0; st < p; ++st) {
                    u64 pat = 0;
                    for (u32 t = 0; t < p; ++t) if ((zmask[i][AB] >> (t * st % p)) & 1) pat |= 1ull << t;
                    pat0[i][static_cast<std::size_t>(AB) * p + st] = pat;
                }
            }
        }
    }

    bool k_divisible(u64 p) const { return static_cast<u64>(std::llabs(c.k)) % p == 0; }

    const std::vector<u64>& kdiv_roots(u64 p, int e) {  // all z mod p^e with z^3 == k, p | k, p != 3
        auto key = std::make_pair(p, e);
        auto it = kdiv_cache.find(key);
        if (it != kdiv_cache.end()) return it->second;
        int v = 0; for (long long a = std::llabs(c.k); a % static_cast<long long>(p) == 0; a /= static_cast<long long>(p)) ++v;
        if (e > v && v % 3 != 0)   // z^3 == k (mod p^e) would force v_p(z^3) = v, impossible
            return kdiv_cache.emplace(key, std::vector<u64>{}).first->second;
        u64 q = 1; for (int i = 0; i < e; ++i) q *= p;   // q divides d, hence fits in u64
        std::vector<u64> r;
        if (e <= v) {
            // k == 0 (mod p^e): exactly the multiples of p^ceil(e/3) are roots.
            u64 step = 1; for (int i = 0; i < (e + 2) / 3; ++i) step *= p;
            for (u64 z = 0; z < q; z += step) r.push_back(z);
        } else {
            // Here v = 3s. Write z = p^s w, solve the nonsingular equation
            // w^3 == k/p^(3s) (mod p^(e-3s)), then retain every one of its p^(2s) lifts.
            // For k=375 and p=5 this produces 25 roots even for very large e.
            const int s = v / 3;
            u64 ps = 1; for (int i = 0; i < s; ++i) ps *= p;
            const u64 lifts = ps * ps, pv = lifts * ps, unit_modulus = q / pv;
            const long long unit_k = c.k / static_cast<long long>(pv);
            std::vector<u64> units;
            cube_roots_prime(mod_signed(unit_k, p), p, units);
            if (unit_modulus > p && !units.empty()) hensel(mod_signed(unit_k, unit_modulus), unit_modulus, units);
            const u64 step = q / lifts;
            r.reserve(units.size() * lifts);
            for (u64 w : units) for (u64 j = 0; j < lifts; ++j) r.push_back(ps * w + j * step);
            std::sort(r.begin(), r.end());
        }
        return kdiv_cache.emplace(key, std::move(r)).first->second;
    }

    void sieve_primes() {
        {   // P = isqrt(d_stop - 1): every composite d < d_stop has a prime factor <= P
            u64 x = static_cast<u64>(__builtin_sqrtl(static_cast<long double>(c.d_stop - 1)));
            while (x * x > c.d_stop - 1) --x;
            while ((x + 1) * (x + 1) <= c.d_stop - 1) ++x;
            P = x;
        }
        u64 L = c.d_stop - c.d_start;
        nblocks = (L + BLOCK - 1) / BLOCK;
        nb = P / BLOCK + 2;
        head.assign(nb, nullptr);
        std::vector<u64> comp(((P >> 1) >> 6) + 2, 0);  // bit i <-> odd number 2i+1 is composite
        auto is_comp = [&](u64 i) { return (comp[i >> 6] >> (i & 63)) & 1; };
        for (u64 i = 1; (2 * i + 1) * (2 * i + 1) <= P; ++i)
            if (!is_comp(i)) for (u64 j = (2 * i + 1) * (2 * i + 1) / 2; j <= P / 2; j += 2 * i + 1) comp[j >> 6] |= 1ull << (j & 63);
        auto add_prime = [&](u64 p) {
            if (p == 3 && !c.dump_factors) return;
            u64 off = (p - c.d_start % p) % p;
            if (p < BLOCK) { small_p.push_back(static_cast<u32>(p)); small_next.push_back(off); return; }
            if (off >= L) return;
            u64 blk = off / BLOCK;
            // Precompute once: k is not a cube mod p (p == 1 mod 3), so every multiple of p is dead.
            bool killer = !c.dump_factors && p % 3 == 1 && !k_divisible(p) && pw(mod_signed(c.k, p), (p - 1) / 3, p) != 1;
            push(blk % nb, {static_cast<u32>(p), static_cast<u32>(off % BLOCK) | (killer ? KILL : 0u)});
        };
        if (P >= 2) add_prime(2);
        for (u64 i = 1; 2 * i + 1 <= P; ++i) if (!is_comp(i)) add_prime(2 * i + 1);
        std::vector<u64>().swap(comp);
        sinfo.resize(small_p.size());
        small_index.assign(BLOCK, -1);
        for (std::size_t t = 0; t < small_p.size(); ++t) small_index[small_p[t]] = static_cast<int32_t>(t);
        std::vector<u64> tmp;
        for (std::size_t i = 0; i < small_p.size(); ++i) {
            u64 p = small_p[i]; SmallInfo& s = sinfo[i];
            s.kdiv = (p == 3) || k_divisible(p);
            s.killer = false;
            if (!s.kdiv) { cube_roots_prime(mod_signed(c.k, p), p, tmp); s.roots = tmp; s.killer = tmp.empty(); }
        }
    }

    // Record prime p dividing d = base + i: divide out its full power.
    inline void hit(u32 i, u64 p, bool killer) {
        if (dead[i]) return;
        if (killer && !c.dump_factors) { dead[i] = 1; return; }
        int e = 0; u64 v = cof[i];
        while (v % p == 0) { v /= p; ++e; }
        cof[i] = v;
        if (nf[i] >= MAXF) throw std::runtime_error("internal: too many prime factors");
        fp[i][nf[i]] = static_cast<u32>(p); fe[i][nf[i]] = static_cast<uint8_t>(e); ++nf[i];
    }

    // Roots of k modulo d from its factorization. Returns false if none.
    std::array<std::vector<u64>, MAXF + 1> rsbuf;   // reused per-factor root lists
    std::vector<u64> crt_tmp;
    std::vector<int32_t> small_index;                  // small_index[p] = index in small_p, or -1

    bool roots_of_k(u32 i, std::vector<u64>& R, u64& M) {
        R.assign(1, 0); M = 1;
        int n = nf[i] + (cof[i] > 1 ? 1 : 0);
        auto& rs = rsbuf;
        auto prime_of = [&](int j) -> u64 { return j < nf[i] ? fp[i][j] : cof[i]; };
        auto exp_of = [&](int j) -> int { return j < nf[i] ? fe[i][j] : 1; };
        // Existence first (cheap), CRT afterwards.
        for (int j = 0; j < n; ++j) {
            u64 p = prime_of(j); int e = exp_of(j);
            if (k_divisible(p)) { rs[j] = kdiv_roots(p, e); }
            else {
                int32_t si = (p < small_index.size()) ? small_index[p] : -1;
                if (si >= 0) rs[j] = sinfo[static_cast<std::size_t>(si)].roots;
                else cube_roots_prime(mod_signed(c.k, p), p, rs[j], false);
                if (!rs[j].empty() && e > 1) { u64 q = 1; for (int t = 0; t < e; ++t) q *= p; hensel(mod_signed(c.k, q), q, rs[j]); }
            }
            if (rs[j].empty()) return false;
        }
        for (int j = 0; j < n; ++j) {
            u64 p = prime_of(j); int e = exp_of(j); u64 q = 1; for (int t = 0; t < e; ++t) q *= p;
            if (M == 1) { R.assign(rs[j].begin(), rs[j].end()); M = q; continue; }
            u64 inv = invmod(M % q, q);
            crt_tmp.clear();
            for (u64 r : R) { u64 rq = r % q; for (u64 s2 : rs[j]) crt_tmp.push_back(r + M * mulmod((s2 + q - rq) % q, inv, q)); }
            R.swap(crt_tmp); M *= q;
        }
        return true;
    }

    // If d lies in a block beginning at A <= H, any solution of height > H has
    // |z|^3 > H^3 - (H-A)^3 - |k|. Indeed, max(|x|,|y|) = (d+sqrt(Delta))/2,
    // and H^3-(H-d)^3 is increasing in d; solutions with |z| > H also satisfy it.
    // Compute this deliberately conservative integer cutoff once per block, not per d.
    u128 height_lower_for_block(u64 A) const {
        if (!c.height_min || static_cast<u128>(A) > c.height_min) return 0;
        mpz_t H, t, N;
        mpz_inits(H, t, N, nullptr);
        set_mpz_u128(H, c.height_min);
        mpz_sub_ui(t, H, A); mpz_pow_ui(t, t, 3);
        mpz_pow_ui(N, H, 3); mpz_sub(N, N, t);
        mpz_sub_ui(N, N, static_cast<unsigned long>(std::llabs(c.k)));
        u128 lower = 0;
        if (mpz_sgn(N) >= 0) {
            mpz_root(t, N, 3); mpz_add_ui(t, t, 1);
            lower = get_mpz_u128(t);
        }
        mpz_clears(H, t, N, nullptr);
        return lower;
    }

    void exact(u64 d, u128 z, long long K, Counters& ct) {
        ++ct.exact_checks;
        mpz_t zz, dd, N, t, D3, x, y, s, a, b, cc, sum, gcd, height, height_min;
        mpz_inits(zz, dd, N, t, D3, x, y, s, a, b, cc, sum, gcd, height, height_min, nullptr);
        set_mpz_u128(zz, z); mpz_set_ui(dd, d);
        mpz_pow_ui(N, zz, 3); if (K >= 0) mpz_sub_ui(N, N, static_cast<unsigned long>(K)); else mpz_add_ui(N, N, static_cast<unsigned long>(-K));
        mpz_mul_ui(N, N, 4);
        mpz_pow_ui(t, dd, 3); mpz_sub(N, N, t);               // N = 4(z^3 - K) - d^3 = 3 d Delta
        mpz_mul_ui(D3, dd, 3);
        bool ok = false;
        if (mpz_sgn(N) >= 0 && mpz_divisible_p(N, D3)) {
            mpz_divexact(N, N, D3);
            if (mpz_perfect_square_p(N)) {
                mpz_sqrt(t, N);
                if (mpz_even_p(t) == mpz_even_p(dd)) {
                    // s = -sign(Z) d with Z = z if K = k, Z = -z if K = -k.
                    bool zpos = (K == c.k);
                    mpz_set(s, dd); if (zpos) mpz_neg(s, s);
                    mpz_add(x, s, t); mpz_divexact_ui(x, x, 2);
                    mpz_sub(y, s, t); mpz_divexact_ui(y, y, 2);
                    mpz_set(cc, zz); if (!zpos) mpz_neg(cc, cc);
                    mpz_gcd(gcd, x, y); mpz_gcd(gcd, gcd, cc);
                    const bool primitive = mpz_cmp_ui(gcd, 1) == 0;
                    mpz_abs(height, x); mpz_abs(a, y); if (mpz_cmp(a, height) > 0) mpz_set(height, a);
                    mpz_abs(a, cc); if (mpz_cmp(a, height) > 0) mpz_set(height, a);
                    set_mpz_u128(height_min, c.height_min);
                    if ((!c.primitive_only || primitive) && mpz_cmp(height, height_min) > 0) {
                        mpz_pow_ui(a, x, 3); mpz_pow_ui(b, y, 3); mpz_add(sum, a, b); mpz_pow_ui(a, cc, 3); mpz_add(sum, sum, a);
                        if (mpz_cmp_si(sum, c.k) != 0) throw std::runtime_error("internal: hit fails x^3+y^3+z^3 = k");
                        ok = true;
                        char *sx = mpz_get_str(nullptr, 10, x), *sy = mpz_get_str(nullptr, 10, y), *sz = mpz_get_str(nullptr, 10, cc);
                        char *sh = mpz_get_str(nullptr, 10, height);
                        std::cout << "{\"type\":\"hit\",\"k\":\"" << c.k << "\",\"x\":\"" << sx << "\",\"y\":\"" << sy
                                  << "\",\"z\":\"" << sz << "\",\"d\":\"" << d << "\",\"method\":\"" << METHOD
                                  << "\",\"primitive\":" << (primitive ? "true" : "false") << ",\"height\":\"" << sh << "\"}\n" << std::flush;
                        free(sx); free(sy); free(sz); free(sh);
                    }
                }
            }
        }
        if (ok) ++ct.hits;
        mpz_clears(zz, dd, N, t, D3, x, y, s, a, b, cc, sum, gcd, height, height_min, nullptr);
    }

    // zm[J]: allowed residues of z mod p; mp[J] = M mod p.
    template <std::size_t J>
    inline void fill_steps(u64 M, u64* zm, u32* mp, const u32* Ap, const u32* Bp, const bool* use) const {
        if constexpr (J < FP.size()) {
            constexpr u32 p = FP[J];
            zm[J] = use[J] ? zmask[J][static_cast<std::size_t>(Ap[J]) * p + Bp[J]] : ((1ull << p) - 1);
            mp[J] = static_cast<u32>(M % p);
            fill_steps<J + 1>(M, zm, mp, Ap, Bp, use);
        }
    }
    template <std::size_t J, std::size_t E = FP.size()>
    static inline void fill_res(u64 z, u32* zr) {
        if constexpr (J < E) { zr[J] = static_cast<u32>(z % FP[J]); fill_res<J + 1, E>(z, zr); }
    }
    // Is z0 + t M allowed modulo every filter prime? (t * mp < 32 * 61, no overflow)
    template <std::size_t J>
    static inline bool step_ok(u32 t, const u32* zr, const u32* mp, const u64* zm) {
        if constexpr (J == FP.size()) { return true; }
        else {
            constexpr u32 p = FP[J];
            if (!((zm[J] >> ((zr[J] + t * mp[J]) % p)) & 1)) return false;
            return step_ok<J + 1>(t, zr, mp, zm);
        }
    }

    void scan_d(u64 d, const std::vector<u64>& rootsK, long long K, Counters& ct) {
        u128 zlo = static_cast<u128>(d) * 3847 / 1000;
        if (zlo < 1) zlo = 1;
        if (block_height_lower > zlo) zlo = block_height_lower;
        const u128 zhi = static_cast<u128>(c.ratio_max) * d;
        if (zlo > zhi) return;
        const u64 dm3 = d % 3;
        // per-d filter constants: Delta == A_p z^3 + B_p (mod p)
        std::array<u32, FP.size()> Ap{}, Bp{}; std::array<bool, FP.size()> use{};
        filter_consts<0>(d, K == c.k ? kmod_pos.data() : kmod_neg.data(), Ap.data(), Bp.data(), use.data());
        const bool odd = d & 1;
        u64 dinv = 0; const u64 Kw = static_cast<u64>(K), d2 = d * d;
        if (odd) { dinv = d; for (int it = 0; it < 6; ++it) dinv *= 2 - d * dinv; }
        constexpr u64 INV3 = 0xAAAAAAAAAAAAAAABull;
        // Every solution has x == y (mod 3), so 9 | Delta = (x-y)^2; for odd d also Delta == 1 (mod 8).
        // With w = (z^3 - K)/d (an integer on z == r mod d), N = 4(z^3-K) - d^3 = d (4w - d^2), so
        // "3d | N and 9 | N/(3d)" is exactly 4w == d^2 (mod 27). For z = r + j d,
        //   w = w0 + 3 r^2 j + 3 r j^2 d + j^3 d^2,   w0 = (r^3 - K)/d,
        // so one exact product modulo 27d per root replaces three per class.
        // Delta mod 8 depends only on z mod 2, so z is confined to a few classes modulo
        // M = 9d (18d for odd d), walked with step M.
        const u64 M = (odd ? 18 : 9) * d, Q = 27 * d;            // Q < 2^63 (d < 2^63/27 enforced)
        const u64 KQ = mod_signed(K, Q);
        const u32 d27 = static_cast<u32>(d % 27), dd27 = d27 * d27 % 27;
        const u32 nj = static_cast<u32>(M / d);
        // Allowed residues of z modulo each filter prime (all residues if p | d), the step M modulo
        // each prime, and z_lo mod M. A height cutoff may put z_lo and the class start above 2^64.
        std::array<u64, FP.size()> zm{}; std::array<u32, FP.size()> mp{};
        fill_steps<0>(M, zm.data(), mp.data(), Ap.data(), Bp.data(), use.data());
        const u64 zloM = static_cast<u64>(zlo % M);
        bool pat_ready = false;                                     // bit-parallel tables, built lazily
        std::array<u128, NBIT> rp{}; std::array<u32, NBIT> stinv{};
        for (u64 r : rootsK) {
            if (c.primitive_only && std::llabs(c.k) == 375 && d % 125 == 0) {
                // Here 5|r and a primitive solution requires Delta mod 5 to be 1 or 4.
                // w=(r^3-K)/d mod 5 is invariant under r -> r+j*d, and Delta == 3*w (mod 5).
                // Thus precisely w=2,3 survive; calculating modulo 5d keeps the division exact.
                const u64 Q5 = 5 * d, K5 = mod_signed(K, Q5);
                const u64 W5 = (mulmod(mulmod(r, r, Q5), r, Q5) + Q5 - K5) % Q5;
                if (W5 % d) throw std::runtime_error("internal: primitive root congruence");
                const u64 w5 = W5 / d;
                if (w5 != 2 && w5 != 3) continue;
            }
            ++ct.roots;
            u64 W = (mulmod(mulmod(r, r, Q), r, Q) + Q - KQ) % Q;
            if (W % d != 0) throw std::runtime_error("internal: root does not cube to K mod d");
            const u32 w0 = static_cast<u32>(W / d), r27 = static_cast<u32>(r % 27);
            const u32 a1 = 3 * r27 * r27 % 27, a2 = 3 * r27 * d27 % 27;
            // z == d (mod 3) with z = r + j d fixes j mod 3: j == (d - r) d^{-1} == (d - r) d (mod 3).
            const u32 j0 = static_cast<u32>(((dm3 + 3 - r % 3) * dm3) % 3);
            for (u32 j = j0; j < nj; j += 3) {
                u64 zc = r + static_cast<u64>(j) * d;
                u32 w = (w0 + a1 * j + a2 * (j * j % 27) + (j * j * j % 27) * dd27) % 27;
                if ((4 * w + 27 - dd27) % 27 != 0) continue;                // Delta integral and 9 | Delta
                if (odd && ((((4 * (zc * zc * zc - Kw) * dinv - d2) * INV3) & 7) != 1)) continue;
                const u128 z0 = zlo + ((zc + M - zloM) % M);
                if (c.dump_candidates) {   // test mode: report both verdicts, exact check skipped
                    for (u128 z = z0; z <= zhi; z += M) {
                        ++ct.candidates;
                        u64 zw = static_cast<u64>(z);
                        bool two = !odd || ((((4 * (zw * zw * zw - Kw) * dinv - d2) * INV3) & 7) == 1);
                        bool res = residue_all(z, Ap.data(), Bp.data(), use.data(), qrmask.data());
                        std::cout << d << ' ' << u128str(z) << ' ' << K << ' ' << two << ' ' << res << '\n';
                        if (--c.dump_candidates == 0) { std::cout.flush(); std::exit(0); }
                    }
                    continue;
                }
                if (z0 > zhi) continue;
                const u128 T = (zhi - z0) / M + 1;                          // candidates in this class
                ct.candidates += static_cast<u64>(T);
                if (c.no_filter) {
                    for (u128 t = 0; t < T; ++t) exact(d, z0 + t * M, K, ct);
                    continue;
                }
                // The 2-adic class test above is exact for every z in the class (Delta mod 8 depends
                // only on z mod 2 and M is even for odd d).
                ct.pass_2adic += static_cast<u64>(T);
                std::array<u32, FP.size()> zr{};
                if (z0 >> 64) {
                    fill_res<0, NBIT>(static_cast<u64>(z0 % P1), zr.data());
                    fill_res<NBIT>(static_cast<u64>(z0 % P2), zr.data());
                } else fill_res<0>(static_cast<u64>(z0), zr.data());
                if (T <= 32) {   // few candidates: z mod p = zr + t * (M mod p), tested prime by prime
                    const u32 Tn = static_cast<u32>(T);
                    for (u32 t = 0; t < Tn; ++t) {
                        if (!step_ok<0>(t, zr.data(), mp.data(), zm.data())) continue;
                        ++ct.pass_residue;
                        exact(d, z0 + static_cast<u128>(t) * M, K, ct);
                    }
                    continue;
                }
                // Many candidates (large ratio_max). For p in 5..29 the allowed steps t form a
                // p-periodic bit pattern: with st = M mod p and z0 == u st (mod p), step t is allowed
                // iff residue (u + t) st is, so one pattern per d (PAT0: bit t <-> residue t st),
                // read from offset u, serves every class. Then AND 64 steps at a time.
                if (!pat_ready) {
                    for (std::size_t J = 0; J < NBIT; ++J) {
                        u32 p = FP[J], st = mp[J];
                        u64 pat = use[J] ? pat0[J][(static_cast<std::size_t>(Ap[J]) * p + Bp[J]) * p + st] : ((1ull << p) - 1);
                        u128 rr = pat;                                       // repeat the p-bit pattern
                        for (u32 len = p; len < 128; len *= 2) rr |= rr << len;
                        rp[J] = rr; stinv[J] = st ? invtab[J][st] : 0;   // st == 0 only if p | d: pattern all ones
                    }
                    pat_ready = true;
                }
                std::array<u32, NBIT> off{};
                for (std::size_t J = 0; J < NBIT; ++J) off[J] = zr[J] * stinv[J] % FP[J];
                for (u128 b0 = 0; b0 < T; b0 += 64) {
                    u64 word = (T - b0 >= 64) ? ~0ull : ((1ull << static_cast<u32>(T - b0)) - 1);
                    for (std::size_t J = 0; J < NBIT; ++J) {
                        word &= static_cast<u64>(rp[J] >> off[J]);
                        off[J] += ADV[J]; if (off[J] >= FP[J]) off[J] -= FP[J];
                    }
                    while (word) {
                        u32 i = static_cast<u32>(__builtin_ctzll(word)); word &= word - 1;
                        u128 z = z0 + (b0 + i) * static_cast<u128>(M);
                        if (!residue_ok<NBIT, FP.size()>(static_cast<u64>(z % P2), Ap.data(), Bp.data(), use.data(), qrmask.data())) continue;
                        ++ct.pass_residue;
                        exact(d, z, K, ct);
                    }
                }
            }
        }
    }

    void run() {
        if (c.d_start < 1 || c.d_stop <= c.d_start) throw std::runtime_error("need 1 <= d_start < d_stop");
        if (c.d_stop > (1ull << 62)) throw std::runtime_error("d_stop must be <= 2^62");
        if (c.ratio_max < 4) throw std::runtime_error("ratio_max must be >= 4");
        if (c.d_stop > (1ull << 63) / 27) throw std::runtime_error("d_stop must be < 2^63/27 (27d must fit in 63 bits)");
        u128 zmax = static_cast<u128>(c.ratio_max) * (c.d_stop - 1) + 18 * static_cast<u128>(c.d_stop);
        if (c.ratio_max > (1ull << 40) || zmax >= (static_cast<u128>(1) << 126))
            throw std::runtime_error("ratio_max * d too large (z must stay below 2^126)");
        auto t0 = std::chrono::steady_clock::now();
        sieve_primes();
        double setup = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (!c.dump_factors && !c.dump_roots)
            std::cout << "{\"type\":\"start\",\"version\":\"" << VERSION << "\",\"method\":\"" << METHOD << "\",\"k\":\"" << c.k
                      << "\",\"d_start\":\"" << c.d_start << "\",\"d_stop\":\"" << c.d_stop << "\",\"ratio_max\":\"" << c.ratio_max
                      << "\",\"primitive_only\":" << (c.primitive_only ? "true" : "false")
                      << ",\"height_min\":\"" << u128str(c.height_min)
                      << "\",\"z_lo\":\"max(floor(3847*d/1000), block_height_lower)\",\"sieve_limit\":\"" << P << "\",\"setup_seconds\":" << setup << "}\n" << std::flush;
        cof.resize(BLOCK); nf.resize(BLOCK); dead.resize(BLOCK); fp.resize(BLOCK); fe.resize(BLOCK);
        Counters chunk_ct; u64 chunk_start = c.d_start;
        auto tchunk = std::chrono::steady_clock::now();
        std::vector<u64> R, RK;
        for (u64 b = 0; b < nblocks; ++b) {
            u64 base = c.d_start + b * BLOCK;
            u32 len = static_cast<u32>(std::min<u64>(BLOCK, c.d_stop - base));
            block_height_lower = height_lower_for_block(base);
            for (u32 i = 0; i < len; ++i) {
                cof[i] = base + i; nf[i] = 0;
                dead[i] = (!c.dump_factors && (base + i) % 3 == 0) ? 2 : 0;
            }
            // Pass 1: primes p == 1 (mod 3) modulo which k is not a cube kill every multiple (no division).
            for (std::size_t j = 0; j < small_p.size() && !c.dump_factors; ++j) {
                if (!sinfo[j].killer) continue;
                u64 p = small_p[j];
                for (u64 rel = small_next[j] - b * BLOCK; rel < len; rel += p) dead[rel] |= 1;
            }
            Page* cur = head[b % nb];      // detached: p >= BLOCK always lands in a later bucket
            head[b % nb] = nullptr;
            for (Page* pg = cur; pg; pg = pg->next)
                for (u32 t = 0; t < pg->n; ++t) {
                    u32 off = pg->e[t].off & ~KILL;
                    if ((pg->e[t].off & KILL) && off < len) dead[off] |= 1;
                }
            // Pass 2: factor the survivors; advance every prime.
            for (std::size_t j = 0; j < small_p.size(); ++j) {
                u64 p = small_p[j];
                u64 rel = small_next[j] - b * BLOCK;  // small_next[j] >= b*BLOCK invariant
                if (!sinfo[j].killer || c.dump_factors) for (; rel < len; rel += p) hit(static_cast<u32>(rel), p, false);
                else while (rel < len) rel += p;
                small_next[j] = b * BLOCK + rel;
            }
            for (Page* pg = cur; pg;) {
                for (u32 t = 0; t < pg->n; ++t) {
                    const Entry& e = pg->e[t];
                    u64 p = e.p; u32 off = e.off & ~KILL, kill = e.off & KILL;
                    if (!kill && off < len) hit(off, p, false);
                    u64 next = b * BLOCK + off + p;
                    if (next < c.d_stop - c.d_start)
                        push((next / BLOCK) % nb, {static_cast<u32>(p), static_cast<u32>(next % BLOCK) | kill});
                }
                Page* nx = pg->next; pool.push_back(pg); pg = nx;
            }
            // per d
            for (u32 i = 0; i < len; ++i) {
                u64 d = base + i;
                ++chunk_ct.d_total;
                if (dead[i] & 2) { ++chunk_ct.d_skipped_mod3; continue; }   // bit 2: d == 0 (mod 3); bit 1: killed
                // A large prime cofactor q (> P) modulo which k is not a cube is detected inside
                // roots_of_k (cube_roots_prime tests residuosity as part of the root computation).
                if (c.dump_factors) {
                    std::cout << d;
                    for (int j = 0; j < nf[i]; ++j) std::cout << ' ' << fp[i][j] << '^' << int(fe[i][j]);
                    if (cof[i] > 1) std::cout << ' ' << cof[i] << "^1";
                    std::cout << '\n';
                    continue;
                }
                // For a primitive solution of +/-375, if 5 | d then 5 | z and x,y are 5-adic units.
                // Thus v5(x^3+y^3)=v5(d), while +/-375-z^3 is divisible by 125: v5(d)=1,2 is impossible.
                // Dump mode still exposes the unrestricted algebraic root sets for independent testing.
                if (c.primitive_only && std::llabs(c.k) == 375 && !c.dump_roots && d % 5 == 0 && d % 125 != 0) {
                    ++chunk_ct.d_skipped_primitive;
                    continue;
                }
                long long K = (static_cast<int>(d % 3) == eps3) ? c.k : -c.k;
                u64 M = 1;
                bool have = !dead[i] && roots_of_k(i, R, M);
                if (have && M != d) throw std::runtime_error("internal: factorization product != d");
                if (c.dump_roots) {
                    std::vector<u64> out;
                    if (have) for (u64 r : R) out.push_back(K == c.k ? r : (r == 0 ? 0 : d - r));
                    std::sort(out.begin(), out.end());
                    std::cout << d << ' ' << K;
                    for (u64 r : out) std::cout << ' ' << r;
                    std::cout << '\n';
                    continue;
                }
                if (!have) { ++chunk_ct.d_no_roots; continue; }
                ++chunk_ct.d_live;
                RK.clear();
                for (u64 r : R) RK.push_back(K == c.k ? r : (r == 0 ? 0 : d - r));   // roots of -k = -(roots of k)
                scan_d(d, RK, K, chunk_ct);
            }
            u64 done_to = base + len;
            const auto block_done = std::chrono::steady_clock::now();
            const double secs = std::chrono::duration<double>(block_done - tchunk).count();
            const double total = std::chrono::duration<double>(block_done - t0).count();
            const bool deadline_reached = c.deadline > 0 && total >= c.deadline;
            // A wide z-walk can make a count-based chunk take hours. Check the deadline and
            // the 30-second checkpoint target after EVERY completed sieve block, retaining exact
            // interval/counter boundaries. Either target can overrun by at most one block.
            if (!c.dump_factors && !c.dump_roots && (done_to - chunk_start >= c.chunk || done_to == c.d_stop
                                                    || secs >= 30.0 || deadline_reached)) {
                std::cout << "{\"type\":\"chunk\",\"d_start\":\"" << chunk_start << "\",\"d_stop\":\"" << done_to
                          << "\",\"seconds\":" << secs << ",\"counters\":" << chunk_ct.json() << "}\n" << std::flush;
                chunk_ct = Counters(); chunk_start = done_to; tchunk = std::chrono::steady_clock::now();
                if (deadline_reached && done_to < c.d_stop) {
                    std::cout << "{\"type\":\"end\",\"state\":\"partial\",\"d_next\":\"" << done_to << "\"}\n" << std::flush;
                    return;
                }
            }
        }
        if (!c.dump_factors && !c.dump_roots)
            std::cout << "{\"type\":\"end\",\"state\":\"complete\",\"d_next\":\"" << c.d_stop << "\"}\n" << std::flush;
    }
};

u64 parse_u64(const std::string& s) {
    if (s.empty() || s.size() > 20) throw std::runtime_error("invalid unsigned integer: " + s);
    for (char ch : s) if (ch < '0' || ch > '9') throw std::runtime_error("invalid unsigned integer: " + s);
    u128 v = 0; for (char ch : s) v = v * 10 + static_cast<u64>(ch - '0');
    if (v >> 64) throw std::runtime_error("integer too large: " + s);
    return static_cast<u64>(v);
}

u128 parse_u128(const std::string& s) {
    if (s.empty()) throw std::runtime_error("invalid unsigned integer: " + s);
    const u128 limit = ~static_cast<u128>(0);
    u128 value = 0;
    for (char ch : s) {
        if (ch < '0' || ch > '9') throw std::runtime_error("invalid unsigned integer: " + s);
        const u128 digit = static_cast<u128>(ch - '0');
        if (value > (limit - digit) / 10) throw std::runtime_error("integer too large: " + s);
        value = value * 10 + digit;
    }
    return value;
}

void usage() {
    std::cout <<
        "Usage: gap_worker --d-start A --d-stop B [--k 375] [--ratio-max 64] [--deadline-seconds S]\n"
        "                  [--primitive-only] [--height-min H] [--chunk N] [--no-filter]\n"
        "                  [--dump-factors] [--dump-roots]\n"
        "  Finds every solution of x^3+y^3+z^3 = k with d = |x+y| in [A, B) and\n"
        "  floor(3.847 d) <= |z| <= ratio_max * d (Booker-Sutherland parametrization).\n"
        "  --primitive-only requires gcd(x,y,z)=1; --height-min H requires max(|x|,|y|,|z|)>H.\n"
        "  Progress is flushed at least every ~30 seconds or on deadline, at a completed 65536-d\n"
        "  sieve-block boundary; either time target may overrun by one block.\n";
}
}  // namespace

int main(int argc, char** argv) {
    try {
        Config c; bool hs = false, he = false;
        for (int i = 1; i < argc; ++i) {
            std::string a = argv[i];
            if (a == "--version") { std::cout << "ce375-primitive-worker " << VERSION << "\n"; return 0; }
            if (a == "--help") { usage(); return 0; }
            if (a == "--no-filter") { c.no_filter = true; continue; }
            if (a == "--dump-factors") { c.dump_factors = true; continue; }
            if (a == "--dump-roots") { c.dump_roots = true; continue; }
            if (a == "--primitive-only") { c.primitive_only = true; continue; }
            if (a == "--dump-candidates") { if (i + 1 == argc) throw std::runtime_error("missing value"); c.dump_candidates = parse_u64(argv[++i]); continue; }
            if (i + 1 == argc) throw std::runtime_error("missing value for " + a);
            std::string v = argv[++i];
            if (a == "--k") { c.k = std::stoll(v); if (c.k == 0 || c.k < -1000000 || c.k > 1000000) throw std::runtime_error("k out of range"); }
            else if (a == "--d-start") { c.d_start = parse_u64(v); hs = true; }
            else if (a == "--d-stop") { c.d_stop = parse_u64(v); he = true; }
            else if (a == "--ratio-max") c.ratio_max = parse_u64(v);
            else if (a == "--height-min") c.height_min = parse_u128(v);
            else if (a == "--chunk") { c.chunk = parse_u64(v); if (!c.chunk) throw std::runtime_error("chunk must be positive"); }
            else if (a == "--deadline-seconds") c.deadline = static_cast<double>(parse_u64(v));
            else throw std::runtime_error("unknown option: " + a);
        }
        if (!hs || !he) throw std::runtime_error("need --d-start and --d-stop");
        Search s(c);
        s.run();
        return std::cout ? 0 : 3;
    } catch (const std::exception& e) {
        std::cout << std::flush;
        std::cerr << "ce375-primitive-worker: " << e.what() << '\n';
        return 2;
    }
}
