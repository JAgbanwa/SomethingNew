// CE114 gap search: the Booker-Sutherland method applied to the part of the
// (d, z) plane that their 2020 search (k = 114, 390, ...) did not cover. See README.md.
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
constexpr const char* VERSION = "1.0.0";
constexpr const char* METHOD = "booker-sutherland-gap-v1";
constexpr u32 BLOCK = 1u << 16;            // d values per sieve block (per-d arrays stay cache-resident)
constexpr int MAXF = 16;                   // distinct prime factors of d < 2^63 is at most 15

// ------------------------------------------------------------ arithmetic
u64 mulmod(u64 a, u64 b, u64 m) { return static_cast<u64>(static_cast<u128>(a) * b % m); }
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
u64 invmod(u64 a, u64 m) {  // a^{-1} mod m, gcd(a, m) = 1
    i128 t = 0, nt = 1, r = m, nr = a % m;
    while (nr) { i128 q = r / nr; i128 tmp = t - q * nt; t = nt; nt = tmp; tmp = r - q * nr; r = nr; nr = tmp; }
    if (r != 1) throw std::runtime_error("internal: non-invertible residue");
    if (t < 0) t += m;
    return static_cast<u64>(t);
}
u64 mod_signed(long long k, u64 m) { long long r = k % static_cast<long long>(m); return static_cast<u64>(r < 0 ? r + static_cast<long long>(m) : r); }

// ------------------------------------------------------------ cube roots
// Every z mod p with z^3 == a (mod p), for a prime p, p != 3, p !| a.
void cube_roots_prime(u64 a, u64 p, std::vector<u64>& out, bool known_residue = false) {
    out.clear();
    a %= p;
    if (p == 2) { out.push_back(a & 1); return; }
    if (p % 3 == 2) { out.push_back(pw(a, (2 * p - 1) / 3, p)); return; }
    if (!known_residue && pw(a, (p - 1) / 3, p) != 1) return;  // not a cubic residue
    u64 t = p - 1; int s = 0;
    while (t % 3 == 0) { t /= 3; ++s; }
    if (s == 1) {
        // p == 4, 7 (mod 9): t = (p-1)/3 is prime to 3 and a^t = 1, so r = a^u with 3u == 1 (mod t)
        // is a root; any b with zeta = b^t != 1 gives the primitive cube root of unity zeta.
        u64 u = (t == 1) ? 0 : invmod(3 % t, t);
        u64 r = pw(a, u, p), zeta = 1;
        for (u64 b = 2; zeta == 1; ++b) zeta = pw(b, t, p);
        if (mulmod(mulmod(r, r, p), r, p) != a) throw std::runtime_error("internal: cube root check failed");
        out.push_back(r); out.push_back(mulmod(r, zeta, p)); out.push_back(mulmod(r, mulmod(zeta, zeta, p), p));
        return;
    }
    u64 b = 2;
    while (pw(b, (p - 1) / 3, p) == 1) ++b;
    u64 g = pw(b, t, p);                      // generator of the 3-Sylow subgroup (order 3^s)
    u64 zeta = g; for (int i = 1; i < s; ++i) zeta = pw(zeta, 3, p);   // primitive cube root of 1
    u64 u = (t == 1) ? 0 : invmod(3 % t, t);  // 3u == 1 (mod t)
    u64 r0 = pw(a, u, p);
    u64 w = mulmod(pw(r0, 3, p), invmod(a, p), p);   // in the 3-Sylow subgroup
    u64 y = invmod(w, p), x = 0, p3 = 1, ginv = invmod(g, p);
    for (int i = 0; i < s; ++i) {             // Pohlig-Hellman: g^x = w^{-1}
        u64 c = mulmod(y, pw(ginv, x, p), p);
        u64 e = 1; for (int j = 0; j < s - 1 - i; ++j) e *= 3;
        c = pw(c, e, p);
        u64 digit = (c == 1) ? 0 : (c == zeta ? 1 : 2);
        if (digit == 2 && c != mulmod(zeta, zeta, p)) throw std::runtime_error("internal: cube-root discrete log");
        x += digit * p3; p3 *= 3;
    }
    if (x % 3 != 0) throw std::runtime_error("internal: cube-root residue class");
    u64 r = mulmod(r0, pw(g, x / 3, p), p);
    if (pw(r, 3, p) != a) throw std::runtime_error("internal: cube root check failed");
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
    u64 d_total = 0, d_skipped_mod3 = 0, d_no_roots = 0, d_live = 0, roots = 0, candidates = 0,
        pass_2adic = 0, pass_residue = 0, exact_checks = 0, hits = 0;
    std::string json() const {
        std::ostringstream o;
        o << "{\"d_total\":" << d_total << ",\"d_skipped_mod3\":" << d_skipped_mod3 << ",\"d_no_roots\":" << d_no_roots
          << ",\"d_live\":" << d_live << ",\"roots\":" << roots << ",\"candidates\":" << candidates
          << ",\"pass_2adic\":" << pass_2adic << ",\"pass_residue\":" << pass_residue
          << ",\"exact_checks\":" << exact_checks << ",\"hits\":" << hits << "}";
        return o.str();
    }
    void add(const Counters& c) {
        d_total += c.d_total; d_skipped_mod3 += c.d_skipped_mod3; d_no_roots += c.d_no_roots; d_live += c.d_live;
        roots += c.roots; candidates += c.candidates; pass_2adic += c.pass_2adic; pass_residue += c.pass_residue;
        exact_checks += c.exact_checks; hits += c.hits;
    }
};

