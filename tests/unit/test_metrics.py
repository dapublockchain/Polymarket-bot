"""
Unit tests for core/metrics.py

Tests follow TDD methodology:
1. Write test first (RED)
2. Implement minimal code (GREEN)
3. Refactor (IMPROVE)
"""
import pytest
import json
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, mock_open, MagicMock
from decimal import Decimal

from src.core.metrics import (
    MetricsCollector,
    LatencyMetric,
    MetricsSnapshot,
    record_latency,
    calculate_percentiles,
    TimeWindow,
)


class TestLatencyMetric:
    """测试 LatencyMetric 数据类"""

    def test_latency_metric_creation(self):
        """应该能够创建延迟指标"""
        metric = LatencyMetric(
            trace_id="test-trace",
            ws_to_book_update_ms=10.5,
            book_to_signal_ms=5.2,
            signal_to_risk_ms=3.1,
            risk_to_send_ms=15.8,
            end_to_end_ms=34.6,
            timestamp=datetime.now()
        )

        assert metric.trace_id == "test-trace"
        assert metric.ws_to_book_update_ms == 10.5
        assert metric.book_to_signal_ms == 5.2
        assert metric.signal_to_risk_ms == 3.1
        assert metric.risk_to_send_ms == 15.8
        assert metric.end_to_end_ms == 34.6

    def test_latency_metric_serialization(self):
        """应该能够序列化为 JSON"""
        metric = LatencyMetric(
            trace_id="test-trace",
            ws_to_book_update_ms=10.5,
            book_to_signal_ms=5.2,
            signal_to_risk_ms=3.1,
            risk_to_send_ms=15.8,
            end_to_end_ms=34.6,
            timestamp=datetime(2026, 1, 31, 12, 0, 0)
        )

        # 转换为字典
        metric_dict = {
            "trace_id": metric.trace_id,
            "ws_to_book_update_ms": metric.ws_to_book_update_ms,
            "book_to_signal_ms": metric.book_to_signal_ms,
            "signal_to_risk_ms": metric.signal_to_risk_ms,
            "risk_to_send_ms": metric.risk_to_send_ms,
            "end_to_end_ms": metric.end_to_end_ms,
            "timestamp": metric.timestamp.isoformat()
        }

        # 应该能够序列化为 JSON
        json_str = json.dumps(metric_dict)
        parsed = json.loads(json_str)

        assert parsed["trace_id"] == "test-trace"
        assert parsed["end_to_end_ms"] == 34.6


class TestMetricsCollector:
    """测试 MetricsCollector 类"""

    def test_metrics_collector_initialization(self):
        """应该能够初始化收集器"""
        collector = MetricsCollector()

        assert len(collector.metrics) == 0

    def test_record_latency(self):
        """应该能够记录延迟指标"""
        collector = MetricsCollector()

        collector.record_latency(
            trace_id="test-trace",
            ws_to_book_update_ms=10.0,
            book_to_signal_ms=5.0,
            signal_to_risk_ms=3.0,
            risk_to_send_ms=15.0
        )

        assert len(collector.metrics) == 1
        metric = collector.metrics[0]
        assert metric.trace_id == "test-trace"
        assert metric.end_to_end_ms == 33.0  # 10+5+3+15

    @pytest.mark.asyncio
    async def test_record_latency_with_automatic_timestamp(self):
        """记录时应该自动添加时间戳"""
        collector = MetricsCollector()

        before = datetime.now()
        await asyncio.sleep(0.01)
        collector.record_latency(
            trace_id="test-trace",
            ws_to_book_update_ms=10.0
        )
        after = datetime.now()

        metric = collector.metrics[0]
        assert before <= metric.timestamp <= after

    def test_get_metrics_in_time_window(self):
        """应该能够获取时间窗口内的指标"""
        collector = MetricsCollector()
        now = datetime.now()

        # 添加不同时间的指标
        collector.metrics.append(LatencyMetric(
            trace_id="old",
            ws_to_book_update_ms=10.0,
            book_to_signal_ms=5.0,
            signal_to_risk_ms=3.0,
            risk_to_send_ms=15.0,
            end_to_end_ms=33.0,
            timestamp=now - timedelta(seconds=120)  # 2 分钟前
        ))
        collector.metrics.append(LatencyMetric(
            trace_id="recent",
            ws_to_book_update_ms=10.0,
            book_to_signal_ms=5.0,
            signal_to_risk_ms=3.0,
            risk_to_send_ms=15.0,
            end_to_end_ms=33.0,
            timestamp=now - timedelta(seconds=30)  # 30 秒前
        ))

        # 获取最近 60 秒的指标
        window = TimeWindow(seconds=60)
        recent_metrics = collector.get_metrics_in_window(window)

        assert len(recent_metrics) == 1
        assert recent_metrics[0].trace_id == "recent"

    def test_calculate_snapshot(self):
        """应该能够计算时间窗口快照"""
        collector = MetricsCollector()

        # 添加测试数据
        for i in range(100):
            collector.record_latency(
                trace_id=f"trace-{i}",
                ws_to_book_update_ms=10 + i * 0.1,  # 10-19 ms
                book_to_signal_ms=5.0,
                signal_to_risk_ms=3.0,
                risk_to_send_ms=15.0
            )

        # 计算 60 秒窗口快照
        window = TimeWindow(seconds=60)
        snapshot = collector.calculate_snapshot(window)

        # 验证快照
        assert snapshot.count == 100
        assert snapshot.avg_end_to_end_ms > 30  # 10+5+3+15=33
        assert snapshot.min_end_to_end_ms == pytest.approx(33.0)
        assert snapshot.max_end_to_end_ms > 33.0


