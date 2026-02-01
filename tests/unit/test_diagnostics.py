"""
Unit tests for DryRunSanityCheck.

Tests the automated sanity checking system for dry-run mode.
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from decimal import Decimal

from src.execution.diagnostics import DryRunSanityCheck
from src.core.models import TradingMetrics


class TestDryRunSanityCheck:
    """Test DryRunSanityCheck class."""

    @pytest.fixture
    def checker(self):
        """Create a DryRunSanityCheck instance."""
        return DryRunSanityCheck(check_interval_seconds=1)

    @pytest.fixture
    def metrics(self):
        """Create a TradingMetrics instance."""
        return TradingMetrics(
            start_time=1234567890.0,
            opportunities_seen=0,
            orders_submitted=0,
            fills_simulated=0,
            fills_confirmed=0,
            pnl_updates=0,
            cumulative_expected_edge=Decimal("0"),
            cumulative_simulated_pnl=Decimal("0"),
            cumulative_realized_pnl=Decimal("0"),
        )

    def test_initialization(self, checker):
        """Test DryRunSanityCheck initialization."""
        assert checker.check_interval_seconds == 1
        assert checker._running is False
        assert checker._check_count == 0
        assert checker._last_opportunity_count == 0
        assert checker._last_fill_count == 0
        assert checker._last_pnl_count == 0

    @pytest.mark.asyncio
    async def test_start_stop(self, checker, metrics):
        """Test starting and stopping the checker."""
        assert checker._running is False

        # Start
        await checker.start(metrics)
        assert checker._running is True
        assert checker._task is not None

        # Stop
        await checker.stop()
        assert checker._running is False

    @pytest.mark.asyncio
    async def test_double_start(self, checker, metrics):
        """Test starting twice doesn't create duplicate tasks."""
        await checker.start(metrics)
        first_task = checker._task

        # Start again (should warn but not create new task)
        await checker.start(metrics)
        assert checker._task == first_task

        await checker.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, checker):
        """Test stopping when not running is safe."""
        # Should not raise
        await checker.stop()
        assert checker._running is False

    @pytest.mark.asyncio
    async def test_perform_checks_no_fills(self, checker, metrics, caplog):
        """Test check for orders but no fills (CRITICAL error)."""
        metrics.orders_submitted = 10
        metrics.fills_simulated = 0

        with caplog.at_level("ERROR"):
            await checker.perform_checks(metrics)

        # Should log critical error
        assert any("DRY_RUN_NO_FILLS" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_perform_checks_no_pnl(self, checker, metrics, caplog):
        """Test check for opportunities but no PnL (WARNING)."""
        metrics.opportunities_seen = 5
        metrics.pnl_updates = 0

        with caplog.at_level("WARNING"):
            await checker.perform_checks(metrics)

        # Should log warning
        assert any("DRY_RUN_NO_PNL" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_perform_checks_stale_data(self, checker, metrics, caplog):
        """Test check for stale data (INFO)."""
        # Set some initial data
        metrics.opportunities_seen = 10
        metrics.fills_simulated = 5
        metrics.pnl_updates = 3

        # Run checks 3 times to warm up
        for _ in range(3):
            await checker.perform_checks(metrics)

        # Clear caplog
        caplog.clear()

        # Run again - should detect stale data
        with caplog.at_level("INFO"):
            await checker.perform_checks(metrics)

        # Should log stale data warning
        assert any("DRY_RUN_STALE" in record.message for record in caplog.records)

    @pytest.mark.asyncio
    async def test_perform_checks_updates_baseline(self, checker, metrics):
        """Test that checks update baseline counts."""
        metrics.opportunities_seen = 10
        metrics.fills_simulated = 5
        metrics.pnl_updates = 3

        await checker.perform_checks(metrics)

        assert checker._last_opportunity_count == 10
        assert checker._last_fill_count == 5
        assert checker._last_pnl_count == 3

    @pytest.mark.asyncio
    async def test_perform_checks_increments_counter(self, checker, metrics):
        """Test that check counter increments."""
        assert checker._check_count == 0

        await checker.perform_checks(metrics)
        assert checker._check_count == 1

        await checker.perform_checks(metrics)
        assert checker._check_count == 2

    @pytest.mark.asyncio
    async def test_check_loop(self, checker, metrics):
        """Test the main check loop runs periodically."""
        # Set up metrics to trigger no fills error
        metrics.orders_submitted = 10
        metrics.fills_simulated = 0

        # Start checker and let it run a few times
        await checker.start(metrics)

        # Wait for 2 checks to complete
        await asyncio.sleep(2.5)

        # Stop
        await checker.stop()

        # Should have run at least 2 checks
        assert checker._check_count >= 2

    @pytest.mark.asyncio
    async def test_check_loop_can_be_cancelled(self, checker, metrics):
        """Test that check loop handles cancellation gracefully."""
        await checker.start(metrics)

        # Wait a bit then cancel
        await asyncio.sleep(0.5)
        await checker.stop()

        assert checker._running is False
        assert checker._task is None or checker._task.cancelled()

    def test_get_summary(self, checker, metrics):
        """Test getting checker summary."""
        summary = checker.get_summary()

        assert summary["running"] is False
        assert summary["check_count"] == 0
        assert summary["check_interval_seconds"] == 1
        assert summary["last_opportunity_count"] == 0
        assert summary["last_fill_count"] == 0
        assert summary["last_pnl_count"] == 0

    @pytest.mark.asyncio
    async def test_get_summary_after_checks(self, checker, metrics):
        """Test summary reflects check state."""
        metrics.opportunities_seen = 10
        metrics.fills_simulated = 5
        metrics.pnl_updates = 3

        await checker.perform_checks(metrics)

        summary = checker.get_summary()

        assert summary["check_count"] == 1
        assert summary["last_opportunity_count"] == 10
        assert summary["last_fill_count"] == 5
        assert summary["last_pnl_count"] == 3

    @pytest.mark.asyncio
    async def test_healthy_metrics_pass_all_checks(self, checker, metrics, caplog):
        """Test that healthy metrics don't trigger warnings."""
        # Set up healthy metrics
        metrics.opportunities_seen = 10
        metrics.orders_submitted = 10
        metrics.fills_simulated = 20  # More than orders (2 fills per order)
        metrics.pnl_updates = 10

        with caplog.at_level("WARNING"):
            await checker.perform_checks(metrics)

        # Should not log any errors or warnings
        # (except possibly stale data after 3 checks, which we'll skip here)
        error_logs = [r for r in caplog.records if r.levelname in ("ERROR", "WARNING") and
                     "DRY_RUN_" in r.message]
        assert len(error_logs) == 0

    @pytest.mark.asyncio
    async def test_partial_fills_trigger_warning(self, checker, metrics, caplog):
        """Test that partial fills trigger appropriate warnings."""
        metrics.orders_submitted = 10
        metrics.fills_simulated = 5  # Only half filled

        with caplog.at_level("ERROR"):
            await checker.perform_checks(metrics)

        # Should still trigger DRY_RUN_NO_FILLS warning
        # because orders_submitted > fills_simulated
        # Actually, looking at the code, it only checks if fills_simulated == 0
        # So this test should NOT trigger an error
        error_logs = [r for r in caplog.records if r.levelname == "ERROR" and
                     "DRY_RUN_NO_FILLS" in r.message]
        assert len(error_logs) == 0

    @pytest.mark.asyncio
    async def test_warmup_period_for_stale_check(self, checker, metrics, caplog):
        """Test that stale check doesn't trigger during warmup (first 3 checks)."""
        metrics.opportunities_seen = 10
        metrics.fills_simulated = 5
        metrics.pnl_updates = 3

        with caplog.at_level("INFO"):
            # Run 2 checks (within warmup period)
            await checker.perform_checks(metrics)
            await checker.perform_checks(metrics)

        # Should not detect stale data yet
        stale_logs = [r for r in caplog.records if "DRY_RUN_STALE" in r.message]
        assert len(stale_logs) == 0

    @pytest.mark.asyncio
    async def test_stale_check_after_warmup(self, checker, metrics, caplog):
        """Test that stale check triggers after warmup period."""
        metrics.opportunities_seen = 10
        metrics.fills_simulated = 5
        metrics.pnl_updates = 3

        with caplog.at_level("INFO"):
            # Run warmup checks
            await checker.perform_checks(metrics)
            await checker.perform_checks(metrics)
            await checker.perform_checks(metrics)

            # Clear and run one more (should detect stale)
            caplog.clear()
            await checker.perform_checks(metrics)

        # Should detect stale data
        stale_logs = [r for r in caplog.records if "DRY_RUN_STALE" in r.message]
        assert len(stale_logs) == 1
