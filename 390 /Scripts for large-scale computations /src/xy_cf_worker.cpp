// CE390 corrected rational target: k=6*n integral, x=X/b and y=Y/b reduced.
// The reduced n denominator is in {1,2,3,6}, independently of b.
// See XY_DENOMINATORS.md for the polynomial, sieve and CF completeness proof.
// All acceptance decisions use GMP integers/rationals, never floating point.
#include <gmpxx.h>
#include "q_sieve.hpp"
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
constexpr const char* VERSION = "1.1.0";

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
    Z xy_denominator = 1;
    std::string congruence_policy = "none";
    std::vector<unsigned long> n_denominators = {1,2,3,6};
    bool noninteger_d = false;
    bool integer_components = false;
    std::string signs = "all";
};

struct Polynomial {
    Z c3, c1, c0, target;
    Polynomial(const Z& a, const Z& q, const Z& b, int tau=1)
        : c3(b*b*b*q*q), c1(12*b*q*(2*q+tau*a)),
          c0(6*a*(2*q+tau*a)), target(390*b*b*b*q*q) {}
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
    (void)a; (void)q;
    Z num = f.c0*D, den = f.c1;
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

// Structural integrality only. The original equation and cube sum are checked
// separately before acceptance. BOTH choices of the +/- expression are required.
bool integral_components(const Q& n, const Q& x, const Q& y, Z& plus, Z& minus, Z& third) {
    Q A=-x+y, B=-x-y, C=2*x+6*n;
    A.canonicalize(); B.canonicalize(); C.canonicalize();
    if (A.get_den()!=1 || B.get_den()!=1 || C.get_den()!=1) return false;
    plus=A.get_num(); minus=B.get_num(); third=C.get_num();
    return true;
}

struct Hit {
    Q n, x, y, d, gap;
    std::string json(bool include_components=false) const {
        std::string result = "{\"n_num\":" + quoted(n.get_num().get_str())
          + ",\"n_den\":" + quoted(n.get_den().get_str())
          + ",\"x_num\":" + quoted(x.get_num().get_str())
          + ",\"x_den\":" + quoted(x.get_den().get_str())
          + ",\"y_num\":" + quoted(y.get_num().get_str())
          + ",\"y_den\":" + quoted(y.get_den().get_str())
          + ",\"d_num\":" + quoted(d.get_num().get_str())
          + ",\"d_den\":" + quoted(d.get_den().get_str())
          + ",\"gap_num\":" + quoted(gap.get_num().get_str())
          + ",\"gap_den\":" + quoted(gap.get_den().get_str())
          + ",\"sqrt_integer\":" + (y.get_den() == 1 ? "true" : "false");
        if (include_components) {
            Z plus,minus,third;
            if (!integral_components(n,x,y,plus,minus,third)
                    || plus*plus*plus+minus*minus*minus+third*third*third!=390)
                throw std::runtime_error("invalid integer cube certificate during serialization");
            result += ",\"cube_plus\":"+quoted(plus.get_str())
                    + ",\"cube_minus\":"+quoted(minus.get_str())
                    + ",\"cube_third\":"+quoted(third.get_str())
                    + ",\"cube_sum\":\"390\"";
        }
        return result+"}";
    }
};

bool accepts_signs(const Config& cfg, int sn, int sx) {
    return cfg.signs=="all" || cfg.signs==std::string(sn>0?"p":"n")+(sx>0?"p":"n");
}

bool coprime(const Z& a, const Z& b) {
    Z g; mpz_gcd(g.get_mpz_t(),a.get_mpz_t(),b.get_mpz_t());
    return g==1;
}

bool xy_prime_obstruction(const Z& q) {
    static const Z product=[] {
        Z z=1;
        for (auto p:ce390_q_sieve::forbidden_primes()) z*=p;
        return z;
    }();
    return !coprime(q,product);
}

bool coordinate_congruences(const Config& cfg, const Q& n, const Q& x) {
    if (cfg.congruence_policy=="none") return true;
    Z rn=n.get_num()-(cfg.congruence_policy=="numerators" ? Z(1) : n.get_den());
    Z rx=x.get_num()-5*(cfg.congruence_policy=="numerators" ? Z(1) : x.get_den());
    return mpz_divisible_ui_p(rn.get_mpz_t(),3)
        && mpz_divisible_ui_p(rx.get_mpz_t(),12)
        && !mpz_divisible_ui_p(x.get_num().get_mpz_t(),7);
}

void verify_and_add(const Config& cfg, const Z& a, const Z& q, int tau,
                    const Z& Ksigned, const Z& Xsigned, std::vector<Hit>& hits,
                    std::set<std::pair<std::string,std::string>>& seen) {
    const Z& b=cfg.xy_denominator;
    Z K=abs(Ksigned), X=abs(Xsigned);
    if (K < cfg.nmin || K > cfg.nmax || X < cfg.xmin || X > cfg.xmax) return;
    if (!coprime(X,b) || !mpz_divisible_p(X.get_mpz_t(),q.get_mpz_t())) return;
    Q n(Ksigned,6), x(Xsigned,b); n.canonicalize(); x.canonicalize();
    if (std::find(cfg.n_denominators.begin(),cfg.n_denominators.end(),n.get_den().get_ui())==cfg.n_denominators.end()) return;
    int sn=mpz_sgn(Ksigned.get_mpz_t()), sx=mpz_sgn(Xsigned.get_mpz_t());
    if (!sn || !sx || sn*sx!=tau || !accepts_signs(cfg,sn,sx)) return;
    if (!coordinate_congruences(cfg,n,x)) return;
    Q scaled_w((q+tau*a)*Xsigned,q); scaled_w-=b*Ksigned; scaled_w.canonicalize();
    Q y=sx*scaled_w/b; y.canonicalize();
    // The requested equality is den(x)==den(y), NOT den(n)==den(x).
    if (y<0 || y.get_den()!=b) return;
    Z cube_plus,cube_minus,cube_third;
    if (cfg.integer_components && !integral_components(n,x,y,cube_plus,cube_minus,cube_third)) return;
    Q S=x+6*n, A=36*n*n*n-65;
    Q d=-(y+S)/(2*x); d.canonicalize();
    if (cfg.noninteger_d && d.get_den()==1) return;
    Q gap=y-S; gap.canonicalize();
    if (y*y!=S*S+A/x || A!=-2*d*x*x*gap)
        throw std::runtime_error("internal original-equation verification failed");
    if (cfg.integer_components && (cube_plus*cube_plus*cube_plus+cube_minus*cube_minus*cube_minus
            +cube_third*cube_third*cube_third!=390 || n.get_den()!=1))
        throw std::runtime_error("internal integer cube sum / integral-n verification failed");
    auto key=std::make_pair(Ksigned.get_str(),Xsigned.get_str());
    if (seen.insert(key).second) hits.push_back({n,x,y,d,gap});
}

bool recover_scale(const Z& target,const Z& value,Z& g) {
    if (value<=0 || value>target
        || !mpz_divisible_p(target.get_mpz_t(),value.get_mpz_t())) return false;
    Z ratio=target/value;
    return mpz_root(g.get_mpz_t(),ratio.get_mpz_t(),3)!=0;
}

void evaluate(const Config& cfg, const Polynomial& f, const Z& a, const Z& q,
              int tau, const Z& u, const Z& v, std::vector<Hit>& hits,
              std::set<std::pair<std::string,std::string>>& seen) {
    if (u <= 0 || v <= 0 || u > cfg.nmax || v > cfg.xmax) return;
    Z value=f.homogeneous(u,v), magnitude=abs(value), g;
    if (!recover_scale(f.target,magnitude,g)) return;
    int sn=mpz_sgn(value.get_mpz_t()), sx=sn*tau;
    verify_and_add(cfg,a,q,tau,sn*g*u,sx*g*v,hits,seen);
}

// f'(t)>=c1>0 and |F(K,X)|=target imply a CF completeness threshold
// 2*target/c1. Scaled nonprimitive points are included (see proof).
Z fallback_limit(const Polynomial& f) { return 2*f.target/f.c1; }

void small_exceptions(const Config& cfg, const Polynomial& f,
                      const Z& a, const Z& q, int tau, std::vector<Hit>& hits,
                      std::set<std::pair<std::string,std::string>>& seen) {
    Z threshold=fallback_limit(f);
    Z last=std::min(cfg.xmax,threshold);
    Z first; mpz_cdiv_q(first.get_mpz_t(),cfg.xmin.get_mpz_t(),q.get_mpz_t()); first*=q;
    for (Z X=first; X<=last; X+=q) {
        if (!coprime(X,cfg.xy_denominator)) continue;
        for (int sn: {1,-1}) {
            int sx=sn*tau;
            if (!accepts_signs(cfg,sn,sx)) continue;
            Z lo=cfg.nmin, hi=cfg.nmax, target=sn*f.target;
            while (lo<=hi) {
                Z mid=(lo+hi)/2, value=f.homogeneous(mid,X);
                if (value == target) {
                    verify_and_add(cfg,a,q,tau,sn*mid,sx*X,hits,seen); break;
                }
                if (value<target) lo=mid+1; else hi=mid-1;
            }
        }
    }
}

struct Result {
    std::vector<Hit> hits;
    unsigned precision=0;
    unsigned long long convergents=0;
    bool excluded_by_congruence=false;
    bool excluded_by_q_sieve=false;
    bool excluded_by_bounds=false;
    bool excluded_by_denominator=false;
};

// A common interval partial quotient is certified exactly. Endpoints are
// open: for an integral upper endpoint H, floor(alpha)<=H-1.
bool cf_attempt(const Config& cfg, const Polynomial& f,
                const Z& a, const Z& q, int tau, unsigned bits,
                Result& out) {
    out.precision=std::max(out.precision,bits);
    std::set<std::pair<std::string,std::string>> seen;
    for (const auto& h:out.hits) {
        Q k=6*h.n, X=cfg.xy_denominator*h.x;
        seen.emplace(k.get_num().get_str(),X.get_num().get_str());
    }
    Isolation root=isolate(f,a,q,bits);
    Z pn2=0,pn1=1,vn2=1,vn1=0;
    if (root.exact) {
        // A rational endpoint is handled exactly as a finite continued
        // fraction. No irrationality assumption is needed by this branch.
        Z p=root.lo,r=root.scale;
        while (r!=0) {
            Z c=p/r, rem=p%r;
            Z u=c*pn1+pn2,v=c*vn1+vn2;
            if (v>cfg.xmax) return true;
            ++out.convergents;
            evaluate(cfg,f,a,q,tau,u,v,out.hits,seen);
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
        evaluate(cfg,f,a,q,tau,u,v,out.hits,seen);
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

// H is increasing in N. For fixed N, the only positive stationary point
// in X is a maximum; minima therefore occur at interval endpoints. A
// stationary maximum is evaluated as a rational without rounding.
bool outside_bounds(const Config& cfg,const Polynomial& f,int tau) {
    Z low=std::min(f.homogeneous(cfg.nmin,cfg.xmin),f.homogeneous(cfg.nmin,cfg.xmax));
    Z high=std::max(f.homogeneous(cfg.nmax,cfg.xmin),f.homogeneous(cfg.nmax,cfg.xmax));
    Z high_num=high, high_den=1;
    Z turn_num=2*f.c1*cfg.nmax, turn_den=3*f.c0;
    if (turn_num>cfg.xmin*turn_den && turn_num<cfg.xmax*turn_den) {
        high_den=27*f.c0*f.c0;
        high_num=cfg.nmax*cfg.nmax*cfg.nmax*(f.c3*high_den+4*f.c1*f.c1*f.c1);
    }
    for (int sn: {1,-1}) {
        if (!accepts_signs(cfg,sn,sn*tau)) continue;
        Z target=sn*f.target;
        if (low<=target && high_num>=target*high_den) return false;
    }
    return true;
}

Result solve(const Config& cfg,const Z& a,const Z& q) {
    if (a<=0 || 2*q<=a || !coprime(a,q))
        throw std::runtime_error("a and q must satisfy 0<a<2*q and gcd(a,q)=1");
    Result result;
    // Defend direct solve() calls as well as validated CLI tasks.
    if (cfg.integer_components && cfg.xy_denominator!=1 && cfg.xy_denominator!=2)
        throw std::runtime_error("integer components require x/y denominator 1 or 2");
    // q|X and gcd(X,b)=1 are necessary for the corrected equal-x/y target.
    if (!coprime(q,cfg.xy_denominator)) {
        result.excluded_by_denominator=true;
        return result;
    }
    // 6*X*(Y^2-(X+b*k)^2)=b^3*(k^3-390), k=6*n.
    // Thus X|k^3-390, and every p|q requires k^3==390 (mod p).
    // For p>3 this has the SAME obstructions as 36*t^3==65 (mod p).
    // Valid even for fractional y; it is the EQUAL-DENOMINATOR policy that
    // supplies the proof. Never export this guard to arbitrary rational y.
    if (xy_prime_obstruction(q)) {
        result.excluded_by_congruence=true;
        result.excluded_by_q_sieve=true;
        return result;
    }
    bool any_bounds_eligible=false;
    std::set<std::pair<std::string,std::string>> seen;
    for (int tau: {1,-1}) {
        if (!accepts_signs(cfg,1,tau) && !accepts_signs(cfg,-1,-tau)) continue;
        Polynomial f(a,q,cfg.xy_denominator,tau);
        if (q>cfg.xmax || outside_bounds(cfg,f,tau)) continue;
        any_bounds_eligible=true;
        small_exceptions(cfg,f,a,q,tau,result.hits,seen);
        Z fallback_last=fallback_limit(f);
        if (cfg.xmax<=fallback_last) continue; // The exact X scan already covered this entire interval.
        for (unsigned bits=cfg.precision;;) {
            if (cf_attempt(cfg,f,a,q,tau,bits,result)) break;
            if (bits>=cfg.max_precision)
                throw std::runtime_error("precision cap reached before fibre completeness; retry with larger --max-precision-bits");
            bits=std::min(cfg.max_precision,bits*2);
        }
    }
    result.excluded_by_bounds=!any_bounds_eligible;
    return result;
}

unsigned positive_unsigned(const std::string& s) {
    Z z=integer(s);
    if (z<1 || z>1048576) throw std::runtime_error("precision must be between 1 and 1048576 bits");
    return static_cast<unsigned>(z.get_ui());
}

Config arguments(int argc,char** argv) {
    Config c;
    bool have_denominator=false;
    for (int i=1;i<argc;++i) {
        std::string name=argv[i];
        if (name=="--version") {std::cout<<"ce390-xy-cf-worker "<<VERSION<<"\n";std::exit(0);}
        if (name=="--help") {
            std::cout<<"Usage: xy_cf_worker --xy-denominator B [--n-denominators 1,2,3,6]\n"
                <<"  [--congruence-policy none|numerators|rational-mod] [--noninteger-d]\n"
                <<"  [--require-integer-components] (both -x +/- y and 2*x+6*n integral)\n"
                <<"  [--n-min N --n-max N --x-min X --x-max X] [--signs all|pp|pn|np|nn]\n"
                <<"  [--precision-bits 512 --max-precision-bits 16384]\n"
                <<"Bounds apply to the rational VALUES. Read coprime 0<a<2*q.\n"
                <<"n has reduced denominator dividing 6; x,y have reduced denominator B.\n";
            std::exit(0);
        }
        if (name=="--noninteger-d") {c.noninteger_d=true;continue;}
        if (name=="--require-integer-components") {c.integer_components=true;continue;}
        if (i+1==argc) throw std::runtime_error("missing value for "+name);
        std::string val=argv[++i];
        if (name=="--xy-denominator") {
            if (have_denominator) throw std::runtime_error("duplicate x/y denominator");
            c.xy_denominator=integer(val); have_denominator=true;
        }
        else if (name=="--n-denominators") {
            c.n_denominators.clear();
            std::istringstream stream(val); std::string part;
            while (std::getline(stream,part,',')) {
                if (part!="1" && part!="2" && part!="3" && part!="6")
                    throw std::runtime_error("n denominators must be a sorted subset of 1,2,3,6");
                unsigned long d=std::stoul(part);
                if (!c.n_denominators.empty() && d<=c.n_denominators.back())
                    throw std::runtime_error("duplicate or unordered n denominators");
                c.n_denominators.push_back(d);
            }
            if (c.n_denominators.empty() || val.back()==',') throw std::runtime_error("empty n denominator");
        }
        else if (name=="--congruence-policy") c.congruence_policy=val;
        else if (name=="--n-min") c.nmin=integer(val);
        else if(name=="--n-max") c.nmax=integer(val);
        else if(name=="--x-min") c.xmin=integer(val);
        else if(name=="--x-max") c.xmax=integer(val);
        else if(name=="--precision-bits") c.precision=positive_unsigned(val);
        else if(name=="--max-precision-bits") c.max_precision=positive_unsigned(val);
        else if(name=="--signs") c.signs=val;
        else throw std::runtime_error("unknown option: "+name);
    }
    if (!have_denominator || c.xy_denominator<1) throw std::runtime_error("positive x/y denominator required");
    if (c.integer_components && c.xy_denominator!=1 && c.xy_denominator!=2)
        throw std::runtime_error("integer components require x/y denominator 1 or 2");
    if (c.congruence_policy!="none" && c.congruence_policy!="numerators" && c.congruence_policy!="rational-mod")
        throw std::runtime_error("congruence-policy must be none, numerators, or rational-mod");
    if (c.congruence_policy=="rational-mod") {
        if (!coprime(c.xy_denominator,Z(84))) throw std::runtime_error("x denominator must be coprime to 84");
        for (auto d:c.n_denominators) if (d%3==0) throw std::runtime_error("n denominators must be coprime to 3");
    }
    if (c.nmin<2 || c.nmax<c.nmin || c.xmax<c.xmin || c.xmin<=6*c.nmax)
        throw std::runtime_error("ordered magnitude bounds must satisfy n_min>=2 and x_min>6*n_max");
    if(c.signs!="all" && c.signs!="pp" && c.signs!="pn" && c.signs!="np" && c.signs!="nn")
        throw std::runtime_error("signs must be all, pp, pn, np, or nn");
    if (c.precision>c.max_precision) throw std::runtime_error("initial precision exceeds maximum precision");
    // k=6*n, but X=b*x. The two scaling factors are intentionally DIFFERENT.
    c.nmin*=6; c.nmax*=6;
    c.xmin*=c.xy_denominator; c.xmax*=c.xy_denominator;
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
                  <<",\"status\":\"complete\",\"parameterization\":\"n-sixths-equal-xy-denominators-v1\""
                  <<",\"signs\":"<<quoted(cfg.signs)
                  <<",\"xy_denominator\":"<<quoted(cfg.xy_denominator.get_str())
                  <<",\"congruence_policy\":"<<quoted(cfg.congruence_policy)
                  <<",\"noninteger_d_required\":"<<(cfg.noninteger_d?"true":"false")
                  <<",\"integer_components_required\":"<<(cfg.integer_components?"true":"false")
                  <<",\"n_denominators\":[";
                for (std::size_t i=0;i<cfg.n_denominators.size();++i) {if(i)output<<',';output<<cfg.n_denominators[i];}
                output<<']'
                  <<",\"excluded_by_denominator\":"<<(r.excluded_by_denominator?"true":"false")
                  <<",\"excluded_by_congruence\":"<<(r.excluded_by_congruence?"true":"false")
                  <<",\"excluded_by_q_sieve\":"<<(r.excluded_by_q_sieve?"true":"false")
                  <<",\"excluded_by_bounds\":"<<(r.excluded_by_bounds?"true":"false")
                  <<",\"precision_bits\":"<<r.precision<<",\"convergents\":"<<r.convergents<<",\"hits\":[";
                for(std::size_t i=0;i<r.hits.size();++i) {if(i)output<<',';output<<r.hits[i].json(cfg.integer_components);}
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
        std::cerr<<"ce390-xy-cf-worker: "<<e.what()<<'\n';
        return 2;
    }
}