constexpr std::array<u32, 16> FP = {5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61};

// Delta == A_p z^3 + B_p (mod p) must be a square mod p (0 included). Constant moduli: no divisions.
template <std::size_t J>
inline bool residue_ok(u64 z, const u32* Ap, const u32* Bp, const bool* use, const u64* qrmask) {
    if constexpr (J == FP.size()) { return true; }
    else {
        constexpr u32 p = FP[J];
        if (use[J]) {
            u32 zr = static_cast<u32>(z % p);
            u32 v = (Ap[J] * (zr * zr % p * zr % p) + Bp[J]) % p;
            if (!((qrmask[J] >> v) & 1)) return false;
        }
        return residue_ok<J + 1>(z, Ap, Bp, use, qrmask);
    }
}

struct Config {
    long long k = 114;
    u64 d_start = 0, d_stop = 0, ratio_max = 64;
    u64 chunk = 1ull << 24;      // d values per progress/checkpoint record
    double deadline = 0;
    bool no_filter = false, dump_factors = false, dump_roots = false;
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
        u64 q = 1; for (int i = 0; i < e; ++i) { if (q > (1ull << 24) / p) throw std::runtime_error("p^e too large for p | k (k with a cube factor)"); q *= p; }
        std::vector<u64> r; u64 km = mod_signed(c.k, q);
        for (u64 z = 0; z < q; ++z) if (mulmod(mulmod(z, z, q), z, q) == km) r.push_back(z);
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
                else cube_roots_prime(mod_signed(c.k, p), p, rs[j], j >= nf[i] && !c.dump_roots && !c.dump_factors);
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

