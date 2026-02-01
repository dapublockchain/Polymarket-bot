#!/bin/bash
# PolyArb-X Configuration Seeder
# 用于初始化和验证配置文件

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "========================================="
echo "  PolyArb-X 配置初始化脚本"
echo "========================================="
echo ""

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# 创建必要的目录
echo "📁 创建必要的目录..."
mkdir -p config/profiles/custom
mkdir -p data/audit
mkdir -p data/alerts
echo "✅ 目录创建完成"
echo ""

# 检查并验证 Profile YAML 文件
echo "📋 检查内置 Profile 文件..."
PROFILES_DIR="config/profiles"
REQUIRED_PROFILES=("conservative.yaml" "balanced.yaml" "aggressive.yaml" "maker.yaml" "taker.yaml" "sandbox.yaml" "live_safe.yaml")

for profile in "${REQUIRED_PROFILES[@]}"; do
    profile_path="$PROFILES_DIR/$profile"
    if [ -f "$profile_path" ]; then
        echo "  ✅ $profile"
        # 验证 YAML 格式（如果有 Python）
        if command -v python3 &> /dev/null; then
            if ! python3 -c "import yaml; yaml.safe_load(open('$profile_path'))" 2>/dev/null; then
                echo "    ${RED}⚠️  YAML 格式错误！${NC}"
                exit 1
            fi
        fi
    else
        echo "  ${RED}❌ 缺失: $profile${NC}"
        exit 1
    fi
done
echo "✅ 所有 Profile 文件检查通过"
echo ""

# 检查 alerts.yaml
echo "📋 检查 alerts.yaml..."
ALERTS_FILE="config/alerts.yaml"
if [ -f "$ALERTS_FILE" ]; then
    echo "  ✅ alerts.yaml"
    # 验证 YAML 格式
    if command -v python3 &> /dev/null; then
        if ! python3 -c "import yaml; yaml.safe_load(open('$ALERTS_FILE'))" 2>/dev/null; then
            echo "    ${RED}⚠️  YAML 格式错误！${NC}"
            exit 1
        fi
    fi
else
    echo "  ${RED}❌ 缺失: alerts.yaml${NC}"
    exit 1
fi
echo "✅ alerts.yaml 检查通过"
echo ""

# 初始化空的审计日志
AUDIT_FILE="data/audit/config_changes.jsonl"
if [ ! -f "$AUDIT_FILE" ]; then
    echo "📝 初始化审计日志..."
    touch "$AUDIT_FILE"
    echo "✅ 审计日志已创建: $AUDIT_FILE"
else
    echo "✅ 审计日志已存在: $AUDIT_FILE"
fi
echo ""

# 初始化空的告警状态文件
ALERTS_STATE_FILE="data/alerts/alerts_state.json"
if [ ! -f "$ALERTS_STATE_FILE" ]; then
    echo "📝 初始化告警状态文件..."
    echo '{"active_alerts": [], "last_updated": null}' > "$ALERTS_STATE_FILE"
    echo "✅ 告警状态文件已创建: $ALERTS_STATE_FILE"
else
    echo "✅ 告警状态文件已存在: $ALERTS_STATE_FILE"
fi
echo ""

# 初始化空的告警事件流
ALERTS_EVENTS_FILE="data/alerts/alerts.jsonl"
if [ ! -f "$ALERTS_EVENTS_FILE" ]; then
    echo "📝 初始化告警事件流..."
    touch "$ALERTS_EVENTS_FILE"
    echo "✅ 告警事件流已创建: $ALERTS_EVENTS_FILE"
else
    echo "✅ 告警事件流已存在: $ALERTS_EVENTS_FILE"
fi
echo ""

# 检查 .env 文件
if [ ! -f ".env" ]; then
    echo "⚠️  未找到 .env 文件"
    echo "   请创建 .env 文件并配置必要的环境变量："
    echo "   - DRY_RUN (默认: true)"
    echo "   - PRIVATE_KEY (实盘模式必需)"
    echo "   - WALLET_ADDRESS (实盘模式必需)"
    echo "   - POLYGON_RPC_URL"
    echo ""
else
    echo "✅ .env 文件已存在"
fi

# 权限检查
echo "🔒 检查文件权限..."
chmod 755 scripts/seed_profiles.sh 2>/dev/null || true
echo "✅ 权限检查完成"
echo ""

# 统计信息
echo "========================================="
echo "  配置文件统计"
echo "========================================="
echo "内置 Profiles: $(ls -1 config/profiles/*.yaml 2>/dev/null | wc -l)"
echo "自定义 Profiles: $(ls -1 config/profiles/custom/*.yaml 2>/dev/null | wc -l)"
echo "告警规则: $(grep -c "^  - id:" config/alerts.yaml 2>/dev/null || echo 0)"
echo ""

echo "${GREEN}========================================="
echo "  ✅ 初始化完成！"
echo "=========================================${NC}"
echo ""
echo "下一步："
echo "  1. 检查并配置 .env 文件"
echo "  2. 启动 Web 服务器: python3 ui/web_server.py"
echo "  3. 访问 Dashboard: http://localhost:8080"
echo "  4. 在 Profiles 页面选择并应用配置"
echo ""
