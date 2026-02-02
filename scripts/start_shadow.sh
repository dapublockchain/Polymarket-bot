#!/bin/bash
# ============================================================
# PolyArb-X Shadow Production Startup Script
# ============================================================
# 用途: 启动 Phase 0 Shadow Production（干运行模式）
# 版本: v1.0.0
# 最后更新: 2026-02-02
# ============================================================

set -euo pipefail  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}PolyArb-X Shadow Production${NC}"
echo -e "${GREEN}=====================================${NC}"
echo ""

# ============================================================
# 配置
# ============================================================
PROFILE_NAME="live_shadow_atomic_v1"
RUN_MODE="shadow"
DESCRIPTION="Shadow Production - DRY_RUN mode, no real trades"

echo "📋 Configuration:"
echo "  - Profile: ${PROFILE_NAME}"
echo "  - Mode: ${RUN_MODE}"
echo "  - Description: ${DESCRIPTION}"
echo ""

# ============================================================
# 启动前验证
# ============================================================
echo "🔍 Pre-start checks..."

# 检查 config.yaml
if [ ! -f "config/config.yaml" ]; then
    echo -e "${RED}❌ config.yaml not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ config.yaml found${NC}"

# 检查 Profile
if [ ! -f "config/profiles/${PROFILE_NAME}.yaml" ]; then
    echo -e "${RED}❌ Profile ${PROFILE_NAME} not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ Profile ${PROFILE_NAME} found${NC}"

# 检查数据目录
if [ ! -d "data" ]; then
    echo -e "${YELLOW}⚠️  data directory not found, creating...${NC}"
    mkdir -p data
fi
echo -e "${GREEN}✅ data directory ready${NC}"

# 检查日志目录
if [ ! -d "data/alerts" ]; then
    mkdir -p data/alerts
fi

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ python3 not found!${NC}"
    exit 1
fi
echo -e "${GREEN}✅ python3 found${NC}"

echo ""

# ============================================================
# 启动系统
# ============================================================
echo -e "${YELLOW}🚀 Starting PolyArb-X...${NC}"
echo ""

# 记录启动时间
START_TIME=$(date +%s)
echo "START_TIME=${START_TIME}" >> .env.shadow

# 启动主程序
# 注意：这里假设主程序是 src/main.py
# 实际启动命令需要根据项目结构调整
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
# 启动后信息
# ============================================================
echo "📊 System Information:"
echo "  - Log file: data/polyarb-x.log"
echo "  - Events log: data/events.jsonl"
echo "  - Alerts log: data/alerts/alerts.jsonl"
echo "  - Alerts state: data/alerts/alerts_state.json"
echo ""

echo -e "${GREEN}=====================================${NC}"
echo -e "${GREEN}Shadow Production Stopped${NC}"
echo -e "${GREEN}=====================================${NC}"
