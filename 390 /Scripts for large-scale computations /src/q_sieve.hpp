#ifndef CE390_Q_SIEVE_HPP
#define CE390_Q_SIEVE_HPP

// Exact C++17/GMP denominator obstruction sieve used by cf_worker.cpp.
// Existing input, gcd(a,q), 2/3 and target-congruence filters remain required.
#include <gmpxx.h>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace ce390_q_sieve {
inline constexpr unsigned long prime_limit = 20000UL;  // strict upper bound
inline constexpr const char* sieve_id = "ce390-q-prime-obstruction-v1";

namespace detail {
inline unsigned long pow_mod(unsigned long base, unsigned long exponent,
                             unsigned long modulus) {
    std::uint64_t result = 1;
    std::uint64_t b = base % modulus;
    while (exponent != 0) {
        if ((exponent & 1UL) != 0) result = (result * b) % modulus;
        b = (b * b) % modulus;
        exponent >>= 1;
    }
    return static_cast<unsigned long>(result);
}

struct Table {
    std::vector<unsigned long> primes;
    mpz_class product = 1;
    Table() {
        std::vector<bool> prime(prime_limit, true);
        prime[0] = prime[1] = false;
        for (unsigned long p = 2; p * p < prime_limit; ++p) {
            if (prime[p]) {
                for (unsigned long j = p * p; j < prime_limit; j += p)
                    prime[j] = false;
            }
        }
        for (unsigned long p = 2; p < prime_limit; ++p) {
            if (!prime[p] || p % 3 != 1 || p == 5 || p == 13) continue;
            const unsigned long exponent = (p - 1) / 3;
            if (pow_mod(65, exponent, p) != pow_mod(36, exponent, p)) {
                primes.push_back(p);
                product *= p;
            }
        }
    }
};

inline const Table& table() {
    static const Table value;
    return value;
}

inline void validate_q(const mpz_class& q) {
    if (q <= 0) throw std::invalid_argument("q must be a positive denominator");
}
}  // namespace detail

inline const std::vector<unsigned long>& forbidden_primes() {
    return detail::table().primes;
}

// The mode flag has NO default: use the worker's resolved task policy.
inline bool reject_q(const mpz_class& q, bool require_integer_sqrt) {
    detail::validate_q(q);
    if (!require_integer_sqrt) return false;
    mpz_class common;
    mpz_gcd(common.get_mpz_t(), q.get_mpz_t(),
            detail::table().product.get_mpz_t());
    return common != 1;
}

// Zero means no witness under this sieve, NOT proof of a valid denominator.
inline unsigned long first_forbidden_prime(const mpz_class& q,
                                           bool require_integer_sqrt) {
    detail::validate_q(q);
    if (!require_integer_sqrt) return 0;
    for (unsigned long p : forbidden_primes()) {
        if (mpz_divisible_ui_p(q.get_mpz_t(), p)) return p;
    }
    return 0;
}

// Optional one-denominator cache. Instantiate one per worker/thread, not as
// mutable shared state. Reuse across numerators in the same denominator row.
class DenominatorCache {
    mpz_class last_q_ = 0;
    bool last_reject_ = false;
public:
    bool reject(const mpz_class& q, bool require_integer_sqrt) {
        detail::validate_q(q);
        if (!require_integer_sqrt) return false;
        if (q != last_q_) {
            last_reject_ = reject_q(q, true);
            last_q_ = q;
        }
        return last_reject_;
    }
};
}  // namespace ce390_q_sieve
#endif
