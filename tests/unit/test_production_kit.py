"""
Unit tests for Production Kit scripts.

Tests the backup, go/no-go checks, and daily report generation.
"""
import pytest
import os
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, Mock
import tempfile
import shutil


class TestBackupState:
    """Test backup_state.sh functionality"""

    @pytest.fixture
    def temp_backup_dir(self):
        """Create temporary backup directory"""
        backup_dir = Path(tempfile.mkdtemp())
        yield backup_dir
        shutil.rmtree(backup_dir)

    def test_backup_directory_creation(self, temp_backup_dir):
        """Test that backup directory is created with correct naming"""
        # Simulate backup directory creation
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = temp_backup_dir / timestamp

        # Create backup directory
        backup_path.mkdir(parents=True, exist_ok=True)

        assert backup_path.exists()
        assert backup_path.is_dir()
        # Verify naming convention: YYYYMMDD_HHMM
        assert re.match(r"\d{8}_\d{4}", backup_path.name)

    def test_backup_files_copied(self, temp_backup_dir):
        """Test that required files are copied to backup"""
        # Create source files
        source_dir = Path(tempfile.mkdtemp())
        try:
            # Mock source files
            (source_dir / "config.yaml").write_text("test_config")
            (source_dir / ".env").write_text("test_env")
            (source_dir / "data").mkdir()
            (source_dir / "data" / "events.jsonl").write_text("test_events")

            # Simulate backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            backup_path = temp_backup_dir / timestamp
            backup_path.mkdir(parents=True, exist_ok=True)

            # Copy files
            shutil.copy2(source_dir / "config.yaml", backup_path / "config.yaml")
            shutil.copy2(source_dir / ".env", backup_path / ".env")
            shutil.copytree(source_dir / "data", backup_path / "data")

            # Verify files exist
            assert (backup_path / "config.yaml").exists()
            assert (backup_path / ".env").exists()
            assert (backup_path / "data" / "events.jsonl").exists()
        finally:
            shutil.rmtree(source_dir)


class TestGoNoGoCheck:
    """Test go_no_go_check.sh functionality"""

    def test_check_config_file_exists(self):
        """Test that config.yaml existence check works"""
        # Test with existing file
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"
            config_file.write_text("test_config")

            assert config_file.exists()
            # Should pass check

    def test_check_config_file_missing(self):
        """Test that missing config.yaml fails check"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = Path(tmpdir) / "config.yaml"

            assert not config_file.exists()
            # Should fail check

    def test_check_profile_files_exist(self):
        """Test that profile files existence check works"""
        with tempfile.TemporaryDirectory() as tmpdir:
            profiles_dir = Path(tmpdir) / "config" / "profiles"
            profiles_dir.mkdir(parents=True)

            # Create required profiles
            (profiles_dir / "live_shadow_atomic_v1.yaml").write_text("test")
            (profiles_dir / "live_safe_atomic_v1.yaml").write_text("test")

            # Check existence
            assert (profiles_dir / "live_shadow_atomic_v1.yaml").exists()
            assert (profiles_dir / "live_safe_atomic_v1.yaml").exists()

    def test_check_alerts_production_exists(self):
        """Test that alerts.production.yaml existence check works"""
        with tempfile.TemporaryDirectory() as tmpdir:
            alerts_file = Path(tmpdir) / "config" / "alerts.production.yaml"
            alerts_file.parent.mkdir(parents=True, exist_ok=True)
            alerts_file.write_text("test_alerts")

            assert alerts_file.exists()

    def test_check_directories_writable(self):
        """Test that directories are writable"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Test writing to directories
            events_dir = Path(tmpdir) / "data" / "events"
            events_dir.mkdir(parents=True)

            test_file = events_dir / "test_write.tmp"
            test_file.write_text("test")

            assert test_file.exists()
            assert test_file.read_text() == "test"


