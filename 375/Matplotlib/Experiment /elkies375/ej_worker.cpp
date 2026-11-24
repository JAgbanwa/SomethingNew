// Exact Elkies--Elsenhans--Jahnel style search for a^3+b^3-c^3 = +/-K.
//
// Provenance: copied from this repository's
// 375/Scripts for large-scale computations/elkies-jahnel/src/elkies375_worker.cpp
// at commit 857adf3f89831816461641d6d4f7bbf89783304f.
// Also copied through 375/Algorithm II/ej_worker.cpp at commit
// 624acc970c5968a63baf684b02d062e98d701099 for the Matplotlib equation adapter.
// The lattice/enclosure/enumeration implementation is unchanged. See EJ_METHOD.md.
//
// This is a separate height/ratio-tile backend, not the fixed-g slope worker.
// Every exclusion, LLL operation, and translated-ball enumeration uses GMP
// integer/rational arithmetic. Tile size is a performance choice only.
// No candidate-count or precision cutoff is used.
//
// Build: c++ -O3 -std=c++17 elkies375_worker.cpp -lgmpxx -lgmp
#include <gmpxx.h>
#include <algorithm>
#include <array>
#include <csignal>
#include <iostream>
#include <set>
#include <stdexcept>
#include <string>
#include <vector>

