# PolyArb-X 新策略实施计划 v0.4.0

**计划日期**: 2026-02-01
**计划版本**: 1.0
**预估工时**: ~114小时（约3周）

---

## 📋 需求概述

在现有 PolyArb-X v0.3.2 基础上新增 **4类策略** 和 **1个防御模块**，要求不破坏现有 trace/metrics/replay/backtest/风控/熔断体系。

### 新增策略

1. **settlement_lag/** - 结算滞后窗口策略
2. **market_making/** - 盘口价差做市
3. **tail_risk_underwriting/** - NO 尾部风险承保（非无风险）
4. **signals/public_info/** - 公开信息信号增强（可选）

### 防御模块

5. **risk/anomaly_guard.py** - 反操纵/异常防御

---

## 🎯 实施阶段

### Phase 1: 基础架构扩展（8小时）

**目标**: 扩展现有模型和风控基础设施

**任务**:
1. 扩展 `src/core/models.py`
   - 新增 `RiskTag` 枚举类
   - 新增 `SettlementLagSignal`, `MarketMakingSignal`, `TailRiskSignal`
   - 扩展 `EdgeBreakdown` 增加 `risk_tags` 字段

2. 扩展 `src/execution/risk_manager.py`
   - 新增拒绝码：`RESOLUTION_UNCERTAIN`, `DISPUTE_RISK_HIGH`, `CARRY_COST_TOO_HIGH`, `MANIPULATION_RISK`, `ABNORMAL_VOLATILITY`

3. 扩展 `src/core/edge.py`
   - 支持风险标签追踪

4. 扩展 `src/core/config.py`
   - 新增策略开关和参数配置

**关键决策**:
- ✅ 统一 Opportunity 结构
- ✅ 向后兼容扩展

---

### Phase 2: 结算滞后窗口策略（16小时）

**目标**: 利用结算窗口期获利，过滤高争议市场

**核心文件**:
```
src/strategies/settlement_lag/
├── market_state_detector.py    # 市场状态检测（仅用公开信息）
├── dispute_risk_filter.py      # 争议风险过滤
├── time_to_resolution_model.py # 资金占用成本
└── __init__.py                  # 策略主类
```

**关键特性**:
- ✅ 仅使用公开的 end_date 信息
- ✅ 基于波动性和关键词的争议评分
- ✅ 资金占用成本计算
- ✅ 风控拒绝码集成

---

### Phase 3: 盘口价差做市策略（20小时）

**目标**: 提供双边报价赚取价差

**核心文件**:
```
src/strategies/market_making/
├── spread_model.py      # 价差模型
├── quote_manager.py     # 报价管理（post-only, aging）
├── inventory_skew.py    # 库存偏斜管理
└── __init__.py          # 策略主类
```

**关键约束**:
- ✅ **post-only**: 强制仅挂单，不主动成交
- ✅ **quote aging**: 报价有效期机制
- ✅ **库存限额**: 单边最大敞口限制
- ✅ **频率限制**: 撤单/改价频率限制

---

### Phase 4: 尾部风险承保策略（16小时）

**目标**: 承保极端事件（非无风险）

**核心文件**:
```
src/strategies/tail_risk_underwriting/
├── candidate_selector.py  # 候选选择器
├── position_sizer.py      # 仓位规模（worst-case loss cap）
├── tail_hedge.py          # 尾部对冲（可选）
└── __init__.py            # 策略主类
```

**关键特性**:
- ✅ **worst-case loss cap**: 明确最大损失限制
- ✅ **相关性簇限额**: 防止过度集中风险
- ✅ **自动止损/止盈**
- ✅ **明确 risk_tag=TAIL_RISK**

---

### Phase 5: 公开信息信号增强（12小时）

**目标**: 可选的公开信息信号（默认关闭）

**核心文件**:
```
src/strategies/signals/public_info/
├── source_adapters.py    # 数据源适配器
├── event_normalizer.py   # 事件标准化
├── latency_model.py      # 延迟模型
└── __init__.py           # 策略主类
```

**关键约束**:
- ✅ **仅使用公开可合法获取的数据源**
- ✅ **默认关闭**
- ✅ **需显式启用**

---

### Phase 6: 反操纵异常防御（12小时）

**目标**: 检测并响应异常市场状况

**核心文件**:
```
src/risk/anomaly_guard.py
```

**检测项目**:
- ✅ 价格脉冲（短时间内大幅波动）
- ✅ 相关性断裂（相关资产价格关系异常）
- ✅ 订单本深度异常（突然枯竭）

**响应措施**:
- ✅ 降级（减少仓位）
- ✅ 熔断（暂停交易）

**集成**: 与现有 `CircuitBreaker` 集成

---

### Phase 7: 测试与验证（24小时）

**目标**: 确保充分的测试覆盖和系统稳定性

**任务**:
1. 为每个新策略编写单元测试
2. 创建回测事件样例
3. 回放一致性测试
4. 运行完整测试套件（确保439个现有测试仍然通过）
5. 验证总覆盖率保持80%+

**新增测试文件**:
```
tests/unit/
├── test_settlement_lag_strategy.py
├── test_market_state_detector.py
├── test_dispute_risk_filter.py
├── test_time_to_resolution_model.py
├── test_market_making_strategy.py
├── test_spread_model.py
├── test_quote_manager.py
├── test_inventory_skew.py
├── test_tail_risk_strategy.py
├── test_candidate_selector.py
├── test_position_sizer.py
├── test_public_info_signals.py
└── test_anomaly_guard.py
```

---

### Phase 8: 文档更新（6小时）

**目标**: 更新所有相关文档

**任务**:
1. 更新 `README.md` - 新增策略说明、风险提示
2. 创建 `docs/STRATEGIES.md` - 详细策略文档
3. 更新 `.env.example` - 新增配置项

---

## 📊 工作量估算

| 阶段 | 工时 | 关键路径 |
|------|------|----------|
| Phase 1: 基础架构 | 8h | ✅ |
| Phase 2: 结算滞后 | 16h | ✅ |
| Phase 3: 盘口做市 | 20h | ✅ |
| Phase 4: 尾部风险 | 16h | ✅ |
| Phase 5: 公开信息 | 12h | ❌ |
| Phase 6: 异常防御 | 12h | ✅ |
| Phase 7: 测试验证 | 24h | ✅ |
| Phase 8: 文档更新 | 6h | ❌ |
| **总计** | **114h** | **~3周** |

---

## ⚠️ 风险评估

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| 新策略破坏现有测试 | 高 | 中 | Phase 7 验证所有测试通过 |
| 策略间冲突 | 高 | 中 | Phase 1 统一 Opportunity 结构 |
| 异常防御误触发 | 中 | 中 | 可配置阈值，分级响应 |
| 盘口做市主动成交 | 高 | 低 | 强制 post-only 机制 |
| 尾部风险过度暴露 | 高 | 中 | worst-case loss cap |
| 公开信息合规问题 | 中 | 低 | 默认关闭，明确数据源 |
| 性能下降 | 中 | 低 | 异步处理，可配置启用 |

---

## ✅ 成功标准

- [ ] 所有新策略代码已完成
- [ ] 每个新策略有独立单元测试文件
- [ ] 测试覆盖率保持在 80%+
- [ ] 现有 439 个测试仍然 100% 通过
- [ ] 回测系统能处理新策略
- [ ] 异常防御模块能正确检测并响应异常
- [ ] README 和策略文档已更新
- [ ] 环境变量配置模板已更新
- [ ] 所有新策略默认关闭，需显式启用
- [ ] 尾部风险策略明确标注风险标签

---

## 🎯 关键决策点

1. **统一 Opportunity 结构**: 所有新策略必须扩展自现有的 `Signal` 基类
2. **风险标签系统**: 使用枚举类型的风险标签，便于追踪和过滤
3. **默认关闭策略**: 所有新策略默认禁用，需要显式配置启用
4. **post-only 强制**: 做市策略必须使用 post-only 订单
5. **worst-case loss cap**: 尾部风险必须有明确的最大损失限制

---

## 📋 待确认事项

**请确认以下事项后开始实施**:

1. **实施顺序**: 是否同意上述8个阶段的顺序？
2. **优先级**: 是否需要调整某些阶段的优先级？
3. **风险接受**: 是否接受上述风险评估？
4. **工作量**: 114小时（约3周）是否可接受？
5. **开始实施**: 是否现在开始 Phase 1？

---

## 🚀 下一步

**如果您同意此计划**，请回复：
- `yes` 或 `proceed` - 开始实施（从 Phase 1 开始）
- `modify: [您的修改意见]` - 修改计划
- `先从 Phase X` - 跳过某些阶段，从指定阶段开始
- `其他问题` - 提出您的疑问或建议

---

**计划创建者**: Claude (Planner Agent)
**创建时间**: 2026-02-01
**计划版本**: 1.0
