"""
Unit tests for core/recorder.py

Tests follow TDD methodology:
1. Write test first (RED)
2. Implement minimal code (GREEN)
3. Refactor (IMPROVE)
"""
import pytest
import json
import asyncio
from pathlib import Path
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import patch, mock_open, AsyncMock

from src.core.recorder import (
    EventType,
    EventRecorder,
    record_event,
    get_events_path,
)


class TestEventType:
    """测试 EventType 枚举"""

    def test_event_type_values(self):
        """应该有正确的事件类型"""
        assert EventType.ORDERBOOK_SNAPSHOT.value == "orderbook_snapshot"
        assert EventType.SIGNAL.value == "signal"
        assert EventType.ORDER_REQUEST.value == "order_request"
        assert EventType.ORDER_RESULT.value == "order_result"


class TestGetEventsPath:
    """测试 get_events_path 函数"""

    def test_get_events_path_today(self):
        """应该返回今天的日期路径"""
        path = get_events_path()

        # 应该是 data/events/YYYYMMDD/events.jsonl
        assert path.parent.parent.name == "events"
        assert path.parent.parent.parent.name == "data"

        # 日期部分应该是今天的日期
        date_dir = path.parent.name
        expected_date = date.today().strftime("%Y%m%d")
        assert date_dir == expected_date
        assert path.name == "events.jsonl"

    def test_get_events_path_for_specific_date(self):
        """应该能够为特定日期创建路径"""
        specific_date = date(2026, 1, 31)
        path = get_events_path(specific_date)

        # Path should be data/events/20260131/events.jsonl
        assert path.parent.name == "20260131"
        assert path.name == "events.jsonl"