namespace {
using Z = mpz_class;
using Q = mpq_class;
using ZRow = std::array<Z, 3>;
using QRow = std::array<Q, 3>;
using ZMat = std::array<ZRow, 3>;
using QMat = std::array<QRow, 3>;
constexpr const char* VERSION = "1.0.0-algorithm-ii";
volatile std::sig_atomic_t interrupted = 0;
void on_signal(int) { interrupted = 1; }

Z cube(const Z& a) { return a * a * a; }
Q cube(const Q& a) { return a * a * a; }
Q fifth(const Q& a) { return a * a * a * a * a; }
Z absz(const Z& a) { return a < 0 ? -a : a; }
int sign(const Z& a) { return mpz_sgn(a.get_mpz_t()); }
Z floor_q(const Q& a) {
    Z z;
    mpz_fdiv_q(z.get_mpz_t(), a.get_num_mpz_t(), a.get_den_mpz_t());
    return z;
}
Z floor_div(const Z& a, const Z& b) {
    if (b <= 0) throw std::runtime_error("internal: nonpositive divisor");
    Z z; mpz_fdiv_q(z.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t()); return z;
}
Z ceil_div(const Z& a, const Z& b) {
    if (b <= 0) throw std::runtime_error("internal: nonpositive divisor");
    Z z; mpz_cdiv_q(z.get_mpz_t(), a.get_mpz_t(), b.get_mpz_t()); return z;
}
Z floor_sqrt(const Z& a) {
    if (a < 0) throw std::runtime_error("internal: square root of negative integer");
    Z z; mpz_sqrt(z.get_mpz_t(), a.get_mpz_t()); return z;
}
Z floor_cbrt(const Z& a) {
    if (a < 0) throw std::runtime_error("internal: cube-root argument is negative");
    Z z; mpz_root(z.get_mpz_t(), a.get_mpz_t(), 3); return z;
}
Z ceil_cbrt(const Z& a) {
    Z z = floor_cbrt(a); if (cube(z) != a) ++z; return z;
}
Q ratio(const Z& a, const Z& b) {
    if (b == 0) throw std::runtime_error("internal: division by zero");
    Q q(a, b); q.canonicalize(); return q;
}
Q lower_cbrt(const Q& a, const Z& denominator) {
    if (a <= 0 || denominator <= 0)
        throw std::runtime_error("internal: invalid rational cube-root bound");
    const Z n = floor_q(a * Q(cube(denominator)));
    return ratio(floor_cbrt(n), denominator);
}

ZMat identity() {
    ZMat a{}; for (int i = 0; i < 3; ++i) a[i][i] = 1; return a;
}
ZMat multiply(const ZMat& a, const ZMat& b) {
    ZMat c{};
    for (int i = 0; i < 3; ++i) for (int j = 0; j < 3; ++j)
        for (int k = 0; k < 3; ++k) c[i][j] += a[i][k] * b[k][j];
    return c;
}
QMat multiply(const ZMat& a, const QMat& b) {
    QMat c{};
    for (int i = 0; i < 3; ++i) for (int j = 0; j < 3; ++j)
        for (int k = 0; k < 3; ++k) c[i][j] += Q(a[i][k]) * b[k][j];
    return c;
}
ZRow multiply(const ZRow& a, const ZMat& b) {
    ZRow c{};
    for (int j = 0; j < 3; ++j) for (int k = 0; k < 3; ++k)
        c[j] += a[k] * b[k][j];
    return c;
}
Z determinant(const ZMat& a) {
    return a[0][0]*(a[1][1]*a[2][2]-a[1][2]*a[2][1])
         - a[0][1]*(a[1][0]*a[2][2]-a[1][2]*a[2][0])
         + a[0][2]*(a[1][0]*a[2][1]-a[1][1]*a[2][0]);
}
Q dot(const QRow& a, const QRow& b) {
    Q v = 0; for (int i = 0; i < 3; ++i) v += a[i]*b[i]; return v;
}

struct GSO {
    QMat star{}, mu{};
    QRow norm{};
};
GSO gram_schmidt(const QMat& b) {
    GSO g;
    for (int i = 0; i < 3; ++i) {
        g.star[i] = b[i];
        for (int j = 0; j < i; ++j) {
            g.mu[i][j] = dot(b[i], g.star[j]) / g.norm[j];
            for (int k = 0; k < 3; ++k)
                g.star[i][k] -= g.mu[i][j] * g.star[j][k];
        }
        g.norm[i] = dot(g.star[i], g.star[i]);
        if (g.norm[i] <= 0) throw std::runtime_error("internal: singular lattice basis");
    }
    return g;
}

// Rank-three LLL with delta=3/4. Rational Gram--Schmidt and exact integral
// row operations preserve the lattice and the unimodular warm transform.
GSO lll(QMat& b, ZMat& u) {
    GSO g = gram_schmidt(b);
    int k = 1;
    while (k < 3) {
        for (int j = k-1; j >= 0; --j) {
            const Z q = floor_q(g.mu[k][j] + Q(1,2));
            if (q != 0) {
                for (int i = 0; i < 3; ++i) {
                    b[k][i] -= Q(q) * b[j][i];
                    u[k][i] -= q * u[j][i];
                }
                g = gram_schmidt(b);
            }
        }
        if (g.norm[k] >= (Q(3,4)-g.mu[k][k-1]*g.mu[k][k-1])*g.norm[k-1]) {
            ++k;
        } else {
            std::swap(b[k], b[k-1]);
            std::swap(u[k], u[k-1]);
            g = gram_schmidt(b);
            k = std::max(1, k-1);
        }
    }
    if (absz(determinant(u)) != 1)
        throw std::runtime_error("internal: LLL transform is not unimodular");
    return g;
}

struct Interval { Z lo, hi; };
Interval integer_interval(const Q& center, const Q& radius2) {
    if (radius2 < 0) return {Z(1), Z(0)};
    const Z a = center.get_num(), b = center.get_den();
    // (b*n-a)^2 is integral, so this inclusive interval is exact even
    // when the radius is irrational or a candidate is on the boundary.
    const Z root = floor_sqrt(floor_q(Q(b*b)*radius2));
    return {ceil_div(a-root,b), floor_div(a+root,b)};
}

Z shell_low_index(const Z& h, const Z& k) {
    const Z amin = ceil_cbrt(3*h*h-3*h+1-k);
    return floor_div(5*amin, Z(2));
}
Z tile_left(const Z& h, const Z& right_index, const Z& low_index, const Q& scale) {
    const Q right = ratio(right_index, 5*h);
    const Z denominator = 64*h*h;
    const Q qr = lower_cbrt(1-cube(right), denominator);
    const Q curvature = 2*right/fifth(qr);
    Z step = floor_cbrt(floor_q(125*cube(scale)/curvature));
    if (step < 1) step = 1;
    Z left = right_index-step;
    if (left < low_index) left = low_index;
    return left;
}

QMat tile_basis(const Z& height, const Z& left_index, const Z& right_index, const Z& k) {
    const Q left = ratio(left_index,5*height), right = ratio(right_index,5*height);
    const Q r = (left+right)/2, h = (right-left)/2;
    const Z denominator = 64*height*height;
    const Q q0 = lower_cbrt(1-cube(r), denominator);
    const Q qr = lower_cbrt(1-cube(right), denominator);
    const Q g = lower_cbrt(1-cube(right)-ratio(k,cube(height)), denominator);
    if (q0 <= 0 || qr <= 0 || g <= 0)
        throw std::runtime_error("internal: nonpositive curve bound");
    const Q slope = -r*r/(q0*q0);
    const Q curvature = 2*right/fifth(qr);
    const Q slope_error = 2*r*r/(Q(denominator)*cube(q0));
    const Q perturb = Q(k)/(3*Q(cube(height))*g*g);
    const Q shift = ratio(Z(1),2*denominator)-curvature*h*h/4;
    const Q envelope = ratio(Z(1),2*denominator)+curvature*h*h/4+slope_error*h+perturb;
    const Q intercept = q0-slope*r+shift;
    const Q w = 2*Q(height)*h, v = 2*Q(height)*envelope;
    QMat b{};
    b[0] = {1/w, -slope/v, Q(0)};
    b[1] = {Q(0), 1/v, Q(0)};
    b[2] = {-r/w, -intercept/v, ratio(Z(2),height)};
    return b;
}

// Exact polynomial root shortcut. Coefficients are in increasing degree.
// Integer points near derivative roots are checked individually. Between
// these points the real polynomial is monotone, so integer binary search
// finds its only possible integer root. No factoring or floating point.
using Poly = std::array<Z,4>;
Z evaluate(const Poly& p, const Z& x) {
    return ((p[3]*x+p[2])*x+p[1])*x+p[0];
}
void add_near_critical(std::set<Z>& special, const Z& numerator_lo,
                       const Z& numerator_hi, const Z& denominator, const Z& last) {
    Z lo = floor_div(numerator_lo, denominator)-1;
    Z hi = floor_div(numerator_hi, denominator)+2;
    if (lo < 0) lo = 0;
    if (hi > last) hi = last;
    for (Z z = lo; z <= hi; ++z) special.insert(z);
}
void monotone_root(const Poly& p, Z lo, Z hi, std::set<Z>& roots) {
    if (lo > hi) return;
    Z vlo = evaluate(p,lo), vhi = evaluate(p,hi);
    if (vlo == 0) { roots.insert(lo); return; }
    if (vhi == 0) { roots.insert(hi); return; }
    if (sign(vlo) == sign(vhi)) return;
    const bool increasing = vlo < vhi;
    while (lo+1 < hi) {
        const Z mid = floor_div(lo+hi, Z(2));
        const Z v = evaluate(p,mid);
        if (v == 0) { roots.insert(mid); return; }
        if ((v < 0) == increasing) lo = mid; else hi = mid;
    }
}
// false means every offset qualifies; the caller must stream the full interval.
bool integer_polynomial_roots(const Poly& p, const Z& last, std::set<Z>& roots) {
    int degree = 3;
    while (degree > 0 && p[degree] == 0) --degree;
    if (degree == 0) return p[0] != 0;
    if (degree == 1) {
        if (mpz_divisible_p(p[0].get_mpz_t(),p[1].get_mpz_t())) {
            const Z r = -p[0]/p[1];
            if (0 <= r && r <= last) roots.insert(r);
        }
        return true;
    }
    std::set<Z> special;
    if (degree == 2) {
        Z num = -p[1], den = 2*p[2];
        if (den < 0) { num = -num; den = -den; }
        add_near_critical(special,num,num,den,last);
    } else {
        Z a = 3*p[3], b = 2*p[2], c = p[1];
        if (a < 0) { a = -a; b = -b; c = -c; }
        const Z disc = b*b-4*a*c;
        if (disc >= 0) {
            const Z sr = floor_sqrt(disc), den = 2*a;
            const Z upper = sr*sr == disc ? sr : Z(sr+1);
            add_near_critical(special,-b-upper,-b-sr,den,last);
            add_near_critical(special,-b+sr,-b+upper,den,last);
        }
    }
    Z cursor = 0;
    for (const Z& n : special) {
        monotone_root(p,cursor,n-1,roots);
        if (evaluate(p,n) == 0) roots.insert(n);
        cursor = n+1;
    }
    monotone_root(p,cursor,last,roots);
    return true;
}

Poly cubic_on_line(const ZRow& a, const ZRow& d) {
    Poly p{};
    for (int i = 0; i < 3; ++i) {
        const int s = i == 2 ? -1 : 1;
        p[0] += s*cube(a[i]);
        p[1] += s*3*a[i]*a[i]*d[i];
        p[2] += s*3*a[i]*d[i]*d[i];
        p[3] += s*cube(d[i]);
    }
    return p;
}
bool cubic_interval_offsets(const ZRow& a, const ZRow& d, const Z& last,
                            const Z& k, std::set<Z>& offsets) {
    const Poly f = cubic_on_line(a,d);
    for (int s : {-1,1}) {
        Poly p = f; p[0] -= s*k;
        if (!integer_polynomial_roots(p,last,offsets)) return false;
    }
    return true;
}

struct Config {
    Z height, index_start, index_stop, k = 375;
    Z max_tiles = 0, progress_every = 100;
    Q tile_scale = Q(11,2);
    bool primitive = true;
};

void emit_hit(const ZRow& a, const Z& value, const Config& cfg,
              const Z& left, const Z& right) {
    if (absz(value) != cfg.k || a[2] < cfg.height || a[2] >= 2*cfg.height
        || a[0] < 0 || a[0] > a[1] || a[1] >= a[2]) return;
    const Z scaled = 5*cfg.height*a[0];
    if (scaled < left*a[2]) return;
    if (!(scaled < right*a[2] || (right == 4*cfg.height && scaled == right*a[2]))) return;
    Z gcd;
    mpz_gcd(gcd.get_mpz_t(),a[0].get_mpz_t(),a[1].get_mpz_t());
    mpz_gcd(gcd.get_mpz_t(),gcd.get_mpz_t(),a[2].get_mpz_t());
    const bool primitive = gcd == 1;
    if (cfg.primitive && !primitive) return;
    if (cube(a[0])+cube(a[1])-cube(a[2]) != value)
        throw std::runtime_error("internal: cubic finite differences disagree");
    const Z x = value == cfg.k ? a[0] : Z(-a[0]);
    const Z y = value == cfg.k ? a[1] : Z(-a[1]);
    const Z z = value == cfg.k ? Z(-a[2]) : a[2];
    if (cube(x)+cube(y)+cube(z) != cfg.k)
        throw std::runtime_error("internal: signed hit is not a solution");
    std::cout << "{\"type\":\"hit\",\"k\":" << cfg.k
              << ",\"x\":\"" << x << "\",\"y\":\"" << y << "\",\"z\":\"" << z
              << "\",\"primitive\":" << (primitive ? "true" : "false")
              << ",\"height\":\"" << a[2] << "\"}\n" << std::flush;
}

void search_tile(const Config& cfg, const Z& left, const Z& right,
                 ZMat& warm, Z& visited) {
    const QMat geometric = tile_basis(cfg.height,left,right,cfg.k);
    ZMat sublattice = identity();
    const Z k9 = cfg.k % 9;
    if (k9 == 3 || k9 == 6) {
        sublattice = {{{Z(3),Z(0),Z(0)}, {Z(0),Z(3),Z(0)}, {Z(-1),Z(-1),Z(1)}}};
    }
    const QMat base = multiply(sublattice,geometric);
    QMat basis = multiply(warm,base);
    const GSO g = lll(basis,warm);
    const ZMat coordinates = multiply(warm,sublattice);
    // Projection of target (0,0,3) on the orthogonal Gram--Schmidt basis.
    QRow target{};
    for (int i = 0; i < 3; ++i) target[i] = 3*g.star[i][2]/g.norm[i];
    const Interval n3range = integer_interval(target[2],3/g.norm[2]);
    const ZRow step = coordinates[0];
    const Z cubic_step = cube(step[0])+cube(step[1])-cube(step[2]);
    const Z third_difference = 6*cubic_step;
    for (Z n3 = n3range.lo; n3 <= n3range.hi; ++n3) {
        const Q e3 = Q(n3)-target[2];
        const Q remaining2 = 3-g.norm[2]*e3*e3;
        const Q center2 = target[1]-g.mu[2][1]*Q(n3);
        const Interval n2range = integer_interval(center2,remaining2/g.norm[1]);
        for (Z n2 = n2range.lo; n2 <= n2range.hi; ++n2) {
            const Q e2 = Q(n2)-center2;
            const Q remaining1 = remaining2-g.norm[1]*e2*e2;
            const Q center1 = target[0]-g.mu[1][0]*Q(n2)-g.mu[2][0]*Q(n3);
            const Interval n1range = integer_interval(center1,remaining1/g.norm[0]);
            if (n1range.lo > n1range.hi) continue;
            ZRow a = multiply(ZRow{n1range.lo,n2,n3},coordinates);
            const Z count = n1range.hi-n1range.lo+1;
            visited += count;  // all ball points covered, including those handled by the root shortcut
            if (count > 256) {
                std::set<Z> offsets;
                if (cubic_interval_offsets(a,step,count-1,cfg.k,offsets)) {
                    for (const Z& offset : offsets) {
                        ZRow at{};
                        for (int i = 0; i < 3; ++i) at[i] = a[i]+step[i]*offset;
                        const Z value = cube(at[0])+cube(at[1])-cube(at[2]);
                        emit_hit(at,value,cfg,left,right);
                    }
                    continue;
                }
            }
            const Poly polynomial = cubic_on_line(a,step);
            Z value = polynomial[0];
            Z first_difference = polynomial[1]+polynomial[2]+polynomial[3];
            Z second_difference = 2*polynomial[2]+6*polynomial[3];
            for (Z n1 = n1range.lo; n1 <= n1range.hi; ++n1) {
                if (absz(value) == cfg.k) emit_hit(a,value,cfg,left,right);
                for (int i = 0; i < 3; ++i) a[i] += step[i];
                value += first_difference;
                first_difference += second_difference;
                second_difference += third_difference;
            }
        }
    }
}

Z parse_integer(const std::string& text, const char* name) {
    if (text.empty()) throw std::runtime_error(std::string("empty ")+name);
    for (char c : text) if (c < '0' || c > '9')
        throw std::runtime_error(std::string(name)+" must be a nonnegative decimal integer");
    Z z;
    if (z.set_str(text,10) != 0) throw std::runtime_error(std::string("invalid ")+name);
    return z;
}
Q parse_scale(const std::string& text) {
    const std::size_t slash = text.find('/');
    const Z numerator = parse_integer(text.substr(0,slash),"tile-scale numerator");
    const Z denominator = slash == std::string::npos ? Z(1)
        : parse_integer(text.substr(slash+1),"tile-scale denominator");
    if (numerator <= 0 || denominator <= 0) throw std::runtime_error("tile-scale must be positive");
    return ratio(numerator,denominator);
}
void usage() {
    std::cout <<
      "Usage: elkies375_worker --height H --index-start L --index-stop R [options]\n"
      "  Exact rational Elkies--Elsenhans--Jahnel ratio tiles in H <= height < 2H.\n"
      "  Grid denominator is 5H; the interval is L <= (5H)*a/c < R, with\n"
      "  the global endpoint R=4H included. Tiles are searched downward from R.\n"
      "  --target K                positive noncube target (default 375)\n"
      "  --max-tiles N             finish at most N complete tiles (0 = entire task)\n"
      "  --include-nonprimitive    include hits with coordinate gcd greater than one\n"
      "  --tile-scale P/Q          positive rational width scale (default 11/2)\n"
      "  --progress-every N        progress record every N tiles (default 100; 0 disables)\n"
      "  --version, --help\n"
      "  Required: H>=25, 125K<=3H^3, 3H^2-3H+1>K,\n"
      "  floor(5*ceil_cuberoot(3H^2-3H+1-K)/2)<=L<=R<=4H.\n"
      "  SIGINT/SIGTERM finish the current tile, then emit a resumable end record.\n";
}

void emit_progress(const Z& next, const Z& tiles, const Z& visited) {
    std::cout << "{\"type\":\"progress\",\"next_index\":\"" << next
              << "\",\"tiles\":" << tiles << ",\"lattice_points\":\"" << visited << "\"}\n" << std::flush;
}
int run(const Config& cfg) {
    if (cfg.height < 25 || cfg.k <= 0 || cube(floor_cbrt(cfg.k)) == cfg.k)
        throw std::runtime_error("need H>=25 and a positive noncube target");
    if (125*cfg.k > 3*cube(cfg.height) || 3*cfg.height*cfg.height-3*cfg.height+1 <= cfg.k)
        throw std::runtime_error("height does not satisfy the certified shell inequalities");
    const Z low = shell_low_index(cfg.height,cfg.k);
    if (cfg.index_start < low || cfg.index_start > cfg.index_stop || cfg.index_stop > 4*cfg.height)
        throw std::runtime_error("index interval outside proved shell domain; minimum index is "+low.get_str());
    std::signal(SIGINT,on_signal);
    std::signal(SIGTERM,on_signal);
    std::cout << "{\"type\":\"start\",\"engine\":\"elkies-jahnel\",\"version\":\"" << VERSION
              << "\",\"k\":" << cfg.k << ",\"height\":\"" << cfg.height
              << "\",\"index_start\":\"" << cfg.index_start << "\",\"index_stop\":\"" << cfg.index_stop
              << "\",\"primitive\":" << (cfg.primitive ? "true" : "false") << "}\n" << std::flush;
    Z next = cfg.index_stop, tiles = 0, visited = 0;
    ZMat warm = identity();
    const char* reason = "complete";
    while (next > cfg.index_start) {
        if (interrupted) { reason = "signal"; break; }
        if (cfg.max_tiles != 0 && tiles >= cfg.max_tiles) { reason = "tile_budget"; break; }
        const Z left = tile_left(cfg.height,next,cfg.index_start,cfg.tile_scale);
        search_tile(cfg,left,next,warm,visited);
        next = left;
        ++tiles;
        if (cfg.progress_every != 0
            && mpz_divisible_p(tiles.get_mpz_t(),cfg.progress_every.get_mpz_t()))
            emit_progress(next,tiles,visited);
    }
    const bool complete = next == cfg.index_start;
    if (complete) reason = "complete";
    std::cout << "{\"type\":\"end\",\"complete\":" << (complete ? "true" : "false")
              << ",\"next_index\":\"" << next << "\",\"tiles\":" << tiles
              << ",\"lattice_points\":\"" << visited << "\",\"reason\":\"" << reason << "\"}\n" << std::flush;
    return std::cout ? 0 : 3;
}
} // namespace

