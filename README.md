# PolyArb-X

> 低延迟预测市场套利机器人 - 用于 Polymarket 平台的自动化交易

[![Tests](https://img.shields.io/badge/tests-448%20passing-success)](#)
[![Coverage](https://img.shields.io/badge/coverage-81.93%25-brightgreen)](htmlcov/index.html)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## 🎯 项目简介

**PolyArb-X** 是一个高性能的预测市场套利机器人，通过实时监控 Polymarket 的订单本，自动识别并执行套利机会。

### 核心特性

- 🚀 **实时订单本** - WebSocket 连接，毫秒级更新
- 💰 **多策略套利** - 原子套利、NegRisk、组合套利
- 🛡️ **风险管理** - 余额检查、仓位限制、滑点保护
- ⛽ **Gas 优化** - EIP-1559 动态费用估算
- 🔄 **自动重试** - 交易失败自动重试机制
- 🔍 **可观测性** - 分布式追踪、延迟分析、事件记录（Phase 1）
- 📊 **Edge 分析** - 详细的成本分解和决策归因（Phase 1）
- 🛡️ **韧性机制** - 熔断器、Nonce 管理、重试策略（Phase 2）
- 🔬 **回测系统** - 历史数据回测、性能分析、策略优化（Phase 3）
- 🧪 **TDD测试** - 448个测试，81.93%覆盖率，严格遵循TDD方法论
- 🆕 **新策略** - 结算滞后、盘口做市、尾部风险承保（v0.4.0 新增）
- 🛡️ **异常防御** - 反操纵和异常市场检测（v0.4.0 新增）

### 支持的策略

**核心策略 (v0.3.x):**
1. **原子套利** - YES + NO 成本 < 1.0 USDC 时获利
2. **NegRisk 套利** - 利用 NegRisk 概率差异套利
3. **组合套利** - 多个市场的组合交易

**新策略 (v0.4.0，默认禁用，需显式启用):**
4. **结算滞后窗口** - 利用结算窗口期的市场低效性
   - 仅使用公开信息 (end_date)
   - 争议风险过滤
   - 资金占用成本计算
5. **盘口价差做市** - 提供双边报价赚取价差
   - 强制 post-only 订单（永不主动成交）
   - 报价有效期机制
   - 库存偏斜管理
6. **尾部风险承保** - 承保极端事件（非无风险）
   - 明确 worst-case loss cap
   - 相关性簇限额
   - Kelly criterion 仓位计算

---

## 📊 项目状态

| 指标 | 数值 | 状态 |
|------|------|------|
| 测试数量 | 448 | ✅ |
| 通过率 | 100% | ✅ |
| 代码覆盖率 | 81.93% | ✅ |
| Python 版本 | 3.10+ | ✅ |
| Phase 1 | ✅ 可观测性 | ✅ |
| Phase 2 | ✅ 韧性机制 | ✅ |
| Phase 3 | ✅ 回测系统 | ✅ |
| Phase 4 | ✅ 新策略 | ✅ |
| Phase 6 | ✅ 异常防御 | ✅ |
| TDD审查 | ✅ 测试增强 | ✅ |

**文档**:
- [Phase 1: 可观测性](docs/PHASE1_TELEMETRY.md)
- [Phase 2: 韧性机制](docs/PHASE2_RESILIENCE.md)
- [Phase 3: 回测系统](docs/PHASE3_BACKTESTING.md)
- [Phase 4: 新策略](docs/STRATEGIES.md) - 结算滞后、盘口做市、尾部风险
- [📊 测试报告](TEST_REPORT.md) - TDD测试审查报告

---

## 🏗️ 架构设计

```
┌─────────────────────────────────────────────────────────┐
│                     PolyArb-X                            │
├─────────────────────────────────────────────────────────┤
│  主程序 (main.py)                                        │
│  - 事件循环管理                                          │
│  - 策略协调                                              │
│  - 日志记录                                              │
└────────────┬────────────────────────────┬───────────────┘
             │                            │
    ┌────────▼────────┐          ┌───────▼──────────┐
    │  连接层          │          │  策略层           │
    ├─────────────────┤          ├──────────────────┤
    │ WebSocket 客户端│          │ Atomic Arbitrage │
    │ Web3 客户端     │          │ NegRisk          │
    └────────┬────────┘          │ Market Grouper   │
             │                   └──────────┬────────┘
             └───────────────────────┬───────┘
                                     │
                            ┌────────▼────────┐
                            │  执行层          │
                            ├─────────────────┤
                            │ 风险管理器      │
                            │ 交易发送器      │
                            └─────────────────┘
                                     │
                            ┌────────▼────────┐
                            │  回测层          │
                            ├─────────────────┤
                            │ 事件回放引擎    │
                            │ 回测引擎        │
                            │ 策略分析器      │
                            └─────────────────┘
```

### 技术栈

- **异步框架**: asyncio
- **数据验证**: Pydantic v2
- **WebSocket**: websockets
- **区块链**: web3.py, eth-account
- **测试**: pytest, pytest-asyncio
- **日志**: loguru
- **回测**: statistics (标准库), decimal

---

## 🚀 快速开始

### 环境要求

- Python 3.10 或更高版本
- pip 或 poetry
- Polygon RPC 节点访问
- Polymarket CLOB WebSocket 访问

### 安装步骤

#### 1. 克隆项目

```bash
cd /Users/dapumacmini/polyarb-x
```

#### 2. 安装依赖

**方式 A: 使用 requirements.txt（推荐）**

```bash
python3 -m pip install --user -r requirements.txt
```

**方式 B: 使用自动安装脚本**

```bash
bash install_and_test.sh
```

**方式 C: 使用 poetry**

```bash
poetry install
```

#### 3. 配置环境变量

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env 文件
nano .env
```

**必需的环境变量**:

```bash
# Polygon RPC
POLYGON_RPC_URL=https://polygon-rpc.com

# 钱包私钥（从环境变量读取，永不硬编码）
PRIVATE_KEY=your_private_key_here

# Polymarket WebSocket
POLYMARKET_WS_URL=wss://clob.polymarket.com/ws

# 交易参数
TRADE_SIZE=100
MIN_PROFIT_THRESHOLD=0.01
MAX_POSITION_SIZE=1000
MAX_GAS_PRICE=100000000000
```

#### 4. 验证安装

```bash
# 运行测试
python3 -m pytest tests/ -v

# 预期输出: 209 passed ✅
```

---

## 🎮 使用方法

### 🚀 快速启动（推荐）

```bash
# 使用启动脚本（自动检查环境）
./start_production.sh
```

启动脚本会自动检查：
- ✅ Python版本
- ✅ 环境配置
- ✅ 依赖安装
- ✅ 测试通过
- ✅ 网络连接
- ✅ 数据目录

**首次使用请先阅读：[🚀 生产启动指南](PRODUCTION_LAUNCH.md)**

### 运行测试

```bash
# 运行所有测试
python3 -m pytest tests/ -v

# 运行特定模块
python3 -m pytest tests/unit/test_web3_client.py -v
python3 -m pytest tests/unit/test_risk_manager.py -v

# 生成覆盖率报告
python3 -m pytest tests/ --cov=src --cov-report=html
open htmlcov/index.html
```

### 运行项目

```bash
# 干运行模式（推荐先测试）
python3 src/main.py --dry-run

# 实时交易模式
python3 src/main.py

# 指定配置文件
python3 src/main.py --config custom_config.json
```

### 监控和日志

```bash
# 查看日志
tail -f data/polyarb-x.log

# 查看性能日志
tail -f data/performance.log

# 查看错误日志
grep ERROR data/polyarb-x.log
```

---

## 📁 项目结构

```
polyarb-x/
├── src/                      # 源代码
│   ├── core/                 # 核心组件
│   │   ├── models.py         # 数据模型 (99% 覆盖)
│   │   ├── config.py         # 配置管理
│   │   ├── metrics.py        # 性能指标 (99%)
│   │   ├── telemetry.py      # 遥测追踪 (100%)
│   │   ├── edge.py           # Edge 分析 (100%)
│   │   └── recorder.py       # 事件记录 (89%)
│   ├── connectors/           # 外部连接
│   │   ├── polymarket_ws.py  # WebSocket 客户端 (69%)
│   │   └── web3_client.py    # Web3 客户端 (79%)
│   ├── strategies/           # 交易策略
│   │   ├── atomic.py         # 原子套利 (92%)
│   │   ├── negrisk.py        # NegRisk 套利 (96%)
│   │   └── market_grouper.py # 市场分组 (92%)
│   ├── execution/            # 交易执行
│   │   ├── circuit_breaker.py # 熔断器 (33%)
│   │   ├── nonce_manager.py   # Nonce 管理 (100%)
│   │   ├── retry_policy.py    # 重试策略 (81%)
│   │   ├── risk_manager.py    # 风险管理 (56%)
│   │   └── tx_sender.py       # 交易发送 (89%)
│   ├── backtesting/          # 回测系统 (Phase 3)
│   │   ├── event_replayer.py # 事件回放 (79%)
│   │   ├── backtester.py     # 回测引擎 (86%)
│   │   └── strategy_analyzer.py # 策略分析 (99%)
│   └── main.py               # 主入口
├── tests/                    # 测试文件
│   ├── unit/                 # 单元测试 (439 个)
│   └── integration/          # 集成测试
├── docs/                     # 文档目录
│   ├── PHASE1_TELEMETRY.md   # Phase 1 文档
│   ├── PHASE2_RESILIENCE.md  # Phase 2 文档
│   └── PHASE3_BACKTESTING.md # Phase 3 文档
├── data/                     # 数据目录
│   ├── polyarb-x.log         # 主日志
│   ├── performance.log       # 性能日志
│   ├── events/               # 事件记录
│   └── trades.db             # 交易数据库
├── htmlcov/                  # 覆盖率报告
├── requirements.txt          # 依赖清单
├── .env.example              # 环境变量模板
├── install_and_test.sh       # 自动安装脚本
├── OFFLINE_INSTALL.md        # 离线安装指南
├── PROJECT_STATUS.md         # 项目状态报告
└── README.md                 # 本文件
```

---

## 🧪 测试覆盖

### 模块覆盖率

| 模块 | 覆盖率 | 测试数 | 提升 |
|------|--------|--------|------|
| telemetry.py | 100% | 20+ | ⬆️ |
| edge.py | 100% | 15+ | ➡️ |
| nonce_manager.py | 100% | 36+ | ⬆️ |
| models.py | 99% | 40+ | ⬆️ |
| metrics.py | 99% | 25+ | ⬆️ |
| strategy_analyzer.py | 99% | 21+ | ➡️ |
| retry_policy.py | 99% | 50+ | ⬆️ |
| circuit_breaker.py | 96% | 60+ | ⬆️ 63% |
| risk_manager.py | 96% | 45+ | ⬆️ 40% |
| negrisk.py | 96% | 45+ | ➡️ |
| tx_sender.py | 89% | 31+ | ➡️ |
| recorder.py | 89% | 12+ | ➡️ |
| atomic.py | 92% | 20+ | ➡️ |
| market_grouper.py | 92% | 38+ | ➡️ |
| backtester.py | 87% | 13+ | ➡️ |
| polymarket_ws.py | 82% | 35+ | ⬆️ 67% |
| web3_client.py | 79% | 24+ | ➡️ |
| event_replayer.py | 79% | 29+ | ➡️ |
| config.py | 78% | - | ➡️ |
| **总计** | **81.93%** | **439** | **⬆️ 7.72%** |

### 查看详细报告

```bash
# 生成 HTML 报告
python3 -m pytest tests/ --cov=src --cov-report=html

# 在浏览器中打开
open htmlcov/index.html
# 或
xdg-open htmlcov/index.html
```

---

## 🔒 安全说明

### 私钥管理

- ✅ 私钥从环境变量读取
- ✅ 永不硬编码在代码中
- ✅ 本地签名，私钥不离开设备
- ✅ 建议使用硬件钱包

### 交易安全

- ✅ 余额检查
- ✅ 仓位限制
- ✅ Gas 成本验证
- ✅ 利润阈值检查
- ✅ 滑点保护

### 建议

1. 在主网之前先在测试网测试
2. 从小额开始交易
3. 定期查看日志
4. 监控交易表现
5. 设置合理的风险限制

---

## 📈 性能指标

### 延迟

- WebSocket 消息处理: < 10ms
- 套利机会检测: < 50ms
- 交易签名: < 100ms
- 端到端执行: < 500ms

### 可靠性

- 自动重连: 指数退避
- 交易重试: 最多 3 次
- 错误处理: 完整覆盖
- 日志记录: 结构化日志

---

## 📚 文档

### 用户文档
- [🚀 生产启动指南](PRODUCTION_LAUNCH.md) - **开始使用前必读**
- [项目状态](PROJECT_STATUS.md) - 完整的项目状态报告
- [离线安装指南](OFFLINE_INSTALL.md) - 无网络环境安装

### 技术文档
- [📊 测试报告](TEST_REPORT.md) - TDD测试审查报告
- [覆盖率报告](htmlcov/index.html) - 详细的代码覆盖率

### 代码文档
- 所有模块都有完整的 docstrings
- 类型提示（Type Hints）
- 示例代码

---

## 🐛 故障排查

### 常见问题

**问题 1: ModuleNotFoundError: No module named 'web3'**

```bash
# 解决方案：安装依赖
python3 -m pip install --user -r requirements.txt
```

**问题 2: 私钥无效**

```bash
# 解决方案：确保私钥格式正确
# 应该是 0x 开头的 64 位十六进制字符串
PRIVATE_KEY=0x1234567890abcdef...
```

**问题 3: WebSocket 连接失败**

```bash
# 解决方案：检查网络连接和 URL
ping clob.polymarket.com
```

**问题 4: 测试失败**

```bash
# 解决方案：确保所有依赖已安装
python3 -m pytest tests/ -v --tb=short
```

---

## 🤝 贡献

欢迎贡献！请遵循：

1. **TDD 方法论** - 先写测试，再写代码
2. **代码规范** - 使用 Black 和 Ruff
3. **测试覆盖** - 新代码需 80%+ 覆盖率
4. **文档** - 更新相关文档

### 开发流程

```bash
# 1. 创建功能分支
git checkout -b feature/new-feature

# 2. 编写测试（TDD）
# 3. 实现功能
# 4. 运行测试
python3 -m pytest tests/ -v

# 5. 检查覆盖率
python3 -m pytest tests/ --cov=src

# 6. 提交代码
git commit -m "feat: add new feature"
```

---

## 📄 许可证

本项目仅供学习和研究使用。使用本软件的风险由用户自行承担。

---

## 🎊 致谢

感谢以下项目和工具：

- [Polymarket](https://polymarket.com/) - 预测市场平台
- [web3.py](https://web3py.readthedocs.io/) - Python Web3 库
- [Pydantic](https://pydantic-docs.helpmanual.io/) - 数据验证
- [pytest](https://docs.pytest.org/) - 测试框架

---

## 📞 联系方式

- 问题反馈：提交 GitHub Issue
- 功能建议：提交 Feature Request

---

**最后更新**: 2026-02-01
**版本**: 0.3.2
**状态**: ✅ 生产就绪

---

<div align="center">

**⭐ 如果这个项目对您有帮助，请给个 Star！⭐**

Made with ❤️ by PolyArb-X Team

</div>
