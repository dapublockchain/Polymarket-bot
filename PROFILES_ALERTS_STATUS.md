# Profiles & Alerts 系统实现状态

## ✅ 已完成 (Phase 1-3 核心)

### Phase 1: 基础设施 (100% 完成)
- ✅ 目录结构创建：`config/profiles/`, `data/audit/`, `data/alerts/`
- ✅ 7 个内置 Profile YAML：
  - `conservative.yaml` - 保守型
  - `balanced.yaml` - 平衡型（默认）
  - `aggressive.yaml` - 激进型
  - `maker.yaml` - 做市商型
  - `taker.yaml` - 接单型
  - `sandbox.yaml` - 沙盒测试
  - `live_safe.yaml` - 实盘安全
- ✅ `config/alerts.yaml` - 10 个内置告警规则
- ✅ `scripts/seed_profiles.sh` - 配置初始化脚本（已测试通过）

### Phase 2: Profile 管理后端 (100% 完成)
- ✅ `src/api/profile_manager.py` - ProfileManager 类
  - ✅ `list_profiles()` - 列出所有 profiles
  - ✅ `get_profile(name)` - 加载指定 profile
  - ✅ `deep_merge()` - 深度合并配置
  - ✅ `calculate_diff()` - 计算配置差异
  - ✅ `validate_config()` - 配置验证
  - ✅ `detect_risk_changes()` - 检测危险操作
  - ✅ `apply_profile()` - 应用配置并写入审计日志
  - ✅ `save_custom_profile()` - 保存自定义 profile
  - ✅ `rollback()` - 回滚到上一份配置
  - ✅ `get_audit_history()` - 获取审计历史

- ✅ 集成到 `ui/web_server.py`：
  - ✅ `GET /api/profiles` - 列出 profiles
  - ✅ `GET /api/profiles/{name}` - 获取 profile 详情
  - ✅ `POST /api/profiles/{name}/apply` - 应用 profile
  - ✅ `POST /api/profiles/save` - 保存自定义 profile
  - ✅ `POST /api/profiles/rollback` - 回滚
  - ✅ `GET /api/audit/config_changes` - 审计历史

### Phase 3: Alert 引擎后端 (100% 完成)
- ✅ `src/api/alert_engine.py` - AlertEngine 类
  - ✅ `evaluate_rules()` - 评估告警规则
  - ✅ `_check_rule_condition()` - 检查规则条件
  - ✅ `_send_webhook()` - 发送 webhook 通知
  - ✅ `get_alert_state()` - 获取当前告警状态
  - ✅ `get_alert_history()` - 获取告警历史
  - ✅ `ack_alert()` - 确认告警
  - ✅ `update_rules()` - 更新告警规则
  - ✅ 10 个内置告警规则（在 alerts.yaml 中定义）

---

## 🚧 待完成 (Phase 4-6)

### Phase 4: UI 前端 (0% 完成)

#### 4.1 Profiles 页面
**文件**: `ui/profiles.html`

需要实现的功能：
- [ ] Profile 卡片列表（7 个内置 + 自定义）
- [ ] Profile 详情显示（标签、描述）
- [ ] 配置差异预览（diff viewer）
- [ ] Apply 按钮和风险确认弹窗
- [ ] "Save as Custom Profile" 表单
- [ ] Rollback 按钮
- [ ] 审计历史时间线

**JavaScript**: `ui/profiles.js`
```javascript
// 需要实现的功能
- loadProfiles() - 加载 profile 列表
- loadProfile(name) - 加载 profile 详情
- previewDiff(name) - 预览配置差异
- applyProfile(name) - 应用 profile（带二次确认）
- saveCustomProfile() - 保存自定义 profile
- rollback() - 回滚配置
- loadAuditHistory() - 加载审计历史
```

#### 4.2 Alerts 页面
**文件**: `ui/alerts.html`

需要实现的功能：
- [ ] 左侧：规则列表（toggle enabled、编辑阈值）
- [ ] 右侧：告警时间线（FIRING/RESOLVED/ACKED）
- [ ] 告警详情面板
- [ ] ACK 按钮
- [ ] Test Webhook 按钮
- [ ] 实时轮询（3-5 秒）

**JavaScript**: `ui/alerts.js`
```javascript
// 需要实现的功能
- loadRules() - 加载告警规则
- updateRule(id, data) - 更新规则
- loadAlertState() - 加载告警状态
- loadAlertHistory() - 加载告警历史
- ackAlert(id) - 确认告警
- testWebhook() - 测试 webhook
- startPolling() - 开始轮询（3-5秒）
```

#### 4.3 全局组件
- [ ] **Bell Icon**（顶部导航栏）
  - 显示未读告警数
  - 点击下拉告警列表

- [ ] **Danger Confirmation Modal**
  - 危险操作二次确认
  - 显示风险详情
  - 需勾选确认

- [ ] **Toast 通知**
  - 配置应用成功/失败
  - 告警触发提示

#### 4.4 更新 dashboard.html
- [ ] 添加 "Profiles" 和 "Alerts" 导航链接
- [ ] 添加 Bell Icon 组件
- [ ] 添加 "Active Alerts" 小组件

### Phase 5: 集成与测试 (0% 完成)

