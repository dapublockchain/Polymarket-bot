# PolyArb-X 生产上线计划

**版本**: v1.0.0
**最后更新**: 2026-02-02
**状态**: Phase 0 (Shadow Production)

---

## 总体策略

### 核心原则
1. **小步快跑**: 分 4 个阶段逐步放量
2. **可回滚**: 每个阶段都有明确的 rollback criteria
3. **数据驱动**: 基于真实数据决策是否进入下一阶段
4. **风险优先**: 资金安全 > 收益

### 默认配置
- **初始资金**: $100 USD
- **交易策略**: Atomic Arbitrage ONLY (YES + NO < 1.0)
- **执行优先级**: Execution Speed > Profit Margin
- **风险等级**: Conservative → Moderate → Aggressive

---

## Phase 0: Shadow Production (影子生产)

### 目标
- 验证系统在真实市场的稳定性
- 测试数据流和日志记录
- 验证风控和熔断器
- **不执行真实交易**

### 配置
- **Mode**: DRY_RUN=true
- **Profile**: `live_shadow_atomic_v1`
- **资金**: $0 (无真实资金)
- **Duration**: 7-14 天

### Success Criteria (DoD)
- [ ] 系统稳定运行 7 天无崩溃
- [ ] WebSocket 断线重连成功率 > 95%
- [ ] 日志记录完整（events.jsonl, alerts.jsonl）
- [ ] 熔断器触发后正确停止
- [ ] PnL 计算准确（干运行模式）
- [ ] Latency P95 < 500ms

### Rollback Criteria (Kill Criteria)
- 系统崩溃频率 > 1次/天
- WebSocket 连接稳定性 < 80%
- 日志丢失或数据损坏
- RPC 调用失败率 > 10%

### Exit Criteria
- 所有 Success Criteria 满足
- 运行至少 7 天
- 无 CRITICAL 级别告警

### 下一阶段
进入 Phase 1: Micro-Live (微量实盘)

---

## Phase 1: Micro-Live (微量实盘)

### 目标
- 验证真实执行流程
- 测试小额资金风控
- 验证订单成交和滑点
- 收集真实 PnL 数据

### 配置
- **Mode**: DRY_RUN=false
- **Profile**: `live_safe_atomic_v1`
- **资金**: $2 USD per trade
- **MAX_POSITION_SIZE**: $20
- **MAX_DAILY_LOSS**: $3
- **Duration**: 14-21 天

### Success Criteria (DoD)
- [ ] 无 CRITICAL 告警持续 7 天
- [ ] 总 PnL 在预期范围内 [-$3, +$10]
- [ ] 成交率 > 50%（提交订单 / 成交订单）
- [ ] 滑点 < MAX_SLIPPAGE (2.5%) 的比例 > 90%
- [ ] 风控触发后正确停止
- [ ] 无资金安全事故

### Rollback Criteria (Kill Criteria)
- **每日亏损** > $5
- **单笔交易亏损** > $2
- **CRITICAL 告警**未解决超过 1 小时
- **成交率** < 20% 持续 3 天
- **滑点超标** > 5% 的交易超过 3 笔
- **资金安全**问题（私钥泄露、未授权交易）

### Go/No-Go Checklist
启动前必须完成：
- [ ] 独立生产钱包（P0）
- [ ] Allowance 最小化（P0）
- [ ] 完成至少 3 天 Shadow Production
- [ ] 所有告警规则配置完成
- [ ] Go/No-Go Checklist 全部通过

### Exit Criteria
- 所有 Success Criteria 满足
- 运行至少 14 天
- 累计交易数 > 50 笔
- 总 PnL > 0

### 下一阶段
进入 Phase 2: Constrained-Live (受限实盘)

---

## Phase 2: Constrained-Live (受限实盘)

### 目标
- 提高交易规模
- 验证 scaled PnL 是否为正
- 测试多市场并发执行
- 优化参数配置

### 配置
- **Mode**: DRY_RUN=false
- **Profile**: `live_constrained_atomic_v1`
- **资金**: $5 USD per trade
- **MAX_POSITION_SIZE**: $50
- **MAX_DAILY_LOSS**: $5
- **Duration**: 21-30 天

### Success Criteria (DoD)
- [ ] 无 CRITICAL 告警持续 14 天
- [ ] 总 PnL > $10 (盈利)
- [ ] Sharpe Ratio > 1.0
- [ ] Max Drawdown < 20%
- [ ] 成交率 > 60%
- [ ] 无资金安全事故

### Rollback Criteria (Kill Criteria)
- **每日亏损** > $10
- **累计回撤** > 30%
- **CRITICAL 告警**未解决超过 30 分钟
- **成交率** < 30% 持续 5 天
- **Sharpe Ratio** < 0.5
- **资金安全**问题

### Go/No-Go Checklist
启动前必须完成：
- [ ] Phase 1 所有 criteria 满足
- [ ] 累计盈利 > $5
- [ ] 审计日志无异常
- [ ] 风控参数调整完成
- [ ] Go/No-Go Checklist 全部通过

### Exit Criteria
- 所有 Success Criteria 满足
- 运行至少 21 天
- 累计交易数 > 200 笔
- 总 PnL > $20

