#!/bin/bash
# PolyArb-X Web监控界面启动脚本

echo "================================"
echo " PolyArb-X Web监控界面"
echo "================================"
echo ""

# 检查端口
PORT=8080
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo "⚠️  端口 $PORT 已被占用"
    echo "   尝试使用端口 8081..."
    PORT=8081
fi

echo "🚀 启动Web服务器..."
echo "📊 访问地址: http://localhost:$PORT"
echo ""
echo "提示: 按 Ctrl+C 停止服务器"
echo ""

# 启动服务器
python3 ui/web_server.py --port $PORT
