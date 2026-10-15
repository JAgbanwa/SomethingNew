// Exercise the actual helper code, including the changed CF fallback bound.
#define main ce390_rational_worker_main_for_test
#include "../src/rational_cf_worker.cpp"
#undef main
#include <cassert>

int main() {
    Config cfg;
    cfg.coordinate_denominator=51;
    cfg.congruence_policy="none";
    cfg.integer_sqrt=false;
    cfg.nmin=102; cfg.nmax=153; cfg.xmin=2040; cfg.xmax=2550;
    const Z a=1325,q=2341,b=51;
    Polynomial f(a,q,b,-1);
    assert(f.target==65*b*b*b*q*q);
    assert(f.homogeneous(Z(110),Z(2341))==f.target);
    // This genuine solution is NOT a convergent. Keeping the old X<=10
    // fallback would silently lose it and incorrectly claim completeness.
    Result only_cf;
    assert(cf_attempt(cfg,f,a,q,-1,512,only_cf));
    assert(only_cf.hits.empty());
    std::vector<Hit> hits;
    std::set<std::pair<std::string,std::string>> seen;
    small_exceptions(cfg,f,a,q,-1,hits,seen);
    assert(hits.size()==1);
    assert(hits[0].n_num==110 && hits[0].x_num==-2341 && hits[0].denominator==51);
    cfg.coordinate_denominator=5;
    cfg.congruence_policy="rational-mod";
    assert(coordinate_congruences(cfg,Z(11),Z(193)));
    cfg.congruence_policy="numerators";
    assert(!coordinate_congruences(cfg,Z(11),Z(193)));
    assert(coordinate_congruences(cfg,Z(16),Z(29)));
    std::cout<<"b^3 target, nonconvergent fallback witness, and modular policies passed\n";
}
