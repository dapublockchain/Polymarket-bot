#!/bin/bash
# ============================================================
# PolyArb-X Go/No-Go Checklist Script
# ============================================================
# 用途: 启动前执行完整的 Go/No-Go 检查
# 版本: v1.0.0
# 最后更新: 2026-02-02
# ============================================================

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 统计
PASS_COUNT=0
FAIL_COUNT=0
WARN_COUNT=0

# 辅助函数
check_pass() {
    echo -e "${GREEN}✅ PASS${NC}: $1"
    PASS_COUNT=$((PASS_COUNT + 1))
}

check_fail() {
    echo -e "${RED}❌ FAIL${NC}: $1"
    FAIL_COUNT=$((FAIL_COUNT + 1))
}

check_warn() {
    echo -e "${YELLOW}⚠️  WARN${NC}: $1"
    WARN_COUNT=$((WARN_COUNT + 1))
}

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Go/No-Go Checklist${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# ============================================================
# 1. 安全检查 (Security)
# ============================================================
echo -e "${BLUE}🔒 Security Checks${NC}"
echo ""

# 检查 .env 文件权限
if [ -f ".env" ] || [ -f "config/.env" ]; then
    ENV_FILE=".env"
    [ -f "config/.env" ] && ENV_FILE="config/.env"

    PERMISSIONS=$(stat -f "%Lp" "${ENV_FILE}" 2>/dev/null || stat -c "%a" "${ENV_FILE}" 2>/dev/null)

    if [ "${PERMISSIONS}" = "600" ] || [ "${PERMISSIONS}" = "400" ]; then
        check_pass "Environment file permissions are correct (${PERMISSIONS})"
    else
        check_fail "Environment file permissions are insecure (${PERMISSIONS}), should be 600"
    fi
else
    check_fail "Environment file not found (.env or config/.env)"
fi

# 检查 PRIVATE_KEY 是否设置
if [ -n "${PRIVATE_KEY:-}" ]; then
    check_pass "PRIVATE_KEY environment variable is set"
else
    check_fail "PRIVATE_KEY environment variable not set"
fi

# 检查 config.yaml 中是否硬编码私钥
if grep -q "PRIVATE_KEY:" config/config.yaml 2>/dev/null; then
    check_fail "PRIVATE_KEY hardcoded in config.yaml (security risk!)"
else
    check_pass "No hardcoded PRIVATE_KEY in config.yaml"
fi

echo ""

# ============================================================
# 2. 系统检查 (System)
# ============================================================
echo -e "${BLUE}⚙️  System Checks${NC}"
echo ""

# 检查 config.yaml
if [ -f "config/config.yaml" ]; then
    # 验证 YAML 格式
    if python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))" 2>/dev/null; then
        check_pass "config.yaml exists and is valid YAML"
    else
        check_fail "config.yaml exists but has invalid YAML format"
    fi
else
    check_fail "config.yaml not found"
fi

# 检查生产 Profile
PROFILES=(
    "live_shadow_atomic_v1"
    "live_safe_atomic_v1"
    "live_constrained_atomic_v1"
    "live_scaled_atomic_v1"
)

ALL_PROFILES_FOUND=true
for profile in "${PROFILES[@]}"; do
    if [ -f "config/profiles/${profile}.yaml" ]; then
        # 验证 YAML 格式
        if ! python3 -c "import yaml; yaml.safe_load(open('config/profiles/${profile}.yaml'))" 2>/dev/null; then
            check_fail "Profile ${profile}.yaml has invalid YAML format"
            ALL_PROFILES_FOUND=false
        fi
    else
        check_warn "Profile ${profile}.yaml not found"
        ALL_PROFILES_FOUND=false
    fi
done

if [ "${ALL_PROFILES_FOUND}" = true ]; then
    check_pass "All production profiles exist and are valid"
fi

# 检查告警配置
if [ -f "config/alerts.production.yaml" ]; then
    if python3 -c "import yaml; yaml.safe_load(open('config/alerts.production.yaml'))" 2>/dev/null; then
        check_pass "alerts.production.yaml exists and is valid YAML"
    else
        check_fail "alerts.production.yaml exists but has invalid YAML format"
    fi
else
    check_fail "alerts.production.yaml not found"
fi

# 检查 DRY_RUN 设置
DRY_RUN=$(grep "^DRY_RUN:" config/config.yaml | awk '{print $2}' | tr -d '"')
if [ "${DRY_RUN}" = "true" ] || [ "${DRY_RUN}" = "false" ]; then
    check_pass "DRY_RUN is set to ${DRY_RUN}"