int main(int argc, char** argv) {
    try {
        Config cfg;
        bool have_height = false, have_start = false, have_stop = false;
        for (int i = 1; i < argc; ++i) {
            const std::string a = argv[i];
            if (a == "--help") { usage(); return 0; }
            if (a == "--version") { std::cout << "elkies375-worker " << VERSION << '\n'; return 0; }
            if (a == "--include-nonprimitive") { cfg.primitive = false; continue; }
            if (i+1 == argc) throw std::runtime_error("missing value for "+a);
            const std::string value = argv[++i];
            if (a == "--height") { cfg.height = parse_integer(value,"height"); have_height = true; }
            else if (a == "--index-start") { cfg.index_start = parse_integer(value,"index-start"); have_start = true; }
            else if (a == "--index-stop") { cfg.index_stop = parse_integer(value,"index-stop"); have_stop = true; }
            else if (a == "--target") cfg.k = parse_integer(value,"target");
            else if (a == "--max-tiles") cfg.max_tiles = parse_integer(value,"max-tiles");
            else if (a == "--progress-every") cfg.progress_every = parse_integer(value,"progress-every");
            else if (a == "--tile-scale") cfg.tile_scale = parse_scale(value);
            else throw std::runtime_error("unknown option: "+a);
        }
        if (!have_height || !have_start || !have_stop)
            throw std::runtime_error("--height, --index-start, and --index-stop are required");
        return run(cfg);
    } catch (const std::exception& e) {
        std::cerr << "elkies375-worker: " << e.what() << '\n';
        return 2;
    }
}

