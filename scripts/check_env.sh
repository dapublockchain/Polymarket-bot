#!/bin/bash
# 检查并显示 .env 配置（隐藏敏感信息）

echo "检查 .env 配置..."
echo ""

if [ ! -f .env ]; then
    echo "❌ .env 文件不存在"
    exit 1
fi

echo "当前 .env 配置："
echo "----------------"

# 检查 DRY_RUN 设置
if grep -q "^DRY_RUN=true" .env; then
    echo "DRY_RUN: true (模拟模式)"
elif grep -q "^DRY_RUN=false" .env; then
    echo "DRY_RUN: false (实盘模式)"
else
    echo "DRY_RUN: [未设置，将使用 config.yaml]"
fi

# 检查 PRIVATE_KEY 是否存在
if grep -q "^PRIVATE_KEY=" .env; then
    KEY_VALUE=$(grep "^PRIVATE_KEY=" .env | cut -d'=' -f2)
    if [ -z "$KEY_VALUE" ]; then
        echo "PRIVATE_KEY: [设置为空]"
    else
        KEY_LEN=${#KEY_VALUE}
        if [ "$KEY_LEN" == "66" ]; then
            echo "PRIVATE_KEY: ✓ 格式正确 (0x + 64位十六进制)"
        else
            echo "PRIVATE_KEY: ⚠ 长度为 $KEY_LEN (应为66字符: 0x + 64位十六进制)"
        fi
    fi
else
    echo "PRIVATE_KEY: [未设置]"
fi

echo ""
echo "建议配置："
echo "----------------"
echo "DRY_RUN=false"
echo "PRIVATE_KEY=0x[你的64位私钥]"
