# Go/No-Go Checklist - 生产上线前检查清单

**版本**: v1.0.0
**最后更新**: 2026-02-02
**用途**: 每个阶段启动前必须完成 ALL 检查项

---

## 使用说明

### 必须通过全部 P0 检查项才能启动
- P0: Critical (必须通过)
- P1: High (强烈建议通过)
- P2: Medium (建议通过)
- P3: Low (可选)

### 检查流程
1. 逐项检查，勾选完成项
2. 记录检查结果（✅ 通过 / ❌ 失败 / ⚠️ 警告）
3. 全部 P0 通过后，签名确认
4. 保存 checklist 到 `docs/go_no_go_checklist_{phase}_{date}.md`

---

## 安全检查 (Security)

### 钱包安全
- [ ] **独立生产钱包** (P0)
  - [ ] 生产环境使用独立钱包（与测试/开发隔离）
  - [ ] 私钥安全存储（硬件钱包/密钥管理服务）
  - [ ] 私钥从未暴露在互联网/代码仓库/日志中
  - [ ] 钱包余额充足但不过度（Phase 1: $10-20, Phase 2: $50-100, Phase 3: $200-500）

- [ ] **Allowance 最小化** (P0)
  - [ ] CTF Exchange 合约 allowance 设置为最小必需值
  - [ ] Phase 1: $20 allowance
  - [ ] Phase 2: $50 allowance
  - [ ] Phase 3: $200 allowance
  - [ ] 不要设置无限 allowance (∞)

- [ ] **私钥权限** (P0)
  - [ ] 私钥文件权限设置为 `600` (仅所有者读写)
  - [ ] 私钥文件路径: `config/.env.production` 或环境变量
  - [ ] 不要将私钥硬编码在代码中
  - [ ] 不要在日志/调试输出中打印私钥

### 网络安全
- [ ] **RPC 端点** (P1)
  - [ ] 使用可信的 Polygon RPC 节点（官方或 Infura/Alchemy）
  - [ ] 配置备用 RPC 节点（至少 2 个）
  - [ ] 验证 RPC 链 ID (Polygon Mainnet: 137)

- [ ] **WebSocket 连接** (P1)
  - [ ] Polymarket WS URL 使用官方 wss://
  - [ ] 验证 SSL 证书有效
  - [ ] 测试断线重连机制

---

## 系统检查 (System)

### 配置文件
- [ ] **config.yaml 存在** (P0)
  - [ ] 文件路径: `config/config.yaml`
  - [ ] YAML 格式正确（可解析）
  - [ ] DRY_RUN 设置正确（Phase 0: true, Phase 1-3: false）
  - [ ] POLYGON_CHAIN_ID = 137

- [ ] **生产 Profile 配置** (P0)
  - [ ] 文件存在: `config/profiles/live_shadow_atomic_v1.yaml` (Phase 0)
  - [ ] 文件存在: `config/profiles/live_safe_atomic_v1.yaml` (Phase 1)
  - [ ] 文件存在: `config/profiles/live_constrained_atomic_v1.yaml` (Phase 2)
  - [ ] 文件存在: `config/profiles/live_scaled_atomic_v1.yaml` (Phase 3)
  - [ ] YAML 格式正确（可解析）
  - [ ] 参数值符合阶段要求

- [ ] **告警配置** (P0)
  - [ ] 文件存在: `config/alerts.production.yaml`
  - [ ] 包含所有必需规则（WS_DISCONNECTED, LIVE_NO_FILLS, CIRCUIT_BREAKER_OPEN 等）
  - [ ] 告警阈值符合阶段要求
  - [ ] YAML 格式正确

- [ ] **环境变量** (P0)
  - [ ] PRIVATE_KEY 已设置（环境变量或 .env 文件）
  - [ ] PRIVATE_KEY 有效（可以签名交易）
  - [ ] WALLET_ADDRESS 与私钥匹配
  - [ ] 不要在 config.yaml 中硬编码私钥

### 脚本与工具
- [ ] **启动脚本** (P0)
  - [ ] `scripts/start_shadow.sh` 可执行（Phase 0）
  - [ ] `scripts/start_live_safe.sh` 可执行（Phase 1-3）
  - [ ] 脚本包含 go_no_go_check.sh 调用（Phase 1-3）
  - [ ] 脚本错误处理正确（set -euo pipefail）

- [ ] **备份脚本** (P0)
  - [ ] `scripts/backup_state.sh` 可执行
  - [ ] 测试备份功能（创建测试备份）
  - [ ] 备份目录存在: `backups/`
  - [ ] 备份命名规范: `YYYYMMDD_HHMM/`

- [ ] **Go/No-Go 检查脚本** (P0)
  - [ ] `scripts/go_no_go_check.sh` 可执行
  - [ ] 脚本返回正确退出码（0=通过, 非0=失败）
  - [ ] 测试脚本运行（bash scripts/go_no_go_check.sh）

- [ ] **每日报告脚本** (P1)
  - [ ] `scripts/production_daily_report.py` 可执行
  - [ ] 测试报告生成（python3 scripts/production_daily_report.py）
  - [ ] 报告目录存在: `reports/daily/`
  - [ ] 报告命名规范: `YYYYMMDD.md`

### 目录结构
- [ ] **数据目录** (P0)
  - [ ] `data/` 目录存在
  - [ ] `data/events.jsonl` 可写
  - [ ] `data/audit/config_changes.jsonl` 可写
  - [ ] `data/alerts/alerts.jsonl` 可写
  - [ ] `data/alerts/alerts_state.json` 可写

- [ ] **日志目录** (P0)
  - [ ] `data/polyarb-x.log` 可写
  - [ ] 日志轮转配置（可选）
  - [ ] 磁盘空间充足（> 1GB）

