# Phase 0 监控指南 (Shadow Production - DRY_RUN)

**监控周期**: 7 天 (2026-02-02 至 2026-02-09)
**当前状态**: Phase 0 运行中 (DRY_RUN 模式)
**目标**: 验证系统稳定性和可靠性

---

## 📊 每日监控检查清单

### ✅ 每天早上（第 1 件事）

**1. 检查系统状态**
```bash
# 检查进程是否运行
ps -p 73941

# 查看运行时长
ps -p 73941 -o etime=

# 查看最新日志
tail -50 /tmp/polyarb_shadow.log
```

**2. 检查 Web UI**
```bash
# 访问 Dashboard
open http://localhost:8080/dashboard.html

# 检查服务是否运行
ps -p 77454
```

**3. 检查告警**
```bash
# 查看告警状态
cat data/alerts/alerts_state.json | python3 -m json.tool

# 或者访问 Web UI
open http://localhost:8080/alerts.html
```

---

## 📈 实时监控指标（每 2-4 小时检查一次）

### 1️⃣ 系统健康指标

#### ✅ WebSocket 连接状态
```bash
# 查看 WebSocket 日志
tail -100 /tmp/polyarb_shadow.log | grep -E "WebSocket|已连接|断开|Disconnected"

# 应该看到:
# ✅ "已连接到 Polymarket WebSocket"
# ✅ "正在监听订单本更新..."
# ❌ 不应该看到: "WebSocket 断开" 或 "连接失败"
```

**🔴 警告**: 如果看到 WebSocket 断开 > 1 次/天

---

#### ✅ 检查速率
```bash
# 查看最新统计
tail -50 /tmp/polyarb_shadow.log | grep "检查速率"

# 应该看到:
# ✅ 检查速率: 59-60 次/分钟
# 🔴 警告: < 50 次/分钟（系统有问题）
# 🔴 警告: > 65 次/分钟（可能异常）
```

---

#### ✅ 内存使用
```bash
# 查看内存使用
ps -p 73941 -o rss=

# 转换为 MB: RSS / 1024
# ✅ 正常: < 500 MB
# 🟡 注意: 500-1000 MB
# 🔴 警告: > 1000 MB（内存泄漏）
```

---

### 2️⃣ 市场数据指标

#### ✅ 市场订阅状态
```bash
# 查看订阅日志
tail -100 /tmp/polyarb_shadow.log | grep "Subscribed to"

# 应该看到:
# ✅ "Subscribed to 31 markets (62 tokens)"
```

**🔴 警告**: 如果市场数 < 31

---

#### ✅ 订单本更新
```bash
# 查看订单本更新频率
tail -f /tmp/polyarb_shadow.log | grep "订单本"

# 应该看到:
# ✅ 持续的订单本更新（每秒多次）
# 🟡 注意: 更新频率明显下降
# 🔴 警告: 长时间无更新（> 1 分钟）
```

---

### 3️⃣ 交易模拟指标

#### ✅ 检测机会
```bash
# 查看套利机会统计
tail -50 /tmp/polyarb_shadow.log | grep "检测机会"

# 应该看到:
# ✅ 检测机会: 0 或少量（套利机会稀少是正常的）
# ✅ 如果有: "发现套利机会" 日志
```

**说明**:
- 套利机会稀少是**正常的**，不是 bug
- Polymarket 流动性相对较低
- YES + NO < 1.0 的机会很少

---

#### ✅ 模拟成交
```bash
# 查看模拟成交记录
tail -50 /tmp/polyarb_shadow.log | grep "模拟成交"

# 如果 DRY_RUN_STALE 告警出现:
# ✅ 这是正常的: "No new activity in last 60s"
# 说明市场平静，无套利机会
```

---

### 4️⃣ PnL 跟踪指标

#### ✅ PnL 统计
```bash
# 查看 PnL 统计
tail -50 /tmp/polyarb_shadow.log | grep -E "预期收益|模拟PnL|实际PnL"

# Phase 0 应该显示:
# ✅ 累计预期收益: $0.0000 (或很小的值)
# ✅ 累计模拟PnL: $0.0000
# ✅ 累计实际PnL: $0.0000
```

