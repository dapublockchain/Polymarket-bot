# 🚀 PolyArb-X 生产环境启动指南

## 启动前检查清单

### ✅ 1. 环境变量配置

确保 `.env` 文件包含所有必需的配置：

```bash
# Polygon RPC 节点
POLYGON_RPC_URL=https://polygon-rpc.com
# 或使用私有节点以提高性能

# 钱包私钥（必需）
PRIVATE_KEY=0x...  # 64位十六进制字符串

# Polymarket WebSocket
POLYMARKET_WS_URL=wss://clob.polymarket.com/ws

# 交易参数
TRADE_SIZE=100                # 每笔交易数量
MIN_PROFIT_THRESHOLD=0.01     # 最小利润阈值 (1%)
MAX_POSITION_SIZE=1000        # 最大仓位大小
MAX_GAS_PRICE=100000000000    # 最大Gas价格 (100 Gwei)

# 风险管理
DAILY_LOSS_LIMIT=100          # 每日最大亏损 (USDC)
MAX_CONSECUTIVE_LOSSES=3      # 最大连续亏损次数

# 可选：日志级别
LOG_LEVEL=INFO                # DEBUG, INFO, WARNING, ERROR
```

### ✅ 2. 验证依赖安装

```bash
# 检查Python版本
python3 --version  # 需要 3.10+

# 安装依赖（如果还没安装）
python3 -m pip install --user -r requirements.txt

# 验证关键依赖
python3 -c "import web3; print('web3:', web3.__version__)"
python3 -c "import pydantic; print('pydantic:', pydantic.__version__)"
python3 -c "import asyncio; print('asyncio: OK')"
```

### ✅ 3. 运行测试套件

```bash
# 运行所有测试确保系统正常
python3 -m pytest tests/unit/ -v

# 预期输出: 350 passed ✅
```

### ✅ 4. 检查数据目录

```bash
# 确保数据目录存在
mkdir -p data/events
mkdir -p data/logs

# 检查目录权限
ls -la data/
```

### ✅ 5. 网络连接测试

```bash
# 测试RPC连接
curl -X POST https://polygon-rpc.com -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# 测试WebSocket连接（使用wscat或类似工具）
# wscat -c wss://clob.polymarket.com/ws
```

---

## 启动步骤

### 步骤 1: 干运行模式（强烈推荐）

在实盘交易前，先进行干运行测试：

```bash
# 干运行模式 - 不会执行实际交易
python3 src/main.py --dry-run
```

**干运行模式会：**
- ✅ 连接WebSocket并接收实时数据
- ✅ 检测套利机会
- ✅ 模拟交易执行
- ❌ 不发送实际交易
- ❌ 不使用真实资金

**观察要点：**
- WebSocket连接是否稳定
- 是否能检测到套利机会
- 日志输出是否正常
- 性能指标是否符合预期

**建议运行时间：** 至少1小时，或直到观察到多次机会检测

### 步骤 2: 小额测试

如果干运行正常，开始小额实盘测试：

```bash
# 编辑 .env 文件
TRADE_SIZE=10              # 降低交易数量到10
MIN_PROFIT_THRESHOLD=0.02  # 提高利润阈值到2%以减少交易频率

# 启动系统
python3 src/main.py
```

**监控要点：**
- 检查每笔交易的盈亏
- 验证Gas费用是否合理
- 确认滑点在可接受范围
- 观察策略胜率

**建议：**
- 运行24小时
- 记录所有交易
- 计算实际收益率
- 如果盈利，逐步增加交易数量

### 步骤 3: 逐步增加规模

根据小额测试结果，逐步增加交易规模：

```bash
# 第1周: 小额运行
TRADE_SIZE=10
MIN_PROFIT_THRESHOLD=0.02

# 第2周: 如果盈利，增加规模
TRADE_SIZE=50
MIN_PROFIT_THRESHOLD=0.015

# 第3周+: 继续优化
TRADE_SIZE=100
MIN_PROFIT_THRESHOLD=0.01
```

---

## 监控和管理

### 实时监控

```bash
# 查看主日志
tail -f data/polyarb-x.log

# 查看性能日志
tail -f data/performance.log

# 查看错误日志
grep ERROR data/polyarb-x.log

# 统计今日交易
grep "Trade executed" data/polyarb-x.log | wc -l
```

### 性能指标检查

```bash
# 检查延迟统计
grep "latency" data/performance.log | tail -20

# 检查胜率
grep "win_rate" data/performance.log | tail -5

# 检查盈亏
grep "net_profit" data/performance.log | tail -5
```

### 停止系统

```bash
# 安全停止（发送SIGTERM）
# 按下 Ctrl+C 或:
kill -TERM $(pgrep -f "python3 src/main.py")

# 等待系统完成当前交易并退出
# 不要使用 kill -9，可能导致数据损坏
```

---

## 故障排查

### 问题 1: WebSocket连接失败

**症状：** `WebSocket connection error`

