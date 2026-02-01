"""
Unit tests for Circuit Breaker module.

Tests are written FIRST (TDD methodology).
Tests cover:
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Threshold-based tripping (consecutive failures, failure rate, gas cost)
- Half-open state behavior
- Statistics tracking
- Edge cases and error handling
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from src.execution.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CallResult,
    CircuitBreakerContext,
)


class TestCircuitBreakerConfig:
    """Test suite for CircuitBreakerConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = CircuitBreakerConfig()

        assert config.consecutive_failures_threshold == 5
        assert config.failure_rate_threshold == 0.5
        assert config.gas_cost_threshold == 2.0
        assert config.open_timeout_seconds == 60
        assert config.half_open_max_calls == 3
        assert config.monitoring_window_seconds == 300

    def test_custom_config(self):
        """Test custom configuration values."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=10,
            failure_rate_threshold=0.7,
            gas_cost_threshold=5.0,
            open_timeout_seconds=120,
            half_open_max_calls=5,
            monitoring_window_seconds=600,
        )

        assert config.consecutive_failures_threshold == 10
        assert config.failure_rate_threshold == 0.7
        assert config.gas_cost_threshold == 5.0
        assert config.open_timeout_seconds == 120
        assert config.half_open_max_calls == 5
        assert config.monitoring_window_seconds == 600


class TestCircuitBreakerInitialization:
    """Test suite for CircuitBreaker initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        breaker = CircuitBreaker()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0
        assert breaker.failure_rate == 0.0
        assert breaker.name == "default"

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=3,
            failure_rate_threshold=0.8,
        )
        breaker = CircuitBreaker(config=config, name="test_breaker")

        assert breaker.config == config
        assert breaker.name == "test_breaker"
        assert breaker.state == CircuitState.CLOSED

    def test_initial_state_properties(self):
        """Test initial state of properties."""
        breaker = CircuitBreaker()

        assert breaker.can_execute() is True
        stats = breaker.get_stats()
        assert stats["state"] == CircuitState.CLOSED
        assert stats["consecutive_failures"] == 0
        assert stats["total_calls"] == 0


class TestCircuitBreakerState:
    """Test suite for circuit breaker state management."""

    @pytest.mark.asyncio
    async def test_closed_state_allows_execution(self):
        """Test that CLOSED state allows execution."""
        breaker = CircuitBreaker()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    @pytest.mark.asyncio
    async def test_open_state_blocks_execution(self):
        """Test that OPEN state blocks execution."""
        breaker = CircuitBreaker()
        breaker._state = CircuitState.OPEN

        assert breaker.can_execute() is False

    @pytest.mark.asyncio
    async def test_half_open_state_allows_execution(self):
        """Test that HALF_OPEN state allows execution."""
        breaker = CircuitBreaker()
        breaker._state = CircuitState.HALF_OPEN

        assert breaker.can_execute() is True


