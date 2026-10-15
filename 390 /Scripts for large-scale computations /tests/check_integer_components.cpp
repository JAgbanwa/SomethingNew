// Exercise the exact C++ structural helper in the actual worker translation unit.
// These inputs test integrality, NOT whether the original 390 equation holds.
#define main ce390_xy_worker_main
#include "../src/xy_cf_worker.cpp"
#undef main
int main(int argc, char** argv) {
    if (argc==2 && std::string(argv[1])=="--invalid-sum") {
        Hit h{Q(2),Q(1,2),Q(3,2),Q(1),Q(1)};
        try { std::cout<<h.json(true)<<'\n'; return 1; }
        catch (const std::exception&) { return 0; }
    }
    std::string ntext,xtext,ytext;
    while (std::cin>>ntext>>xtext>>ytext) {
        Q n(ntext),x(xtext),y(ytext); n.canonicalize();x.canonicalize();y.canonicalize();
        Z A,B,C;
        if (integral_components(n,x,y,A,B,C)) std::cout<<"yes "<<A<<' '<<B<<' '<<C<<'\n';
        else std::cout<<"no\n";
    }
    return std::cin.bad()?2:0;
}
