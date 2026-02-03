#!/bin/bash
# PolyArb-X Live Mode - Auto-Confirm Startup
# This script skips interactive prompts - use only if you have verified everything!

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "========================================================================"
echo "  PolyArb-X Phase 1: Micro-Live (Auto-Confirm)"
echo "========================================================================"
echo ""
echo -e "${RED}⚠️  AUTO-CONFIRM MODE: Starting without manual confirmation${NC}"
echo ""

# Create backup
BACKUP_DIR="backups/pre_live_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp config/config.yaml "$BACKUP_DIR/"
cp -r data/events.jsonl "$BACKUP_DIR/" 2>/dev/null || true
cp -r data/alerts "$BACKUP_DIR/" 2>/dev/null || true
echo -e "${GREEN}✅ Backup created: $BACKUP_DIR${NC}"

echo ""
echo "Starting PolyArb-X in LIVE mode..."
echo "Press Ctrl+C to stop at any time."
echo ""
echo "========================================================================"
echo ""

# Set environment and start
export DRY_RUN=false
export PROFILE_NAME="live_safe_atomic_v1"

python3 src/main.py
