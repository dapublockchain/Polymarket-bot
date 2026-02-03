#!/bin/bash
# PolyArb-X Live Mode Startup Script
# Phase 1: Micro-Live ($2/trade, max position $20, max daily loss $3)
#
# ⚠️  WARNING: This script will start REAL trading with REAL money!
# Please ensure you have:
# 1. Read and understood the risks
# 2. Set up an independent production wallet
# 3. Set CTF Exchange allowance to $20 ONLY (NOT unlimited!)
# 4. Completed the Go/No-Go checklist

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "========================================================================"
echo "  PolyArb-X Phase 1: Micro-Live Startup"
echo "========================================================================"
echo ""
echo "${YELLOW}⚠️  WARNING: REAL MONEY TRADING MODE${NC}"
echo ""
echo "Configuration:"
echo "  - Trade Size: \$2 per trade"
echo "  - Max Position: \$20"
echo "  - Max Daily Loss: \$3"
echo "  - Max Slippage: 2.5%"
echo ""
echo "⏰ 5 seconds to cancel (Ctrl+C)..."
echo ""
sleep 5

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${RED}❌ .env file not found!${NC}"
    echo "Please create .env file with PRIVATE_KEY set."
    exit 1
fi

# Verify PRIVATE_KEY is set (without showing it)
if ! grep -q "^PRIVATE_KEY=" .env 2>/dev/null; then
    echo -e "${RED}❌ PRIVATE_KEY not set in .env!${NC}"
    exit 1
fi

# Check .env permissions
ENV_PERMS=$(stat -f "%Lp" .env 2>/dev/null || stat -c "%a" .env 2>/dev/null)
if [ "$ENV_PERMS" != "600" ]; then
    echo -e "${YELLOW}⚠️  Warning: .env permissions are $ENV_PERMS (recommended: 600)${NC}"
    echo "Run: chmod 600 .env"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "${GREEN}✅ .env file exists and PRIVATE_KEY is set${NC}"

# Check DRY_RUN setting
if grep -q "^DRY_RUN=false" .env 2>/dev/null; then
    echo -e "${RED}⚠️  DRY_RUN=false - LIVE MODE ENABLED${NC}"
elif grep -q "^DRY_RUN=true" .env 2>/dev/null; then
    echo -e "${YELLOW}⚠️  DRY_RUN=true still set in .env${NC}"
    echo "Config.yaml has DRY_RUN=false, but .env overrides may apply."
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create backup
echo ""
echo "Creating pre-start backup..."
BACKUP_DIR="backups/pre_live_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp config/config.yaml "$BACKUP_DIR/"
cp -r data/events.jsonl "$BACKUP_DIR/" 2>/dev/null || true
cp -r data/alerts "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✅ Backup created: $BACKUP_DIR${NC}"

# Show configuration summary
echo ""
echo "========================================================================"
echo "  Go/No-Go Checklist"
echo "========================================================================"
echo ""
echo "Please verify the following BEFORE starting:"
echo ""
echo "  [ ] PRIVATE_KEY is set in .env"
echo "  [ ] Private key is for an INDEPENDENT production wallet"
echo "  [ ] CTF Exchange allowance is set to \$20 (NOT unlimited)"
echo "  [ ] Wallet has at least \$20 USDC"
echo "  [ ] You understand the risks of real trading"
echo "  [ ] Monitoring dashboard is accessible"
echo "  [ ] Alert notifications are configured"
echo ""
read -p "Have you completed ALL items above? (yes/NO): " -r
echo
if [[ ! $REPLY == "yes" ]]; then
    echo -e "${RED}❌ Aborted: Please complete the checklist first${NC}"
    exit 1
fi

# Start the bot
echo ""
echo "========================================================================"
echo "  Starting PolyArb-X in LIVE mode..."
echo "========================================================================"
echo ""

# Set environment variables for live mode
export DRY_RUN=false
export PROFILE_NAME="live_safe_atomic_v1"

# Run the bot
python3 src/main.py
