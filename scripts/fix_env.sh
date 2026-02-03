#!/bin/bash
# 修复 .env 配置以启用实盘模式

set -e

echo "正在修复 .env 配置..."
echo ""

# 备份 .env
BACKUP_FILE=".env.backup_$(date +%Y%m%d_%H%M%S)"
cp .env "$BACKUP_FILE"
echo "✅ 已备份到: $BACKUP_FILE"

# 检查当前 DRY_RUN 设置
if grep -q "^DRY_RUN=true" .env; then
    # 替换 DRY_RUN=true 为 DRY_RUN=false
    sed -i '' 's/^DRY_RUN=true/DRY_RUN=false/' .env
    echo "✅ 已将 DRY_RUN=true 改为 DRY_RUN=false"
elif grep -q "^DRY_RUN=false" .env; then
    echo "✅ DRY_RUN 已经是 false"
else
    # 添加 DRY_RUN=false
    echo "" >> .env
    echo "# Auto-added: Enable live mode" >> .env
    echo "DRY_RUN=false" >> .env
    echo "✅ 已添加 DRY_RUN=false"
fi

echo ""
echo "修复完成！当前配置："
grep "^DRY_RUN=" .env || echo "DRY_RUN=[未找到]"

echo ""
echo "运行以下命令验证："
echo "  bash scripts/check_env.sh"
