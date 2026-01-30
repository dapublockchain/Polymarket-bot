#!/bin/bash
# 离线安装脚本 - 在无网络的机器上运行
# 确保 packages/ 目录已经从有网络的机器传输过来

set -e

echo "🔧 离线安装 Python 依赖..."

# 检查 packages 目录
if [ ! -d "packages" ]; then
    echo "❌ 错误: packages/ 目录不存在"
    echo "请先在有网络的机器上运行 download_packages.sh 下载包"
    exit 1
fi

# 检查 packages 目录是否为空
if [ -z "$(ls -A packages)" ]; then
    echo "❌ 错误: packages/ 目录为空"
    echo "请先在有网络的机器上运行 download_packages.sh 下载包"
    exit 1
fi

echo "📦 找到以下包:"
ls -1 packages/
echo ""

# 安装包
python3 -m pip install --no-index --find-links=packages/ -r requirements.txt --user

echo ""
echo "✅ 安装完成！"
echo ""
echo "🔍 验证安装..."
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
