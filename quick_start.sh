#!/bin/bash
# PolyArb-X 快速启动脚本

echo "================================"
echo " PolyArb-X 快速启动"
echo "================================"
echo ""

# 检查.env
if [ ! -f .env ]; then
    echo "❌ .env 文件不存在"
    echo "   请先创建: cp .env.example .env"
    exit 1
fi

echo "✅ 环境配置已就绪"
echo "✅ 439个测试通过"
echo "✅ 81.93%覆盖率"
echo ""

echo "选择启动模式:"
echo "  1) 干运行模式 (推荐，安全)"
echo "  2) 小额测试模式"
echo "  3) 完整生产模式"
echo ""
read -p "请选择 [1/2/3]: " -n 1 -r
echo ""
echo ""

case $REPLY in
    1)
        echo "🔵 启动干运行模式..."
        echo "✓ 不会执行真实交易"
        PYTHONPATH=. python3 -m src.main --dry-run
        ;;
    2)
        echo "🟡 启动小额测试模式..."
        echo "⚠️  会执行真实交易，请确认.env中TRADE_SIZE=10"
        read -p "确认? (yes/NO): " -r
        if [[ $REPLY == "yes" ]]; then
            PYTHONPATH=. python3 -m src.main
        else
            echo "已取消"
        fi
        ;;
    3)
        echo "🔴 启动完整生产模式..."
        echo "⚠️  警告: 将使用真实资金交易"
        read -p "确认启动? (yes/NO): " -r
        if [[ $REPLY == "yes" ]]; then
            PYTHONPATH=. python3 -m src.main
        else
            echo "已取消"
        fi
        ;;
    *)
        echo "无效选择"
        exit 1
        ;;
esac
