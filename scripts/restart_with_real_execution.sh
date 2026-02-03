#!/bin/bash
# 重启脚本：应用实盘交易修复
# 使用方法: bash scripts/restart_with_real_execution.sh

set -e  # Exit on error

echo "=========================================="
echo "🔄 PolyArb-X 实盘交易模式重启脚本"
echo "=========================================="
echo ""

# 检查是否有正在运行的进程
RUNNING_PID=$(pgrep -f "python.*src/main.py" || true)

if [ -n "$RUNNING_PID" ]; then
    echo "⏹️  检测到正在运行的进程 (PID: $RUNNING_PID)"
    echo "🛑 停止旧进程..."
    kill $RUNNING_PID
    sleep 2

    # 确认进程已停止
    if pgrep -f "python.*src/main.py" > /dev/null; then
        echo "⚠️  进程未响应，强制终止..."
        pkill -9 -f "python.*src/main.py"
        sleep 1
    fi
    echo "✅ 旧进程已停止"
else
    echo "ℹ️  未检测到正在运行的进程"
fi

echo ""
echo "🚀 启动新进程（实盘交易模式）..."
echo ""

# 启动主程序（后台运行）
nohup python3 src/main.py > data/main.log 2>&1 &
NEW_PID=$!

echo "✅ 新进程已启动 (PID: $NEW_PID)"
echo ""

# 等待几秒让系统初始化
echo "⏳ 等待系统初始化..."
sleep 5

# 检查进程是否正常运行
if ps -p $NEW_PID > /dev/null; then
    echo "✅ 进程运行正常"
else
    echo "❌ 进程启动失败，请检查日志:"
    echo "   tail -100 data/main.log"
    exit 1
fi

# 检查日志中的关键信息
echo ""
echo "📋 检查启动日志..."
echo ""

# 显示最后20行日志
echo "最近日志:"
tail -20 data/main.log

echo ""
echo "=========================================="
echo "🔍 验证实盘交易模式"
echo "=========================================="
echo ""

# 检查关键日志
if grep -q "use_real_execution=True" data/main.log; then
    echo "✅ use_real_execution=True 已设置"
else
    echo "⚠️  未找到 'use_real_execution=True' 在日志中"
fi

if grep -q "REAL TRADING MODE" data/main.log; then
    echo "✅ 实盘交易模式已启用"
else
    echo "⚠️  未找到 'REAL TRADING MODE' 在日志中"
fi

if grep -q "LiveExecutor initialized" data/main.log; then
    echo "✅ LiveExecutor 已初始化"
else
    echo "⚠️  LiveExecutor 可能未初始化"
fi

echo ""
echo "=========================================="
echo "✅ 系统重启完成"
echo "=========================================="
echo ""
echo "监控命令:"
echo "  实时日志: tail -f data/polyarb-x.log"
echo "  主进程日志: tail -f data/main.log"
echo "  Dashboard: http://localhost:8089"
echo "  系统状态: curl http://localhost:8089/api/status"
echo ""
echo "预期日志输出:"
echo "  🔴 LiveExecutor initialized (REAL TRADING MODE - use_real_execution=True)"
echo "  🔴 REAL EXECUTION - Using CLOB API"
echo ""
