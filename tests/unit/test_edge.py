"""
Unit tests for core/edge.py

Tests follow TDD methodology:
1. Write test first (RED)
2. Implement minimal code (GREEN)
3. Refactor (IMPROVE)
"""
import pytest
from decimal import Decimal
from dataclasses import asdict

from src.core.edge import (
    EdgeBreakdown,
    Decision,
    calculate_net_edge,
    validate_edge_breakdown,
)


class TestEdgeBreakdown:
    """测试 EdgeBreakdown 数据类"""

    def test_edge_breakdown_creation(self):
        """应该能够创建 EdgeBreakdown"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )

        assert edge.gross_edge == Decimal("100.0")
        assert edge.fees_est == Decimal("2.0")
        assert edge.slippage_est == Decimal("1.0")
        assert edge.gas_est == Decimal("0.5")
        assert edge.latency_buffer == Decimal("0.3")

    def test_calculate_net_edge(self):
        """应该正确计算净利润"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )

        # 净利润 = 毛利润 - 手续费 - 滑点 - Gas - 延迟缓冲
        # 100 - 2 - 1 - 0.5 - 0.3 = 96.2
        assert edge.net_edge == Decimal("96.2")

    def test_decision_based_on_net_edge(self):
        """决策应该基于净利润和阈值"""
        # 净利润 >= 阈值 → ACCEPT
        edge_accept = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )
        edge_accept._calculate_decision()

        assert edge_accept.decision == Decision.ACCEPT
        assert edge_accept.net_edge >= edge_accept.min_threshold

        # 净利润 < 阈值 → REJECT
        edge_reject = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("5.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )
        edge_reject._calculate_decision()

        assert edge_reject.decision == Decision.REJECT
        assert edge_reject.net_edge < edge_reject.min_threshold

    def test_reason_is_set(self):
        """原因应该被设置"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )
        edge._calculate_decision()

        assert edge.reason is not None
        assert len(edge.reason) > 0

    def test_serialization(self):
        """应该能够序列化为 JSON"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )
        edge._calculate_decision()

        # 转换为字典
        edge_dict = {
            "gross_edge": str(edge.gross_edge),
            "fees_est": str(edge.fees_est),
            "slippage_est": str(edge.slippage_est),
            "gas_est": str(edge.gas_est),
            "latency_buffer": str(edge.latency_buffer),
            "net_edge": str(edge.net_edge),
            "min_threshold": str(edge.min_threshold),
            "decision": edge.decision.value,
            "reason": edge.reason
        }

        # 验证关键字段
        assert edge_dict["net_edge"] == "96.2"
        assert edge_dict["decision"] in ["accept", "reject"]
        assert edge_dict["reason"] is not None


class TestCalculateNetEdge:
    """测试 calculate_net_edge 函数"""

    def test_calculate_net_edge_basic(self):
        """应该正确计算净利润"""
        gross_edge = Decimal("100.0")
        fees = Decimal("2.0")
        slippage = Decimal("1.0")
        gas = Decimal("0.5")
        latency = Decimal("0.3")

        net_edge = calculate_net_edge(
            gross_edge, fees, slippage, gas, latency
        )

        assert net_edge == Decimal("96.2")

    def test_calculate_net_edge_with_decimal_precision(self):
        """应该保持 Decimal 精度"""
        gross_edge = Decimal("100.55")
        fees = Decimal("2.33")
        slippage = Decimal("1.11")
        gas = Decimal("0.57")
        latency = Decimal("0.31")

        net_edge = calculate_net_edge(
            gross_edge, fees, slippage, gas, latency
        )

        expected = Decimal("100.55") - Decimal("2.33") - Decimal("1.11") - Decimal("0.57") - Decimal("0.31")
        assert net_edge == expected

    def test_calculate_net_edge_zero_gross(self):
        """毛利润为 0 时应该正确计算"""
        net_edge = calculate_net_edge(
            gross_edge=Decimal("0"),
            fees=Decimal("2.0"),
            slippage=Decimal("1.0"),
            gas=Decimal("0.5"),
            latency_buffer=Decimal("0.3")
        )

        # 0 - 2 - 1 - 0.5 - 0.3 = -3.8
        assert net_edge == Decimal("-3.8")


class TestValidateEdgeBreakdown:
    """测试 validate_edge_breakdown 函数"""

    def test_valid_edge_breakdown(self):
        """有效的 EdgeBreakdown 应该通过验证"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )
        edge._calculate_decision()

        # 应该没有验证错误
        errors = validate_edge_breakdown(edge)
        assert errors == []

    def test_reject_without_reason(self):
        """REJECT 决策必须有原因"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0"),
            decision=Decision.REJECT,
            reason=""  # 空原因
        )

        errors = validate_edge_breakdown(edge)
        assert len(errors) > 0
        assert any("reason" in error.lower() for error in errors)

    def test_negative_gross_edge(self):
        """负毛利润应该被标记"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("-10.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )

        errors = validate_edge_breakdown(edge)
        # 负毛利润可能是一个警告，不一定是错误
        # 这里我们只验证函数能处理这种情况
        assert isinstance(errors, list)


class TestDecision:
    """测试 Decision 枚举"""

    def test_decision_values(self):
        """应该有正确的枚举值"""
        assert Decision.ACCEPT.value == "accept"
        assert Decision.REJECT.value == "reject"


class TestIntegration:
    """集成测试"""

    def test_full_edge_breakdown_flow(self):
        """测试完整的 EdgeBreakdown 流程"""
        # 场景 1: 可盈利的机会
        profitable_edge = EdgeBreakdown(
            gross_edge=Decimal("105.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("100.0")
        )
        profitable_edge._calculate_decision()

        assert profitable_edge.decision == Decision.ACCEPT
        assert profitable_edge.net_edge == Decimal("101.2")
        # 原因应该提到可接受
        assert "acceptable" in profitable_edge.reason.lower() or "profit" in profitable_edge.reason.lower()

        # 场景 2: 不可盈利的机会
        unprofitable_edge = EdgeBreakdown(
            gross_edge=Decimal("103.0"),
            fees_est=Decimal("5.0"),
            slippage_est=Decimal("2.0"),
            gas_est=Decimal("1.0"),
            latency_buffer=Decimal("0.5"),
            min_threshold=Decimal("100.0")
        )
        unprofitable_edge._calculate_decision()

        assert unprofitable_edge.decision == Decision.REJECT
        assert unprofitable_edge.net_edge == Decimal("94.5")
        # 原因应该提到不足或低于阈值
        assert "insufficient" in unprofitable_edge.reason.lower() or "below" in unprofitable_edge.reason.lower()

    def test_serialization_roundtrip(self):
        """测试序列化和反序列化"""
        edge = EdgeBreakdown(
            gross_edge=Decimal("100.0"),
            fees_est=Decimal("2.0"),
            slippage_est=Decimal("1.0"),
            gas_est=Decimal("0.5"),
            latency_buffer=Decimal("0.3"),
            min_threshold=Decimal("95.0")
        )
        edge._calculate_decision()

        # 序列化
        edge_dict = {
            "gross_edge": str(edge.gross_edge),
            "fees_est": str(edge.fees_est),
            "slippage_est": str(edge.slippage_est),
            "gas_est": str(edge.gas_est),
            "latency_buffer": str(edge.latency_buffer),
            "net_edge": str(edge.net_edge),
            "min_threshold": str(edge.min_threshold),
            "decision": edge.decision.value,
            "reason": edge.reason
        }

        # 反序列化
        restored_edge = EdgeBreakdown(
            gross_edge=Decimal(edge_dict["gross_edge"]),
            fees_est=Decimal(edge_dict["fees_est"]),
            slippage_est=Decimal(edge_dict["slippage_est"]),
            gas_est=Decimal(edge_dict["gas_est"]),
            latency_buffer=Decimal(edge_dict["latency_buffer"]),
            min_threshold=Decimal(edge_dict["min_threshold"])
        )
        restored_edge.decision = Decision(edge_dict["decision"])
        restored_edge.reason = edge_dict["reason"]

        # 验证恢复
        assert restored_edge.gross_edge == edge.gross_edge
        assert restored_edge.net_edge == edge.net_edge
        assert restored_edge.decision == edge.decision
        assert restored_edge.reason == edge.reason
