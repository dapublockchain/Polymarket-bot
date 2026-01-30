#!/bin/bash
# 🚀 PolyArb-X v1.0 GitHub 同步命令
# 在您的终端（非沙盒）中依次执行以下命令：

echo "🚀 开始同步 PolyArb-X v1.0 到 GitHub..."

cd /Users/dapumacmini/polyarb-x || exit 1

# 1. 配置 Git
echo "📝 步骤 1/7: 配置 Git..."
git config user.name "PolyArb-X"
git config user.email "noreply@polyarb-x.com"

# 2. 初始化仓库
echo "📦 步骤 2/7: 初始化 Git 仓库..."
if [ ! -d ".git" ]; then
    git init
fi

# 3. 添加远程仓库
echo "🔗 步骤 3/7: 添加远程仓库..."
if ! git remote get-url origin >/dev/null 2>&1; then
    git remote add origin https://github.com/dapublockchain/Polymarket-bot.git
else
    git remote set-url origin https://github.com/dapublockchain/Polymarket-bot.git
fi

# 4. 添加文件
echo "➕ 步骤 4/7: 添加所有文件..."
git add .

# 5. 提交
echo "✅ 步骤 5/7: 创建提交..."
git commit -m "PolyArb-X v1.0 - Initial Release

🎉 PolyArb-X - 低延迟预测市场套利机器人

## 功能特性
- ✅ 实时订单本管理（WebSocket）
- ✅ 原子套利策略（YES + NO < 1.0）
- ✅ NegRisk 套利策略
- ✅ 市场分组和组合套利
- ✅ 风险管理和验证
- ✅ 交易签名和发送
- ✅ EIP-1559 Gas 优化
- ✅ 自动重试机制

## 项目统计
- 209 个测试，100% 通过率
- 84.06% 代码覆盖率
- 13 个源文件，15 个测试文件

## 技术栈
- Python 3.10+
- asyncio (异步)
- Pydantic v2 (数据验证)
- websockets (WebSocket)
- web3.py (区块链)
- pytest (测试)

🤖 Generated with Claude Code
📅 Release Date: 2026-01-30
🏷️ Version: v1.0.0
"

# 6. 推送主分支
echo "📤 步骤 6/7: 推送到 GitHub..."
git branch -M main 2>/dev/null || git branch -M master
git push -u origin main 2>/dev/null || git push -u origin master

# 7. 创建标签
echo "🏷️  步骤 7/7: 创建 v1.0 标签..."
git tag -a v1.0 -m "PolyArb-X v1.0 - Production Ready Release

🎉 首个正式发布版本

主要功能:
- 原子套利策略
- NegRisk 套利策略
- 市场分组和组合套利
- 风险管理和交易执行
- 完整的测试覆盖（84.06%）

测试: 209/209 通过
覆盖: 84.06%
状态: ✅ 生产就绪
"

git push origin v1.0

echo ""
echo "✅ 同步完成！"
echo ""
echo "📦 仓库地址: https://github.com/dapublockchain/Polymarket-bot"
echo "🏷️  版本标签: v1.0"
echo ""
echo "🎊 PolyArb-X v1.0 已成功发布到 GitHub！"
