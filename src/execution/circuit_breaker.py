"""
Circuit breaker module for trading system resilience.

Implements the circuit breaker pattern to prevent cascading failures
when the trading system encounters persistent errors.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Circuit tripped, requests blocked
- HALF_OPEN: Testing if system has recovered

Example:
    breaker = CircuitBreaker(
        consecutive_failures_threshold=5,
        failure_rate_threshold=0.5,
        open_timeout_seconds=60
    )

    async with breaker.execute("trade"):
        # This will only execute if circuit is CLOSED or HALF_OPEN
        await execute_trade()
"""
import asyncio
import time
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from loguru import logger

from src.core.telemetry import log_event, EventType as TeleEventType


logger = logger.bind(context="circuit_breaker")


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Circuit tripped, blocking requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    # Trigger thresholds
    consecutive_failures_threshold: int = 5
    failure_rate_threshold: float = 0.5  # 50% failure rate
    gas_cost_threshold: float = 2.0  # USDC

    # Timing
    open_timeout_seconds: int = 60  # How long to stay OPEN before HALF_OPEN
    half_open_max_calls: int = 3  # Max calls to test in HALF_OPEN state

    # Monitoring window (for failure rate calculation)
    monitoring_window_seconds: int = 300  # 5 minutes


@dataclass
class CallResult:
    """Result of a single call through the circuit breaker."""

    success: bool
    timestamp: datetime = field(default_factory=datetime.now)
    error: Optional[str] = None
    gas_cost: float = 0.0
    execution_time_ms: float = 0.0


