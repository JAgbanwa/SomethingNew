// CE390: certified continued-fraction search of fixed rational-d fibres.
// All acceptance decisions use GMP integers/rationals, never floating point.
#include <gmpxx.h>
#include <algorithm>
#include <chrono>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Z = mpz_class;
using Q = mpq_class;
constexpr const char* VERSION = "3.0.0";

Z integer(const std::string& s) {
    if (s.empty()) throw std::runtime_error("empty integer");
    std::size_t i = (s[0] == '-' || s[0] == '+') ? 1 : 0;
    if (i == s.size()) throw std::runtime_error("invalid integer");
    for (; i < s.size(); ++i)
        if (s[i] < '0' || s[i] > '9') throw std::runtime_error("invalid decimal integer");
    Z z;
    if (mpz_set_str(z.get_mpz_t(), s.c_str(), 10) != 0)
        throw std::runtime_error("invalid decimal integer");
    return z;
}

std::string quoted(const std::string& s) {
    std::string r = "\"";
    for (unsigned char c : s) {
        if (c == '"' || c == '\\') { r += '\\'; r += char(c); }
        else if (c == '\n') r += "\\n";
        else if (c == '\r') r += "\\r";
        else if (c == '\t') r += "\\t";
        else if (c >= 32 && c < 127) r += char(c);
        else r += '?';
    }
    return r + '"';
}

struct Config {
    Z nmin = integer("10000000000000000000000000000000000000000000");
    Z nmax = integer("1000000000000000000000000000000000000000000000");
    Z xmin = integer("1000000000000000000000000000000000000000000000000000000");
    Z xmax = integer("10000000000000000000000000000000000000000000000000000000");
    unsigned precision = 512;
    unsigned max_precision = 16384;
    bool congruences = true;
    bool integer_sqrt = false;
};

struct Polynomial {
    Z c3, c1, c0, target;
    Polynomial(const Z& a, const Z& q)
        : c3(36*q*q), c1(12*q*(2*q+a)), c0(a*(2*q+a)), target(65*q*q) {}
    Z homogeneous(const Z& u, const Z& v) const {
        return c3*u*u*u + c1*u*v*v - c0*v*v*v;
    }
    Z scaled(const Z& u, const Z& scale) const {
        return homogeneous(u, scale);
    }
};

struct Isolation { Z lo, hi, scale; bool exact = false; };

// Find floor(alpha*2^bits), where c3*alpha^3+c1*alpha-c0=0.
// Newton starts strictly above the unique positive root. Convexity ensures
// its unrounded iterate stays above the root; flooring can only reach its
// floor, never jump below it. A negative residual therefore certifies lo.
Isolation isolate(const Polynomial& f, const Z& a, const Z& q, unsigned bits) {
    Z D = Z(1) << bits;
    Z num = a*D, den = 12*q;
    Z z;
    mpz_cdiv_q(z.get_mpz_t(), num.get_mpz_t(), den.get_mpz_t());
    Z D2 = D*D, C = f.c0*D2*D;
    while (true) {
        Z value = f.scaled(z, D);
        if (value == 0) return {z, z, D, true};
        if (value < 0) {
            Z upper = z+1;
            if (f.scaled(upper, D) <= 0)
                throw std::runtime_error("internal root-isolation invariant failed");
            return {z, upper, D, false};
        }
        Z numerator = 2*f.c3*z*z*z+C;
        Z denominator = 3*f.c3*z*z+f.c1*D2;
        Z next = numerator/denominator;
        if (next >= z)
            throw std::runtime_error("internal Newton descent invariant failed");
        z = std::move(next);
    }
}

struct Hit {
    Z n, x;
    Q y, d, gap;
    std::string json() const {
        return "{\"n\":" + quoted(n.get_str()) + ",\"x\":" + quoted(x.get_str())
          + ",\"y_num\":" + quoted(y.get_num().get_str())
          + ",\"y_den\":" + quoted(y.get_den().get_str())
          + ",\"d_num\":" + quoted(d.get_num().get_str())
          + ",\"d_den\":" + quoted(d.get_den().get_str())
          + ",\"gap_num\":" + quoted(gap.get_num().get_str())
          + ",\"gap_den\":" + quoted(gap.get_den().get_str())
          + ",\"sqrt_integer\":" + (y.get_den() == 1 ? "true" : "false") + "}";
    }
};

