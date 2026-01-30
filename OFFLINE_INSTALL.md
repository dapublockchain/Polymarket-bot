# 离线安装指南

## 问题诊断结果

当前环境运行在 **macOS 沙盒** 中，网络访问被完全禁止（`SANDBOX_RUNTIME=1`）。

## 解决方案

### 方案 A: 直接安装（推荐）✅

**在您自己的终端（非沙盒环境）中执行**：

```bash
cd /Users/dapumacmini/polyarb-x

# 方法1: 使用 requirements.txt
python3 -m pip install --user -r requirements.txt

# 方法2: 使用安装脚本
bash install_deps.sh

# 方法3: 手动安装
python3 -m pip install --user \
  web3==6.11.3 \
  eth-account==0.10.0 \
  pydantic==2.5.3 \
  websockets==12.0 \
  aiohttp==3.9.1 \
  python-dotenv==1.0.0 \
  loguru==0.7.3
```

### 方案 B: 离线安装（需要另一台机器）

如果您的终端也无法访问网络：

#### 步骤 1: 在有网络的机器上下载包

```bash
# 克隆或复制项目到有网络的机器
cd /path/to/polyarb-x

# 运行下载脚本
bash download_packages.sh

# 这将创建 packages/ 目录，包含所有 .whl 文件
```

#### 步骤 2: 传输包文件

将 `packages/` 目录传输到目标机器（Mac）：
- USB 驱动器
- 文件共享（AirDrop、SMB 等）
- 云存储（iCloud、Google Drive 等）

#### 步骤 3: 在目标机器上安装

```bash
cd /Users/dapumacmini/polyarb-x

# 确保已传输 packages/ 目录
ls packages/  # 应该看到很多 .whl 文件

# 运行离线安装脚本
bash install_offline.sh
```

## 验证安装

安装完成后，运行以下命令验证：

```bash
cd /Users/dapumacmini/polyarb-x

# 验证导入
python3 -c "import web3; print('web3:', web3.__version__)"
python3 -c "import eth_account; print('eth_account: OK')"

# 运行测试
python3 -m pytest tests/ -v

# 检查覆盖率
python3 -m pytest tests/ --cov=src --cov-report=term-missing
```

## 文件说明

| 文件 | 用途 |
|------|------|
| `requirements.txt` | Python 依赖清单 |
| `install_deps.sh` | 在线安装脚本 |
| `download_packages.sh` | 下载离线包（在有网络的机器上） |
| `install_offline.sh` | 离线安装脚本 |
| `packages/` | 离线包目录（由 download_packages.sh 生成） |

## 故障排查

### 问题: pip 命令不存在

```bash
# 使用 python3 -m pip 代替
python3 -m pip install --user -r requirements.txt
```

### 问题: 权限错误

```bash
# 使用 --user 标志安装到用户目录
python3 -m pip install --user -r requirements.txt
```

### 问题: Python 版本不兼容

```bash
# 检查 Python 版本（需要 3.10+）
python3 --version

# 如果版本过低，请安装 Python 3.10 或更高版本
```

## 下一步

安装成功后：

1. 配置环境变量（复制 `.env.example` 到 `.env`）
2. 运行测试：`python3 -m pytest tests/`
3. 运行项目：`python3 src/main.py`

## 需要帮助？

如果遇到问题，请提供以下信息：
- Python 版本：`python3 --version`
- pip 版本：`python3 -m pip --version`
- 错误信息：完整的错误输出