**说明**: Phase 0 不执行真实交易，PnL 应该为 0

---

### 5️⃣ 告警监控

#### ✅ 查看活跃告警
```bash
# 方式 1: 查看告警状态文件
cat data/alerts/alerts_state.json | python3 -m json.tool

# 方式 2: 访问 Web UI
open http://localhost:8080/alerts.html

# 方式 3: 查看告警日志
tail -f data/alerts/alerts.jsonl
```

**关键告警**:
- 🔴 **CRITICAL**: 需要立即处理
  - `WS_DISCONNECTED` - WebSocket 断开
  - `LIVE_NO_FILLS` - 实盘无成交（Phase 0 不适用）
  - `CIRCUIT_BREAKER_OPEN` - 熔断器开启

- 🟡 **WARNING**: 需要注意
  - `DRY_RUN_NO_FILLS` - 干运行无成交（正常）
  - `RPC_UNHEALTHY` - RPC 不健康
  - `HIGH_REJECT_RATE` - 高拒绝率
  - `LATENCY_P95_HIGH` - 高延迟

---

## 🎯 每日生成报告

### 每天晚上生成日报

```bash
# 运行每日报告脚本
python3 scripts/production_daily_report.py

# 查看报告
cat reports/daily/$(date +%Y%m%d).md
```

**报告内容**:
- 运行模式
- 交易统计
- 订单执行情况
- 延迟统计 (P50, P95, P99)
- 告警总结
- 异常诊断

---

## 📋 Success Criteria 追踪

### 🎯 7 天目标检查表

打印或复制此清单，每天勾选完成情况:

```
=== Phase 0 Success Criteria 追踪 ===

Day 1 (2026-02-02): [ ] 运行中
Day 2 (2026-02-03): [ ] 运行中
Day 3 (2026-02-04): [ ] 运行中
Day 4 (2026-02-05): [ ] 运行中
Day 5 (2026-02-06): [ ] 运行中
Day 6 (2026-02-07): [ ] 运行中
Day 7 (2026-02-08): [ ] 运行中

=== 关键指标 ===

[ ] 系统无崩溃运行 7 天
[ ] WebSocket 稳定性 > 95%
[ ] 无 CRITICAL 告警
[ ] 完整日志记录
[ ] 熔断器正确触发（待测试）
[ ] PnL 计算准确（待验证）
[ ] P95 延迟 < 500ms
```

---

## 🔍 每周详细检查

### 每周日晚上（第 7 天）

**1. 系统稳定性**
```bash
# 计算运行时间
ps -p 73941 -o etime=

# 应该显示: 7-00:00:00 (7天)
```

**2. WebSocket 稳定性**
```bash
# 统计 WebSocket 断开次数
grep -i "websocket.*断开\|websocket.*disconnect" /tmp/polyarb_shadow.log | wc -l

# ✅ 目标: < 10 次 (7天)
# 计算: 7天 * 24小时 * 60分钟 = 10,080 分钟
# 稳定性 = (10080 - 断开次数) / 10080
# 目标: > 95%
```

**3. 告警统计**
```bash
# 统计 CRITICAL 告警
grep -c '"severity":"CRITICAL"' data/alerts/alerts.jsonl

# ✅ 目标: 0 次
```

```bash
# 统计 WARNING 告警
grep -c '"severity":"WARNING"' data/alerts/alerts.jsonl

# ✅ 目标: < 50 次
```

**4. 日志完整性**
```bash
# 检查事件日志
wc -l data/events.jsonl

# ✅ 目标: > 0 行（应该有大量记录）
```

```bash
# 检查日志文件大小
ls -lh /tmp/polyarb_shadow.log

# ✅ 目标: < 1 GB
```

**5. 延迟统计**
```bash
# 从每日报告中提取 P95 延迟
grep "P95" reports/daily/*.md

# ✅ 目标: P95 < 500ms
```

---

## ⚠️ 异常情况处理

### 🔴 CRITICAL - 立即处理

**1. 系统崩溃**
```bash
# 检查进程
ps -p 73941

# 如果进程不存在:
# 1. 查看崩溃日志
tail -100 /tmp/polyarb_shadow.log

# 2. 重启系统
bash scripts/start_shadow.sh
```

