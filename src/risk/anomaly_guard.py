"""
Anomaly Guard Module - Anti-Manipulation and Anomaly Defense.

This module detects and responds to abnormal market conditions.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum
from collections import deque
import time

from loguru import logger

from src.core.config import Config
from src.execution.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


class AnomalyType(str, Enum):
    """Types of anomalies."""
    PRICE_PULSE = "price_pulse"  # Sudden large price movement
    CORRELATION_BREAK = "correlation_break"  # Correlation breakdown
    DEPTH_DEPLETION = "depth_depletion"  # Sudden liquidity loss


class ResponseAction(str, Enum):
    """Response actions to anomalies."""
    NONE = "none"  # No action
    DEGRADE = "degrade"  # Reduce position sizes
    HALT = "halt"  # Stop trading temporarily


@dataclass
class AnomalyEvent:
    """An anomaly detection event.

    Attributes:
        anomaly_type: Type of anomaly
        token_id: Token identifier
        severity: Severity score (0-1)
        timestamp: Event timestamp
        details: Additional details
        response_action: Action taken
    """
    anomaly_type: AnomalyType
    token_id: str
    severity: float
    timestamp: float
    details: Dict[str, Any]
    response_action: ResponseAction


@dataclass
class AnomalyMetrics:
    """Metrics for anomaly detection.

    Attributes:
        total_anomalies_detected: Total anomalies detected
        price_pulse_count: Price pulse anomalies
        correlation_break_count: Correlation breakdown anomalies
        depth_depletion_count: Depth depletion anomalies
        total_degrades: Total degrade responses
        total_halts: Total halt responses
        current_state: Current system state
    """
    total_anomalies_detected: int = 0
    price_pulse_count: int = 0
    correlation_break_count: int = 0
    depth_depletion_count: int = 0
    total_degrades: int = 0
    total_halts: int = 0
    current_state: ResponseAction = ResponseAction.NONE


class AnomalyGuard:
    """
    Detects and responds to market anomalies.

    Key features:
    - Price pulse detection (sudden large movements)
    - Correlation breakdown detection
    - Order book depth depletion detection
    - Graduated response (degrade → halt)
    - Integration with CircuitBreaker
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        circuit_breaker: Optional[CircuitBreaker] = None,
    ):
        """
        Initialize anomaly guard.

        Args:
            config: Optional configuration
            circuit_breaker: Optional circuit breaker for integration
        """
        self.config = config or Config()

        # Thresholds from config
        self.price_pulse_threshold = self.config.ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD
        self.correlation_break_threshold = self.config.ANOMALY_DEFENSE_CORRELATION_BREAK_THRESHOLD
        self.depth_depletion_threshold = self.config.ANOMALY_DEFENSE_DEPTH_DEPLETION_THRESHOLD

        # Circuit breaker integration
        self.circuit_breaker = circuit_breaker

        # Price history for pulse detection
        self.price_history: Dict[str, deque] = {}  # token_id -> deque of (price, timestamp)
        self.max_history_size = 100

        # Depth history for depletion detection
        self.depth_history: Dict[str, deque] = {}  # token_id -> deque of depth values
        self.max_depth_history = 50

        # Metrics
        self.metrics = AnomalyMetrics()

        # Anomaly history
        self.anomaly_history: List[AnomalyEvent] = []

        self.enabled = self.config.ANOMALY_DEFENSE_ENABLED

        if self.enabled:
            logger.info("Anomaly Guard initialized")
        else:
            logger.info("Anomaly Guard initialized (DISABLED)")

    async def check_price_pulse(
        self,
        token_id: str,
        current_price: Decimal,
    ) -> Optional[AnomalyEvent]:
        """
        Check for price pulse anomaly (sudden large movement).

        Args:
            token_id: Token identifier
            current_price: Current price

        Returns:
            AnomalyEvent if detected, None otherwise
        """
        if not self.enabled:
            return None

        now = time.time()

        # Initialize history if needed
        if token_id not in self.price_history:
            self.price_history[token_id] = deque(maxlen=self.max_history_size)
            self.price_history[token_id].append((float(current_price), now))
            return None

        history = self.price_history[token_id]

        # Add current price
        history.append((float(current_price), now))

        # Need at least 3 data points
        if len(history) < 3:
            return None

        # Calculate price change percentage
        # Compare current price to average of last 3-5 prices (within last 30 seconds)
        recent_prices = [
            p for p, t in history
            if now - t < 30  # Last 30 seconds
        ]

        if len(recent_prices) < 3:
            return None

        avg_price = sum(recent_prices[:-1]) / (len(recent_prices) - 1)  # Exclude current
        price_change_pct = abs((float(current_price) - avg_price) / avg_price)

        # Check if threshold exceeded
        if price_change_pct > self.price_pulse_threshold:
            severity = min(price_change_pct / (self.price_pulse_threshold * 2), 1.0)

            event = AnomalyEvent(
                anomaly_type=AnomalyType.PRICE_PULSE,
                token_id=token_id,
                severity=severity,
                timestamp=now,
                details={
                    "price_change_pct": price_change_pct,
                    "avg_price": avg_price,
                    "current_price": float(current_price),
                },
                response_action=self._determine_response(severity),
            )

            await self._handle_anomaly(event)
            return event

        return None

    async def check_correlation_break(
        self,
        token_id: str,
        correlated_prices: Dict[str, Decimal],
        expected_correlation: float,
    ) -> Optional[AnomalyEvent]:
        """
        Check for correlation breakdown.

        Args:
            token_id: Primary token identifier
            correlated_prices: Dictionary of correlated token prices
            expected_correlation: Expected correlation coefficient (-1 to 1)

        Returns:
            AnomalyEvent if detected, None otherwise
        """
        if not self.enabled:
            return None

        # For simplicity, we check if prices have moved in opposite directions
        # A more sophisticated implementation would calculate actual correlation

        if not correlated_prices:
            return None

        # Get price changes for all tokens
        changes = []
        for tok_id, price in correlated_prices.items():
            if tok_id in self.price_history and len(self.price_history[tok_id]) > 0:
                last_price, _ = self.price_history[tok_id][-1]
                if last_price > 0:
                    change = (float(price) - last_price) / last_price
                    changes.append(change)

        if len(changes) < 2:
            return None

        # Check if changes are in same direction (positive correlation)
        # or opposite directions (negative correlation)
        correlation_violation = False

        if expected_correlation > 0:
            # Should move together - check for opposite moves
            if any(c < 0 for c in changes) and any(c > 0 for c in changes):
                correlation_violation = True
        else:
            # Should move opposite - check for same direction
            if all(c > 0 for c in changes) or all(c < 0 for c in changes):
                correlation_violation = True

        if correlation_violation:
            severity = 0.5  # Moderate severity

            event = AnomalyEvent(
                anomaly_type=AnomalyType.CORRELATION_BREAK,
                token_id=token_id,
                severity=severity,
                timestamp=time.time(),
                details={
                    "expected_correlation": expected_correlation,
                    "price_changes": changes,
                },
                response_action=self._determine_response(severity),
            )

            await self._handle_anomaly(event)
            return event

        return None

    async def check_depth_depletion(
        self,
        token_id: str,
        current_depth: float,
    ) -> Optional[AnomalyEvent]:
        """
        Check for order book depth depletion.

        Args:
            token_id: Token identifier
            current_depth: Current order book depth (total size)

        Returns:
            AnomalyEvent if detected, None otherwise
        """
        if not self.enabled:
            return None

        now = time.time()

        # Initialize history if needed
        if token_id not in self.depth_history:
            self.depth_history[token_id] = deque(maxlen=self.max_depth_history)
            self.depth_history[token_id].append(current_depth)
            return None

        history = self.depth_history[token_id]

        # Add current depth
        history.append(current_depth)

        # Need at least 5 data points
        if len(history) < 5:
            return None

        # Calculate average depth
        avg_depth = sum(list(history)[:-1]) / (len(history) - 1)

        # Check if depth dropped significantly
        if avg_depth > 0:
            depth_change_pct = (avg_depth - current_depth) / avg_depth

            if depth_change_pct > self.depth_depletion_threshold:
                severity = min(depth_change_pct / (self.depth_depletion_threshold * 2), 1.0)

                event = AnomalyEvent(
                    anomaly_type=AnomalyType.DEPTH_DEPLETION,
                    token_id=token_id,
                    severity=severity,
                    timestamp=now,
                    details={
                        "depth_change_pct": depth_change_pct,
                        "avg_depth": avg_depth,
                        "current_depth": current_depth,
                    },
                    response_action=self._determine_response(severity),
                )

                await self._handle_anomaly(event)
                return event

        return None

    def _determine_response(self, severity: float) -> ResponseAction:
        """
        Determine response action based on severity.

        Args:
            severity: Severity score (0-1)

        Returns:
            ResponseAction
        """
        if severity >= 0.7:
            return ResponseAction.HALT
        elif severity >= 0.4:
            return ResponseAction.DEGRADE
        else:
            return ResponseAction.NONE

    async def _handle_anomaly(self, event: AnomalyEvent) -> None:
        """
        Handle detected anomaly.

        Args:
            event: Anomaly event
        """
        # Update metrics
        self.metrics.total_anomalies_detected += 1

        if event.anomaly_type == AnomalyType.PRICE_PULSE:
            self.metrics.price_pulse_count += 1
        elif event.anomaly_type == AnomalyType.CORRELATION_BREAK:
            self.metrics.correlation_break_count += 1
        elif event.anomaly_type == AnomalyType.DEPTH_DEPLETION:
            self.metrics.depth_depletion_count += 1

        if event.response_action == ResponseAction.DEGRADE:
            self.metrics.total_degrades += 1
        elif event.response_action == ResponseAction.HALT:
            self.metrics.total_halts += 1

        self.metrics.current_state = event.response_action

        # Add to history
        self.anomaly_history.append(event)

        # Take action
        if event.response_action == ResponseAction.HALT:
            logger.warning(
                f"Anomaly HALT triggered: {event.anomaly_type.value} on {event.token_id} "
                f"(severity={event.severity:.2f})"
            )

            # Trip circuit breaker if available
            if self.circuit_breaker:
                await self.circuit_breaker.trip(f"Anomaly detected: {event.anomaly_type.value}")

        elif event.response_action == ResponseAction.DEGRADE:
            logger.warning(
                f"Anomaly DEGRADE triggered: {event.anomaly_type.value} on {event.token_id} "
                f"(severity={event.severity:.2f})"
            )

        else:
            logger.info(
                f"Anomaly detected (no action): {event.anomaly_type.value} on {event.token_id} "
                f"(severity={event.severity:.2f})"
            )

    def get_metrics(self) -> AnomalyMetrics:
        """
        Get current anomaly metrics.

        Returns:
            AnomalyMetrics
        """
        return self.metrics

    def get_anomaly_history(self, limit: int = 100) -> List[AnomalyEvent]:
        """
        Get recent anomaly history.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent anomaly events
        """
        return self.anomaly_history[-limit:]

    def reset(self) -> None:
        """Reset anomaly guard state."""
        self.metrics = AnomalyMetrics()
        self.price_history.clear()
        self.depth_history.clear()
        logger.info("Anomaly Guard reset")
