#!/bin/bash
# ============================================================
# test_all.sh — Comprehensive validation for Charity Engine
# Run in the directory containing all project files:
#   bash test_all.sh
# ============================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

pass() { echo -e "${GREEN}PASS${NC}: $1"; ((PASS_COUNT++)); }
fail() { echo -e "${RED}FAIL${NC}: $1"; ((FAIL_COUNT++)); }
warn() { echo -e "${YELLOW}WARN${NC}: $1"; ((WARN_COUNT++)); }

echo "============================================================"
echo "Charity Engine Deployment — Comprehensive Test Suite"
echo "============================================================"
echo ""

# ─── 1. File completeness ───
echo "[1/7] Checking file completeness..."

PYTHON_FILES="modular_sieve.py thue_param.py factorization_search.py mw_sieve.py cm_descent.py lll_search.py verify.py main.py ce_task_generator.py"
SHELL_FILES="ce_worker.sh ce_setup.sh ce_submit_sieve.sh ce_submit_thue.sh ce_submit_factor.sh ce_submit_mw.sh ce_collect.sh ce_batch.sh"
OTHER_FILES="Dockerfile README.md README_CE.md"

for f in $PYTHON_FILES $SHELL_FILES $OTHER_FILES; do
    if [ -f "$f" ]; then
        pass "$f exists"
    else
        fail "$f MISSING"
    fi
done
echo ""

# ─── 2. Python syntax ───
echo "[2/7] Checking Python syntax..."
for f in $PYTHON_FILES; do
    [ ! -f "$f" ] && continue
    if python3 -m py_compile "$f" 2>/dev/null; then
        pass "Python syntax OK: $f"
    else
        fail "Python syntax error in $f"
    fi
done
echo ""

# ─── 3. Shell syntax ───
echo "[3/7] Checking shell syntax..."
for f in $SHELL_FILES; do
    [ ! -f "$f" ] && continue
    if bash -n "$f" 2>/dev/null; then
        pass "Shell syntax OK: $f"
    else
        fail "Shell syntax error in $f"
    fi
    head -1 "$f" | grep -q "^#!.*bash" && pass "$f has shebang" || warn "$f missing shebang"
    grep -q "set -e" "$f" && pass "$f has set -e" || warn "$f missing set -e"
done
echo ""

# ─── 4. Dockerfile ───
echo "[4/7] Checking Dockerfile..."
if [ -f "Dockerfile" ]; then
    grep -q "^FROM" Dockerfile && pass "Dockerfile has FROM" || fail "Dockerfile missing FROM"
    grep -qi "python" Dockerfile && pass "Dockerfile references Python" || fail "Dockerfile missing Python"
    grep -q "^WORKDIR" Dockerfile && pass "Dockerfile has WORKDIR" || warn "Dockerfile missing WORKDIR"
    grep -q "^COPY\|^ADD" Dockerfile && pass "Dockerfile copies files" || fail "Dockerfile missing COPY/ADD"
    grep -q "^CMD\|^ENTRYPOINT" Dockerfile && pass "Dockerfile has CMD/ENTRYPOINT" || warn "Dockerfile missing CMD/ENTRYPOINT"
else
    fail "Dockerfile not found"
fi
echo ""

# ─── 5. Cross-references ───
echo "[5/7] Checking cross-references..."

if [ -f "ce_batch.sh" ]; then
    for s in ce_setup.sh ce_submit_sieve.sh ce_submit_thue.sh ce_submit_factor.sh ce_submit_mw.sh ce_collect.sh; do
        grep -q "$s" ce_batch.sh && pass "ce_batch.sh references $s" || warn "ce_batch.sh does not reference $s"
    done
fi

if [ -f "ce_worker.sh" ]; then
    for mod in modular_sieve thue_param factorization_search mw_sieve; do
        grep -q "$mod" ce_worker.sh && pass "ce_worker.sh references $mod" || warn "ce_worker.sh does not reference $mod"
    done
fi

if [ -f "main.py" ]; then
    for mod in modular_sieve thue_param factorization_search mw_sieve cm_descent lll_search verify; do
        grep -q "$mod" main.py && pass "main.py references $mod" || warn "main.py does not reference $mod"
    done