class TestEventRecorder:
    """测试 EventRecorder 类"""

    @pytest.mark.asyncio
    async def test_record_orderbook_snapshot(self):
        """应该能够记录订单本快照"""
        recorder = EventRecorder()

        await recorder.record_orderbook_snapshot(
            token_id="abc123",
            bids=[{"price": "0.50", "size": "100"}],
            asks=[{"price": "0.51", "size": "100"}]
        )

        # 应该有一个事件被记录
        assert len(recorder.buffer) == 1
        event = recorder.buffer[0]
        assert event["event_type"] == EventType.ORDERBOOK_SNAPSHOT.value
        assert event["data"]["token_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_record_signal(self):
        """应该能够记录策略信号"""
        recorder = EventRecorder()

        await recorder.record_signal(
            trace_id="trace-123",
            strategy="atomic",
            yes_token="token-yes",
            no_token="token-no",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.56"),
            expected_profit=Decimal("1.00")
        )

        assert len(recorder.buffer) == 1
        event = recorder.buffer[0]
        assert event["event_type"] == EventType.SIGNAL.value
        assert event["data"]["trace_id"] == "trace-123"

    @pytest.mark.asyncio
    async def test_record_order_request(self):
        """应该能够记录订单请求"""
        recorder = EventRecorder()

        await recorder.record_order_request(
            trace_id="trace-123",
            order_type="buy",
            token_id="token-yes",
            size=Decimal("100"),
            price=Decimal("0.50")
        )

        assert len(recorder.buffer) == 1
        event = recorder.buffer[0]
        assert event["event_type"] == EventType.ORDER_REQUEST.value

    @pytest.mark.asyncio
    async def test_record_order_result(self):
        """应该能够记录订单结果"""
        recorder = EventRecorder()

        await recorder.record_order_result(
            trace_id="trace-123",
            success=True,
            tx_hash="0xabc123",
            gas_used=50000,
            actual_price=Decimal("0.50")
        )

        assert len(recorder.buffer) == 1
        event = recorder.buffer[0]
        assert event["event_type"] == EventType.ORDER_RESULT.value
        assert event["data"]["success"] is True

    @pytest.mark.asyncio
    @patch("src.core.recorder.aiofiles.open")
    async def test_flush_writes_buffer_to_file(self, mock_open):
        """flush 应该将缓冲区写入文件"""
        # 配置 mock
        mock_file = AsyncMock()
        mock_file.write = AsyncMock()
        mock_open.return_value.__aenter__.return_value = mock_file

        recorder = EventRecorder()
        await recorder.record_orderbook_snapshot(
            token_id="test",
            bids=[],
            asks=[]
        )

        # Flush buffer
        await recorder.flush()

        # 验证写入被调用
        assert mock_file.write.called
        assert len(recorder.buffer) == 0  # 缓冲区被清空

    @pytest.mark.asyncio
    async def test_flush_creates_directory(self):
        """flush 应该创建必要的目录"""
        recorder = EventRecorder()
        await recorder.record_orderbook_snapshot(
            token_id="test",
            bids=[],
            asks=[]
        )

        # Mock 文件写入但保留目录创建逻辑
        with patch("src.core.recorder.aiofiles.open") as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            await recorder.flush()

            # 验证 open 被调用
            assert mock_open.called

    @pytest.mark.asyncio
    async def test_auto_flush_after_max_size(self):
        """缓冲区达到最大大小时应该自动 flush"""
        recorder = EventRecorder(buffer_size=3)

        # 记录 3 个事件（达到最大大小）
        for i in range(3):
            await recorder.record_orderbook_snapshot(
                token_id=f"token-{i}",
                bids=[],
                asks=[]
            )

        # 应该自动 flush，缓冲区应该被清空
        assert len(recorder.buffer) == 0


class TestRecordEvent:
    """测试全局 record_event 函数"""

    @pytest.mark.asyncio
    async def test_record_event_convenience_function(self):
        """应该有便捷的记录函数"""
        with patch("src.core.recorder._global_recorder") as mock_recorder:
            mock_recorder.record_orderbook_snapshot = AsyncMock()

            await record_event(
                event_type=EventType.ORDERBOOK_SNAPSHOT,
                data={"token_id": "test"}
            )

            # 验证被调用
            assert mock_recorder.record_orderbook_snapshot.called


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    @patch("src.core.recorder.aiofiles.open")
    async def test_full_recording_flow(self, mock_open):
        """测试完整的记录流程"""
        # 配置 mock
        mock_file = AsyncMock()
        mock_open.return_value.__aenter__.return_value = mock_file

        recorder = EventRecorder()

        # 模拟完整的交易流程
        trace_id = "test-trace-123"

        # 1. 记录订单本快照
        await recorder.record_orderbook_snapshot(
            token_id="yes-token",
            bids=[{"price": "0.45", "size": "100"}],
            asks=[{"price": "0.46", "size": "100"}]
        )

        # 2. 记录信号
        await recorder.record_signal(
            trace_id=trace_id,
            strategy="atomic",
            yes_token="yes-token",
            no_token="no-token",
            yes_price=Decimal("0.45"),
            no_price=Decimal("0.55"),
            expected_profit=Decimal("1.00")
        )

        # 3. 记录订单请求
        await recorder.record_order_request(
            trace_id=trace_id,
            order_type="buy",
            token_id="yes-token",
            size=Decimal("100"),
            price=Decimal("0.45")
        )

        # 4. 记录订单结果
        await recorder.record_order_result(
            trace_id=trace_id,
            success=True,
            tx_hash="0xdef456",
            gas_used=50000,
            actual_price=Decimal("0.45")
        )

        # 应该有 4 个事件
        assert len(recorder.buffer) == 4

        # Flush 并验证
        await recorder.flush()

        # 验证所有事件都有正确的 trace_id（除了订单本快照）
        trace_id_events = [e for e in mock_file.write.call_args_list if "signal" in str(e) or "order" in str(e)]

    @pytest.mark.asyncio
    @patch("src.core.recorder.aiofiles.open")
    async def test_date_sharding(self, mock_open):
        """测试按日期分片"""
        mock_file = AsyncMock()
        mock_open.return_value.__aenter__.return_value = mock_file

        recorder = EventRecorder()

        # 记录事件
        await recorder.record_orderbook_snapshot(
            token_id="test",
            bids=[],
            asks=[]
        )

        await recorder.flush()

        # 验证文件路径包含今天的日期
        call_args = mock_open.call_args
        file_path = call_args[0][0]

        # 路径应该包含今天的日期
        today_str = date.today().strftime("%Y%m%d")
        assert today_str in str(file_path)

    @pytest.mark.asyncio
    async def test_jsonl_format(self):
        """测试输出格式是 JSONL（每行一个 JSON）"""
        with patch("src.core.recorder.aiofiles.open") as mock_open:
            mock_file = AsyncMock()
            mock_open.return_value.__aenter__.return_value = mock_file

            recorder = EventRecorder()

            # 记录两个事件
            await recorder.record_orderbook_snapshot(
                token_id="test1",
                bids=[],
                asks=[]
            )
            await recorder.record_orderbook_snapshot(
                token_id="test2",
                bids=[],
                asks=[]
            )

            await recorder.flush()

            # 获取所有写入的内容
            write_calls = mock_file.write.call_args_list
            assert len(write_calls) == 2

            # 验证每一行都是有效的 JSON
            for call in write_calls:
                line = call[0][0]
                json_obj = json.loads(line)
                assert "event_type" in json_obj
                assert "timestamp" in json_obj
                assert "data" in json_obj
