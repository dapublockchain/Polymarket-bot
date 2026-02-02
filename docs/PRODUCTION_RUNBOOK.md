# PolyArb-X 生产运行手册 (Production Runbook)

**版本**: v1.0.0
**最后更新**: 2026-02-02
**适用阶段**: Phase 0-3

---

## 快速参考

### 紧急停止
```bash
# 立即停止交易
pkill -f "python3 src/main.py"

# 或者通过 API (如果 web server 运行中)
curl -X POST http://localhost:8083/api/emergency_stop
```

### 查看状态
```bash
# 查看进程
ps aux | grep "python3 src/main.py"

# 查看日志
tail -f data/polyarb-x.log

# 查看告警
curl http://localhost:8083/api/alerts/state
```

### 常用命令
```bash
# 启动 Shadow Production (Phase 0)
bash scripts/start_shadow.sh

# 启动 Live Safe (Phase 1)
bash scripts/start_live_safe.sh

# 备份当前状态
bash scripts/backup_state.sh

# 生成每日报告
python3 scripts/production_daily_report.py
```

---

## 第一章：系统启动

### 1.1 启动前检查清单

**每个阶段启动前必须执行 Go/No-Go 检查：**

```bash
# 执行完整检查
bash scripts/go_no_go_check.sh

# 查看检查结果
echo $?
# 0 = 通过 (GO)
# 非0 = 失败 (NO-GO)
```

**手动检查关键项：**
1. ✅ 确认 DRY_RUN 设置（Phase 0: true, Phase 1-3: false）
2. ✅ 确认 Profile 配置正确
3. ✅ 确认钱包余额充足
4. ✅ 确认 RPC 和 WS 连接正常
5. ✅ 确认告警规则已加载

### 1.2 启动 Phase 0 (Shadow Production)

```bash
# 1. 检查系统状态
bash scripts/go_no_go_check.sh

# 2. 启动系统（干运行模式）
bash scripts/start_shadow.sh

# 3. 验证启动成功
tail -f data/polyarb-x.log
# 应该看到: "Starting in DRY_RUN mode"
```

**预期行为：**
- 系统连接到 Polygon 和 Polymarket WebSocket
- 订阅市场数据流
- 发现套利机会但不执行交易
- 记录所有事件到 `data/events.jsonl`

### 1.3 启动 Phase 1 (Micro-Live)

```bash
# 1. 执行完整 Go/No-Go 检查
bash scripts/go_no_go_check.sh

# 2. 创建启动前备份
bash scripts/backup_state.sh

# 3. 启动系统（实盘模式，$2/trade）
bash scripts/start_live_safe.sh

# 4. 验证启动成功
tail -f data/polyarb-x.log
# 应该看到: "Starting in LIVE mode"
# 应该看到: "Profile: live_safe_atomic_v1"

# 5. 监控告警
curl http://localhost:8083/api/alerts/state
```

**预期行为：**
- 系统执行真实交易（极小资金）
- 每笔交易最大 $2
- 每日最大亏损 $3
- 触发风控自动停止

### 1.4 启动 Phase 2 (Constrained-Live)

```bash
# 1. 确认 Phase 1 Success Criteria 全部满足
# 2. 执行 Go/No-Go 检查
bash scripts/go_no_go_check.sh

# 3. 修改 Profile 为 live_constrained_atomic_v1
# 4. 创建备份
bash scripts/backup_state.sh

# 5. 启动系统（$5/trade）
# 注意：需要修改 start_live_safe.sh 中的 PROFILE_NAME
export PROFILE_NAME="live_constrained_atomic_v1"
bash scripts/start_live_safe.sh
```

### 1.5 启动 Phase 3 (Scaled-Live)

```bash
# 1. 确认 Phase 2 Success Criteria 全部满足
# 2. 执行 Go/No-Go 检查
bash scripts/go_no_go_check.sh

# 3. 修改 Profile 为 live_scaled_atomic_v1
# 4. 创建备份
bash scripts/backup_state.sh

# 5. 启动系统（$10-20/trade）
export PROFILE_NAME="live_scaled_atomic_v1"
bash scripts/start_live_safe.sh
```