### 下一阶段
进入 Phase 3: Scaled-Live (规模化实盘)

---

## Phase 3: Scaled-Live (规模化实盘)

### 目标
- 扩大资金规模
- 增加市场覆盖
- 优化收益效率
- 长期稳定运行

### 配置
- **Mode**: DRY_RUN=false
- **Profile**: `live_scaled_atomic_v1`
- **资金**: $10-20 USD per trade
- **MAX_POSITION_SIZE**: $100-200
- **MAX_DAILY_LOSS**: $10-20
- **Duration**: 长期运行

### Success Criteria (DoD)
- [ ] 无 CRITICAL 告警持续 30 天
- [ ] 月化收益率 > 5%
- [ ] Sharpe Ratio > 1.5
- [ ] Max Drawdown < 15%
- [ ] 成交率 > 70%
- [ ] 无资金安全事故

### Rollback Criteria (Kill Criteria)
- **每日亏损** > $20
- **累计回撤** > 25%
- **CRITICAL 告警**未解决超过 15 分钟
- **成交率** < 40% 持续 7 天
- **月化收益** < 2%
- **资金安全**问题

### Go/No-Go Checklist
启动前必须完成：
- [ ] Phase 2 所有 criteria 满足
- [ ] 累计盈利 > $50
- [ ] 风控模型验证完成
- [ ] 应急预案制定完成
- [ ] Go/No-Go Checklist 全部通过

### Exit Criteria
- 长期稳定运行
- 月化收益稳定 > 5%
- 无重大安全事故

---

## 风险管理框架

### 仓位管理
- **Phase 0**: $0 (shadow)
- **Phase 1**: $2/trade, max $20 total
- **Phase 2**: $5/trade, max $50 total
- **Phase 3**: $10-20/trade, max $200 total

### 止损规则
- **Daily Loss Limit**: 根据阶段设定 ($3 → $5 → $10-20)
- **Position Limit**: 单笔最大仓位
- **Drawdown Limit**: 累计回撤限制
- **Circuit Breaker**: 连续失败触发熔断

### 告警响应
- **CRITICAL**: 立即停止交易，人工介入
- **WARNING**: 监控并记录，持续触发则降级
- **INFO**: 仅记录，无需响应

### 回滚策略
每个阶段都有明确的 Rollback Criteria，触发后立即：
1. 停止交易（DRY_RUN=true）
2. 保存现场（backup_state.sh）
3. 分析原因（daily report + logs）
4. 修复问题
5. 从上一个阶段重新开始

---

## 监控与报告

### 每日报告 (production_daily_report.py)
每天自动生成，包含：
- 运行模式与配置
- 交易统计（数量、胜率、PnL）
- 订单执行（提交、成交、拒绝率）
- 延迟统计（P50, P95, P99）
- 告警汇总
- 异常诊断

### 告警规则 (alerts.production.yaml)
- WS_DISCONNECTED (CRITICAL)
- LIVE_NO_FILLS (CRITICAL)
- CIRCUIT_BREAKER_OPEN (CRITICAL)
- HIGH_REJECT_RATE (WARNING)
- PNL_DRAWDOWN (WARNING)
- LATENCY_P95_HIGH (WARNING)
- LOW_BALANCE (WARNING)
- POSITION_LIMIT_NEAR (WARNING)

### Go/No-Go 检查 (go_no_go_check.sh)
每个阶段启动前必须执行，检查：
- 安全检查（钱包、allowance）
- 系统检查（config.yaml、profiles、alerts）
- 数据检查（events.jsonl、磁盘空间）
- 操作检查（备份、脚本权限）

---

## 时间线

| 阶段 | 开始时间 | 结束时间 | 状态 |
|------|----------|----------|------|
| Phase 0 | TBD | TBD | 🚧 Pending |
| Phase 1 | TBD | TBD | 🚧 Pending |
| Phase 2 | TBD | TBD | 🚧 Pending |
| Phase 3 | TBD | TBD | 🚧 Pending |

---

## 附录

### A. 术语表
- **Shadow Production**: 影子生产（干运行，真实数据）
- **Micro-Live**: 微量实盘（极小资金，$2/trade）
- **Constrained-Live**: 受限实盘（小资金，$5/trade）
- **Scaled-Live**: 规模化实盘（正常资金，$10-20/trade）
- **DoD**: Definition of Done (完成定义)
- **PnL**: Profit and Loss (盈亏)
- **Sharpe Ratio**: 夏普比率（风险调整后收益）

### B. 相关文档
- `GO_NO_GO_CHECKLIST.md` - 启动前检查清单
- `PRODUCTION_RUNBOOK.md` - 运行手册
- `config/profiles/live_*_atomic_v1.yaml` - 各阶段配置
- `config/alerts.production.yaml` - 生产告警规则
- `scripts/start_*.sh` - 启动脚本
- `scripts/production_daily_report.py` - 每日报告生成

### C. 联系方式
- **紧急情况**: [电话/即时通讯]
- **日常沟通**: [邮箱/Slack/Discord]
- **Bug 报告**: GitHub Issues

---

**最后更新**: 2026-02-02
**文档版本**: v1.0.0
**维护者**: PolyArb-X Team