**解决方案：**
```bash
# 1. 检查网络连接
ping clob.polymarket.com

# 2. 检查防火墙设置
# 3. 尝试使用VPN
# 4. 检查Polymarket服务状态
```

### 问题 2: 交易失败

**症状：** `Transaction failed` 或 `Gas too low`

**解决方案：**
```bash
# 1. 检查钱包余额
python3 -c "from web3 import Web3; w3 = Web3(Web3.HTTPProvider('https://polygon-rpc.com')); print(w3.eth.get_balance('YOUR_ADDRESS'))"

# 2. 增加Gas价格限制
MAX_GAS_PRICE=200000000000  # 200 Gwei

# 3. 检查Nonce是否正确
# 系统会自动管理，但重启后可能需要时间同步
```

### 问题 3: 没有检测到机会

**症状：** 长时间没有交易

**解决方案：**
```bash
# 1. 降低利润阈值
MIN_PROFIT_THRESHOLD=0.005  # 0.5%

# 2. 检查日志确认数据接收正常
grep "orderbook" data/polyarb-x.log | tail -20

# 3. 市场可能没有足够的套利机会
# 这是正常的，耐心等待
```

### 问题 4: 系统崩溃

**症状：** 程序意外退出

**解决方案：**
```bash
# 1. 查看完整错误日志
cat data/polyarb-x.log | tail -100

# 2. 检查系统资源
top  # 查看CPU/内存使用

# 3. 重启系统
python3 src/main.py

# 4. 如果持续崩溃，可能是代码bug
# 检查GitHub Issues或提交新Issue
```

---

## 最佳实践

### ✅ DO - 推荐做法

1. **从小额开始** - 先用小额测试策略
2. **持续监控** - 定期检查日志和性能
3. **设置止损** - 配置DAILY_LOSS_LIMIT
4. **备份数据** - 定期备份data目录
5. **保持更新** - 关注新版本和安全更新
6. **记录交易** - 保留交易日志用于分析
7. **风险分散** - 不要投入所有资金

### ❌ DON'T - 避免做法

1. **不要投入无法承受损失的资金**
2. **不要在未经测试的情况下运行**
3. **不要修改生产代码而不测试**
4. **不要共享私钥或.env文件**
5. **不要在公共WiFi下运行**
6. **不要忽略错误日志**
7. **不要让系统无人值守过久**

---

## 安全建议

### 私钥保护

- ✅ 使用硬件钱包（推荐）
- ✅ .env文件设置权限600：`chmod 600 .env`
- ✅ 不要将私钥提交到Git
- ✅ 使用专门的交易账户，不要存放大量资金
- ✅ 定期轮换私钥

### 系统安全

- ✅ 使用防火墙限制入站连接
- ✅ 在安全的环境中运行（VPS或本地）
- ✅ 定期更新系统和依赖
- ✅ 监控异常活动
- ✅ 设置告警通知

---

## 盈利退出策略

### 当达到盈利目标时

1. **部分退出** - 提取初始投资
2. ** reinvest** - 将利润再投资
3. **优化参数** - 根据实际数据调整策略

### 当持续亏损时

1. **停止交易** - 暂停系统
2. **分析原因** - 检查日志和数据
3. **重新回测** - 使用新数据回测
4. **调整策略** - 优化参数或切换策略

---

## 联系和支持

- **文档**: [README.md](README.md)
- **问题反馈**: GitHub Issues
- **技术文档**: [docs/](docs/)
- **Phase文档**:
  - [Phase 1: 可观测性](docs/PHASE1_TELEMETRY.md)
  - [Phase 2: 韧性机制](docs/PHASE2_RESILIENCE.md)
  - [Phase 3: 回测系统](docs/PHASE3_BACKTESTING.md)

---

## 免责声明

**重要提示：**

- ⚠️ 加密货币交易涉及高风险
- ⚠️ 过去表现不代表未来结果
- ⚠️ 只投入你能承受损失的资金
- ⚠️ 作者不对任何损失负责
- ⚠️ 本软件按"原样"提供，无任何保证

**使用本软件即表示您同意：**
1. 自行承担所有风险
2. 进行充分的测试
3. 遵守当地法律法规
4. 理性投资，量力而行

---

## 启动检查清单

在启动生产环境前，确保：

- [ ] .env文件已正确配置
- [ ] 私钥安全且未泄露
- [ ] 所有依赖已安装
- [ ] 350个测试全部通过
- [ ] 干运行测试已完成（至少1小时）
- [ ] 网络连接正常
- [ ] 数据目录已创建
- [ ] 日志监控已设置
- [ ] 止损参数已配置
- [ ] 理解所有风险
- [ ] 有应急预案
- [ ] 只投入可承受损失的资金

**全部勾选后，可以开始：**

```bash
# 启动生产环境
python3 src/main.py
```

---

**祝交易顺利！🚀📈**

*最后更新: 2026-02-01*
*版本: 0.3.0*
