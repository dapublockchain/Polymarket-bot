#!/bin/bash
# ============================================================
# PolyArb-X State Backup Script
# ============================================================
# 用途: 备份当前系统状态（配置、数据、日志）
# 版本: v1.0.0
# 最后更新: 2026-02-02
# ============================================================

set -euo pipefail

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ============================================================
# 配置
# ============================================================
BACKUP_ROOT_DIR="backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M")
BACKUP_DIR="${BACKUP_ROOT_DIR}/${TIMESTAMP}"

# 创建备份目录
mkdir -p "${BACKUP_DIR}"

echo "💾 Creating backup: ${BACKUP_DIR}"

# ============================================================
# 备份配置文件
# ============================================================
echo "  - Backing up config files..."

if [ -f "config/config.yaml" ]; then
    cp config/config.yaml "${BACKUP_DIR}/config.yaml"
fi

# 注意：不备份 .env 文件（可能包含敏感信息）
# 但备份 .env.example（如果存在）
if [ -f ".env.example" ]; then
    cp .env.example "${BACKUP_DIR}/.env.example"
fi

# ============================================================
# 备份 Profile 配置
# ============================================================
echo "  - Backing up profile files..."

if [ -d "config/profiles" ]; then
    mkdir -p "${BACKUP_DIR}/profiles"
    cp -r config/profiles/*.yaml "${BACKUP_DIR}/profiles/" 2>/dev/null || true
fi

# ============================================================
# 备份告警配置
# ============================================================
echo "  - Backing up alert configs..."

if [ -f "config/alerts.yaml" ]; then
    cp config/alerts.yaml "${BACKUP_DIR}/alerts.yaml"
fi

if [ -f "config/alerts.production.yaml" ]; then
    cp config/alerts.production.yaml "${BACKUP_DIR}/alerts.production.yaml"
fi

# ============================================================
# 备份数据文件
# ============================================================
echo "  - Backing up data files..."

mkdir -p "${BACKUP_DIR}/data"

# Events 日志（如果文件太大，只备份最近部分）
if [ -f "data/events.jsonl" ]; then
    # 只备份最后 10000 行
    tail -10000 data/events.jsonl > "${BACKUP_DIR}/data/events.jsonl"
fi

# 审计日志
if [ -f "data/audit/config_changes.jsonl" ]; then
    mkdir -p "${BACKUP_DIR}/data/audit"
    cp data/audit/config_changes.jsonl "${BACKUP_DIR}/data/audit/"
fi

# 告警日志
if [ -f "data/alerts/alerts.jsonl" ]; then
    mkdir -p "${BACKUP_DIR}/data/alerts"
    cp data/alerts/alerts.jsonl "${BACKUP_DIR}/data/alerts/"
fi

# 告警状态
if [ -f "data/alerts/alerts_state.json" ]; then
    cp data/alerts/alerts_state.json "${BACKUP_DIR}/data/alerts/"
fi

# ============================================================
# 创建备份元数据
# ============================================================
echo "  - Creating backup metadata..."

cat > "${BACKUP_DIR}/metadata.json" << EOF
{
  "timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "timestamp_local": "$(date)",
  "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
  "git_branch": "$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo 'unknown')",
  "hostname": "$(hostname)",
  "user": "$(whoami)"
}
EOF

# ============================================================
# 压缩备份（可选）
# ============================================================
# 如果需要节省空间，可以压缩备份
# tar -czf "${BACKUP_DIR}.tar.gz" -C "${BACKUP_ROOT_DIR}" "$(basename ${BACKUP_DIR})"
# rm -rf "${BACKUP_DIR}"
# BACKUP_DIR="${BACKUP_DIR}.tar.gz"

# ============================================================
# 完成
# ============================================================
echo ""
echo -e "${GREEN}✅ Backup created successfully${NC}"
echo "  Location: ${BACKUP_DIR}"
echo ""

# 显示备份大小
if [ -d "${BACKUP_DIR}" ]; then
    BACKUP_SIZE=$(du -sh "${BACKUP_DIR}" | cut -f1)
    echo "  Size: ${BACKUP_SIZE}"
fi

# ============================================================
# 清理旧备份（可选）
# ============================================================
# 只保留最近 7 天的备份
echo ""
echo "🧹 Cleaning up old backups (keeping last 7 days)..."

find "${BACKUP_ROOT_DIR}" -maxdepth 1 -type d -name "20*" -mtime +7 -exec rm -rf {} \; 2>/dev/null || true

echo -e "${GREEN}✅ Cleanup complete${NC}"