---

## 数据检查 (Data)

### 历史数据
- [ ] **Events 日志** (P1)
  - [ ] `data/events.jsonl` 存在（Phase 0 后续阶段）
  - [ ] 文件格式正确（JSONL）
  - [ ] 数据完整性检查（无截断/损坏）
  - [ ] 备份最新 events.jsonl

- [ ] **审计日志** (P1)
  - [ ] `data/audit/config_changes.jsonl` 存在
  - [ ] 包含历史配置变更记录
  - [ ] 可用于 rollback

### 备份验证
- [ ] **最新备份** (P0)
  - [ ] `backups/` 目录中有最新备份
  - [ ] 备份包含: config.yaml, .env, data/
  - [ ] 测试恢复流程（从备份恢复）

---

## 操作检查 (Operational)

### 启动前准备
- [ ] **系统资源** (P1)
  - [ ] CPU 使用率正常（< 50%）
  - [ ] 内存充足（> 2GB 可用）
  - [ ] 磁盘空间充足（> 1GB 可用）
  - [ ] 网络连接稳定

- [ ] **服务依赖** (P0)
  - [ ] Polygon RPC 节点可访问（curl https://polygon-rpc.com）
  - [ ] Polymarket WebSocket 可连接（wss://ws-subscriptions-clob.polymarket.com/ws/market）
  - [ ] NTP 时间同步（系统时间准确）

- [ ] **监控告警** (P1)
  - [ ] 告警规则已加载（curl http://localhost:8083/api/alerts/rules）
  - [ ] Webhook 配置正确（如使用）
  - [ ] 测试告警触发（手动触发一个告警）

### 文档确认
- [ ] **生产计划** (P1)
  - [ ] `docs/PRODUCTION_PLAN.md` 已阅读
  - [ ] 理解当前阶段目标和 Success Criteria
  - [ ] 理解 Rollback Criteria

- [ ] **运行手册** (P2)
  - [ ] `docs/PRODUCTION_RUNBOOK.md` 已阅读
  - [ ] 知道如何停止系统
  - [ ] 知道如何处理告警
  - [ ] 知道如何 rollback

### 团队沟通
- [ ] **启动通知** (P1)
  - [ ] 通知团队成员即将启动生产
  - [ ] 确认负责人在线（紧急情况响应）
  - [ ] 设置监控轮换（如果 24/7 运行）

- [ ] **应急预案** (P2)
  - [ ] 准备应急联系方式（电话/即时通讯）
  - [ ] 准备 rollback 步骤文档
  - [ ] 准备资金转移流程（如需紧急撤资）

---

## 通过/不通过规则 (Pass/Fail Criteria)

### 通过条件 (GO)
- ✅ **全部 P0 检查项通过**
- ⚠️ P1 检查项失败不超过 2 项
- ❌ P2/P3 检查项失败不影响启动

### 不通过条件 (NO-GO)
- ❌ **任意 P0 检查项失败**
- ❌ P1 检查项失败超过 2 项
- ❌ 发现严重安全漏洞（私钥泄露/无限 allowance）
- ❌ 系统测试失败（RPC/WS 连接失败）

### 处理流程
1. **NO-GO**: 修复所有失败项，重新检查
2. **GO (带警告)**: 记录警告项，监控运行，启动后尽快修复
3. **GO (干净)**: 立即启动生产

---

## 检查记录模板

```markdown
# Go/No-Go Checklist - Phase {X} - {DATE}

## 检查结果

### 安全检查
- P0: ✅ 全部通过
- P1: ⚠️ 1 项警告（RPC 备用节点未配置）

### 系统检查
- P0: ✅ 全部通过
- P1: ✅ 全部通过

### 数据检查
- P0: ✅ 全部通过
- P1: ✅ 全部通过

### 操作检查
- P0: ✅ 全部通过
- P1: ⚠️ 1 项警告（应急预案未准备）

## 总体评估
✅ **GO** (带 2 项警告)

## 签名确认
- 检查人: {Name}
- 检查时间: {YYYY-MM-DD HH:MM:SS}
- 备注: 警告项将在启动后 24 小时内修复

## 警告项跟踪
1. RPC 备用节点未配置 → 负责人: {Name}, 截止: {Date}
2. 应急预案未准备 → 负责人: {Name}, 截止: {Date}
```

---

## 附录

### A. 快速检查命令

```bash
# 一键执行所有检查
bash scripts/go_no_go_check.sh

# 手动检查关键项
# 1. 验证 config.yaml
python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))"

# 2. 验证 profile YAML
python3 -c "import yaml; yaml.safe_load(open('config/profiles/live_safe_atomic_v1.yaml'))"

# 3. 验证告警配置
python3 -c "import yaml; yaml.safe_load(open('config/alerts.production.yaml'))"

# 4. 测试 RPC 连接
curl -X POST https://polygon-rpc.com -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","method":"eth_chainId","params":[],"id":1}'

# 5. 测试备份
bash scripts/backup_state.sh

# 6. 测试告警规则（假设系统运行中）
curl http://localhost:8083/api/alerts/rules
```

### B. 常见问题

**Q: 如果 P0 检查项失败怎么办？**
A: 必须修复后重新检查，不能跳过。

**Q: 如果 P1 检查项失败怎么办？**
A: 可以启动，但必须在启动后 24-48 小时内修复。

**Q: 谁有权决定 GO/NO-GO？**
A: 至少 2 名团队成员确认（建议包括技术负责人）。

**Q: 检查有效期多久？**
A: 检查结果有效期 24 小时，超过需重新检查。

---

**最后更新**: 2026-02-02
**文档版本**: v1.0.0
**维护者**: PolyArb-X Team