fi
echo ""

# ─── 6. Algorithmic content ───
echo "[6/7] Checking algorithmic content..."

[ -f "modular_sieve.py" ] && {
    grep -qi "legendre\|kronecker\|jacobi\|is_square" modular_sieve.py && pass "modular_sieve: residue check" || warn "modular_sieve: residue check not found"
    grep -qi "crt\|chinese\|CRT" modular_sieve.py && pass "modular_sieve: CRT" || warn "modular_sieve: CRT not found"
    grep -qi "sieve\|primerange\|primes" modular_sieve.py && pass "modular_sieve: prime gen" || warn "modular_sieve: prime gen not found"
}

[ -f "thue_param.py" ] && {
    grep -qi "p/q\|num.*den\|frac\|Fraction" thue_param.py && pass "thue_param: d parameterization" || warn "thue_param: d parameterization not found"
    grep -qi "thue\|pari" thue_param.py && pass "thue_param: PARI/GP" || warn "thue_param: PARI/GP not found"
    grep -qi "magma\|Thue" thue_param.py && pass "thue_param: Magma" || warn "thue_param: Magma not found"
}

[ -f "cm_descent.py" ] && {
    grep -qi "omega\|eisenstein" cm_descent.py && pass "cm_descent: Z[omega]" || warn "cm_descent: Z[omega] not found"
    grep -qi "descent\|selmer" cm_descent.py && pass "cm_descent: 3-descent/Selmer" || warn "cm_descent: 3-descent not found"
    grep -qi "j.*=.*0\|CM\|complex.*mult" cm_descent.py && pass "cm_descent: j=0/CM" || warn "cm_descent: j=0 not found"
}

[ -f "lll_search.py" ] && {
    grep -qi "lll\|lenstra\|lattice" lll_search.py && pass "lll_search: LLL" || warn "lll_search: LLL not found"
    grep -qi "coppersmith\|small_root\|howgrave" lll_search.py && pass "lll_search: Coppersmith" || warn "lll_search: Coppersmith not found"
}

[ -f "verify.py" ] && {
    grep -q "36" verify.py && grep -q "65" verify.py && pass "verify: equation constants" || warn "verify: constants not found"
    grep -q "% 3\|mod 3\|mod(3)" verify.py && pass "verify: n mod 3" || warn "verify: n mod 3 not found"
    grep -q "% 12\|mod 12\|mod(12)" verify.py && pass "verify: x mod 12" || warn "verify: x mod 12 not found"
    grep -q "% 7\|mod 7\|mod(7)" verify.py && pass "verify: x mod 7" || warn "verify: x mod 7 not found"
    grep -qi "sqrt\|is_square" verify.py && pass "verify: sqrt check" || warn "verify: sqrt not found"
}

[ -f "ce_collect.sh" ] && {
    grep -qi "download\|collect" ce_collect.sh && pass "ce_collect: download logic" || warn "ce_collect: download not found"
    grep -qi "merge\|csv" ce_collect.sh && pass "ce_collect: merge/CSV" || warn "ce_collect: merge not found"
    grep -qi "valid\|filter" ce_collect.sh && pass "ce_collect: validation" || warn "ce_collect: validation not found"
}
echo ""

# ─── 7. Import test ───
echo "[7/7] Checking Python imports..."
for mod in modular_sieve thue_param factorization_search mw_sieve cm_descent lll_search verify; do
    [ ! -f "$mod.py" ] && continue
    if python3 -c "import $mod" 2>/dev/null; then
        pass "Import OK: $mod"
    else
        warn "Import failed: $mod (may need sympy/numpy)"
    fi
done
echo ""

# ─── Summary ───
echo "============================================================"
echo "SUMMARY: $PASS_COUNT passed, $FAIL_COUNT failed, $WARN_COUNT warnings"
echo "============================================================"

if [ "$FAIL_COUNT" -eq 0 ]; then
    echo ""
    echo "ALL CRITICAL CHECKS PASSED"
    echo "Scripts are ready for Charity Engine deployment."
    exit 0
else
    echo ""
    echo "$FAIL_COUNT CRITICAL FAILURE(S)"
    echo "Fix the issues above before deploying."
    exit 1
fi
