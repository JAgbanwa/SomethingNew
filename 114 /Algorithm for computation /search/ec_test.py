import cypari, time
pari = cypari.pari
pari.allocatemem(1<<30, silent=True) if hasattr(pari,'allocatemem') else None

def curve(x):
    k = -432*x**3*(x**3+57)
    return pari.ellinit([0,0,0,0,k]), k

for x in [-9, 784, 1, 2, 3, 100, 1000]:
    t0=time.time()
    E,k = curve(x)
    r = E.ellrank()
    print(x, k, r, "%.2fs"%(time.time()-t0))