class TestCalculatePercentiles:
    """测试百分位数计算"""

    def test_calculate_percentiles_empty(self):
        """空数据应该返回 None"""
        values = []
        result = calculate_percentiles(values)

        assert result is None

    def test_calculate_percentiles_single_value(self):
        """单个值应该返回相同值"""
        values = [50.0]
        result = calculate_percentiles(values)

        assert result["p50"] == 50.0
        assert result["p95"] == 50.0
        assert result["p99"] == 50.0

    def test_calculate_percentiles_multiple_values(self):
        """应该正确计算百分位数"""
        values = [10.0, 20.0, 30.0, 40.0, 50.0,
                  60.0, 70.0, 80.0, 90.0, 100.0]
        result = calculate_percentiles(values)

        # p50 (中位数) 应该约为 55
        assert 50 <= result["p50"] <= 60

        # p95 应该接近 95
        assert 90 <= result["p95"] <= 100

        # p99 应该接近 100
        assert 95 <= result["p99"] <= 100

    def test_calculate_percentiles_with_numpy(self):
        """如果有 numpy，应该使用 numpy 进行计算"""
        values = list(range(1000))  # 0-999
        result = calculate_percentiles(values)

        # numpy 应该给出精确的百分位数
        assert result["p50"] == pytest.approx(499.5, abs=1)
        assert result["p95"] == pytest.approx(949.05, abs=1)
        assert result["p99"] == pytest.approx(989.01, abs=1)


class TestRecordLatency:
    """测试全局 record_latency 函数"""

    @pytest.mark.asyncio
    async def test_record_latency_writes_to_file(self):
        """应该将指标写入文件"""
        written_data = []

        # Mock file writing
        async def mock_write(data):
            written_data.append(data)

        with patch("src.core.metrics._write_metrics_log", side_effect=mock_write):
            await record_latency(
                trace_id="test-trace",
                ws_to_book_update_ms=10.0,
                book_to_signal_ms=5.0,
                signal_to_risk_ms=3.0,
                risk_to_send_ms=15.0
            )

        # 验证写入
        assert len(written_data) == 1
        metric_dict = json.loads(written_data[0])
        assert metric_dict["trace_id"] == "test-trace"
        assert metric_dict["end_to_end_ms"] == 33.0


class TestTimeWindow:
    """测试 TimeWindow 类"""

    def test_time_window_creation(self):
        """应该能够创建时间窗口"""
        window = TimeWindow(seconds=60)

        assert window.seconds == 60

    def test_time_window_contains(self):
        """应该能够判断时间是否在窗口内"""
        window = TimeWindow(seconds=60)
        now = datetime.now()

        # 当前时间应该在窗口内
        assert window.contains(now)

        # 30 秒前应该在窗口内
        assert window.contains(now - timedelta(seconds=30))

        # 90 秒前不应该在窗口内
        assert not window.contains(now - timedelta(seconds=90))


class TestIntegration:
    """集成测试"""

    def test_full_metrics_flow(self):
        """测试完整的指标收集流程"""
        collector = MetricsCollector()

        # 模拟记录多个套利机会的延迟
        for i in range(10):
            collector.record_latency(
                trace_id=f"opportunity-{i}",
                ws_to_book_update_ms=10 + i,
                book_to_signal_ms=5,
                signal_to_risk_ms=3,
                risk_to_send_ms=15 + i * 0.5
            )

        # 计算 60 秒窗口快照
        window = TimeWindow(seconds=60)
        snapshot = collector.calculate_snapshot(window)

        # 验证
        assert snapshot.count == 10
        assert snapshot.avg_end_to_end_ms > 33  # 基础延迟

        # 验证端到端延迟递增
        latencies = [m.end_to_end_ms for m in collector.metrics]
        assert latencies == sorted(latencies)  # 应该是递增的

    @pytest.mark.asyncio
    async def test_concurrent_metrics_recording(self):
        """测试并发记录指标"""
        collector = MetricsCollector()
        trace_ids = []

        async def record_opportunity(i):
            trace_id = f"trace-{i}"
            trace_ids.append(trace_id)
            await record_latency(
                trace_id=trace_id,
                ws_to_book_update_ms=10.0,
                book_to_signal_ms=5.0,
                signal_to_risk_ms=3.0,
                risk_to_send_ms=15.0
            )

        # 并发记录 10 个指标
        tasks = [record_opportunity(i) for i in range(10)]
        await asyncio.gather(*tasks)

        # 验证所有记录都成功
        assert len(trace_ids) == 10
        assert len(set(trace_ids)) == 10  # 所有 trace_id 唯一