---

## 第二章：日常操作

### 2.1 监控系统状态

**实时监控：**
```bash
# 查看日志（实时）
tail -f data/polyarb-x.log

# 查看告警状态（5 秒刷新）
watch -n 5 'curl -s http://localhost:8083/api/alerts/state | python3 -m json.tool'

# 查看活跃告警
curl http://localhost:8083/api/alerts/state | jq '.alerts[] | select(.state=="FIRING")'
```

**关键指标：**
- **WebSocket 连接状态**: 应该保持 `connected`
- **订单提交/成交比例**: 成交率应 > 50%
- **PnL**: 应该为正或小负（在允许范围内）
- **告警数量**: FIRING 告警应该 = 0

### 2.2 查看每日报告

**生成报告：**
```bash
# 生成今日报告
python3 scripts/production_daily_report.py

# 查看报告
cat reports/daily/$(date +%Y%m%d).md
```

**报告内容：**
- 运行模式与配置
- 交易统计（数量、胜率、PnL）
- 订单执行（提交、成交、拒绝率）
- 延迟统计（P50, P95, P99）
- 告警汇总
- 异常诊断

### 2.3 备份当前状态

**定期备份（推荐每日）：**
```bash
# 创建备份
bash scripts/backup_state.sh

# 查看备份列表
ls -lh backups/ | tail -10
```

**备份内容：**
- `config.yaml` - 当前配置
- `.env` - 环境变量（不含私钥）
- `data/events.jsonl` - 事件日志
- `data/audit/config_changes.jsonl` - 审计日志

### 2.4 更新配置

**切换 Profile：**
```bash
# 1. 停止系统
pkill -f "python3 src/main.py"

# 2. 创建备份
bash scripts/backup_state.sh

# 3. 应用新 Profile
curl -X POST http://localhost:8083/api/profiles/live_constrained_atomic_v1/apply

# 4. 验证配置变更
cat data/audit/config_changes.jsonl | tail -1 | python3 -m json.tool

# 5. 重启系统
bash scripts/start_live_safe.sh
```

**手动修改配置：**
```bash
# 1. 编辑 config.yaml
vim config/config.yaml

# 2. 验证 YAML 格式
python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# 3. 重启系统
pkill -f "python3 src/main.py"
bash scripts/start_live_safe.sh
```

---

## 第三章：告警处理

### 3.1 告警级别

**CRITICAL (立即处理):**
- `WS_DISCONNECTED` - WebSocket 断开 > 10 秒
- `LIVE_NO_FILLS` - 实盘有订单但无成交 > 60 秒
- `CIRCUIT_BREAKER_OPEN` - 熔断器开启

**WARNING (监控并处理):**
- `RPC_UNHEALTHY` - RPC 错误 > 5 (60 秒窗口)
- `HIGH_REJECT_RATE` - 订单拒绝率 > 5%
- `LATENCY_P95_HIGH` - P95 延迟 > 500ms
- `PNL_DRAWDOWN` - 回撤 > 阈值
- `LOW_BALANCE` - 余额 < $100
- `POSITION_LIMIT_NEAR` - 仓位使用率 > 90%

### 3.2 告警响应流程

**CRITICAL 告警处理：**
```bash
# 1. 立即停止交易
pkill -f "python3 src/main.py"

# 2. 查看告警详情
curl http://localhost:8083/api/alerts/state | python3 -m json.tool

# 3. 查看日志（最后 100 行）
tail -100 data/polyarb-x.log

# 4. 诊断问题
# 根据告警类型执行相应诊断（见下文）

# 5. 修复问题

# 6. 确认告警已解除
curl http://localhost:8083/api/alerts/state | jq '.alerts[] | select(.id=="WS_DISCONNECTED")'

# 7. 重启系统
bash scripts/start_live_safe.sh
```