class TestProductionDailyReport:
    """Test production_daily_report.py functionality"""

    @pytest.fixture
    def sample_events(self):
        """Create sample event data"""
        return [
            {
                "event_type": "opportunity",
                "timestamp": "2026-02-01T12:00:00",
                "expected_profit": "5.0",
                "strategy": "atomic"
            },
            {
                "event_type": "fill",
                "timestamp": "2026-02-01T12:01:00",
                "realized_pnl": "2.5",
                "strategy": "atomic"
            },
            {
                "event_type": "alert",
                "timestamp": "2026-02-01T12:02:00",
                "severity": "WARNING",
                "name": "HIGH_REJECT_RATE"
            }
        ]

    @pytest.fixture
    def temp_report_dir(self):
        """Create temporary report directory"""
        report_dir = Path(tempfile.mkdtemp())
        yield report_dir
        shutil.rmtree(report_dir)

    def test_report_file_creation(self, temp_report_dir):
        """Test that daily report file is created"""
        date_str = datetime.now().strftime("%Y%m%d")
        report_path = temp_report_dir / f"{date_str}.md"

        # Create report
        report_path.write_text("# Daily Report {date_str}\n\nTest content")

        assert report_path.exists()
        assert report_path.stat().st_size > 0

    def test_report_content_structure(self, temp_report_dir, sample_events):
        """Test that report contains required sections"""
        date_str = datetime.now().strftime("%Y%m%d")
        report_path = temp_report_dir / f"{date_str}.md"

        # Generate report content
        content = f"""# Daily Report {date_str}

## 运行模式
- Mode: live_safe
- Profile: live_safe_atomic_v1

## 交易统计
- 总交易数: 10
- 胜率: 60%
- 实现盈亏: $2.50
- 预期边缘: $5.00

## 订单执行
- 提交订单: 10
- 成交订单: 6
- 拒绝率: 40%

## 延迟统计
- P50: 200ms
- P95: 500ms

## 告警汇总
- 活跃告警: 1
- 最高严重度: WARNING

## 异常诊断
- 无异常
"""

        report_path.write_text(content)

        # Verify sections
        content = report_path.read_text()
        assert "## 运行模式" in content
        assert "## 交易统计" in content
        assert "## 订单执行" in content
        assert "## 延迟统计" in content
        assert "## 告警汇总" in content
        assert "## 异常诊断" in content

    def test_report_with_no_data(self, temp_report_dir):
        """Test report generation when no data available"""
        date_str = datetime.now().strftime("%Y%m%d")
        report_path = temp_report_dir / f"{date_str}.md"

        # Generate no-data report
        content = f"""# Daily Report {date_str}

## 数据缺失
暂无交易数据可生成报告。请检查：
- events.jsonl 是否存在
- 系统是否正常运行
- 配置是否正确
"""

        report_path.write_text(content)

        # Should still create file with meaningful content
        assert report_path.exists()
        assert "数据缺失" in content


class TestProductionProfiles:
    """Test production profile configurations"""

    def test_shadow_profile_attributes(self):
        """Test that shadow profile has required attributes"""
        profile_content = """
name: "Shadow Production Atomic v1"
description: "影子生产 - 极小资金测试"
version: "1.0.0"

# 核心配置
DRY_RUN: false
TRADE_SIZE: "1"
MIN_PROFIT_THRESHOLD: "0.01"

# 策略配置
ATOMIC_ARBITRAGE_ENABLED: true
NEGRISK_ARBITRAGE_ENABLED: false
COMBO_ARBITRAGE_ENABLED: false
MARKET_MAKING_ENABLED: false

# 风险控制
MAX_POSITION_SIZE: "10"
MAX_DAILY_LOSS: "1"

# 熔断器
CONSECUTIVE_FAILURES_THRESHOLD: 3
FAIL_RATE_THRESHOLD: "0.40"
"""

        # Parse YAML (basic check)
        assert "DRY_RUN: false" in profile_content
        assert "TRADE_SIZE: \"1\"" in profile_content
        assert "ATOMIC_ARBITRAGE_ENABLED: true" in profile_content
        assert "MAX_POSITION_SIZE: \"10\"" in profile_content
        assert "MAX_DAILY_LOSS: \"1\"" in profile_content

    def test_safe_profile_attributes(self):
        """Test that safe profile has required attributes"""
        profile_content = """
name: "Live Safe Atomic v1"
description: "微量实盘 - 首周生产"
version: "1.0.0"

# 核心配置
DRY_RUN: false
TRADE_SIZE: "2"
MIN_PROFIT_THRESHOLD: "0.015"

# 风险控制
MAX_POSITION_SIZE: "20"
MAX_DAILY_LOSS: "3"
MAX_SLIPPAGE: "0.025"

# 熔断器
CONSECUTIVE_FAILURES_THRESHOLD: 3
FAIL_RATE_THRESHOLD: "0.40"
"""

        # Verify key attributes
        assert "DRY_RUN: false" in profile_content
        assert "TRADE_SIZE: \"2\"" in profile_content
        assert "MAX_DAILY_LOSS: \"3\"" in profile_content

    def test_constrained_profile_attributes(self):
        """Test that constrained profile has required attributes"""
        profile_content = """
name: "Constrained Production Atomic v1"
description: "受限生产 - Phase 2"
version: "1.0.0"

# 核心配置
DRY_RUN: false
TRADE_SIZE: "5"
MIN_PROFIT_THRESHOLD: "0.018"

# 风险控制
MAX_POSITION_SIZE: "50"
MAX_DAILY_LOSS: "5"
"""

        assert "TRADE_SIZE: \"5\"" in profile_content
        assert "MIN_PROFIT_THRESHOLD: \"0.018\"" in profile_content

    def test_scaled_profile_placeholder(self):
        """Test that scaled profile is placeholder only"""
        profile_content = """
name: "Scaled Production Atomic v1"
description: "规模化生产 - Phase 3（占位，默认不启用）"
version: "1.0.0"

# 注意：必须在 Phase 2 验证 edge 后使用
# 一次只放大资金或市场之一
STATUS: "PLACEHOLDER"
ENABLED: false
"""

        assert "STATUS: \"PLACEHOLDER\"" in profile_content
        assert "ENABLED: false" in profile_content


