#!/bin/bash
# PolyArb-X Go/No-Go Checklist Script
# Run this before starting live trading to ensure all prerequisites are met

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAIL_COUNT=0
WARN_COUNT=0

check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

echo ""
echo "========================================================================"
echo "  PolyArb-X Go/No-Go Checklist"
echo "========================================================================"
echo ""

# 1. .env file check
echo "1. Environment Configuration"
echo "   -------------------------"

if [ -f .env ]; then
    check_pass ".env file exists"

    # Check .env permissions
    ENV_PERMS=$(stat -f "%Lp" .env 2>/dev/null || stat -c "%a" .env 2>/dev/null)
    if [ "$ENV_PERMS" == "600" ]; then
        check_pass ".env permissions are 600"
    else
        check_fail ".env permissions are $ENV_PERMS (should be 600)"
    fi

    # Check PRIVATE_KEY is set (without showing the value)
    if grep -q "^PRIVATE_KEY=" .env 2>/dev/null; then
        check_pass "PRIVATE_KEY is set in .env"
    else
        check_fail "PRIVATE_KEY is NOT set in .env"
    fi

    # Check DRY_RUN setting
    if grep -q "^DRY_RUN=false" .env 2>/dev/null; then
        check_pass "DRY_RUN=false (live mode)"
    elif grep -q "^DRY_RUN=true" .env 2>/dev/null; then
        check_warn "DRY_RUN=true (dry-run mode) - set to false for live trading"
    else
        check_warn "DRY_RUN not set in .env (will use config.yaml)"
    fi

    # Check for common private key mistakes
    if grep -q "PRIVATE_KEY=0x.*" .env 2>/dev/null; then
        KEY_LENGTH=$(grep "^PRIVATE_KEY=" .env | cut -d'=' -f2 | tr -d '0x' | wc -c | tr -d ' ')
        if [ "$KEY_LENGTH" == "64" ]; then
            check_pass "PRIVATE_KEY format is correct (64 hex chars)"
        else
            check_warn "PRIVATE_KEY length verification (format check passed)"
        fi
    fi
else
    check_fail ".env file does not exist"
fi

echo ""

# 2. Config file check
echo "2. Configuration Files"
echo "   --------------------"

if [ -f config/config.yaml ]; then
    check_pass "config/config.yaml exists"

    # Check DRY_RUN in config
    if grep -q "^DRY_RUN: false" config/config.yaml; then
        check_pass "DRY_RUN=false in config.yaml"
    else
        check_fail "DRY_RUN is not set to false in config.yaml"
    fi

    # Check profile
    if grep -q "PROFILE_NAME: \"live_safe_atomic_v1\"" config/config.yaml; then
        check_pass "PROFILE=live_safe_atomic_v1 (Phase 1 safe config)"
    else
        check_warn "PROFILE is not set to live_safe_atomic_v1"
    fi
else
    check_fail "config/config.yaml does not exist"
fi

# Check profile exists
if [ -f config/profiles/live_safe_atomic_v1.yaml ]; then
    check_pass "live_safe_atomic_v1.yaml profile exists"
else
    check_fail "live_safe_atomic_v1.yaml profile not found"
fi

echo ""

# 3. Python dependencies check
echo "3. Python Dependencies"
echo "   --------------------"

if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    check_pass "Python3 installed: $PYTHON_VERSION"
else
    check_fail "Python3 not found"
fi

# Check critical packages
CRITICAL_PACKAGES=("web3" "loguru" "pydantic" "aiohttp")
for pkg in "${CRITICAL_PACKAGES[@]}"; do
    if python3 -c "import $pkg" 2>/dev/null; then
        check_pass "$pkg installed"
    else
        check_fail "$pkg not installed"
    fi
done

echo ""

# 4. Disk space check
echo "4. System Resources"
echo "   ----------------"

DISK_AVAILABLE=$(df -h . | tail -1 | awk '{print $4}')
echo -e "${GREEN}✅ INFO${NC}: Disk space available: ${DISK_AVAILABLE}"

echo ""

# 5. Data directory check
echo "5. Data Directory"
echo "   ---------------"

if [ -d data ]; then
    check_pass "data directory exists"
else
    check_warn "data directory does not exist (will be created)"
fi

echo ""

# 6. Manual verification items
echo "6. Manual Verification (USER MUST VERIFY)"
echo "   ---------------------------------------"
echo ""
check_warn "Please manually verify:"
echo "   - PRIVATE_KEY is for an INDEPENDENT production wallet"
echo "   - CTF Exchange allowance is set to \$20 (NOT unlimited)"
echo "   - Wallet has at least \$20 USDC"
echo "   - You understand the risks of real trading"
echo ""

# Summary
echo "========================================================================"
echo "  Summary"
echo "========================================================================"
echo ""

if [ $FAIL_COUNT -eq 0 ]; then
    echo -e "${GREEN}✅ ALL CHECKS PASSED${NC}"
    echo ""
    echo "You may proceed with live trading."
    echo "Run: ./start_live_safe.sh"
    exit 0
else
    echo -e "${RED}❌ $FAIL_COUNT check(s) FAILED${NC}"
    if [ $WARN_COUNT -gt 0 ]; then
        echo -e "${YELLOW}⚠️  $WARN_COUNT warning(s)${NC}"
    fi
    echo ""
    echo "Please fix the FAILED items before proceeding with live trading."
    exit 1
fi
