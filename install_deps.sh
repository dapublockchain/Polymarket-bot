#!/bin/bash
# 安装 PolyArb-X 依赖脚本
# 请在您的终端环境中运行此脚本

set -e

echo "🚀 开始安装 PolyArb-X 依赖..."

# 方法1: 使用 pip 安装到用户目录
echo "📦 方法1: 使用 pip 安装..."
python3 -m pip install --user -r requirements.txt

echo "✅ 依赖安装完成！"

# 验证安装
echo ""
echo "🔍 验证安装..."
python3 -c "
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
"

echo ""
echo "📝 下一步："
echo "1. 配置环境变量（复制 .env.example 到 .env）"
echo "2. 运行测试: python3 -m pytest tests/"
echo "3. 运行项目: python3 src/main.py"