    void exact(u64 d, u64 z, long long K, Counters& ct) {
        ++ct.exact_checks;
        mpz_t zz, dd, N, t, D3, x, y, s, a, b, cc, sum;
        mpz_inits(zz, dd, N, t, D3, x, y, s, a, b, cc, sum, nullptr);
        mpz_set_ui(zz, z); mpz_set_ui(dd, d);
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
                    mpz_pow_ui(a, x, 3); mpz_pow_ui(b, y, 3); mpz_add(sum, a, b); mpz_pow_ui(a, cc, 3); mpz_add(sum, sum, a);
                    if (mpz_cmp_si(sum, c.k) != 0) throw std::runtime_error("internal: hit fails x^3+y^3+z^3 = k");
                    ok = true;
                    char *sx = mpz_get_str(nullptr, 10, x), *sy = mpz_get_str(nullptr, 10, y), *sz = mpz_get_str(nullptr, 10, cc);
                    std::cout << "{\"type\":\"hit\",\"k\":\"" << c.k << "\",\"x\":\"" << sx << "\",\"y\":\"" << sy
                              << "\",\"z\":\"" << sz << "\",\"d\":\"" << d << "\",\"method\":\"" << METHOD << "\"}\n" << std::flush;
                    free(sx); free(sy); free(sz);
                }
            }
        }
        if (ok) ++ct.hits;
        mpz_clears(zz, dd, N, t, D3, x, y, s, a, b, cc, sum, nullptr);
    }

    void scan_d(u64 d, const std::vector<u64>& rootsK, long long K, Counters& ct) {
        u64 D3 = 3 * d;
        u128 zlo128 = static_cast<u128>(d) * 3847 / 1000;
        u64 zlo = static_cast<u64>(zlo128), zhi = c.ratio_max * d;
        if (zlo < 1) zlo = 1;
        u64 dm3 = d % 3;
        // per-d filter constants: Delta == A_p z^3 + B_p (mod p)
        std::array<u32, FP.size()> Ap{}, Bp{}; std::array<bool, FP.size()> use{};
        filter_consts<0>(d, K == c.k ? kmod_pos.data() : kmod_neg.data(), Ap.data(), Bp.data(), use.data());
        bool odd = d & 1;
        u64 dinv = 0, Kw = static_cast<u64>(K), d2 = d * d;
        if (odd) { dinv = d; for (int it = 0; it < 6; ++it) dinv *= 2 - d * dinv; }
        constexpr u64 INV3 = 0xAAAAAAAAAAAAAAABull;
        // Every solution has x == y (mod 3), so 9 | Delta = (x-y)^2; for odd d also Delta == 1 (mod 8).
        // Delta mod 9 depends only on z mod 9d (N = 3d Delta mod 27d), and Delta mod 8 only on z mod 2,
        // so z is confined to a few classes modulo M = 9d (18d for odd d), walked with step M.
        const u64 M = (odd ? 18 : 9) * d, Q = 27 * d;            // Q < 2^63 (d < 2^63/27 enforced)
        const u64 d3Q = mulmod(mulmod(d, d, Q), d, Q), KQ = mod_signed(K, Q);
        for (u64 r : rootsK) {
            ++ct.roots;
            for (u64 zc = r; zc < M; zc += d) {
                if (zc % 3 != dm3) continue;
                u64 z3 = mulmod(mulmod(zc, zc, Q), zc, Q);
                u64 NQ = (mulmod(4, (z3 + Q - KQ) % Q, Q) + Q - d3Q) % Q;     // N mod 27d
                if (NQ % D3 != 0 || (NQ / D3) % 9 != 0) continue;           // Delta integral and 9 | Delta
                if (odd && ((((4 * (zc * zc * zc - Kw) * dinv - d2) * INV3) & 7) != 1)) continue;
                u64 z = zlo + ((zc + M - zlo % M) % M);
                for (; z <= zhi; z += M) {
                ++ct.candidates;
                if (c.dump_candidates) {   // test mode: report both verdicts, exact check skipped
                    bool two = !odd || ((((4 * (z * z * z - Kw) * dinv - d2) * INV3) & 7) == 1);
                    bool res = residue_ok<0>(z, Ap.data(), Bp.data(), use.data(), qrmask.data());
                    std::cout << d << ' ' << z << ' ' << K << ' ' << two << ' ' << res << '\n';
                    if (--c.dump_candidates == 0) { std::cout.flush(); std::exit(0); }
                    continue;
                }
                if (!c.no_filter) {
                    if (odd) {
                        u64 delta = (4 * (z * z * z - Kw) * dinv - d2) * INV3;   // Delta mod 2^64, exact
                        if ((delta & 7) != 1) continue;                            // odd square: == 1 mod 8
                    }
                    ++ct.pass_2adic;
                    if (!residue_ok<0>(z, Ap.data(), Bp.data(), use.data(), qrmask.data())) continue;
                    ++ct.pass_residue;
                }
                exact(d, z, K, ct);
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
        if (zmax >= (static_cast<u128>(1) << 64)) throw std::runtime_error("ratio_max * d too large for 64-bit z");
        auto t0 = std::chrono::steady_clock::now();
        sieve_primes();
        double setup = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
        if (!c.dump_factors && !c.dump_roots)
            std::cout << "{\"type\":\"start\",\"version\":\"" << VERSION << "\",\"method\":\"" << METHOD << "\",\"k\":\"" << c.k
                      << "\",\"d_start\":\"" << c.d_start << "\",\"d_stop\":\"" << c.d_stop << "\",\"ratio_max\":\"" << c.ratio_max
                      << "\",\"z_lo\":\"floor(3847*d/1000)\",\"sieve_limit\":\"" << P << "\",\"setup_seconds\":" << setup << "}\n" << std::flush;
        cof.resize(BLOCK); nf.resize(BLOCK); dead.resize(BLOCK); fp.resize(BLOCK); fe.resize(BLOCK);
        Counters chunk_ct; u64 chunk_start = c.d_start;
        auto tchunk = std::chrono::steady_clock::now();
        std::vector<u64> R, RK;
        for (u64 b = 0; b < nblocks; ++b) {
            u64 base = c.d_start + b * BLOCK;
            u32 len = static_cast<u32>(std::min<u64>(BLOCK, c.d_stop - base));
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
                if (!dead[i] && cof[i] > 1) {
                    u64 q = cof[i];  // prime > P (all smaller primes removed)
                    bool killer = !c.dump_factors && !k_divisible(q) && q % 3 == 1 && pw(mod_signed(c.k, q), (q - 1) / 3, q) != 1;
                    if (killer) dead[i] = 1;   // cof[i] stays as the last prime factor of d
                }
                if (c.dump_factors) {
                    std::cout << d;
                    for (int j = 0; j < nf[i]; ++j) std::cout << ' ' << fp[i][j] << '^' << int(fe[i][j]);
                    if (cof[i] > 1) std::cout << ' ' << cof[i] << "^1";
                    std::cout << '\n';
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
            if (!c.dump_factors && !c.dump_roots && (done_to - chunk_start >= c.chunk || done_to == c.d_stop)) {
                double secs = std::chrono::duration<double>(std::chrono::steady_clock::now() - tchunk).count();
                std::cout << "{\"type\":\"chunk\",\"d_start\":\"" << chunk_start << "\",\"d_stop\":\"" << done_to
                          << "\",\"seconds\":" << secs << ",\"counters\":" << chunk_ct.json() << "}\n" << std::flush;
                chunk_ct = Counters(); chunk_start = done_to; tchunk = std::chrono::steady_clock::now();
                double total = std::chrono::duration<double>(tchunk - t0).count();
                if (c.deadline > 0 && total >= c.deadline && done_to < c.d_stop) {
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

void usage() {
    std::cout <<
        "Usage: gap_worker --d-start A --d-stop B [--k 114] [--ratio-max 64] [--deadline-seconds S]\n"
        "                  [--chunk N] [--no-filter] [--dump-factors] [--dump-roots]\n"
        "  Finds every solution of x^3+y^3+z^3 = k with d = |x+y| in [A, B) and\n"
        "  floor(3.847 d) <= |z| <= ratio_max * d (Booker-Sutherland parametrization).\n";
}
}  // namespace

int main(int argc, char** argv) {
    try {
        Config c; bool hs = false, he = false;
        for (int i = 1; i < argc; ++i) {
            std::string a = argv[i];
            if (a == "--version") { std::cout << "ce114-gap-worker " << VERSION << "\n"; return 0; }
            if (a == "--help") { usage(); return 0; }
            if (a == "--no-filter") { c.no_filter = true; continue; }
            if (a == "--dump-factors") { c.dump_factors = true; continue; }
            if (a == "--dump-roots") { c.dump_roots = true; continue; }
            if (a == "--dump-candidates") { if (i + 1 == argc) throw std::runtime_error("missing value"); c.dump_candidates = parse_u64(argv[++i]); continue; }
            if (i + 1 == argc) throw std::runtime_error("missing value for " + a);
            std::string v = argv[++i];
            if (a == "--k") { c.k = std::stoll(v); if (c.k == 0 || std::llabs(c.k) > 1000000) throw std::runtime_error("k out of range"); }
            else if (a == "--d-start") { c.d_start = parse_u64(v); hs = true; }
            else if (a == "--d-stop") { c.d_stop = parse_u64(v); he = true; }
            else if (a == "--ratio-max") c.ratio_max = parse_u64(v);
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
        std::cerr << "ce114-gap-worker: " << e.what() << '\n';
        return 2;
    }
}
