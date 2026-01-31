#!/bin/bash
# Helper script to run PolyArb-X in LIVE TRADING mode
# WARNING: This will execute real transactions if private key is valid!

echo "🚀 启动 PolyArb-X (实盘交易模式)..."
echo "⚠️  注意: 请确保 .env 中的 PRIVATE_KEY 已配置为真实钱包私钥"

# Check if private key is default
if grep -q "0x0000000000000000000000000000000000000000000000000000000000000001" .env; then
    echo "❌ 错误: 检测到默认私钥。请修改 .env 文件配置真实私钥后重试。"
    exit 1
fi

PYTHONPATH=. python3 src/main.py