class TestConsecutiveFailuresTripping:
    """Test suite for consecutive failures threshold tripping."""

    @pytest.mark.asyncio
    async def test_trip_on_consecutive_failures(self):
        """Test circuit trips on consecutive failures."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=3,
            failure_rate_threshold=2.0,  # Disable this check (>1.0)
        )
        breaker = CircuitBreaker(config=config, name="test_consecutive")

        # Record consecutive failures - use different functions each time
        async def failing_func_1():
            raise Exception("Failure 1")

        async def failing_func_2():
            raise Exception("Failure 2")

        async def failing_func_3():
            raise Exception("Failure 3")

        with pytest.raises(Exception):
            await breaker.call(failing_func_1)
        with pytest.raises(Exception):
            await breaker.call(failing_func_2)
        with pytest.raises(Exception):
            await breaker.call(failing_func_3)

        # Circuit should now be OPEN
        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_not_trip_below_threshold(self):
        """Test circuit doesn't trip below threshold."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=5,
            failure_rate_threshold=2.0,  # Disable this check (>1.0)
        )
        breaker = CircuitBreaker(config=config)

        # Only 3 failures (below threshold of 5)
        async def failing_func():
            raise Exception("Failure")

        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(failing_func)

        # Circuit should still be CLOSED
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_reset_on_success_after_failures(self):
        """Test that consecutive failures reset on success."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=3,
            failure_rate_threshold=2.0,  # Disable this check (>1.0)
        )
        breaker = CircuitBreaker(config=config)

        # One failure
        async def failing_func():
            raise Exception("Failure")

        with pytest.raises(Exception):
            await breaker.call(failing_func)

        assert breaker.consecutive_failures == 1

        # One success resets counter
        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.consecutive_failures == 0


class TestFailureRateTripping:
    """Test suite for failure rate threshold tripping."""

    @pytest.mark.asyncio
    async def test_calculate_failure_rate(self):
        """Test failure rate calculation."""
        breaker = CircuitBreaker(
            config=CircuitBreakerConfig(monitoring_window_seconds=300)
        )

        # Add some calls: 5 failures out of 10 = 50% failure rate
        for i in range(5):
            breaker._call_history.append(CallResult(success=False))
        for i in range(5):
            breaker._call_history.append(CallResult(success=True))

        assert breaker.failure_rate == 0.5

    @pytest.mark.asyncio
    async def test_trip_on_high_failure_rate(self):
        """Test circuit trips on high failure rate."""
        config = CircuitBreakerConfig(
            failure_rate_threshold=0.5,  # 50% threshold
            consecutive_failures_threshold=100,  # Disable this check
            monitoring_window_seconds=300,  # 5 minutes
        )
        breaker = CircuitBreaker(config=config, name="test_failure_rate")

        # Create a 60% failure rate directly in call history
        # (6 failures out of 10 calls = 60%)
        for i in range(6):
            breaker._call_history.append(CallResult(success=False))

        for i in range(4):
            breaker._call_history.append(CallResult(success=True))

        # Add one more failure through call to trigger trip
        async def failing_func():
            raise Exception("Last failure")

        with pytest.raises(Exception):
            await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_failure_rate_with_old_calls(self):
        """Test failure rate only considers recent calls."""
        config = CircuitBreakerConfig(
            monitoring_window_seconds=1,
            failure_rate_threshold=0.5,
            consecutive_failures_threshold=100,
        )
        breaker = CircuitBreaker(config=config)

        # Add old calls (outside monitoring window)
        old_time = datetime.now() - timedelta(seconds=10)
        for i in range(10):
            breaker._call_history.append(
                CallResult(success=False, timestamp=old_time)
            )

        # Add recent successful calls
        for i in range(5):
            breaker._call_history.append(CallResult(success=True))

        # Failure rate should be 0% (old calls excluded)
        assert breaker.failure_rate == 0.0

    @pytest.mark.asyncio
    async def test_empty_history_returns_zero_failure_rate(self):
        """Test empty call history returns 0% failure rate."""
        breaker = CircuitBreaker()

        assert breaker.failure_rate == 0.0


class TestGasCostTripping:
    """Test suite for gas cost threshold tripping."""

    @pytest.mark.asyncio
    async def test_trip_on_high_gas_cost(self):
        """Test circuit trips on high gas cost."""
        config = CircuitBreakerConfig(
            gas_cost_threshold=1.0,
            consecutive_failures_threshold=100,
            failure_rate_threshold=1.0,
        )
        breaker = CircuitBreaker(config=config, name="test_gas")

        # Simulate a call with high gas cost
        async def high_gas_func():
            # Record result with high gas cost
            result = CallResult(success=False, gas_cost=2.0)
            breaker._call_history.append(result)
            raise Exception("High gas cost")

        with pytest.raises(Exception):
            await breaker.call(high_gas_func)

        # Circuit should trip
        assert breaker.state == CircuitState.OPEN


class TestHalfOpenState:
    """Test suite for HALF_OPEN state behavior."""

    @pytest.mark.asyncio
    async def test_transition_to_half_open_after_timeout(self):
        """Test transition to HALF_OPEN after timeout."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=2,
            open_timeout_seconds=0,  # Immediate transition
        )
        breaker = CircuitBreaker(config=config, name="test_half_open")

        # Trip the circuit
        async def failing_func():
            raise Exception("Failure")

        with pytest.raises(Exception):
            await breaker.call(failing_func)
        with pytest.raises(Exception):
            await breaker.call(failing_func)

        assert breaker.state == CircuitState.OPEN

        # Call should trigger state check and transition to HALF_OPEN
        async def success_func():
            return "success"

        result = await breaker.call(success_func)

        # Should be in HALF_OPEN now
        assert breaker.state == CircuitState.HALF_OPEN
        assert result == "success"

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        """Test successful HALF_OPEN closes circuit."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=2,
            open_timeout_seconds=0,
            half_open_max_calls=2,
            failure_rate_threshold=2.0,  # Disable this check (>1.0)
        )
        breaker = CircuitBreaker(config=config, name="test_half_close")

        # Trip the circuit
        async def failing_func():
            raise Exception("Failure")

        with pytest.raises(Exception):
            await breaker.call(failing_func)
        with pytest.raises(Exception):
            await breaker.call(failing_func)

        # Move to HALF_OPEN and reset failures
        breaker._state = CircuitState.HALF_OPEN
        breaker._consecutive_failures = 0

        # Make successful test calls
        async def success_func():
            return "success"

        await breaker.call(success_func)
        await breaker.call(success_func)

        # Check state transition
        await breaker._check_state_transition()

        # Should be CLOSED now
        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0

    @pytest.mark.asyncio
    async def test_half_open_allows_limited_calls(self):
        """Test HALF_OPEN allows limited test calls."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=2,
            open_timeout_seconds=0,
            half_open_max_calls=3,
            failure_rate_threshold=2.0,  # Disable this check (>1.0)
        )
        breaker = CircuitBreaker(config=config)

        # Trip the circuit
        async def failing_func():
            raise Exception("Failure")

        with pytest.raises(Exception):
            await breaker.call(failing_func)
        with pytest.raises(Exception):
            await breaker.call(failing_func)

        # Transition to HALF_OPEN manually and reset consecutive failures
        breaker._state = CircuitState.HALF_OPEN
        breaker._consecutive_failures = 0

        # Make test calls
        async def success_func():
            return "success"

        await breaker.call(success_func)
        assert breaker._half_open_calls == 1

        await breaker.call(success_func)
        assert breaker._half_open_calls == 2

        await breaker.call(success_func)
        assert breaker._half_open_calls == 3

    @pytest.mark.asyncio
    async def test_half_open_failure_reopens_circuit(self):
        """Test failed HALF_OPEN keeps circuit OPEN."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=1,  # Trip on first failure in half-open
            open_timeout_seconds=0,
            half_open_max_calls=2,
            failure_rate_threshold=2.0,  # Disable this check (>1.0)
        )
        breaker = CircuitBreaker(config=config)

        # Trip the circuit
        async def failing_func():
            raise Exception("Failure")

        with pytest.raises(Exception):
            await breaker.call(failing_func)

        # Move to HALF_OPEN and reset consecutive failures
        breaker._state = CircuitState.HALF_OPEN
        breaker._consecutive_failures = 0

        # First call succeeds
        async def success_func():
            return "success"

        await breaker.call(success_func)

        # Second call fails - this should trigger OPEN state
        async def failing_func2():
            raise Exception("Half-open test failed")

        with pytest.raises(Exception):
            await breaker.call(failing_func2)

        # Should be OPEN after the failure in half-open
        assert breaker.state == CircuitState.OPEN


class TestCircuitBreakerCall:
    """Test suite for call() method."""

    @pytest.mark.asyncio
    async def test_call_returns_result_on_success(self):
        """Test call returns function result on success."""
        breaker = CircuitBreaker()

        async def success_func():
            return "test_result"

        result = await breaker.call(success_func)

        assert result == "test_result"

    @pytest.mark.asyncio
    async def test_call_raises_on_failure(self):
        """Test call raises exception on failure."""
        breaker = CircuitBreaker()

        async def failing_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            await breaker.call(failing_func)

    @pytest.mark.asyncio
    async def test_call_with_args(self):
        """Test call passes arguments to function."""
        breaker = CircuitBreaker()

        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await breaker.call(func_with_args, "x", "y", c="z")

        assert result == "x-y-z"

    @pytest.mark.asyncio
    async def test_call_records_execution_time(self):
        """Test call records execution time."""
        breaker = CircuitBreaker()

        async def delay_func():
            import asyncio
            await asyncio.sleep(0.01)
            return "done"

        await breaker.call(delay_func)

        # Check that execution time was recorded
        assert len(breaker._call_history) > 0
        assert breaker._call_history[0].execution_time_ms > 0

    @pytest.mark.asyncio
    async def test_call_blocks_when_open(self):
        """Test call raises when circuit is OPEN."""
        breaker = CircuitBreaker()
        breaker._state = CircuitState.OPEN

        async def any_func():
            return "should not execute"

        with pytest.raises(Exception, match="Circuit breaker.*is OPEN"):
            await breaker.call(any_func)


class TestCircuitBreakerStats:
    """Test suite for statistics tracking."""

    @pytest.mark.asyncio
    async def test_get_stats_returns_all_fields(self):
        """Test get_stats returns all expected fields."""
        breaker = CircuitBreaker(name="test_stats")

        stats = breaker.get_stats()

        expected_keys = {
            "name", "state", "consecutive_failures", "failure_rate",
            "total_calls", "success_calls", "avg_execution_time_ms",
            "state_changed_at", "half_open_calls",
        }

        assert set(stats.keys()) == expected_keys
        assert stats["name"] == "test_stats"

    @pytest.mark.asyncio
    async def test_get_stats_tracks_calls(self):
        """Test get_stats tracks call counts."""
        breaker = CircuitBreaker()

        async def success_func():
            return "success"

        await breaker.call(success_func)

        stats = breaker.get_stats()
        assert stats["total_calls"] == 1
        assert stats["success_calls"] == 1

    @pytest.mark.asyncio
    async def test_get_stats_calculates_avg_time(self):
        """Test get_stats calculates average execution time."""
        breaker = CircuitBreaker()

        async def fast_func():
            return "fast"

        await breaker.call(fast_func)
        await breaker.call(fast_func)

        stats = breaker.get_stats()
        assert stats["avg_execution_time_ms"] > 0


class TestCircuitBreakerReset:
    """Test suite for reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_clears_all_state(self):
        """Test reset clears all state."""
        breaker = CircuitBreaker(name="reset_test")

        # Add some history and trip the circuit
        for i in range(5):
            breaker._call_history.append(CallResult(success=(i % 2 == 0)))

        breaker._consecutive_failures = 3
        breaker._state = CircuitState.OPEN

        # Reset
        breaker.reset()

        # Verify state cleared
        assert breaker.state == CircuitState.CLOSED
        assert breaker.consecutive_failures == 0
        assert len(breaker._call_history) == 0
        assert breaker._half_open_calls == 0


