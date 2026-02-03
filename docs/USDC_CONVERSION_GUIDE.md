# USDC.b 转换为原生 USDC 指南

## 问题诊断

您当前的余额分布：
- **原生 USDC** (Polymarket 支持): 0.00 USDC
- **桥接 USDC.b** (Polymarket 不支持): 49.84 USDC
- **总资产**: 49.84 USDC（但无法在 Polymarket 交易）

## 解决方案

### 方案 1: 通过 Uniswap Swap（推荐 - 最快）

**优点**:
- 最快速（几分钟完成）
- 无需桥接回以太坊
- 直接在 Polygon 上完成

**步骤**:

1. **打开 MetaMask 钱包**
   - 切换到 Polygon 网络
   - 确认钱包地址: `0x66B3775D...7132Af`

2. **访问 Uniswap**
   - 网址: https://app.uniswap.org/swap
   - 连接您的 MetaMask 钱包

3. **配置 Swap**
   - From: **USDC.b** (0x3c49...c3359)
   - To: **USDC** (0x2791...a84174)
   - Amount: **49.84 USDC.b**

4. **执行 Swap**
   - 点击 "Swap"
   - 确认 MetaMask 交易
   - 等待确认（约 30 秒）

5. **验证结果**
   - 访问 http://localhost:8089/api/balance
   - 确认余额显示 > 0 USDC

**预期滑点**: < 0.1% (几乎可忽略)
**Gas 费用**: 约 $0.01-0.05 (Polygon 很便宜)

---

### 方案 2: 通过 SushiSwap Swap（备选）

如果 Uniswap 流动性不足，可以使用 SushiSwap：

1. 访问: https://www.sushi.com/swap
2. 切换到 Polygon 网络
3. Swap: USDC.b → USDC (Circle)

---

### 方案 3: 桥接回以太坊（不推荐 - 成本高）

**缺点**:
- 需要 $5-20 桥接费用
- 需要 $10-50 以太坊 Gas 费
- 总时间 30-60 分钟
- 仍需在以太坊上兑换

**仅在以下情况使用**:
- Uniswap 和 SushiSwap 都没有流动性
- 您需要将资金转移到以太坊生态

---

### 方案 4: 使用 1inch 聚合器（最佳汇率）

1. 访问: https://app.1inch.io/
2. 连接钱包并切换到 Polygon
3. Swap USDC.b → USDC
4. 1inch 会自动寻找最佳路径和汇率

---

## 转换后验证

### 方法 1: 通过 API 验证
```bash
curl http://localhost:8089/api/balance
```

应该返回:
```json
{
  "balance": "49.xx",  # 应该 > 0
  "currency": "USDC",
  "mode": "live"
}
```

### 方法 2: 通过 Polygonscan 验证
1. 访问: https://polygonscan.com/address/0x66B3775D0577C97f6e6eb8ce01468fB4ab7132Af
2. 查看 USDC 代币余额
3. 确认余额 > 0

### 方法 3: 通过 Dashboard 验证
访问: http://localhost:8089
查看"账户余额"卡片显示

---

## 常见问题

### Q: 为什么要转换？
A: Polymarket CLOB 只接受原生 USDC（Circle 官方发行），不识别桥接的 USDC.b。

### Q: 转换会损失资金吗？
A: 几乎不会。滑点通常 < 0.1%，49.84 USDC.b → 约 49.79 USDC。

### Q: 转换需要多长时间？
A: Uniswap/SushiSwap 约 2-5 分钟，桥接回以太坊需要 30-60 分钟。

### Q: 转换有风险吗？
A: 风险很低。Polygon 网络安全，USDC 是稳定币。

### Q: 转换后资金安全吗？
A: 完全安全。您的资金仍在自己的钱包中，只是换了代币形式。

---

## 安全提醒

⚠️ **永远不要**:
- 向任何人透露您的私钥或助记词
- 授权可疑的智能合约
- 点击不明链接连接钱包

✅ **始终**:
- 验证网站 URL（uniswap.org, sushi.com, 1inch.io）
- 在 MetaMask 中确认交易详情
- 从官方网址访问 DEX

---

## 转换完成后的下一步

转换完成后，您将拥有：
- ✅ 49.79 USDC（原生）- 可用于 Polymarket 交易
- ✅ 系统可以执行真实的套利交易
- ✅ 账户余额将正确显示

然后我们可以继续测试和优化 CLOB API 的真实交易功能。