void verify_and_add(const Config& cfg, const Z& a, const Z& q,
                    const Z& n, const Z& x, std::vector<Hit>& hits,
                    std::set<std::pair<std::string,std::string>>& seen) {
    if (n < cfg.nmin || n > cfg.nmax || x < cfg.xmin || x > cfg.xmax) return;
    if (cfg.congruences && (mpz_fdiv_ui(n.get_mpz_t(),3) != 1
        || mpz_fdiv_ui(x.get_mpz_t(),12) != 5
        || mpz_divisible_ui_p(x.get_mpz_t(),7))) return;
    Q y((q+a)*x,q); y -= 6*n; y.canonicalize();
    Q d(-(2*q+a),2*q); d.canonicalize();
    Q gap = y-x-6*n; gap.canonicalize();
    if (y < 0) return; // Principal square root is required.
    if (cfg.integer_sqrt && y.get_den()!=1) return;
    Z A = 36*n*n*n-65, S=x+6*n;
    Q radicand(A,x); radicand += S*S; radicand.canonicalize();
    if (y*y != radicand || Q(A) != -2*d*x*x*(y-S))
        throw std::runtime_error("internal original-equation verification failed");
    auto key=std::make_pair(n.get_str(),x.get_str());
    if (seen.insert(key).second) hits.push_back({n,x,y,d,gap});
}

bool recover_scale(const Z& target,const Z& value,Z& g) {
    if (value<=0 || value>target
        || !mpz_divisible_p(target.get_mpz_t(),value.get_mpz_t())) return false;
    Z ratio=target/value;
    return mpz_root(g.get_mpz_t(),ratio.get_mpz_t(),3)!=0;
}

void evaluate(const Config& cfg, const Polynomial& f, const Z& a, const Z& q,
              const Z& u, const Z& v, std::vector<Hit>& hits,
              std::set<std::pair<std::string,std::string>>& seen) {
    if (u <= 0 || v <= 0 || u > cfg.nmax || v > cfg.xmax) return;
    Z value=f.homogeneous(u,v);
    Z g;
    if (!recover_scale(f.target,value,g)) return;
    verify_and_add(cfg,a,q,g*u,g*v,hits,seen);
}

// Legendre's sufficient inequality only potentially fails when g=1 and
// reduced denominator v<=5. Such a point has x<=5. For each of those five
// x values, strict monotonicity in n permits an exact binary search.
void small_exceptions(const Config& cfg, const Polynomial& f,
                      const Z& a, const Z& q, std::vector<Hit>& hits,
                      std::set<std::pair<std::string,std::string>>& seen) {
    if (cfg.xmin > 5) return;
    for (unsigned xsmall=1; xsmall<=5; ++xsmall) {
        Z x=xsmall;
        if (x<cfg.xmin || x>cfg.xmax) continue;
        Z lo=cfg.nmin, hi=cfg.nmax;
        while (lo<=hi) {
            Z mid=(lo+hi)/2, value=f.homogeneous(mid,x);
            if (value == f.target) {
                verify_and_add(cfg,a,q,mid,x,hits,seen); break;
            }
            if (value<f.target) lo=mid+1; else hi=mid-1;
        }
    }
}

struct Result {
    std::vector<Hit> hits;
    unsigned precision=0;
    unsigned long long convergents=0;
    bool excluded_by_congruence=false;
    bool excluded_by_bounds=false;
};

