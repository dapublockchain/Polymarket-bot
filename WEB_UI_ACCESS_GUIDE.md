# 🌐 PolyArb-X v5.0.0 - Web UI 访问指南

**启动时间**: $(date '+%Y-%m-%d %H:%M:%S')
**Web 服务器**: ✅ **运行中**
**端口**: 8080
**PID**: 77454

---

## ✅ 服务器状态

```
进程 ID: 77454
状态: 运行中 (SN - 睡眠状态)
端口: 8080 (HTTP)
监听地址: 0.0.0.0:8080
运行时长: 约 15 秒
```

---

## 🌐 访问地址

### 本地访问

```
主 Dashboard:    http://localhost:8080/dashboard.html
配置模板管理:    http://localhost:8080/profiles.html
告警中心:       http://localhost:8080/alerts.html
```

### 网络访问

```
主 Dashboard:    http://0.0.0.0:8080/dashboard.html
配置模板管理:    http://0.0.0.0:8080/profiles.html
告警中心:       http://0.0.0.0:8080/alerts.html
```

---

## 📊 可用页面

### 1. 主 Dashboard

**URL**: `http://localhost:8080/dashboard.html`

**功能**:
- 📊 系统状态概览
- 💰 实时 PnL 显示
- 📈 交易统计
- 🔔 告警通知
- 🎯 配置信息

**适用场景**:
- 快速查看系统状态
- 监控整体运行情况
- 查看关键指标

### 2. 配置模板管理 (Profiles)

**URL**: `http://localhost:8080/profiles.html`

**功能**:
- ✅ 7 个内置配置模板卡片
- ✅ 查看配置详情
- ✅ 预览配置差异
- ✅ 一键应用配置
- ✅ 风险确认弹窗
- ✅ 自定义配置保存
- ✅ 配置回滚
- ✅ 审计历史时间线

**内置模板**:
1. `conservative` - 保守型（小仓位、高阈值）
2. `balanced` - 平衡型（默认配置）
3. `aggressive` - 激进型（大仓位、低阈值）
4. `maker` - 做市商型（post-only）
5. `taker` - 接单型（快速成交）
6. `sandbox` - 沙盒测试（极小仓位）
7. `live_safe` - 实盘安全（Phase 1）

**生产配置**:
1. `live_shadow_atomic_v1` - Phase 0 Shadow (DRY_RUN)
2. `live_safe_atomic_v1` - Phase 1 Micro-Live ($2/trade)
3. `live_constrained_atomic_v1` - Phase 2 Constrained ($5/trade)
4. `live_scaled_atomic_v1` - Phase 3 Scaled ($10-20/trade)

**使用方法**:
1. 浏览配置卡片
2. 点击"查看详情"查看差异
3. 点击"应用配置"（如有风险需确认）
4. 查看"审计历史"了解变更记录

### 3. 告警中心 (Alerts)

**URL**: `http://localhost:8080/alerts.html`

**功能**:
- ✅ 告警规则列表（10 个规则）
- ✅ 告警时间线（FIRING/RESOLVED/ACKED）
- ✅ 活跃告警统计
- ✅ 实时轮询（5 秒）
- ✅ 告警确认（ACK）功能
- ✅ 严重性颜色编码

**内置规则** (10 个):
- `WS_DISCONNECTED` - WebSocket 断开 (CRITICAL)
- `RPC_UNHEALTHY` - RPC 不健康 (WARNING)
- `DRY_RUN_NO_FILLS` - 干运行无成交 (WARNING)
- `LIVE_NO_FILLS` - 实盘无成交 (CRITICAL)
- `HIGH_REJECT_RATE` - 高拒绝率 (WARNING)
- `LATENCY_P95_HIGH` - 高延迟 (WARNING)
- `CIRCUIT_BREAKER_OPEN` - 熔断器开启 (CRITICAL)
- `LOW_BALANCE` - 低余额 (WARNING)
- `POSITION_LIMIT_NEAR` - 仓位接近上限 (WARNING)
- `PNL_DRAWDOWN` - 回撤过大 (WARNING)