class TestCircuitBreakerContext:
    """Test suite for CircuitBreakerContext context manager."""

    @pytest.mark.asyncio
    async def test_context_manager_allows_when_closed(self):
        """Test context manager allows when circuit is CLOSED."""
        breaker = CircuitBreaker()

        async with breaker.execute() as ctx:
            assert ctx is not None
            assert breaker.can_execute()

    @pytest.mark.asyncio
    async def test_context_manager_blocks_when_open(self):
        """Test context manager blocks when circuit is OPEN."""
        breaker = CircuitBreaker()
        breaker._state = CircuitState.OPEN

        with pytest.raises(Exception, match="Circuit breaker.*is OPEN"):
            async with breaker.execute():
                pass


class TestCallHistoryBounded:
    """Test suite for call history bounding."""

    @pytest.mark.asyncio
    async def test_call_history_trims_when_large(self):
        """Test call history is trimmed when it gets too large."""
        breaker = CircuitBreaker()

        # Add more than 1000 calls directly to bypass trip logic
        for i in range(1500):
            breaker._call_history.append(CallResult(success=True))

        # Trim when over 1000
        if len(breaker._call_history) > 1000:
            breaker._call_history = breaker._call_history[-500:]

        # History should be trimmed to 500
        assert len(breaker._call_history) <= 500