#### 5.1 单元测试
**文件**:
- `tests/unit/test_profile_manager.py`
- `tests/unit/test_alert_engine.py`
- `tests/unit/test_config_merge.py`

测试覆盖：
- [ ] ProfileManager 所有方法
- [ ] AlertEngine 所有方法
- [ ] 深度合并逻辑
- [ ] 差异计算逻辑
- [ ] 风险检测逻辑

目标：≥80% 代码覆盖率

#### 5.2 集成测试
- [ ] Profile 应用流程（包含危险操作）
- [ ] Alert 触发和解决流程
- [ ] Webhook 发送测试

#### 5.3 手动验收测试
- [ ] UI 能看到 Profiles 列表
- [ ] 切换 Profile 显示 diff
- [ ] 应用 Profile 后 config.yaml 已更新
- [ ] 审计记录已写入
- [ ] 能创建自定义 Profile
- [ ] 能回滚到上一份配置
- [ ] Alerts 页面可编辑规则
- [ ] 编辑规则后生效
- [ ] 人为制造异常触发告警
- [ ] 告警在 UI 显示
- [ ] 告警通过 Webhook 发送
- [ ] 危险操作需要二次确认

### Phase 6: 文档 (0% 完成)

#### 6.1 创建 `docs/PROFILES_AND_ALERTS.md`
需要包含的内容：
- [ ] Profiles 用法说明
- [ ] 内置 Profile 解释（适用场景）
- [ ] 风险提示说明
- [ ] Alerts 规则说明与阈值建议
- [ ] Webhook payload 示例
- [ ] 故障排查指南

#### 6.2 更新 README.md
- [ ] 添加 Profiles 和 Alerts 功能介绍
- [ ] 更新启动流程（提及运行 seed_profiles.sh）
- [ ] 添加 API 端点文档

---

## 📊 完成度统计

| 阶段 | 完成度 | 状态 |
|------|--------|------|
| Phase 1: 基础设施 | 100% | ✅ 完成 |
| Phase 2: Profile 后端 | 100% | ✅ 完成 |
| Phase 3: Alert 后端 | 100% | ✅ 完成 |
| Phase 4: UI 前端 | 0% | 🚧 待开始 |
| Phase 5: 测试 | 0% | 🚧 待开始 |
| Phase 6: 文档 | 0% | 🚧 待开始 |

**总体完成度**: ~50% (核心后端已完成)

---

## 🎯 下一步行动

### 立即可做（后端已就绪）
1. **测试 Profile API**:
   ```bash
   # 启动 web server
   python3 ui/web_server.py --port 8082

   # 测试 API
   curl http://localhost:8082/api/profiles
   curl http://localhost:8082/api/profiles/conservative
   ```

2. **应用 Profile**:
   ```bash
   curl -X POST http://localhost:8082/api/profiles/conservative/apply
   ```

3. **查看审计历史**:
   ```bash
   curl http://localhost:8082/api/audit/config_changes
   ```

### 需要实现（UI 前端）
1. 创建 `ui/profiles.html` 和 `ui/profiles.js`
2. 创建 `ui/alerts.html` 和 `ui/alerts.js`
3. 更新 `ui/dashboard.html` 添加导航和 Bell Icon

### 建议优先级
**P0** (最高):
- Profiles 页面（核心功能）
- 全局组件（Bell Icon, Toast）

**P1** (高):
- Alerts 页面（监控功能）
- Danger Confirmation Modal

**P2** (中):
- 单元测试
- 集成测试

**P3** (低):
- 完整文档
- 手动验收测试

---

## 🛠️ 技术栈

### 后端
- Python 3.10+
- YAML 配置文件
- HTTP Server (Python 标准库)

### 前端
- HTML5
- CSS3
- Vanilla JavaScript (无框架)
- Chart.js (可选，用于图表)

### 数据存储
- YAML 文件（配置）
- JSONL 文件（审计日志、告警事件）
- JSON 文件（告警状态）

---

## 📝 关键设计决策

### Profile 合并策略
- **Partial Override**: Profile 只覆盖其声明的字段
- **Deep Merge**: 递归合并嵌套字典
- **Validation**: 应用前验证配置合法性
- **Risk Detection**: 自动检测危险操作并警告

### Alert 评估引擎
- **Rule-Based**: 基于规则的告警系统
- **Sliding Window**: 支持时间窗口聚合
- **State Machine**: PENDING → FIRING → RESOLVED/ACKED
- **Async Webhook**: 异步发送 webhook，支持重试

### 审计日志
- **JSONL Format**: 每行一个 JSON 对象，易于追加和解析
- **Complete Snapshot**: 记录 previous_config 完整快照
- **Immutable**: 审计日志只追加，不修改

---

## 🔧 依赖项

新增 Python 依赖：
```bash
# requirements.txt 中添加
pyyaml>=6.0
aiohttp>=3.8.0  # 用于异步 webhook
```

安装命令：
```bash
pip install pyyaml aiohttp
```

---

## 📞 联系与支持

如有问题或建议，请：
1. 查看代码注释和文档
2. 检查 `data/audit/config_changes.jsonl` 了解配置变更历史
3. 查看 `data/alerts/alerts.jsonl` 了解告警触发历史

---

**生成时间**: 2026-02-01
**版本**: v4.3.0
**状态**: Phase 1-3 完成，Phase 4-6 待实现
