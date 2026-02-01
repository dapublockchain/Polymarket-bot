#!/bin/bash
# 🚀 PolyArb-X v1.0 推送脚本
# 配置 GitHub 认证后执行此脚本

set -e

echo "🚀 推送 PolyArb-X v1.0 到 GitHub..."
echo ""

cd /Users/dapumacmini/polyarb-x

echo "📝 当前状态:"
echo "  提交: $(git log --oneline -1)"
echo "  标签: $(git tag -l)"
echo "  远程: $(git remote get-url origin)"
echo ""

echo "📤 推送主分支..."
git push -u origin main

echo ""
echo "🏷️  推送 v1.0 标签..."
git push origin v1.0

echo ""
echo "✅ 推送完成！"
echo ""
echo "🎉 访问: https://github.com/dapublockchain/Polymarket-bot"
echo ""