**使用方法**:
1. 查看活跃告警统计
2. 浏览告警规则列表
3. 查看告警时间线
4. 点击"ACK"确认告警

---

## 🔌 API 端点

### Profiles API

#### 列出所有配置
```bash
GET http://localhost:8080/api/profiles
```

**响应示例**:
```json
{
  "profiles": [
    {
      "name": "conservative",
      "tags": ["low-risk", "small-position"],
      "description": "保守型配置",
      "is_custom": false
    }
  ],
  "count": 11,
  "status": "ok"
}
```

#### 获取配置详情
```bash
GET http://localhost:8080/api/profiles/{name}
```

**示例**:
```bash
curl http://localhost:8080/api/profiles/conservative
```

#### 应用配置
```bash
POST http://localhost:8080/api/profiles/{name}/apply
```

**示例**:
```bash
curl -X POST http://localhost:8080/api/profiles/sandbox/apply
```

**响应**:
```json
{
  "success": true,
  "result": {
    "profile_name": "sandbox",
    "applied_at": "2026-02-02T21:30:00",
    "diff": {
      "MIN_PROFIT_THRESHOLD": {"old": "0.01", "new": "0.05"}
    },
    "risk_warnings": []
  }
}
```

#### 保存自定义配置
```bash
POST http://localhost:8080/api/profiles/save
Content-Type: application/json

{
  "name": "my_custom_profile",
  "description": "My custom settings",
  "tags": ["custom"],
  "config_override": {
    "TRADE_SIZE": "3",
    "MIN_PROFIT_THRESHOLD": "0.012"
  }
}
```

#### 回滚配置
```bash
POST http://localhost:8080/api/profiles/rollback
```

#### 审计历史
```bash
GET http://localhost:8080/api/audit/config_changes?limit=50
```

---

## 🎨 UI 特性

### 配置模板页面

1. **现代化设计**
   - 渐变背景
   - 卡片式布局
   - 悬停动画
   - 响应式设计

2. **智能功能**
   - 自动风险检测
   - 差异预览
   - 一键应用
   - 风险确认弹窗

3. **实时反馈**
   - Toast 通知
   - 加载动画
   - 状态指示器

### 告警中心页面

1. **双面板布局**
   - 左侧：告警规则列表
   - 右侧：告警时间线

2. **实时更新**
   - 5 秒自动轮询
   - 页面隐藏时暂停
   - FIRING 告警脉冲动画

3. **视觉辅助**
   - 严重性颜色编码（红/黄/蓝）
   - 状态标签（FIRING/RESOLVED/ACKED）
   - 统计卡片

---

## 📱 快速开始

### 1. 打开浏览器

访问主 Dashboard:
```
http://localhost:8080/dashboard.html
```

### 2. 查看配置模板

```
http://localhost:8080/profiles.html
```

**操作步骤**:
1. 浏览 11 个配置模板
2. 点击"查看详情"预览差异
3. 点击"应用配置"（如有风险需确认）
4. 查看"审计历史"了解变更

### 3. 监控告警

```
http://localhost:8080/alerts.html
```

**操作步骤**:
1. 查看活跃告警统计
2. 浏览告警规则列表
3. 查看告警时间线
4. 点击"ACK"确认告警

---

## 🔧 管理命令

### 重启 Web 服务器

```bash
# 停止当前服务器
kill 77454

# 重新启动
PYTHONPATH=/Users/dapumacmini/polyarb-x python3 ui/web_server.py --port 8080 &
```

### 停止 Web 服务器

```bash
kill 77454
```

### 查看服务器日志

```bash
tail -f /tmp/web_server.log
```

### 更改端口

```bash
# 使用 8081 端口
PYTHONPATH=/Users/dapumacmini/polyarb-x python3 ui/web_server.py --port 8081 &
```

---

## 🎯 使用场景

### 场景 1: 切换到保守型配置

1. 访问 `http://localhost:8080/profiles.html`
2. 找到 `conservative` 配置卡片
3. 点击"查看详情"
4. 查看配置差异
5. 点击"应用配置"
6. 确认变更

