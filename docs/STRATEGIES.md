# PolyArb-X 策略文档 (v0.4.0)

本文档详细描述了 PolyArb-X v0.4.0 新增的交易策略。

---

## 📋 目录

1. [策略概述](#策略概述)
2. [结算滞后窗口策略](#结算滞后窗口策略)
3. [盘口价差做市策略](#盘口价差做市策略)
4. [尾部风险承保策略](#尾部风险承保策略)
5. [异常防御模块](#异常防御模块)
6. [风险控制](#风险控制)
7. [配置说明](#配置说明)

---

## 策略概述

### 核心策略 (v0.3.x)

| 策略 | 类型 | 风险等级 | 描述 |
|------|------|----------|------|
| 原子套利 | 套利 | 低 | YES + NO 成本 < 1.0 |
| NegRisk套利 | 套利 | 低 | 概率差异套利 |
| 组合套利 | 套利 | 中 | 多市场组合交易 |

### 新策略 (v0.4.0)

| 策略 | 类型 | 风险等级 | 默认状态 |
|------|------|----------|----------|
| 结算滞后窗口 | 机会型 | 中 | 🔴 关闭 |
| 盘口价差做市 | 做市 | 中 | 🔴 关闭 |
| 尾部风险承保 | 保险 | 高 | 🔴 关闭 |

**重要**: 所有新策略默认关闭，需要显式配置启用。

---

## 结算滞后窗口策略

### 策略描述

在市场接近结算时，由于信息不确定性增加，市场可能出现低效性。本策略旨在利用这些窗口期的机会。

### 核心组件

#### 1. 市场状态检测器 (`market_state_detector.py`)

**功能**:
- 检测市场是否处于结算窗口期（1-72小时）
- 评估流动性和波动性
- 计算买卖价差

**仅使用公开信息**:
- `end_date` - 市场结束日期
- `order_book` - 当前订单本状态
- `volume_24h` - 24小时交易量

#### 2. 争议风险过滤器 (`dispute_risk_filter.py`)

**功能**:
- 分析市场问题文本中的风险关键词
- 评估争议概率
- 拒绝高风险市场

**高风险关键词**:
- subjective, interpretation, judgment, discretionary
- undefined, unclear, ambiguous
- controversial, debate, disagreement

**中风险关键词**:
- approximately, around, roughly
- estimate, projection, forecast

#### 3. 结算时间模型 (`time_to_resolution_model.py`)

**功能**:
- 计算资金占用成本
- 评估资金时间价值

**公式**:
```
carry_cost = capital * daily_rate * days
daily_rate = 0.001  # 0.1% per day
```

### 信号生成

```python
SettlementLagSignal(
    market_id="market_123",
    resolution_window_hours=12.5,
    dispute_score=0.15,
    carry_cost=Decimal("0.15"),
    expected_profit=Decimal("0.50"),
    risk_tags=["SETTLEMENT_RISK", "CARRY_COST_RISK"]
)
```

### 配置参数

```bash
SETTLEMENT_LAG_ENABLED=false                    # 默认关闭
SETTLEMENT_LAG_MAX_DISPUTE_SCORE=0.3           # 最大争议分数
SETTLEMENT_LAG_MAX_CARRY_COST_PCT=0.02         # 最大资金成本 2%
SETTLEMENT_LAG_MIN_WINDOW_HOURS=1.0             # 最小窗口 1小时
```

### 使用示例

```python
from src.strategies.settlement_lag import SettlementLagStrategy
from src.core.config import Config

config = Config()
config.SETTLEMENT_LAG_ENABLED = True  # 启用策略

strategy = SettlementLagStrategy(config=config)

signal = await strategy.evaluate_market(
    market_id="market_123",
    question="Will X happen by 2025?",
    end_date=datetime(2025, 12, 31),
    order_book_snapshot={...},
    token_id="token_123",
    yes_price=Decimal("0.45"),
    no_price=Decimal("0.54"),
    trade_size=Decimal("100"),
)
```

---

## 盘口价差做市策略

### 策略描述

通过提供双边报价（bid-ask spread）赚取价差。类似于传统做市商，但专为预测市场设计。

### 关键约束

#### ⚠️ Post-Only 强制要求

**所有订单必须是 post-only**，永不主动成交。

```python
# ✅ 正确
MM_POST_ONLY=true  # MUST be true

# ❌ 错误 - 会导致启动失败
MM_POST_ONLY=false
```

#### 报价有效期机制

- 报价有 TTL（Time-To-Live）
- 过期报价自动取消
- 防止在不利价格成交

#### 库存偏斜管理

- 单边最大敞口限制
- 根据库存调整报价
- 防止过度集中风险

### 核心组件

#### 1. 价差模型 (`spread_model.py`)

**功能**:
- 计算最优 bid-ask 价差
- 根据波动率调整价差
- 根据库存偏斜调整价格

**价差计算**:
```python
# 固定价差模式
spread_bps = 50  # 0.5%

# 波动率调整模式
spread_bps = base_spread * (1.0 + volatility_score * 2.0)

# 库存调整模式
spread_bps = volatility_adjusted * (1.0 + abs(skew) * 0.5)
```

#### 2. 报价管理器 (`quote_manager.py`)

**功能**:
- 管理报价生命周期
- 强制 post-only 执行
- 限制撤单频率

**频率限制**:
```python
max_cancel_rate_per_min = 10  # 每分钟最多10次撤单
```

#### 3. 库存偏斜管理 (`inventory_skew.py`)

**功能**:
- 跟踪多头/空头寸
- 计算库存偏斜度
- 强制仓位限制

**偏斜度计算**:
```python
skew = (long_exposure - short_exposure) / max_total_exposure
# -1 (完全空头) 到 +1 (完全多头)
```

### 信号生成

```python
MarketMakingSignal(
    token_id="token_123",
    bid_price=Decimal("0.495"),
    ask_price=Decimal("0.505"),
    spread_bps=100,
    inventory_skew=Decimal("0.2"),
    post_only=True,  # CRITICAL
    max_position_size=Decimal("500"),
    risk_tags=["LOW_LIQUIDITY"]
)
```

### 配置参数

```bash
MARKET_MAKING_ENABLED=false               # 默认关闭
MM_POST_ONLY=true                        # 必须为 true
MM_MAX_SPREAD_BPS=100                    # 最大价差 1%
MM_QUOTE_AGE_LIMIT_SECONDS=30.0          # 报价有效期 30秒
MM_MAX_POSITION_SIZE=500                 # 单边最大仓位 $500
MM_MAX_CANCEL_RATE_PER_MIN=10             # 每分钟最多撤单10次
```

### 使用示例

```python
from src.strategies.market_making import MarketMakingStrategy

config = Config()
config.MARKET_MAKING_ENABLED = True
config.MM_POST_ONLY = True  # 必须设置

strategy = MarketMakingStrategy(config=config)

signal = await strategy.evaluate_market(
    token_id="token_123",
    mid_price=Decimal("0.50"),
    order_book_snapshot={...},
)
```

---

## 尾部风险承保策略

### 策略描述

⚠️ **这不是无风险策略！**

为极端事件提供保险，收取保费。类似于卖出虚值期权。

### 关键特征

#### 🚨 明确 Worst-Case Loss Cap

每个仓位都有明确的**最大损失上限**。

```python
worst_case_loss = position_size  # 如果尾部事件不发生，损失本金
```

#### 相关性簇限制

防止在相关事件上过度集中。

```python
cluster_id = "us_election"  # 所有美国选举相关市场
max_cluster_exposure = Decimal("300")  # 每个簇最大敞口
```

#### Kelly Criterion 仓位计算

使用 Kelly Criterion 优化仓位大小。

```python
kelly_fraction = (p * b - q) / b
position_size = capital * kelly_fraction * 0.25  # Quarter Kelly
```

### 核心组件

#### 1. 候选选择器 (`candidate_selector.py`)

**功能**:
- 识别尾部风险市场
- 分类尾部风险类型
- 评估尾部概率

**尾部风险分类**:
- `GEOPOLITICAL` - 地缘政治（战争、冲突）
- `ECONOMIC` - 经济（衰退、崩盘）
- `TECHNOLOGY` - 技术（AI突破、失败）
- `ENVIRONMENTAL` - 环境（自然灾害、气候）
- `SOCIAL` - 社会（选举、公投）
- `BLACK_SWAN` - 黑天鹅（不可预测）

**筛选标准**:
```python
min_tail_probability = 0.01   # 1% 最小概率
max_tail_probability = 0.20   # 20% 最大概率
min_payout_ratio = 10.0        # 10倍最小赔付比
```

#### 2. 仓位规模计算 (`position_sizer.py`)

**功能**:
- 计算 Kelly Criterion 仓位
- 应用 worst-case loss 限制
- 强制相关性簇限额

#### 3. 尾部对冲 (`tail_hedge.py`)

**功能**:
- 可选的对冲功能
- 降低尾部风险暴露

### 信号生成

```python
TailRiskSignal(
    token_id="token_123",
    worst_case_loss=Decimal("100"),      # 明确上限
    correlation_cluster="geopolitical_us",
    tail_probability=0.05,                # 5% 概率
    max_exposure=Decimal("300"),
    hedge_ratio=None,  # 可选对冲
    risk_tags=["TAIL_RISK", "CORRELATION_CLUSTER_RISK"]
)
```

### 配置参数

```bash
TAIL_RISK_ENABLED=false                          # 默认关闭
TAIL_RISK_MAX_WORST_CASE_LOSS=100                # 每个仓位最大损失
TAIL_RISK_MAX_CORRELATION_CLUSTER_EXPOSURE=300   # 每个簇最大敞口
TAIL_RISK_MIN_TAIL_PROBABILITY=0.05               # 最小尾部概率
```

### 使用示例

```python
from src.strategies.tail_risk_underwriting import TailRiskStrategy

config = Config()
config.TAIL_RISK_ENABLED = True

strategy = TailRiskStrategy(config=config)

markets = [
    {
        "market_id": "market_123",
        "question": "Will there be a major war in 2025?",
        "yes_price": Decimal("0.02"),  # 2% 概率
        "no_price": Decimal("0.98"),
    }
]

signals = await strategy.evaluate_markets(
    markets=markets,
    capital=Decimal("1000"),
)
```

---

## 异常防御模块

### 模块描述

检测并响应异常市场状况，保护系统免受操纵和异常波动影响。

### 检测项目

#### 1. 价格脉冲检测

短时间内价格大幅波动。

```python
price_change_pct > price_pulse_threshold  # 默认 10%
```

#### 2. 相关性断裂检测

相关资产价格关系异常。

```python
# 应该一起变动的资产向相反方向变动
correlation_violation = True
```

#### 3. 深度枯竭检测

订单本深度突然下降。

```python
depth_change_pct > depth_depletion_threshold  # 默认 50%
```

### 响应措施

| 严重程度 | 响应动作 | 触发条件 |
|----------|----------|----------|
| 0.0 - 0.3 | 无动作 | 正常波动 |
| 0.4 - 0.6 | 降级 (DEGRADE) | 减少仓位 |
| 0.7 - 1.0 | 熔断 (HALT) | 停止交易 |

### 与 CircuitBreaker 集成

```python
# 异常检测触发时自动熔断
if event.severity >= 0.7:
    await circuit_breaker.trip("Anomaly detected")
```

### 配置参数

```bash
ANOMALY_DEFENSE_ENABLED=true                    # 默认开启
ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD=0.10      # 10% 价格变动
ANOMALY_DEFENSE_CORRELATION_BREAK_THRESHOLD=0.5  # 相关系数阈值
ANOMALY_DEFENSE_DEPTH_DEPLETION_THRESHOLD=0.5    # 50% 深度下降
```

---

## 风险控制

### 风险标签系统

所有信号都标记风险标签：

| 标签 | 适用策略 | 描述 |
|------|----------|------|
| `SETTLEMENT_RISK` | 结算滞后 | 结算不确定性风险 |
| `CARRY_COST_RISK` | 结算滞后 | 资金占用成本风险 |
| `LOW_LIQUIDITY` | 盘口做市 | 流动性风险 |
| `TAIL_RISK` | 尾部风险 | 尾部事件风险 |
| `CORRELATION_CLUSTER_RISK` | 尾部风险 | 相关性集中风险 |
| `MANIPULATION_RISK` | 全部 | 操纵风险（异常防御） |

### 新增拒绝码

```python
class RejectCode(str, Enum):
    # 原有拒绝码
    INSUFFICIENT_BALANCE = "insufficient_balance"
    POSITION_LIMIT = "position_limit"
    GAS_TOO_HIGH = "gas_too_high"
    PROFIT_TOO_LOW = "profit_too_low"

    # 新增拒绝码 (v0.4.0)
    RESOLUTION_UNCERTAIN = "resolution_uncertain"         # 结算不确定性高
    DISPUTE_RISK_HIGH = "dispute_risk_high"             # 争议风险高
    CARRY_COST_TOO_HIGH = "carry_cost_too_high"         # 资金成本过高
    MANIPULATION_RISK = "manipulation_risk"             # 操纵风险
    ABNORMAL_VOLATILITY = "abnormal_volatility"           # 异常波动
```

---

## 配置说明

### 环境变量配置

创建 `.env` 文件并配置：

```bash
# ========== 基础配置 ==========
TRADE_SIZE=100
MIN_PROFIT_THRESHOLD=0.01
MAX_POSITION_SIZE=1000

# ========== 结算滞后策略 ==========
SETTLEMENT_LAG_ENABLED=false
SETTLEMENT_LAG_MAX_DISPUTE_SCORE=0.3
SETTLEMENT_LAG_MAX_CARRY_COST_PCT=0.02
SETTLEMENT_LAG_MIN_WINDOW_HOURS=1.0

# ========== 盘口做市策略 ==========
MARKET_MAKING_ENABLED=false
MM_POST_ONLY=true  # ⚠️ 必须为 true
MM_MAX_SPREAD_BPS=100
MM_QUOTE_AGE_LIMIT_SECONDS=30.0
MM_MAX_POSITION_SIZE=500
MM_MAX_CANCEL_RATE_PER_MIN=10

# ========== 尾部风险策略 ==========
TAIL_RISK_ENABLED=false
TAIL_RISK_MAX_WORST_CASE_LOSS=100
TAIL_RISK_MAX_CORRELATION_CLUSTER_EXPOSURE=300
TAIL_RISK_MIN_TAIL_PROBABILITY=0.05

# ========== 公开信息信号（可选）==========
PUBLIC_INFO_ENABLED=false
PUBLIC_INFO_MAX_LATENCY_SECONDS=300.0

# ========== 异常防御 ==========
ANOMALY_DEFENSE_ENABLED=true
ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD=0.10
ANOMALY_DEFENSE_CORRELATION_BREAK_THRESHOLD=0.5
ANOMALY_DEFENSE_DEPTH_DEPLETION_THRESHOLD=0.5
```

### 策略启用流程

1. **了解风险** - 仔细阅读策略描述和风险
2. **配置参数** - 在 `.env` 中设置参数
3. **启用策略** - 设置 `*_ENABLED=true`
4. **小额测试** - 使用小交易量测试
5. **监控运行** - 观察策略表现
6. **逐步扩大** - 根据结果调整规模

---

## 安全建议

### ⚠️ 风险警告

1. **结算滞后策略**
   - 市场可能争议导致资金被锁定
   - 资金占用成本可能超过利润
   - 建议：仅在高流动性市场使用

2. **盘口做市策略**
   - 必须 post-only，不能主动成交
   - 库存风险可能导致损失
   - 建议：设置严格的仓位限制

3. **尾部风险策略**
   - 不是无风险！可能损失全部本金
   - 极端事件可能同时发生
   - 建议：使用小的仓位规模

### 最佳实践

1. **从小开始**
   ```bash
   TRADE_SIZE=10  # 小额测试
   ```

2. **启用异常防御**
   ```bash
   ANOMALY_DEFENSE_ENABLED=true
   ```

3. **监控日志**
   ```bash
   tail -f data/polyarb-x.log
   ```

4. **定期审查**
   - 每周审查策略表现
   - 根据市场条件调整参数
   - 必要时关闭策略

---

## 性能监控

### 关键指标

每个策略都会记录以下指标：

```python
# 结算滞后策略
- 争议分数 (dispute_score)
- 资金成本 (carry_cost)
- 结算窗口 (resolution_window_hours)

# 盘口做市策略
- 价差 (spread_bps)
- 库存偏斜 (inventory_skew)
- 报价年龄 (quote_age_seconds)

# 尾部风险策略
- 最大损失 (worst_case_loss)
- 尾部概率 (tail_probability)
- 相关性簇 (correlation_cluster)
```

---

## 故障排查

### 策略未生成信号

**问题**: 策略已启用但没有生成信号

**检查**:
1. 确认 `*_ENABLED=true`
2. 检查日志中的拒绝原因
3. 验证市场数据完整性
4. 确认策略阈值配置合理

### 盘口做市主动成交

**问题**: 做市策略主动成交（不应该发生）

**检查**:
```bash
# 确认 post-only 为 true
echo $MM_POST_ONLY  # 应该输出 true

# 如果不是，立即停止系统
# 这可能意味着配置错误
```

### 异常防御频繁触发

**问题**: 异常防御频繁触发导致无法交易

**解决**:
```bash
# 调整阈值（暂时放宽）
ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD=0.20  # 从 10% 到 20%
```

---

## 总结

PolyArb-X v0.4.0 新增了 3 个交易策略和 1 个防御模块：

- ✅ **结算滞后窗口** - 利用结算期低效性
- ✅ **盘口价差做市** - 赚取买卖价差
- ✅ **尾部风险承保** - 极端事件保险（有风险）
- ✅ **异常防御** - 保护免受操纵

**关键特性**:
- 所有新策略默认关闭
- 强制 post-only 做市
- 明确 worst-case loss cap
- 风险标签系统
- 异常检测与响应

**下一步**:
1. 了解每个策略的风险
2. 在 `.env` 中配置参数
3. 小额测试
4. 逐步扩大规模

---

**文档版本**: 1.0
**创建日期**: 2026-02-01
**适用版本**: PolyArb-X v0.4.0
