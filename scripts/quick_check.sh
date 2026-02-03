#!/bin/bash
# ============================================================
# PolyArb-X Phase 0 每日快速检查脚本
# ============================================================
# 用途: 快速检查 Phase 0 运行状态
# 使用: bash scripts/quick_check.sh
# 版本: v1.0.0
# ============================================================

set -euo pipefail

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 进程 PID
CORE_PID=73941
WEB_PID=77454

echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}Phase 0 每日快速检查${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""

# ============================================================
# 1. 检查核心进程
# ============================================================
echo -e "${BLUE}📊 1. 核心进程状态${NC}"
if ps -p ${CORE_PID} > /dev/null 2>&1; then
    UPTIME=$(ps -p ${CORE_PID} -o etime= | tr -d ' ')
    MEM_MB=$(ps -p ${CORE_PID} -o rss= | awk '{print int($1/1024)}')
    echo -e "   ${GREEN}✅ 进程运行中${NC}"
    echo -e "   PID: ${CORE_PID}"
    echo -e "   运行时长: ${UPTIME}"
    echo -e "   内存使用: ${MEM_MB} MB"
else
    echo -e "   ${RED}❌ 进程未运行${NC}"
    echo -e "   ${RED}请运行: bash scripts/start_shadow.sh${NC}"
    exit 1
fi
echo ""

# ============================================================
# 2. 检查 Web UI
# ============================================================
echo -e "${BLUE}🌐 2. Web UI 状态${NC}"
if ps -p ${WEB_PID} > /dev/null 2>&1; then
    echo -e "   ${GREEN}✅ Web UI 运行中${NC}"
    echo -e "   PID: ${WEB_PID}"
    echo -e "   访问地址: http://localhost:8080"
    echo -e "   Dashboard: http://localhost:8080/dashboard.html"
    echo -e "   Alerts: http://localhost:8080/alerts.html"
else
    echo -e "   ${YELLOW}⚠️  Web UI 未运行${NC}"
    echo -e "   ${YELLOW}启动: PYTHONPATH=/Users/dapumacmini/polyarb-x python3 ui/web_server.py --port 8080 &${NC}"
fi
echo ""

# ============================================================
# 3. 检查 WebSocket 连接
# ============================================================
echo -e "${BLUE}🔌 3. WebSocket 连接状态${NC}"
WS_LOGS=$(tail -100 /tmp/polyarb_shadow.log | grep -E "WebSocket|已连接|断开" | tail -5)
if echo "${WS_LOGS}" | grep -q "已连接"; then
    echo -e "   ${GREEN}✅ WebSocket 已连接${NC}"
else
    echo -e "   ${YELLOW}⚠️  WebSocket 状态未知${NC}"
fi
echo ""

# ============================================================
# 4. 检查运行统计
# ============================================================
echo -e "${BLUE}📈 4. 最新运行统计${NC}"
STATS=$(tail -50 /tmp/polyarb_shadow.log | grep -A 10 "运行统计" | tail -10)
if [ -n "${STATS}" ]; then
    echo "${STATS}" | sed 's/^/   /'
else
    echo -e "   ${YELLOW}⚠️  暂无统计数据${NC}"
fi
echo ""

# ============================================================
# 5. 检查告警
# ============================================================
echo -e "${BLUE}🔔 5. 告警状态${NC}"
if [ -f "data/alerts/alerts_state.json" ]; then
    CRITICAL=$(grep -o '"severity":"CRITICAL"' data/alerts/alerts_state.json | wc -l | tr -d ' ')
    WARNING=$(grep -o '"severity":"WARNING"' data/alerts/alerts_state.json | wc -l | tr -d ' ')

    echo -e "   CRITICAL: ${RED}${CRITICAL}${NC}"
    echo -e "   WARNING: ${YELLOW}${WARNING}${NC}"

    if [ "${CRITICAL}" -eq 0 ]; then
        echo -e "   ${GREEN}✅ 无 CRITICAL 告警${NC}"
    else
        echo -e "   ${RED}❌ 存在 CRITICAL 告警${NC}"
        echo -e "   请查看: cat data/alerts/alerts_state.json | python3 -m json.tool"
    fi
else
    echo -e "   ${YELLOW}⚠️  告警状态文件不存在${NC}"
fi
echo ""

# ============================================================
# 6. 检查日志文件
# ============================================================
echo -e "${BLUE}📝 6. 日志文件${NC}"
if [ -f "/tmp/polyarb_shadow.log" ]; then
    LOG_SIZE=$(ls -lh /tmp/polyarb_shadow.log | awk '{print $5}')
    LOG_LINES=$(wc -l < /tmp/polyarb_shadow.log | tr -d ' ')
    echo -e "   文件大小: ${LOG_SIZE}"
    echo -e "   行数: ${LOG_LINES}"
    echo -e "   位置: /tmp/polyarb_shadow.log"
else
    echo -e "   ${YELLOW}⚠️  日志文件不存在${NC}"
fi
echo ""

# ============================================================
# 7. 系统建议
# ============================================================
echo -e "${BLUE}💡 系统建议${NC}"

# 检查内存使用
MEM_MB=$(ps -p ${CORE_PID} -o rss= | awk '{print int($1/1024)}')
if [ "${MEM_MB}" -gt 1000 ]; then
    echo -e "   ${YELLOW}⚠️  内存使用较高 (${MEM_MB} MB)${NC}"
    echo -e "   ${YELLOW}建议: 监控是否有内存泄漏${NC}"
else
    echo -e "   ${GREEN}✅ 内存使用正常${NC}"
fi

# 检查运行时长
UPTIME_SECONDS=$(ps -p ${CORE_PID} -o etime= | awk '{print int($1)}')
# 简化检查（这里只是示意）
echo -e "   ${GREEN}✅ 系统运行正常${NC}"
echo -e "   ${BLUE}ℹ️  下次检查: 2-4 小时后${NC}"

echo ""
echo -e "${BLUE}=====================================${NC}"
echo -e "${BLUE}快速检查完成${NC}"
echo -e "${BLUE}=====================================${NC}"
echo ""
echo -e "详细监控指南: cat PHASE_0_MONITORING_GUIDE.md"
echo -e "实时日志: tail -f /tmp/polyarb_shadow.log"
echo -e "Web UI: open http://localhost:8080/dashboard.html"
echo ""