**效果**:
- 最小利润阈值: 1% → 2%
- 最大仓位: $1000 → $200
- 交易规模: $10 → $5

### 场景 2: 切换到沙盒测试

1. 访问 `http://localhost:8080/profiles.html`
2. 找到 `sandbox` 配置卡片
3. 点击"应用配置"
4. 查看配置差异（11 个字段变更）

**效果**:
- DRY_RUN: 保持 true
- 最小利润阈值: 1% → 5%
- 最大仓位: $1000 → $50
- 交易规模: $10 → $1

### 场景 3: 查看告警历史

1. 访问 `http://localhost:8080/alerts.html`
2. 查看活跃告警统计
3. 浏览告警时间线
4. 确认已解决的告警

---

## 🔍 故障排查

### 页面无法访问

**问题**: 浏览器显示"无法访问此网站"

**解决方案**:
```bash
# 检查服务器是否运行
ps -p 77454

# 检查端口是否监听
lsof -i:8080

# 查看服务器日志
tail -20 /tmp/web_server.log
```

### API 返回 404

**问题**: API 端点返回 404

**解决方案**:
- 确认 URL 路径正确
- 检查配置文件是否存在
- 查看服务器日志

### 配置无法应用

**问题**: 点击"应用配置"后无响应

**解决方案**:
1. 打开浏览器开发者工具 (F12)
2. 查看 Console 错误信息
3. 查看 Network 标签页请求详情
4. 检查配置文件权限

---

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         Browser                             │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│  │Dashboard │  │Profiles  │  │ Alerts   │                   │
│  │  Page    │  │  Page    │  │  Page    │                   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘                   │
│       │             │              │                          │
│       └─────────────┴──────────────┘                          │
│                     │                                        │
│                     ▼                                        │
│           ┌─────────────────────┐                            │
│           │   HTTP (Port 8080)  │                            │
│           └─────────┬───────────┘                            │
│                     │                                        │
│                     ▼                                        │
│  ┌────────────────────────────────────────────┐              │
│  │       Web Server (Python)                  │              │
│  │  - SimpleHTTPRequestHandler               │              │
│  │  - PolyArbAPIHandler                      │              │
│  │  - Profile Manager                        │              │
│  └──────────────┬─────────────────────────────┘              │
│                 │                                             │
│                 ▼                                             │
│  ┌────────────────────────────────────────────┐              │
│  │       Configuration Files                  │              │
│  │  - config/config.yaml                     │              │
│  │  - config/profiles/*.yaml                 │              │
│  │  - data/audit/config_changes.jsonl        │              │
│  └────────────────────────────────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎉 总结

```
╔══════════════════════════════════════════════════════════════╗
║                                                                ║
║   🌐 Web UI 服务器已启动                                       ║
║                                                                ║
║   端口: 8080                                                   ║
║   状态: ✅ 运行中                                              ║
║   PID: 77454                                                  ║
║                                                                ║
║   📊 主 Dashboard:                                             ║
║      http://localhost:8080/dashboard.html                     ║
║                                                                ║
║   ⚙️ 配置模板管理:                                             ║
║      http://localhost:8080/profiles.html                      ║
║                                                                ║
║   🔔 告警中心:                                                ║
║      http://localhost:8080/alerts.html                        ║
║                                                                ║
║   🎯 立即在浏览器中打开上述地址即可访问！                      ║
║                                                                ║
╚══════════════════════════════════════════════════════════════╝
```

---

## 📞 支持

- **UI 使用指南**: 本文档
- **API 文档**: README.md (API 端点部分)
- **故障排查**: `docs/PRODUCTION_RUNBOOK.md` 第五章
- **GitHub**: https://github.com/dapublockchain/Polymarket-bot

---

**生成时间**: $(date '+%Y-%m-%d %H:%M:%S')
**版本**: v5.0.0
**状态**: ✅ **运行中**

**🚀 Web UI 已就绪，请在浏览器中打开！**