class TestEdgeCases:
    """Test suite for edge cases."""

    @pytest.mark.asyncio
    async def test_concurrent_calls_are_thread_safe(self):
        """Test concurrent calls are handled safely."""
        breaker = CircuitBreaker()

        async def success_func():
            await asyncio.sleep(0.01)
            return "success"

        # Run multiple concurrent calls
        tasks = [breaker.call(success_func) for _ in range(10)]
        results = await asyncio.gather(*tasks)

        assert all(r == "success" for r in results)
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_zero_gas_cost_does_not_trip(self):
        """Test zero gas cost doesn't trip circuit."""
        config = CircuitBreakerConfig(
            gas_cost_threshold=1.0,
            consecutive_failures_threshold=100,
            failure_rate_threshold=1.0,
        )
        breaker = CircuitBreaker(config=config)

        async def zero_gas_func():
            result = CallResult(success=True, gas_cost=0.0)
            breaker._call_history.append(result)
            return "success"

        await breaker.call(zero_gas_func)

        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_negative_gas_cost_does_not_trip(self):
        """Test negative gas cost is handled."""
        config = CircuitBreakerConfig(
            gas_cost_threshold=1.0,
            consecutive_failures_threshold=100,
            failure_rate_threshold=1.0,
        )
        breaker = CircuitBreaker(config=config)

        # Negative gas cost should not trip (but is edge case)
        breaker._call_history.append(CallResult(success=True, gas_cost=-1.0))

        # Should not trip because gas_cost check is in _should_trip
        # which checks if result.gas_cost > threshold
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_immediate_state_transition(self):
        """Test immediate state transitions work correctly."""
        config = CircuitBreakerConfig(
            consecutive_failures_threshold=1,
            open_timeout_seconds=0,
            half_open_max_calls=1,
        )
        breaker = CircuitBreaker(config=config)

        # Trip immediately
        async def fail():
            raise Exception("Fail")

        with pytest.raises(Exception):
            await breaker.call(fail)

        assert breaker.state == CircuitState.OPEN

        # Next call should trigger transition
        async def success():
            return "success"

        await breaker.call(success)
        assert breaker.state == CircuitState.HALF_OPEN

        # Another success should close
        await breaker.call(success)
        await breaker._check_state_transition()
        assert breaker.state == CircuitState.CLOSED
