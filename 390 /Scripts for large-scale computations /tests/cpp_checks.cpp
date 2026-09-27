// Test the actual GMP implementation in the same translation unit.
// Root brackets, signed scale recovery, and original-equation certificates.
#define main ce390_worker_program_main
#include "../src/cf_worker.cpp"
#undef main
#include <cassert>

int main() {
    // Compare Newton root isolation with an independent binary search.
    unsigned cases=0;
    for (long a: {1L,3L,17L,109L}) {
        for (long q: {1L,5L,101L,1000000007L}) {
            if (a>=q) continue;
            for (int tau: {1,-1}) {
            Polynomial f{Z(a),Z(q),tau};
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
    Z a=integer("10385340983"),q=integer("6948452840");
    Polynomial f(a,q,-1);
    Z value=f.homogeneous(Z(52799),Z(457436));
    assert(value==integer("73195680385557184"));
    assert(recover_scale(f.target,value,g) && g==35);
    Config cfg;
    assert(cfg.integer_sqrt);
    cfg.integer_sqrt=false; // The historical certificate has a rational radical.
    cfg.nmin=1; cfg.nmax=2000000; cfg.xmin=1; cfg.xmax=20000000;
    cfg.congruences=false;
    std::vector<Hit> hits;
    std::set<std::pair<std::string,std::string>> seen;
    verify_and_add(cfg,a,q,-1,Z(1847965),Z(-16010260),hits,seen);
    assert(hits.size()==1);
    assert(hits[0].y==Q(integer("1375212717"),Z(434)));
    assert(hits[0].d==Q(integer("-761139263"),integer("13896905680")));
    // Duplicate certificates must not be emitted twice.
    verify_and_add(cfg,a,q,-1,Z(1847965),Z(-16010260),hits,seen);
    assert(hits.size()==1);
    cfg.integer_sqrt=true;
    std::vector<Hit> integer_hits;
    std::set<std::pair<std::string,std::string>> integer_seen;
    verify_and_add(cfg,a,q,-1,Z(1847965),Z(-16010260),integer_hits,integer_seen);
    assert(integer_hits.empty());
    // Production-valid negative-n fixture reaches the actual CF search.
    cfg.nmin=1; cfg.nmax=100; cfg.xmin=11; cfg.xmax=1000;
    cfg.integer_sqrt=false;
    for (const std::string signs: {"all","pp","pn","np","nn"}) {
        cfg.signs=signs;
        Result r=solve(cfg,Z(545),Z(729));
        bool found=false;
        for (const Hit& h:r.hits) {
            if (h.n==-5 && h.x==81) found=true;
            assert(accepts_signs(cfg,mpz_sgn(h.n.get_mpz_t()),mpz_sgn(h.x.get_mpz_t())));
        }
        assert(found==(signs=="all" || signs=="np"));
    }
    // Relaxed parity permits a genuine opposite mixed-sign fixture.
    cfg.nmin=160; cfg.nmax=170; cfg.xmin=2400; cfg.xmax=2600;
    cfg.signs="pn";
    Result pn=solve(cfg,Z(100703),Z(125000));
    assert(pn.hits.size()==1 && pn.hits[0].n==166 && pn.hits[0].x==-2500);
    assert(pn.hits[0].d==Q(-1103,250000));
    std::cout << "GMP helper checks passed: " << cases
              << " root brackets; scale, signed certificate, dedup, integer-radical checks\n";
}