else
    check_fail "DRY_RUN is not properly set in config.yaml"
fi

echo ""

# ============================================================
# 3. 数据检查 (Data)
# ============================================================
echo -e "${BLUE}📊 Data Checks${NC}"
echo ""

# 检查数据目录
if [ -d "data" ]; then
    check_pass "data directory exists"
else
    check_fail "data directory not found"
fi

# 检查告警目录
if [ -d "data/alerts" ]; then
    check_pass "data/alerts directory exists"
else
    check_warn "data/alerts directory not found (will be created)"
fi

# 检查磁盘空间
DISK_AVAILABLE=$(df -BM . | tail -1 | awk '{print $4}' | tr -d 'M')
if [ "${DISK_AVAILABLE}" -gt 1000 ]; then
    check_pass "Disk space available: ${DISK_AVAILABLE}MB (> 1GB)"
else
    check_fail "Disk space low: ${DISK_AVAILABLE}MB (< 1GB)"
fi

echo ""

# ============================================================
# 4. 操作检查 (Operational)
# ============================================================
echo -e "${BLUE}🔧 Operational Checks${NC}"
echo ""

# 检查 Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    check_pass "Python found: ${PYTHON_VERSION}"
else
    check_fail "python3 not found"
fi

# 检查脚本可执行权限
SCRIPTS=(
    "start_shadow.sh"
    "start_live_safe.sh"
    "backup_state.sh"
    "go_no_go_check.sh"
)

ALL_SCRIPTS_EXECUTABLE=true
for script in "${SCRIPTS[@]}"; do
    if [ -f "scripts/${script}" ]; then
        if [ -x "scripts/${script}" ]; then
            check_pass "Script ${script} is executable"
        else
            check_warn "Script ${script} exists but is not executable (chmod +x scripts/${script})"
            ALL_SCRIPTS_EXECUTABLE=false
        fi
    else
        check_warn "Script ${script} not found"
        ALL_SCRIPTS_EXECUTABLE=false
    fi
done

# 检查 RPC 连接
if command -v curl &> /dev/null; then
    if curl -s -X POST https://polygon-rpc.com \
        -H "Content-Type: application/json" \
        -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}' \
        | grep -q "0x89"; then
        check_pass "Polygon RPC is reachable (chainId: 137)"
    else
        check_fail "Polygon RPC is not reachable"
    fi
else
    check_warn "curl not found, skipping RPC check"
fi

# 检查日志目录可写
if [ -d "data" ]; then
    if touch data/.test_write 2>/dev/null; then
        rm data/.test_write
        check_pass "data directory is writable"
    else
        check_fail "data directory is not writable"
    fi
fi

echo ""

# ============================================================
# 5. 文档检查 (Documentation)
# ============================================================
echo -e "${BLUE}📚 Documentation Checks${NC}"
echo ""

DOCS=(
    "PRODUCTION_PLAN.md"
    "GO_NO_GO_CHECKLIST.md"
    "PRODUCTION_RUNBOOK.md"
)

ALL_DOCS_FOUND=true
for doc in "${DOCS[@]}"; do
    if [ -f "docs/${doc}" ]; then
        check_pass "Document ${doc} exists"
    else
        check_warn "Document ${doc} not found"
        ALL_DOCS_FOUND=false
    fi
done

echo ""

# ============================================================
# 总结
# ============================================================
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Checklist Summary${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo -e "${GREEN}PASS: ${PASS_COUNT}${NC}"
echo -e "${YELLOW}WARN: ${WARN_COUNT}${NC}"
echo -e "${RED}FAIL: ${FAIL_COUNT}${NC}"
echo ""

# 决策逻辑
if [ ${FAIL_COUNT} -gt 0 ]; then
    echo -e "${RED}=====================================${NC}"
    echo -e "${RED}❌ NO-GO: Cannot start production${NC}"
    echo -e "${RED}=====================================${NC}"
    echo ""
    echo "Please fix all FAIL items before proceeding."
    exit 1
elif [ ${WARN_COUNT} -gt 2 ]; then
    echo -e "${YELLOW}=====================================${NC}"
    echo -e "${YELLOW}⚠️  GO (with warnings)${NC}"
    echo -e "${YELLOW}=====================================${NC}"
    echo ""
    echo "System can start, but please address warnings ASAP."
    exit 0
else
    echo -e "${GREEN}=====================================${NC}"
    echo -e "${GREEN}✅ GO: All checks passed${NC}"
    echo -e "${GREEN}=====================================${NC}"
    echo ""
    echo "System is ready to start production."
    exit 0
fi
