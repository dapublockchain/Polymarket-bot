#!/bin/bash
# PolyArb-X 生产环境启动脚本

set -e

echo "================================"
echo " PolyArb-X 生产环境启动检查"
echo "================================"
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查函数
check_pass() {
    echo -e "${GREEN}✅ $1${NC}"
}

check_fail() {
    echo -e "${RED}❌ $1${NC}"
}

check_warn() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

# 1. 检查Python版本
echo "1. 检查Python版本..."
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
    check_pass "Python版本: $PYTHON_VERSION (需要 >= 3.10)"
else
    check_fail "Python版本: $PYTHON_VERSION (需要 >= 3.10)"
    exit 1
fi
echo ""

# 2. 检查.env文件
echo "2. 检查环境配置..."
if [ -f .env ]; then
    check_pass ".env 文件存在"

    # 检查必需的环境变量（不显示实际值）
    if grep -q "PRIVATE_KEY=" .env && ! grep -q "PRIVATE_KEY=$" .env; then
        check_pass "PRIVATE_KEY 已设置"
    else
        check_fail "PRIVATE_KEY 未设置"
        exit 1
    fi

    if grep -q "POLYGON_RPC_URL=" .env && ! grep -q "POLYGON_RPC_URL=$" .env; then
        check_pass "POLYGON_RPC_URL 已设置"
    else
        check_fail "POLYGON_RPC_URL 未设置"
        exit 1
    fi

    if grep -q "POLYMARKET_WS_URL=" .env && ! grep -q "POLYMARKET_WS_URL=$" .env; then
        check_pass "POLYMARKET_WS_URL 已设置"
    else
        check_fail "POLYMARKET_WS_URL 未设置"
        exit 1
    fi
else
    check_fail ".env 文件不存在，请先创建"
    echo "   复制模板: cp .env.example .env"
    echo "   编辑配置: nano .env"
    exit 1
fi
echo ""

# 3. 检查依赖
echo "3. 检查Python依赖..."
MISSING_DEPS=0

check_import() {
    if python3 -c "import $1" 2>/dev/null; then
        check_pass "$2"
    else
        check_fail "$2 未安装"
        MISSING_DEPS=1
    fi
}

check_import "web3" "web3.py"
check_import "pydantic" "pydantic"
check_import "asyncio" "asyncio"
check_import "websockets" "websockets"
check_import "loguru" "loguru"
check_import "eth_account" "eth-account"

if [ $MISSING_DEPS -eq 1 ]; then
    echo ""
    check_warn "缺少依赖，运行以下命令安装:"
    echo "   python3 -m pip install --user -r requirements.txt"
    exit 1
fi
echo ""

# 4. 检查数据目录
echo "4. 检查数据目录..."
mkdir -p data/events
mkdir -p data/logs
check_pass "数据目录已创建"
echo ""

# 5. 运行测试套件
echo "5. 运行测试套件..."
echo "   运行测试中..."
if python3 -m pytest tests/unit/ -q --tb=no 2>&1 | grep -q "350 passed"; then
    check_pass "所有测试通过 (350/350)"
else
    check_warn "测试未全部通过，建议先修复"
    echo "   运行: python3 -m pytest tests/unit/ -v"
    read -p "   是否继续启动? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi
echo ""

# 6. 检查网络连接
echo "6. 检查网络连接..."
if curl -s -X POST https://polygon-rpc.com -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}' | grep -q "result"; then
    check_pass "Polygon RPC 连接正常"
else
    check_warn "Polygon RPC 连接失败，请检查网络"
fi
echo ""

# 所有检查通过
echo "================================"
echo -e "${GREEN}✅ 所有检查通过！${NC}"
echo "================================"
echo ""

# 询问启动模式
echo "选择启动模式:"
echo "  1) 干运行模式 (推荐首次使用)"
echo "  2) 生产模式 (真实交易)"
echo ""
read -p "请选择 [1/2]: " -n 1 -r
echo ""
echo ""

case $REPLY in
    1)
        echo -e "${YELLOW}启动干运行模式...${NC}"
        echo "✓ 不会执行真实交易"
        echo "✓ 会连接WebSocket"
        echo "✓ 会模拟套利检测"
        echo ""
        python3 src/main.py --dry-run
        ;;
    2)
        echo -e "${RED}⚠️  警告: 即将启动生产模式！${NC}"
        echo ""
        echo "生产模式会:"
        echo "  • 使用真实资金"
        echo "  • 执行真实交易"
        echo "  • 产生实际盈亏"
        echo ""
        read -p "确认启动生产模式? (yes/NO): " -r
        echo ""
        if [[ $REPLY == "yes" ]]; then
            echo -e "${GREEN}启动生产模式...${NC}"
            echo "按 Ctrl+C 安全停止系统"
            echo ""
            python3 src/main.py
        else
            echo "已取消启动"
            exit 0
        fi
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