**WARNING 告警处理：**
```bash
# 1. 监控告警状态
watch -n 10 'curl -s http://localhost:8083/api/alerts/state | jq ".alerts[]"'

# 2. 如果持续触发，升级为 CRITICAL 处理
# 3. 记录告警到日志

# 4. 确认告警（ACK）
curl -X POST http://localhost:8083/api/alerts/{alert_id}/ack
```

### 3.3 常见告警诊断

**WS_DISCONNECTED (WebSocket 断开)**
```bash
# 1. 检查网络连接
ping ws-subscriptions-clob.polymarket.com

# 2. 检查 DNS 解析
nslookup ws-subscriptions-clob.polymarket.com

# 3. 查看日志中的错误
grep "WebSocket" data/polyarb-x.log | tail -20

# 4. 如果频繁断开，可能是网络不稳定或 Polymarket 服务问题
# 解决：等待网络恢复，或联系 Polymarket 支持
```

**LIVE_NO_FILLS (实盘无成交)**
```bash
# 1. 检查是否提交了订单
grep "order_submitted" data/events.jsonl | tail -10

# 2. 检查订单是否被拒绝
grep "order_rejected" data/events.jsonl | tail -10

# 3. 检查滑点设置
grep "MAX_SLIPPAGE" config/config.yaml

# 4. 可能原因：
# - 滑点设置过严
# - Gas 价格太低
# - 市场流动性不足
# 解决：调整 MAX_SLIPPAGE 或 MAX_GAS_PRICE
```

**CIRCUIT_BREAKER_OPEN (熔断器开启)**
```bash
# 1. 查看熔断原因
grep "circuit_breaker" data/polyarb-x.log | tail -20

# 2. 检查连续失败次数
grep "consecutive_failures" data/events.jsonl | tail -10

# 3. 可能原因：
# - RPC 问题
# - 私钥余额不足
# - Gas 价格飙升
# 解决：修复问题后，手动重置熔断器
```

**HIGH_REJECT_RATE (高拒绝率)**
```bash
# 1. 检查拒绝原因
grep "order_rejected" data/events.jsonl | tail -20

# 2. 常见原因：
# - 滑点超限
# - Gas 不足
# - 余额不足
# - 价格变动过快

# 3. 解决：
# - 调整 MAX_SLIPPAGE（提高容忍度）
# - 提高 MAX_GAS_COST
# - 增加钱包余额
```

**LATENCY_P95_HIGH (高延迟)**
```bash
# 1. 检查 RPC 延迟
grep "rpc_latency" data/events.jsonl | jq -r '.latency' | tail -100 | sort -n | tail -10

# 2. 测试 RPC 节点
time curl -X POST https://polygon-rpc.com -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# 3. 可能原因：
# - RPC 节点过载
# - 网络延迟
# - 本地系统负载高

# 4. 解决：
# - 切换到备用 RPC 节点
# - 使用付费 RPC 服务（Alchemy/Infura）
```

### 3.4 告警确认 (ACK)

```bash
# 确认告警（标记为已读）
curl -X POST http://localhost:8083/api/alerts/WS_DISCONNECTED/ack

# 查看已确认的告警
curl http://localhost:8083/api/alerts/state | jq '.alerts[] | select(.state=="ACKED")'
```

---

## 第四章：应急程序

### 4.1 紧急停止交易

**场景：发现严重问题，需要立即停止**

```bash
# 方法 1: 直接 kill 进程
pkill -9 -f "python3 src/main.py"

# 方法 2: 通过 API（如果可用）
curl -X POST http://localhost:8083/api/emergency_stop

# 验证进程已停止
ps aux | grep "python3 src/main.py"
```

### 4.2 紧急撤资

**场景：发现安全问题，需要立即转移资金**

```bash
# 1. 立即停止系统
pkill -9 -f "python3 src/main.py"

# 2. 使用钱包工具（如 MetaMask/Schrodinger）连接生产钱包

# 3. 将所有 USDC 转移到安全钱包

# 4. 撤销 CTF Exchange 合约的 allowance
# 使用 etherscan/revoke.cow 等工具

# 5. 保存私钥到安全位置（如果尚未存储）

# 6. 分析问题原因
# 7. 修复问题后，使用新钱包重新启动
```

