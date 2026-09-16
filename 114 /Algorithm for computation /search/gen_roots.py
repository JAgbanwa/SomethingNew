"""Precompute, for every prime p <= PMAX, the roots of 36 X^3 = 19 (mod p).
Output: binary file 'roots.bin' with records  <uint32 p><uint32 nr><uint32 r0,r1,r2>.
"""
import sys, struct, time
from sympy import sieve
from sympy.ntheory.residue_ntheory import nthroot_mod

PMAX = int(sys.argv[1]) if len(sys.argv) > 1 else 2000000
out = open('roots.bin', 'wb')
t0 = time.time(); cnt = 0
sieve.extend(PMAX)
for p in sieve.primerange(5, PMAX+1):
    if p == 19:
        rs = [0]
    else:
        c = (19 * pow(36, -1, p)) % p
        try:
            rr = nthroot_mod(c, 3, p, all_roots=True)
        except Exception:
            rr = []
        rs = sorted(set(rr if isinstance(rr, list) else ([rr] if rr is not None else [])))
    rs = [r for r in rs if (36*r**3 - 19) % p == 0]
    if not rs:
        continue
    out.write(struct.pack('<II', p, len(rs)))
    for i in range(3):
        out.write(struct.pack('<I', rs[i] if i < len(rs) else 0))
    cnt += 1
out.close()
print("primes with roots:", cnt, "%.1fs" % (time.time()-t0))
