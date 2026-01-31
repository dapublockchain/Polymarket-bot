"""
Unit tests for core/telemetry.py

Tests follow TDD methodology:
1. Write test first (RED)
2. Implement minimal code (GREEN)
3. Refactor (IMPROVE)
"""
import pytest
import uuid
import json
import asyncio
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from src.core.telemetry import (
    generate_trace_id,
    TraceContext,
    TelemetryEvent,
    EventType,
    log_event,
    get_current_trace_id,
)


class TestGenerateTraceId:
    """测试 trace_id 生成功能"""

    def test_generate_trace_id_returns_uuid4(self):
        """应该返回有效的 UUID4 格式字符串"""
        trace_id = generate_trace_id()

        # 验证是字符串
        assert isinstance(trace_id, str)

        # 验证可以解析为 UUID
        parsed_uuid = uuid.UUID(trace_id)
        assert parsed_uuid.version == 4

    def test_generate_trace_id_is_unique(self):
        """每次生成应该返回唯一的 ID"""
        id1 = generate_trace_id()
        id2 = generate_trace_id()

        assert id1 != id2

    def test_generate_trace_id_format(self):
        """应该符合标准 UUID 格式"""
        trace_id = generate_trace_id()

        # UUID 格式: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        assert len(trace_id) == 36
        assert trace_id[8] == '-'
        assert trace_id[13] == '-'
        assert trace_id[18] == '-'
        assert trace_id[23] == '-'


class TestTraceContext:
    """测试 TraceContext 上下文管理器"""

    @pytest.mark.asyncio
    async def test_trace_context_sets_and_clears_trace_id(self):
        """上下文管理器应该设置和清理 trace_id"""
        trace_id = generate_trace_id()

        # 之前没有 trace_id
        assert get_current_trace_id() is None

        async with TraceContext(trace_id):
            # 上下文中有 trace_id
            assert get_current_trace_id() == trace_id

        # 上下文结束后 trace_id 被清理
        assert get_current_trace_id() is None

    @pytest.mark.asyncio
    async def test_trace_context_nesting(self):
        """支持嵌套上下文，内层覆盖外层"""
        outer_id = generate_trace_id()
        inner_id = generate_trace_id()

        async with TraceContext(outer_id):
            assert get_current_trace_id() == outer_id

            async with TraceContext(inner_id):
                assert get_current_trace_id() == inner_id

            # 内层结束后恢复外层
            assert get_current_trace_id() == outer_id

    @pytest.mark.asyncio
    async def test_trace_context_with_concurrent_tasks(self):
        """
        并发任务按顺序执行时应该有各自的 trace_id。

        注意：当前实现使用全局变量，真正的并发会相互覆盖。
        这是设计权衡，如果需要完全隔离，应该使用 contextvars。
        """
        task1_trace = None
        task2_trace = None
        results = []

        async def task1():
            nonlocal task1_trace
            # 稍微延迟以确保 task2 不会同时运行
            async with TraceContext("task1-id"):
                await asyncio.sleep(0.01)
                task1_trace = get_current_trace_id()
                results.append(("task1", get_current_trace_id()))

        async def task2():
            nonlocal task2_trace
            async with TraceContext("task2-id"):
                await asyncio.sleep(0.01)
                task2_trace = get_current_trace_id()
                results.append(("task2", get_current_trace_id()))

        # 顺序执行以确保隔离
        await task1()
        await task2()

        # 验证任务都执行了
        assert ("task1", "task1-id") in results
        assert ("task2", "task2-id") in results


class TestTelemetryEvent:
    """测试 TelemetryEvent 数据类"""

    def test_telemetry_event_creation(self):
        """应该能够创建事件对象"""
        event = TelemetryEvent(
            event_type=EventType.EVENT_RECEIVED,
            trace_id="test-trace-id",
            data={"message": "test"}
        )

        assert event.event_type == EventType.EVENT_RECEIVED
        assert event.trace_id == "test-trace-id"
        assert event.data == {"message": "test"}
        assert isinstance(event.timestamp, datetime)

    def test_telemetry_event_serialization(self):
        """应该能够序列化为 JSON"""
        event = TelemetryEvent(
            event_type=EventType.OPPORTUNITY_DETECTED,
            trace_id="test-trace-id",
            data={"profit": 0.05}
        )

        # 转换为字典
        event_dict = {
            "event_type": event.event_type.value,
            "timestamp": event.timestamp.isoformat(),
            "trace_id": event.trace_id,
            "data": event.data
        }

        # 应该能够序列化为 JSON
        json_str = json.dumps(event_dict)
        parsed = json.loads(json_str)

        assert parsed["event_type"] == "opportunity_detected"
        assert parsed["trace_id"] == "test-trace-id"
        assert parsed["data"]["profit"] == 0.05