### 4.3 回滚到上一份配置

**场景：新配置导致问题，需要快速回滚**

```bash
# 1. 停止系统
pkill -f "python3 src/main.py"

# 2. 查看审计历史
cat data/audit/config_changes.jsonl | tail -5 | python3 -m json.tool

# 3. 回滚到上一份配置
curl -X POST http://localhost:8083/api/profiles/rollback

# 4. 验证配置已恢复
cat config/config.yaml

# 5. 重启系统
bash scripts/start_live_safe.sh
```

### 4.4 从备份恢复

**场景：系统崩溃，需要从备份恢复**

```bash
# 1. 停止系统（如果还在运行）
pkill -f "python3 src/main.py"

# 2. 选择最近的备份
ls -lht backups/ | head -5

# 3. 恢复配置文件
cp backups/20260202_1200/config.yaml config/config.yaml

# 4. 恢复数据文件（可选）
cp backups/20260202_1200/data/events.jsonl data/events.jsonl

# 5. 验证恢复
python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# 6. 重启系统
bash scripts/start_live_safe.sh
```

---

## 第五章：故障排查

### 5.1 系统无法启动

**症状：执行 start_shadow.sh 或 start_live_safe.sh 后立即退出**

```bash
# 1. 查看详细错误
bash scripts/start_shadow.sh 2>&1 | tee /tmp/start_error.log

# 2. 常见原因：
# - config.yaml 不存在或格式错误
# - Profile 文件不存在
# - 私钥未设置
# - 端口被占用

# 3. 诊断步骤：
# 检查 config.yaml
python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# 检查 Profile
ls -l config/profiles/live_*.yaml

# 检查私钥
echo $PRIVATE_KEY  # 应该不为空

# 检查端口
lsof -i :8083  # 如果占用，kill 进程
```

### 5.2 订单无法成交

**症状：系统提交订单但无成交记录**

```bash
# 1. 检查订单提交
grep "order_submitted" data/events.jsonl | tail -10

# 2. 检查订单拒绝
grep "order_rejected" data/events.jsonl | tail -10

# 3. 检查滑点设置
grep "MAX_SLIPPAGE" config/config.yaml

# 4. 检查 Gas 价格
grep "MAX_GAS_PRICE" config/config.yaml

# 5. 常见原因：
# - 滑点设置过严（提高 MAX_SLIPPAGE）
# - Gas 价格太低（提高 MAX_GAS_PRICE）
# - 市场流动性不足（等待或切换市场）
```

### 5.3 WebSocket 频繁断线

**症状：WS_DISCONNECTED 告警频繁触发**

```bash
# 1. 检查网络连接
ping -c 10 ws-subscriptions-clob.polymarket.com

# 2. 检查日志中的 WS 错误
grep "WebSocket" data/polyarb-x.log | tail -50

# 3. 检查重连配置
grep "WS_RECONNECT" config/config.yaml

# 4. 可能原因：
# - 网络不稳定
# - Polymarket WS 服务问题
# - 防火墙/代理问题

# 5. 解决：
# - 检查网络稳定性
# - 联系 Polymarket 支持
# - 调整重连参数
```

### 5.4 RPC 调用失败

**症状：RPC_UNHEALTHY 告警触发**

```bash
# 1. 测试 RPC 节点
curl -X POST https://polygon-rpc.com \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# 2. 检查 RPC URL 配置
grep "POLYGON_RPC_URL" config/config.yaml

# 3. 可能原因：
# - RPC 节点过载
# - RPC 节点故障
# - 网络问题

# 4. 解决：
# - 切换到备用 RPC 节点
# - 使用付费 RPC 服务（Alchemy/Infura）
# - 配置多个 RPC 节点（负载均衡）
```

---

## 第六章：性能优化

### 6.1 降低延迟