**2. WebSocket 长时间断开**
```bash
# 如果断开 > 5 分钟:
# 1. 检查网络
ping api.polymarket.com

# 2. 查看错误日志
tail -100 /tmp/polyarb_shadow.log | grep -i "error\|exception"

# 3. 重启系统
kill 73941
bash scripts/start_shadow.sh
```

**3. CRITICAL 告警**
```bash
# 查看告警详情
tail -20 data/alerts/alerts.jsonl | python3 -m json.tool

# 记录到文档
echo "$(date): CRITICAL alert - 查看日志" >> CRITICAL_INCIDENTS.md
```

---

### 🟡 WARNING - 关注处理

**1. RPC 不健康**
```bash
# 测试 RPC 连接
curl -s -X POST https://polygon-rpc.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# 应该返回: "0x89"
# 如果失败: RPC 可能有问题，但不影响 Phase 0
```

**2. 高延迟**
```bash
# 查看延迟统计
grep "P95" /tmp/polyarb_shadow.log | tail -10

# 如果 P95 > 500ms:
# - 记录到文档
# - 观察是否持续
# - 如果持续 > 1 天，考虑优化
```

---

## 📝 记录模板

### 每日观察日志

创建文件 `PHASE_0_DAILY_LOG.md`:

```markdown
# Phase 0 每日观察日志

## Day 1 - 2026-02-02

### 系统状态
- [ ] 进程运行正常
- [ ] Web UI 可访问
- [ ] WebSocket 连接稳定

### 观察到的现象
- 检测机会: 0 次
- 模拟成交: 0 次
- 套利机会稀少（正常）

### 告警情况
- CRITICAL: 0 次
- WARNING: X 次
  - `DRY_RUN_NO_FILLS` (正常)

### 问题和解决方案
- (记录任何问题)

### 备注
- (任何其他观察)
```

---

## 🎓 理解 Phase 0 的目标

### ✅ Phase 0 的目的

**1. 验证系统稳定性**
   - 系统能否 7×24 小时运行
   - WebSocket 连接是否稳定
   - 内存是否泄漏

**2. 验证监控和告警**
   - 告警是否正确触发
   - 日志是否完整记录
   - Web UI 是否正常更新

**3. 验证交易逻辑**
   - 套利检测是否正确
   - 模拟成交是否准确
   - PnL 计算是否正确

**4. 识别问题**
   - 发现潜在 bug
   - 优化性能瓶颈
   - 改进用户体验

### ❌ Phase 0 的限制

**不会执行真实交易**:
- DRY_RUN = true
- 不会消耗 GAS
- 不会使用真实资金

**套利机会稀少**:
- 这是市场特性，不是 bug
- Polymarket 流动性较低
- YES + NO < 1.0 的机会很少

---

## 🚀 进入 Phase 1 的条件

完成 Phase 0 后，如果满足以下条件，可以考虑进入 Phase 1:

### ✅ 必须满足

- [ ] 系统稳定运行 7 天，无崩溃
- [ ] WebSocket 稳定性 > 95%
- [ ] 7 天内无 CRITICAL 告警
- [ ] 日志记录完整（events.jsonl > 0 行）
- [ ] 理解系统行为和风险

### 🟡 建议满足

- [ ] P95 延迟 < 500ms
- [ ] WARNING 告警 < 50 次
- [ ] 完成至少 1 次熔断器测试
- [ ] 验证 PnL 计算准确性

---

## 📞 需要帮助？

**查看日志**:
```bash
tail -f /tmp/polyarb_shadow.log
```

**查看告警**:
```bash
open http://localhost:8080/alerts.html
```

**查看文档**:
- Production Plan: `docs/PRODUCTION_PLAN.md`
- Runbook: `docs/PRODUCTION_RUNBOOK.md`

**GitHub Issues**:
https://github.com/dapublockchain/Polymarket-bot/issues

---

**生成时间**: 2026-02-02
**Phase 0 开始时间**: 2026-02-02 21:24:28
**预计结束时间**: 2026-02-09 21:24:28

**祝 Phase 0 运行顺利！** 🎯
