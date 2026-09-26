// Test the actual GMP implementation in the same translation unit.
// Signed fixtures below test arithmetic helpers, not the positive campaign.
#define main ce390_worker_program_main
#include "../src/cf_worker.cpp"
#undef main
#include <cassert>

int main() {
    // Compare Newton root isolation with an independent binary search.
    unsigned cases=0;
    for (long a: {1L,3L,17L,109L}) {
        for (long q: {1L,5L,101L,1000000007L}) {
            Polynomial f{Z(a),Z(q)};
            for (unsigned bits: {4U,64U,512U}) {
                Isolation r=isolate(f,Z(a),Z(q),bits);
                Z lo=0, hi=(Z(a)*r.scale)/(12*Z(q))+2;
                while (hi-lo>1) {
                    Z mid=(lo+hi)/2;
                    if (f.scaled(mid,r.scale)<=0) lo=mid;
                    else hi=mid;
                }
                assert(r.lo==lo);
                assert(f.scaled(r.lo,r.scale)<=0);
                if (!r.exact) {
                    assert(r.hi==lo+1);
                    assert(f.scaled(r.hi,r.scale)>0);
                }
                ++cases;
            }
        }
    }
    Z g;
    assert(recover_scale(Z(65),Z(65),g) && g==1);
    assert(recover_scale(Z(65)*3375*3375,Z(65),g) && g==225);
    assert(!recover_scale(Z(65),Z(0),g));
    assert(!recover_scale(Z(65),Z(-1),g));
    assert(!recover_scale(Z(65),Z(66),g));
    assert(!recover_scale(Z(65),Z(2),g));
    assert(!recover_scale(Z(65),Z(5),g));
    // Genuine equation fixture with gcd(n,x)=35 exercises cube scaling.
    Z a=integer("-13135766417"),q=integer("6948452840");
    Polynomial f(a,q);
    Z value=f.homogeneous(Z(52799),Z(-457436));
    assert(value==integer("73195680385557184"));
    assert(recover_scale(f.target,value,g) && g==35);
    Config cfg;
    cfg.nmin=1; cfg.nmax=2000000; cfg.xmin=-20000000; cfg.xmax=-1;
    cfg.congruences=false;
    std::vector<Hit> hits;
    std::set<std::pair<std::string,std::string>> seen;
    verify_and_add(cfg,a,q,Z(1847965),Z(-16010260),hits,seen);
    assert(hits.size()==1);
    assert(hits[0].y==Q(integer("1375212717"),Z(434)));
    assert(hits[0].d==Q(integer("-761139263"),integer("13896905680")));
    // Duplicate certificates must not be emitted twice.
    verify_and_add(cfg,a,q,Z(1847965),Z(-16010260),hits,seen);
    assert(hits.size()==1);
    cfg.integer_sqrt=true;
    std::vector<Hit> integer_hits;
    std::set<std::pair<std::string,std::string>> integer_seen;
    verify_and_add(cfg,a,q,Z(1847965),Z(-16010260),integer_hits,integer_seen);
    assert(integer_hits.empty());
    std::cout << "GMP helper checks passed: " << cases
              << " root brackets; scale, signed certificate, dedup, integer-radical checks\n";
}
