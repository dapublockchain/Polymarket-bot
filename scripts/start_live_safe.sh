#!/bin/bash
# ============================================================
# PolyArb-X Live Safe Startup Script
# ============================================================
# 用途: 启动 Phase 1-3 Live Production（实盘模式）
# 版本: v1.0.0
# 最后更新: 2026-02-02
# ============================================================

set -euo pipefail  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}PolyArb-X Live Production${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# ============================================================
# 配置
# ============================================================
PROFILE_NAME="${PROFILE_NAME:-live_safe_atomic_v1}"  # 默认 Phase 1
RUN_MODE="live"

echo "📋 Configuration:"
echo "  - Profile: ${PROFILE_NAME}"
echo "  - Mode: ${RUN_MODE} (REAL MONEY)"
echo ""

# ============================================================
# Go/No-Go 检查
# ============================================================
echo -e "${YELLOW}⚠️  Running Go/No-Go checks...${NC}"
echo ""

# 执行 go_no_go_check.sh
if [ -f "scripts/go_no_go_check.sh" ]; then
    bash scripts/go_no_go_check.sh
    CHECK_RESULT=$?

    if [ ${CHECK_RESULT} -ne 0 ]; then
        echo -e "${RED}❌ Go/No-Go check FAILED${NC}"
        echo -e "${RED}❌ Cannot start live production${NC}"
        echo ""
        echo "Please fix the issues and run again."
        exit 1
    fi

    echo -e "${GREEN}✅ Go/No-Go check PASSED${NC}"
    echo ""
else
    echo -e "${YELLOW}⚠️  go_no_go_check.sh not found, skipping...${NC}"
    echo ""
fi

# ============================================================
# 创建启动前备份
# ============================================================
echo -e "${YELLOW}💾 Creating pre-start backup...${NC}"

if [ -f "scripts/backup_state.sh" ]; then
    bash scripts/backup_state.sh
    echo -e "${GREEN}✅ Backup created${NC}"
else
    echo -e "${YELLOW}⚠️  backup_state.sh not found, skipping...${NC}"
fi

echo ""

# ============================================================
# 安全确认
# ============================================================
echo -e "${RED}=====================================${NC}"
echo -e "${RED}⚠️  WARNING: LIVE TRADING MODE${NC}"
echo -e "${RED}=====================================${NC}"
echo ""
echo "You are about to start the system in LIVE mode."
echo "This will execute REAL trades with REAL money."
echo ""
echo "Profile: ${PROFILE_NAME}"
echo ""

# 读取配置以显示风险信息
if [ -f "config/profiles/${PROFILE_NAME}.yaml" ]; then
    echo "Risk Parameters:"
    grep -E "TRADE_SIZE|MAX_POSITION_SIZE|MAX_DAILY_LOSS|MAX_SLIPPAGE" "config/profiles/${PROFILE_NAME}.yaml" | sed 's/^/  /'
    echo ""
fi

echo -e "${YELLOW}Press Ctrl+C to cancel, or wait 5 seconds to continue...${NC}"
sleep 5

echo ""
echo -e "${GREEN}✅ Starting live production...${NC}"
echo ""

# ============================================================
# 启动系统
# ============================================================
# 记录启动时间
START_TIME=$(date +%s)
echo "START_TIME=${START_TIME}" >> .env.live

# 启动主程序
python3 src/main.py \
    --profile "${PROFILE_NAME}" \
    --mode "${RUN_MODE}" \
    2>&1 | tee -a data/polyarb-x.log

EXIT_CODE=$?

# 记录退出时间
END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

echo ""
if [ ${EXIT_CODE} -eq 0 ]; then
    echo -e "${GREEN}✅ System stopped successfully${NC}"
else
    echo -e "${RED}❌ System stopped with error code ${EXIT_CODE}${NC}"
fi

echo "Duration: ${DURATION} seconds"
echo ""

# ============================================================
# 停止后信息
# ============================================================
echo "📊 System Information:"
echo "  - Log file: data/polyarb-x.log"
echo "  - Events log: data/events.jsonl"
echo "  - Audit log: data/audit/config_changes.jsonl"
echo "  - Alerts log: data/alerts/alerts.jsonl"
echo "  - Alerts state: data/alerts/alerts_state.json"
echo ""

# ============================================================
# 生成停止报告
# ============================================================
echo -e "${YELLOW}📝 Generating shutdown report...${NC}"

if [ -f "scripts/production_daily_report.py" ]; then
    python3 scripts/production_daily_report.py
    echo -e "${GREEN}✅ Report generated${NC}"
else
    echo -e "${YELLOW}⚠️  production_daily_report.py not found${NC}"
fi

echo ""
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Live Production Stopped${NC}"
echo -e "${BLUE}=====================================${NC}"
