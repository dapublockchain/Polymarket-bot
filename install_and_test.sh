#!/bin/bash
# Phase 4 安装和验证脚本

set -e

echo "🚀 Phase 4: 执行层依赖安装和验证"
echo ""

# 颜色输出
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 步骤 1: 检查当前状态
echo "📋 步骤 1: 检查当前依赖状态..."
echo ""

if python3 -c "import web3" 2>/dev/null; then
    VERSION=$(python3 -c "import web3; print(web3.__version__)")
    echo -e "${GREEN}✅ web3 已安装 (版本: $VERSION)${NC}"
else
    echo -e "${YELLOW}⚠️  web3 未安装${NC}"
fi

if python3 -c "import eth_account" 2>/dev/null; then
    VERSION=$(python3 -c "import eth_account; print(eth_account.__version__)")
    echo -e "${GREEN}✅ eth_account 已安装 (版本: $VERSION)${NC}"
else
    echo -e "${YELLOW}⚠️  eth_account 未安装${NC}"
fi

echo ""

# 步骤 2: 安装缺失的依赖
echo "📦 步骤 2: 安装缺失的依赖..."
echo ""

if ! python3 -c "import web3" 2>/dev/null; then
    echo "安装 web3==6.11.3..."
    python3 -m pip install --user web3==6.11.3

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ web3 安装成功${NC}"
    else
        echo -e "${RED}❌ web3 安装失败${NC}"
        exit 1
    fi
fi

echo ""

# 步骤 3: 验证所有依赖
echo "🔍 步骤 3: 验证所有依赖..."
echo ""

python3 -c "
import sys
try:
    import web3
    import eth_account
    import pydantic
    import websockets
    import aiohttp
    from dotenv import load_dotenv
    from loguru import logger

    print('✅ web3 版本:', web3.__version__)
    print('✅ eth_account 版本:', eth_account.__version__)
    print('✅ pydantic 版本:', pydantic.__version__)
    print('✅ websockets 已安装')
    print('✅ aiohttp 版本:', aiohttp.__version__)
    print('✅ python-dotenv 已安装')
    print('✅ loguru 已安装')
    print('')
    print('🎉 所有依赖安装成功！')
    sys.exit(0)
except ImportError as e:
    print(f'❌ 导入失败: {e}')
    sys.exit(1)
"

if [ $? -ne 0 ]; then
    echo -e "${RED}❌ 依赖验证失败${NC}"
    exit 1
fi

echo ""

# 步骤 4: 运行测试
echo "🧪 步骤 4: 运行测试..."
echo ""

echo "运行执行层测试..."
python3 -m pytest tests/unit/test_web3_client.py tests/unit/test_risk_manager.py tests/unit/test_tx_sender.py -v

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ 所有测试通过！${NC}"
else
    echo -e "${RED}❌ 部分测试失败${NC}"
fi

echo ""

# 步骤 5: 生成覆盖率报告
echo "📊 步骤 5: 生成覆盖率报告..."
echo ""

python3 -m pytest tests/unit/test_web3_client.py tests/unit/test_risk_manager.py tests/unit/test_tx_sender.py --cov=src/connectors/web3_client --cov=src/execution --cov-report=html --cov-report=term-missing

echo ""
echo -e "${GREEN}✅ Phase 4 验证完成！${NC}"
echo ""
echo "📝 查看详细覆盖率报告: htmlcov/index.html"