**目标：P95 延迟 < 500ms**

```bash
# 1. 使用更快的 RPC 节点
# 配置 Alchemy 或 Infura（付费）

# 2. 启用 WebSocket RPC（如果支持）
# 修改 POLYGON_RPC_URL 为 wss://

# 3. 优化本地处理
# - 减少日志输出（LOG_LEVEL=WARNING）
# - 禁用不必要的策略

# 4. 监控延迟
grep "latency" data/events.jsonl | jq -r '.latency' | awk '{sum+=$1; count++} END {print "Avg:", sum/count}'
```

### 6.2 提高成交率

**目标：成交率 > 60%**

```bash
# 1. 调整滑点容忍度
# 编辑 config.yaml
MAX_SLIPPAGE: "0.03"  # 提高到 3%

# 2. 提高 Gas 价格
MAX_GAS_PRICE: 600000000000  # 600 gwei

# 3. 优化订单大小
# 不要使用过大或过小的订单
TRADE_SIZE: "5"  # $5 per trade

# 4. 监控成交率
echo "Total orders: $(grep 'order_submitted' data/events.jsonl | wc -l)"
echo "Filled orders: $(grep 'order_filled' data/events.jsonl | wc -l)"
```

### 6.3 减少 Gas 成本

**目标：Gas 成本 < $0.5 per trade**

```bash
# 1. 使用 EIP-1559 动态 Gas
GAS_PRICE_MODE: "eip1559"

# 2. 设置合理的 Gas 限制
GAS_LIMIT_MULTIPLIER: 1.1  # 增加 10%

# 3. 避免 Gas 价格峰值
# 在 Gas 价格低时交易（使用 Gas Price Oracle）

# 4. 监控 Gas 成本
grep "gas_cost" data/events.jsonl | jq -r '.gas_cost' | awk '{sum+=$1; count++} END {print "Avg:", sum/count}'
```

---

## 第七章：日常维护

### 7.1 每日任务

- [ ] 检查系统状态（日志、告警）
- [ ] 生成并查看每日报告
- [ ] 验证 PnL 在预期范围内
- [ ] 检查钱包余额
- [ ] 创建备份（如果配置有重大变更）

### 7.2 每周任务

- [ ] 回顾本周交易数据
- [ ] 分析告警趋势
- [ ] 优化参数配置（如果需要）
- [ ] 清理旧日志文件（保留最近 30 天）
- [ ] �验查备份恢复流程

### 7.3 每月任务

- [ ] 评估是否进入下一阶段
- [ ] 全面性能审计
- [ ] 安全审计（私钥、allowance）
- [ ] 更新文档（PRODUCTION_PLAN.md）
- [ ] 团队复盘会议

---

## 第八章：联系支持

### 8.1 紧急联系

- **技术负责人**: [姓名] - [电话/即时通讯]
- **安全负责人**: [姓名] - [电话/即时通讯]
- **紧急邮箱**: [邮箱地址]

### 8.2 Bug 报告

- **GitHub Issues**: https://github.com/dapublockchain/Polymarket-bot/issues
- **报告模板**:
  ```
  ## 问题描述
  [简要描述问题]

  ## 复现步骤
  1. ...
  2. ...

  ## 期望行为
  [应该发生什么]

  ## 实际行为
  [实际发生了什么]

  ## 日志
  ```
  tail -100 data/polyarb-x.log
  ```

  ## 环境
  - Phase: [0/1/2/3]
  - Profile: [live_safe_atomic_v1]
  - 版本: [git commit hash]
  ```

### 8.3 资源链接

- **项目主页**: https://github.com/dapublockchain/Polymarket-bot
- **生产计划**: `docs/PRODUCTION_PLAN.md`
- **Go/No-Go 检查清单**: `docs/GO_NO_GO_CHECKLIST.md`
- **告警规则**: `config/alerts.production.yaml`

---

**最后更新**: 2026-02-02
**文档版本**: v1.0.0
**维护者**: PolyArb-X Team