// A common interval partial quotient is certified exactly. Endpoints are
// open: for an integral upper endpoint H, floor(alpha)<=H-1.
bool cf_attempt(const Config& cfg, const Polynomial& f,
                const Z& a, const Z& q, unsigned bits,
                Result& out) {
    out.precision=bits;
    std::set<std::pair<std::string,std::string>> seen;
    for (const auto& h:out.hits) seen.emplace(h.n.get_str(),h.x.get_str());
    Isolation root=isolate(f,a,q,bits);
    Z pn2=0,pn1=1,vn2=1,vn1=0;
    if (root.exact) {
        // Defensive handling of a rational root, even though positive roots
        // in the admissible family are irrational (Fermat's theorem for 3).
        Z p=root.lo,r=root.scale;
        while (r!=0) {
            Z c=p/r, rem=p%r;
            Z u=c*pn1+pn2,v=c*vn1+vn2;
            if (v>cfg.xmax) return true;
            ++out.convergents;
            evaluate(cfg,f,a,q,u,v,out.hits,seen);
            pn2=pn1;pn1=u;vn2=vn1;vn1=v;
            p=r;r=rem;
        }
        return true;
    }
    Z ln=root.lo,ld=root.scale,hn=root.hi,hd=root.scale;
    while (true) {
        Z cmin,cmax;
        mpz_fdiv_q(cmin.get_mpz_t(),ln.get_mpz_t(),ld.get_mpz_t());
        mpz_cdiv_q(cmax.get_mpz_t(),hn.get_mpz_t(),hd.get_mpz_t());
        --cmax;
        Z minv=cmin*vn1+vn2;
        if (vn1>0 && minv>cfg.xmax) return true;
        if (cmin!=cmax) return false; // Refine root, then replay CF.
        Z u=cmin*pn1+pn2,v=cmin*vn1+vn2;
        if (v>cfg.xmax) return true;
        ++out.convergents;
        evaluate(cfg,f,a,q,u,v,out.hits,seen);
        pn2=pn1;pn1=u;vn2=vn1;vn1=v;
        if (vn1>0 && vn1+vn2>cfg.xmax) return true;
        Z low_rem=ln-cmin*ld, high_rem=hn-cmin*hd;
        if (low_rem==0) return false;
        if (low_rem<0 || high_rem<=0)
            throw std::runtime_error("internal CF interval invariant failed");
        Z next_ln=hd,next_ld=high_rem,next_hn=ld,next_hd=low_rem;
        ln=std::move(next_ln);ld=std::move(next_ld);
        hn=std::move(next_hn);hd=std::move(next_hd);
    }
}

Result solve(const Config& cfg,const Z& a,const Z& q) {
    Z divisor;
    mpz_gcd(divisor.get_mpz_t(),a.get_mpz_t(),q.get_mpz_t());
    if (a<=0 || q<=0 || mpz_even_p(a.get_mpz_t()) || mpz_even_p(q.get_mpz_t()) || divisor!=1)
        throw std::runtime_error("a and q must be positive odd coprime integers");
    Polynomial f(a,q);
    Result result;
    if (cfg.congruences && (mpz_divisible_ui_p(q.get_mpz_t(),3)
        || (mpz_fdiv_ui(a.get_mpz_t(),3)+mpz_fdiv_ui(q.get_mpz_t(),3))%3!=0)) {
        result.excluded_by_congruence=true;
        return result;
    }
    // P is increasing in n. At fixed n, its derivative in x has one
    // positive zero, a maximum, so the minimum on an x interval is at an
    // endpoint. These exclusions avoid CF work on irrelevant fibres.
    if (f.homogeneous(cfg.nmax,cfg.xmin)<=0
        || (f.homogeneous(cfg.nmin,cfg.xmin)>f.target
            && f.homogeneous(cfg.nmin,cfg.xmax)>f.target)) {
        result.excluded_by_bounds=true;
        return result;
    }
    std::set<std::pair<std::string,std::string>> seen;
    small_exceptions(cfg,f,a,q,result.hits,seen);
    for (unsigned bits=cfg.precision;;) {
        if (cf_attempt(cfg,f,a,q,bits,result)) return result;
        if (bits>=cfg.max_precision)
            throw std::runtime_error("precision cap reached before fibre completeness; retry with larger --max-precision-bits");
        bits=std::min(cfg.max_precision,bits*2);
    }
}