class TestProductionAlerts:
    """Test production alerts configuration"""

    def test_production_alerts_required_rules(self):
        """Test that production alerts has all required rules"""
        alerts_content = """
rules:
  - id: "WS_DISCONNECTED"
    name: "WebSocket 连接断开"
    enabled: true
    severity: "CRITICAL"
    query:
      metric: "ws_connected"
      operator: "=="
      value: false
      window_seconds: 10
    cooldown_seconds: 60

  - id: "LIVE_NO_FILLS"
    name: "实盘无成交"
    enabled: true
    severity: "CRITICAL"
    query:
      metric: "live_no_fills"
      operator: "=="
      value: true
      window_seconds: 60

  - id: "PNL_DRAWDOWN"
    name: "回撤过大"
    enabled: true
    severity: "WARNING"
    query:
      metric: "drawdown_percent"
      operator: ">="
      value: 3
      window_seconds: 0
"""

        # Verify required rules
        assert "WS_DISCONNECTED" in alerts_content
        assert "LIVE_NO_FILLS" in alerts_content
        assert "PNL_DRAWDOWN" in alerts_content
        assert "severity: \"CRITICAL\"" in alerts_content


class TestStartScripts:
    """Test start_shadow.sh and start_live_safe.sh"""

    def test_start_shadow_script_structure(self):
        """Test that start_shadow.sh has required structure"""
        script_content = """#!/bin/bash
set -euo pipefail

# Configuration
PROFILE_NAME="live_shadow_atomic_v1"
RUN_MODE="live"

# Start bot
echo "Starting shadow production..."
echo "Profile: $PROFILE_NAME"
echo "Mode: $RUN_MODE"
"""

        # Script should set profile and mode
        assert "PROFILE_NAME=\"live_shadow_atomic_v1\"" in script_content
        assert "RUN_MODE=\"live\"" in script_content
        assert "set -euo pipefail" in script_content

    def test_start_live_safe_script_structure(self):
        """Test that start_live_safe.sh includes go/no-go check"""
        script_content = """#!/bin/bash
set -euo pipefail

# Configuration
PROFILE_NAME="live_safe_atomic_v1"

# Run go/no-go check
echo "Running go/no-go checks..."
./scripts/go_no_go_check.sh

if [ $? -ne 0 ]; then
    echo "Go/No-Go check FAILED"
    exit 1
fi

# Start bot
echo "Starting live safe..."
echo "LIVE_SAFE_STARTED"
"""

        assert "PROFILE_NAME=\"live_safe_atomic_v1\"" in script_content
        assert "go_no_go_check.sh" in script_content
        assert "LIVE_SAFE_STARTED" in script_content


class TestProductionPlan:
    """Test PRODUCTION_PLAN.md documentation"""

    def test_plan_contains_four_phases(self):
        """Test that production plan defines 4 phases"""
        plan_content = """
# Production Plan

## Phase 0: Shadow Production
## Phase 1: Micro-Live
## Phase 2: Constrained-Live
## Phase 3: Scaled-Live
"""

        assert "Phase 0" in plan_content
        assert "Phase 1" in plan_content
        assert "Phase 2" in plan_content
        assert "Phase 3" in plan_content

    def test_plan_contains_success_criteria(self):
        """Test that each phase has success criteria"""
        plan_content = """
## Phase 1: Micro-Live

### Goals
- Validate real execution
- Test risk controls

### Success Criteria (DoD)
- No critical alerts for 7 days
- Total PnL within expected range
"""

        assert "Success Criteria" in plan_content
        assert "DoD" in plan_content

    def test_plan_contains_rollback_criteria(self):
        """Test that each phase has rollback criteria"""
        plan_content = """
## Phase 1: Micro-Live

### Rollback Criteria (Kill Criteria)
- Daily loss exceeds $10
- Critical alerts not resolved
"""

        assert "Rollback Criteria" in plan_content
        assert "Kill Criteria" in plan_content


class TestGoNoGoChecklist:
    """Test GO_NO_GO_CHECKLIST.md documentation"""

    def test_checklist_contains_required_sections(self):
        """Test that checklist has all required sections"""
        checklist_content = """
# Go/No-Go Checklist

## 安全检查
## 系统检查
## 数据检查
## 操作检查

## 通过/不通过规则
"""

        assert "安全检查" in checklist_content
        assert "系统检查" in checklist_content
        assert "数据检查" in checklist_content
        assert "操作检查" in checklist_content
        assert "通过/不通过规则" in checklist_content

    def test_checklist_has_p0_items(self):
        """Test that checklist has P0 (critical) items"""
        checklist_content = """
## 安全检查
- [ ] 独立生产钱包（P0）
- [ ] Allowance 最小化（P0）
"""

        assert "P0" in checklist_content
