#!/bin/bash
# 在有网络的机器上运行此脚本下载依赖包
# 然后将 packages/ 目录传输到目标机器

set -e

echo "📦 下载 Python 依赖包..."

# 创建 packages 目录
mkdir -p packages

# 下载所有依赖包到 packages 目录
python3 -m pip download \
  -r requirements.txt \
  -d packages/ \
  --only-binary=:all:

echo "✅ 下载完成！"
echo ""
echo "📦 packages/ 目录内容:"
ls -lh packages/
echo ""
echo "📝 下一步:"
echo "1. 将 packages/ 目录传输到目标机器"
echo "2. 在目标机器上运行: bash install_offline.sh"
