"""
Dry-run sanity checks for validating simulated execution.

This module provides automated diagnostics to ensure dry-run mode
is working correctly and catch common issues early.

Key checks:
- Orders submitted but no fills generated
- Opportunities detected but no PnL updates
- Event recording failures
"""
import asyncio
from typing import Optional
from loguru import logger

from src.core.models import TradingMetrics


class DryRunSanityCheck:
    """
    Automated sanity checks for dry-run mode.

    Periodically validates that dry-run execution is working correctly
    and provides clear error messages when issues are detected.

    Checks performed:
    1. DRY_RUN_NO_FILLS: Orders submitted but no simulated fills
    2. DRY_RUN_NO_PNL: Opportunities seen but no PnL updates
    3. DRY_RUN_STALE: No activity for extended period
    """

    def __init__(self, check_interval_seconds: int = 60):
        """
        Initialize dry-run sanity checker.

        Args:
            check_interval_seconds: How often to run checks (default: 60s)
        """
        self.check_interval_seconds = check_interval_seconds
        self._last_opportunity_count: int = 0
        self._last_fill_count: int = 0
        self._last_pnl_count: int = 0
        self._check_count: int = 0
        self._running: bool = False
        self._task: Optional[asyncio.Task] = None

    async def start(self, metrics: TradingMetrics) -> None:
        """
        Start periodic sanity checks.

        Args:
            metrics: TradingMetrics instance to check
        """
        if self._running:
            logger.warning("DryRunSanityCheck already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._check_loop(metrics))
        logger.info(f"DryRunSanityCheck started (interval: {self.check_interval_seconds}s)")

    async def stop(self) -> None:
        """Stop periodic sanity checks."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        logger.info("DryRunSanityCheck stopped")

    async def _check_loop(self, metrics: TradingMetrics) -> None:
        """
        Main check loop.

        Args:
            metrics: TradingMetrics instance to monitor
        """
        try:
            while self._running:
                await asyncio.sleep(self.check_interval_seconds)
                await self.perform_checks(metrics)
                self._check_count += 1
        except asyncio.CancelledError:
            pass

    async def perform_checks(self, metrics: TradingMetrics) -> None:
        """
        Perform all sanity checks.

        Args:
            metrics: TradingMetrics instance to check
        """
        self._check_no_fills(metrics)
        self._check_no_pnl(metrics)
        self._check_stale_data(metrics)

        # Update baseline counts
        self._last_opportunity_count = metrics.opportunities_seen
        self._last_fill_count = metrics.fills_simulated
        self._last_pnl_count = metrics.pnl_updates

    def _check_no_fills(self, metrics: TradingMetrics) -> None:
        """
        Check for orders submitted but no fills generated.

        This is a CRITICAL error - if dry-run is submitting orders
        but not generating fills, something is fundamentally broken.

        Args:
            metrics: TradingMetrics to check
        """
        if metrics.orders_submitted > 0 and metrics.fills_simulated == 0:
            logger.error("")
            logger.error("=" * 60)
            logger.error("⚠️  DRY_RUN_NO_FILLS: 订单已提交但没有模拟成交!")
            logger.error("")
            logger.error("   This indicates dry-run mode is NOT working correctly.")
            logger.error("   Expected: SimulatedExecutor should generate fills")
            logger.error("   Actual: No fills detected")
            logger.error("")
            logger.error("   Troubleshooting:")
            logger.error("   1. Check if SimulatedExecutor is properly initialized")
            logger.error("   2. Check if order books have liquidity")
            logger.error("   3. Check ExecutionRouter routing to SimulatedExecutor")
            logger.error("   4. Review logs for 'Insufficient liquidity' warnings")
            logger.error("=" * 60)
            logger.error("")

    def _check_no_pnl(self, metrics: TradingMetrics) -> None:
        """
        Check for opportunities detected but no PnL updates.

        This is a WARNING - opportunities were found but PnLTracker
        didn't process the fills.

        Args:
            metrics: TradingMetrics to check
        """
        if metrics.opportunities_seen > 0 and metrics.pnl_updates == 0:
            logger.warning("")
            logger.warning("⚠️  DRY_RUN_NO_PNL: 检测到机会但没有PnL更新!")
            logger.warning("")
            logger.warning("   This indicates PnLTracker is not processing fills.")
            logger.warning("   Expected: PnL updates after each fill")
            logger.warning("   Actual: No PnL updates detected")
            logger.warning("")
            logger.warning("   Troubleshooting:")
            logger.warning("   1. Check if PnLTracker.process_fills() is called")
            logger.warning("   2. Check if fills are being generated (see DRY_RUN_NO_FILLS)")
            logger.warning("   3. Review main.py execution flow after fills")
            logger.warning("")

    def _check_stale_data(self, metrics: TradingMetrics) -> None:
        """
        Check for stale data (no new opportunities/fills/PnL).

        This is an INFO message - not necessarily an error, but
        worth monitoring.

        Args:
            metrics: TradingMetrics to check
        """
        # Only check after 3+ iterations (give it time to warm up)
        if self._check_count < 3:
            return

        # Check if no new data since last check
        no_new_opportunities = metrics.opportunities_seen == self._last_opportunity_count
        no_new_fills = metrics.fills_simulated == self._last_fill_count
        no_new_pnl = metrics.pnl_updates == self._last_pnl_count

        if no_new_opportunities and no_new_fills and no_new_pnl:
            logger.info(f"ℹ️  DRY_RUN_STALE: No new activity in last {self.check_interval_seconds}s")
            logger.info(f"   This is normal if market conditions are quiet.")
            logger.info(f"   Opportunities: {metrics.opportunities_seen}, Fills: {metrics.fills_simulated}, PnL updates: {metrics.pnl_updates}")

    def get_summary(self) -> dict:
        """Get checker summary."""
        return {
            "running": self._running,
            "check_count": self._check_count,
            "check_interval_seconds": self.check_interval_seconds,
            "last_opportunity_count": self._last_opportunity_count,
            "last_fill_count": self._last_fill_count,
            "last_pnl_count": self._last_pnl_count,
        }
