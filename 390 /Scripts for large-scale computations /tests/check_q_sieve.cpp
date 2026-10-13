#include "../src/q_sieve.hpp"
#include <exception>
#include <iostream>
#include <string>

// Test-only protocol: lines containing decimal_q and a mode flag 0 or 1.
// Output is rejection (0/1), first prime witness (0 means none).
int main(int argc, char** argv) {
    try {
        if (argc == 2 && std::string(argv[1]) == "--primes") {
            for (auto p : ce390_q_sieve::forbidden_primes()) std::cout << p << '\n';
            return 0;
        }
        ce390_q_sieve::DenominatorCache cache;
        std::string text;
        int mode;
        while (std::cin >> text) {
            if (!(std::cin >> mode) || (mode != 0 && mode != 1)) {
                std::cerr << "Expected decimal_q and mode 0 or 1\n";
                return 2;
            }
            const mpz_class q(text, 10);
            bool result = cache.reject(q, mode == 1);
            if (result != ce390_q_sieve::reject_q(q, mode == 1)) return 3;
            const auto witness = ce390_q_sieve::first_forbidden_prime(q, mode == 1);
            if (result != (witness != 0)) return 4;
            std::cout << (result ? 1 : 0) << ' ' << witness << '\n';
        }
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 2;
    }
}