class CircuitBreaker:
    """
    Circuit breaker for trading system resilience.

    Prevents execution when:
    - Too many consecutive failures
    - Failure rate exceeds threshold
    - Gas costs too high

    Automatically recovers after timeout and testing.
    """

    def __init__(
        self,
        config: Optional[CircuitBreakerConfig] = None,
        name: str = "default"
    ):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
            name: Circuit breaker name (for logging)
        """
        self.config = config or CircuitBreakerConfig()
        self.name = name

        # State
        self._state = CircuitState.CLOSED
        self._state_changed_at = datetime.now()

        # Tracking
        self._consecutive_failures = 0
        self._call_history: list[CallResult] = []
        self._half_open_calls = 0

        # Lock for thread safety
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @property
    def consecutive_failures(self) -> int:
        """Get consecutive failure count."""
        return self._consecutive_failures

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate in monitoring window."""
        if not self._call_history:
            return 0.0

        cutoff = datetime.now() - timedelta(seconds=self.config.monitoring_window_seconds)
        recent_calls = [c for c in self._call_history if c.timestamp >= cutoff]

        if not recent_calls:
            return 0.0

        failures = sum(1 for c in recent_calls if not c.success)
        return failures / len(recent_calls)

    def _should_trip(self, result: CallResult) -> bool:
        """
        Determine if circuit should trip based on result.

        Args:
            result: Call result to check

        Returns:
            True if circuit should trip
        """
        # Check gas cost threshold
        if result.gas_cost > self.config.gas_cost_threshold:
            logger.warning(
                f"[{self.name}] Gas cost threshold exceeded: "
                f"{result.gas_cost} > {self.config.gas_cost_threshold}"
            )
            return True

        # Check consecutive failures
        if self._consecutive_failures >= self.config.consecutive_failures_threshold:
            logger.warning(
                f"[{self.name}] Consecutive failures threshold exceeded: "
                f"{self._consecutive_failures} >= {self.config.consecutive_failures_threshold}"
            )
            return True

        # Check failure rate
        if self.failure_rate >= self.config.failure_rate_threshold:
            logger.warning(
                f"[{self.name}] Failure rate threshold exceeded: "
                f"{self.failure_rate:.2%} >= {self.config.failure_rate_threshold:.2%}"
            )
            return True

        return False

    async def _transition_to(self, new_state: CircuitState, reason: str):
        """
        Transition to new state with logging.

        Args:
            new_state: New circuit state
            reason: Reason for transition
        """
        old_state = self._state
        self._state = new_state
        self._state_changed_at = datetime.now()

        # Log state change
        logger.info(
            f"[{self.name}] Circuit state transition: {old_state} -> {new_state}"
        )
        logger.info(f"[{self.name}] Reason: {reason}")

        # Log to telemetry
        await log_event(
            TeleEventType.RISK_PASSED,  # Using existing event type
            {
                "circuit_breaker": self.name,
                "state_transition": f"{old_state}_to_{new_state}",
                "reason": reason,
                "consecutive_failures": self._consecutive_failures,
                "failure_rate": f"{self.failure_rate:.2%}",
            },
            trace_id=f"cb_{self.name}_{int(time.time() * 1000)}"
        )

        # Reset counters on certain transitions
        if new_state == CircuitState.CLOSED:
            self._consecutive_failures = 0
            self._half_open_calls = 0
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0

    async def _check_state_transition(self):
        """Check if state should transition based on time and conditions."""
        now = datetime.now()
        time_in_state = (now - self._state_changed_at).total_seconds()

        if self._state == CircuitState.OPEN:
            # Check if timeout elapsed
            if time_in_state >= self.config.open_timeout_seconds:
                await self._transition_to(
                    CircuitState.HALF_OPEN,
                    f"Open timeout elapsed ({time_in_state:.0f}s >= {self.config.open_timeout_seconds}s)"
                )

        elif self._state == CircuitState.HALF_OPEN:
            # Check if we've made enough test calls
            if self._half_open_calls >= self.config.half_open_max_calls:
                # Check if we should close or re-open
                if self._consecutive_failures == 0:
                    await self._transition_to(
                        CircuitState.CLOSED,
                        f"Half-open test successful ({self._half_open_calls} calls)"
                    )
                else:
                    await self._transition_to(
                        CircuitState.OPEN,
                        f"Half-open test failed ({self._consecutive_failures} failures)"
                    )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker.

        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments

        Returns:
            Function return value

        Raises:
            Exception: If circuit is OPEN or function raises exception
        """
        async with self._lock:
            # Check for state transitions
            await self._check_state_transition()

            # Check if circuit is open
            if self._state == CircuitState.OPEN:
                logger.warning(f"[{self.name}] Circuit is OPEN, blocking request")
                raise Exception(f"Circuit breaker '{self.name}' is OPEN")

            # Increment half-open call counter
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                logger.info(
                    f"[{self.name}] Half-open test call {self._half_open_calls}/{self.config.half_open_max_calls}"
                )

        # Execute the function
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)

            # Record success
            execution_time = (time.time() - start_time) * 1000
            call_result = CallResult(
                success=True,
                execution_time_ms=execution_time,
                gas_cost=0.0  # Should be set by caller
            )

            async with self._lock:
                self._call_history.append(call_result)
                self._consecutive_failures = 0

                # Keep history bounded
                if len(self._call_history) > 1000:
                    self._call_history = self._call_history[-500:]

            return result

        except Exception as e:
            # Record failure
            execution_time = (time.time() - start_time) * 1000
            call_result = CallResult(
                success=False,
                error=str(e),
                execution_time_ms=execution_time,
                gas_cost=0.0
            )

            async with self._lock:
                self._call_history.append(call_result)
                self._consecutive_failures += 1

                # Check if circuit should trip
                if self._should_trip(call_result):
                    await self._transition_to(CircuitState.OPEN, f"Threshold exceeded: {str(e)}")

                # Keep history bounded
                if len(self._call_history) > 1000:
                    self._call_history = self._call_history[-500:]

            raise

    def can_execute(self) -> bool:
        """
        Check if execution is allowed (circuit is not OPEN).

        Returns:
            True if execution is allowed
        """
        return self._state != CircuitState.OPEN

    def reset(self):
        """Reset circuit breaker to CLOSED state (for testing)."""
        self._state = CircuitState.CLOSED
        self._state_changed_at = datetime.now()
        self._consecutive_failures = 0
        self._half_open_calls = 0
        self._call_history.clear()
        logger.info(f"[{self.name}] Circuit breaker reset")

    def get_stats(self) -> dict:
        """
        Get circuit breaker statistics.

        Returns:
            Dictionary with stats
        """
        cutoff = datetime.now() - timedelta(seconds=self.config.monitoring_window_seconds)
        recent_calls = [c for c in self._call_history if c.timestamp >= cutoff]

        total_calls = len(recent_calls)
        success_calls = sum(1 for c in recent_calls if c.success)
        avg_execution_time_ms = (
            sum(c.execution_time_ms for c in recent_calls) / total_calls
            if total_calls > 0
            else 0.0
        )

        return {
            "name": self.name,
            "state": self._state,
            "consecutive_failures": self._consecutive_failures,
            "failure_rate": self.failure_rate,
            "total_calls": total_calls,
            "success_calls": success_calls,
            "avg_execution_time_ms": avg_execution_time_ms,
            "state_changed_at": self._state_changed_at.isoformat(),
            "half_open_calls": self._half_open_calls,
        }


# Context manager for easier use
class CircuitBreakerContext:
    """Context manager for circuit breaker execution."""

    def __init__(self, breaker: CircuitBreaker):
        """
        Initialize context manager.

        Args:
            breaker: Circuit breaker instance
        """
        self.breaker = breaker

    async def __aenter__(self):
        """Enter context, check if execution is allowed."""
        if not self.breaker.can_execute():
            raise Exception(f"Circuit breaker '{self.breaker.name}' is OPEN")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit context, record result."""
        # Result recording is handled by the call() method
        return None


CircuitBreaker.execute = lambda self, name=None: CircuitBreakerContext(self)