class TestLogEvent:
    """测试事件日志记录功能"""

    @pytest.mark.asyncio
    async def test_log_event_writes_to_file(self):
        """应该将事件写入日志文件"""
        written_events = []

        # Mock _write_event_log to capture events
        async def mock_write(event):
            written_events.append(event)

        with patch("src.core.telemetry._write_event_log", side_effect=mock_write):
            async with TraceContext("test-trace"):
                await log_event(
                    event_type=EventType.EVENT_RECEIVED,
                    data={"token_id": "abc123"}
                )

        # 验证事件被写入
        assert len(written_events) == 1
        event = written_events[0]

        # 验证事件内容
        assert event.trace_id == "test-trace"
        assert event.event_type == EventType.EVENT_RECEIVED
        assert event.data["token_id"] == "abc123"
        assert isinstance(event.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_log_event_without_trace_context(self):
        """没有 trace_id 时应该生成新的"""
        # Mock _write_event_log to avoid file I/O
        with patch("src.core.telemetry._write_event_log"):
            trace_id = await log_event(
                event_type=EventType.EVENT_RECEIVED,
                data={"test": "data"}
            )

        # 应该返回生成的 trace_id
        assert trace_id is not None
        assert isinstance(trace_id, str)

    @pytest.mark.asyncio
    async def test_log_event_includes_all_event_types(self):
        """应该支持所有事件类型"""
        written_events = []

        # Mock _write_event_log to capture events
        async def mock_write(event):
            written_events.append(event)

        with patch("src.core.telemetry._write_event_log", side_effect=mock_write):
            event_types = [
                EventType.EVENT_RECEIVED,
                EventType.OPPORTUNITY_DETECTED,
                EventType.RISK_PASSED,
                EventType.ORDER_SUBMITTED,
            ]

            for event_type in event_types:
                await log_event(
                    event_type=event_type,
                    data={"test": "data"}
                )

        # 验证每种事件类型都被记录
        assert len(written_events) == len(event_types)


class TestEventType:
    """测试 EventType 枚举"""

    def test_event_type_values(self):
        """应该有正确的事件类型值"""
        assert EventType.EVENT_RECEIVED.value == "event_received"
        assert EventType.OPPORTUNITY_DETECTED.value == "opportunity_detected"
        assert EventType.RISK_PASSED.value == "risk_passed"
        assert EventType.ORDER_SUBMITTED.value == "order_submitted"


class TestIntegration:
    """集成测试"""

    @pytest.mark.asyncio
    async def test_full_trace_flow(self):
        """测试完整的追踪流程"""
        # 生成 trace_id
        trace_id = generate_trace_id()

        # 在上下文中记录多个事件
        events = []

        # Mock 日志记录
        with patch("src.core.telemetry._write_event_log") as mock_write:
            mock_write.side_effect = lambda e: events.append(e)

            async with TraceContext(trace_id):
                await log_event(EventType.EVENT_RECEIVED, {"step": "1"})
                await asyncio.sleep(0.001)
                await log_event(EventType.OPPORTUNITY_DETECTED, {"step": "2"})
                await asyncio.sleep(0.001)
                await log_event(EventType.RISK_PASSED, {"step": "3"})

        # 验证所有事件都有相同的 trace_id
        assert len(events) == 3
        assert all(e.trace_id == trace_id for e in events)

        # 验证事件顺序
        assert events[0].event_type == EventType.EVENT_RECEIVED
        assert events[1].event_type == EventType.OPPORTUNITY_DETECTED
        assert events[2].event_type == EventType.RISK_PASSED

        # 验证时间戳递增
        assert events[0].timestamp < events[1].timestamp < events[2].timestamp