unsigned positive_unsigned(const std::string& s) {
    Z z=integer(s);
    if (z<1 || z>1048576) throw std::runtime_error("precision must be between 1 and 1048576 bits");
    return static_cast<unsigned>(z.get_ui());
}

Config arguments(int argc,char** argv) {
    Config c;
    for (int i=1;i<argc;++i) {
        std::string name=argv[i];
        if (name=="--version") {std::cout<<"ce390-cf-worker "<<VERSION<<"\n";std::exit(0);}
        if (name=="--help") {
            std::cout<<"Usage: cf_worker [--n-min N --n-max N --x-min X --x-max X]\n"
                <<"  [--precision-bits 512 --max-precision-bits 16384]\n"
                <<"  [--integer-sqrt] [--relax-congruences]\n"
                <<"Read positive odd coprime a q pairs on stdin; emit one JSON record per fibre.\n"
                <<"d=-1-a/(2q). Bounds are positive and inclusive. Default target residues:\n"
                <<"n=1 mod 3, x=5 mod 12, x!=0 mod 7.\n";
            std::exit(0);
        }
        if (name=="--relax-congruences") {c.congruences=false;continue;}
        if (name=="--integer-sqrt") {c.integer_sqrt=true;continue;}
        if (i+1==argc) throw std::runtime_error("missing value for "+name);
        std::string val=argv[++i];
        if (name=="--n-min") c.nmin=integer(val);
        else if(name=="--n-max") c.nmax=integer(val);
        else if(name=="--x-min") c.xmin=integer(val);
        else if(name=="--x-max") c.xmax=integer(val);
        else if(name=="--precision-bits") c.precision=positive_unsigned(val);
        else if(name=="--max-precision-bits") c.max_precision=positive_unsigned(val);
        else throw std::runtime_error("unknown option: "+name);
    }
    if (c.nmin<1 || c.xmin<1 || c.nmax<c.nmin || c.xmax<c.xmin)
        throw std::runtime_error("bounds must be positive ordered inclusive intervals");
    if (c.precision>c.max_precision) throw std::runtime_error("initial precision exceeds maximum precision");
    return c;
}
} // namespace

int main(int argc,char** argv) {
    try {
        Config cfg=arguments(argc,argv);
        std::string line;
        while (std::getline(std::cin,line)) {
            if (line.empty()) continue;
            std::string sa,sq,extra;
            auto start=std::chrono::steady_clock::now();
            std::ostringstream output;
            try {
                std::istringstream in(line);
                if (!(in>>sa>>sq) || (in>>extra)) throw std::runtime_error("expected exactly two decimal integers: a q");
                Z a=integer(sa),q=integer(sq);
                Result r=solve(cfg,a,q);
                output<<"{\"a\":"<<quoted(a.get_str())<<",\"q\":"<<quoted(q.get_str())
                  <<",\"status\":\"complete\",\"congruences_enforced\":"<<(cfg.congruences?"true":"false")
                  <<",\"integer_sqrt_required\":"<<(cfg.integer_sqrt?"true":"false")
                  <<",\"excluded_by_congruence\":"<<(r.excluded_by_congruence?"true":"false")
                  <<",\"excluded_by_bounds\":"<<(r.excluded_by_bounds?"true":"false")
                  <<",\"precision_bits\":"<<r.precision<<",\"convergents\":"<<r.convergents<<",\"hits\":[";
                for(std::size_t i=0;i<r.hits.size();++i) {if(i)output<<',';output<<r.hits[i].json();}
                output<<']';
            } catch(const std::exception& e) {
                output<<"{\"a\":"<<quoted(sa)<<",\"q\":"<<quoted(sq)
                  <<",\"status\":\"error\",\"error\":"<<quoted(e.what());
            }
            double seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();
            output<<",\"elapsed_seconds\":"<<seconds<<"}";
            std::cout<<output.str()<<'\n'<<std::flush;
            if (!std::cout) return 3;
        }
        return std::cin.bad()?3:0;
    } catch(const std::exception& e) {
        std::cerr<<"ce390-cf-worker: "<<e.what()<<'\n';
        return 2;
    }
}
