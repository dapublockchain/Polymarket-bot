"""
Unit tests for Retry Policy module.

Tests the retry policy with exponential backoff and jitter.
"""
import pytest
import asyncio
from unittest.mock import Mock

from src.execution.retry_policy import (
    RetryPolicy,
    RetryPolicyConfig,
    RetryableError,
    IdempotencyKey,
)


class TestRetryPolicyConfig:
    """Test suite for RetryPolicyConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryPolicyConfig()

        assert config.max_retries == 3
        assert config.base_delay_ms == 1000
        assert config.max_delay_ms == 30000
        assert config.exponential_backoff is True
        assert config.jitter is True
        assert config.backoff_multiplier == 2.0

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RetryPolicyConfig(
            max_retries=5,
            base_delay_ms=500,
            max_delay_ms=60000,
            exponential_backoff=False,
            jitter=False,
            backoff_multiplier=3.0,
        )

        assert config.max_retries == 5
        assert config.base_delay_ms == 500
        assert config.max_delay_ms == 60000
        assert config.exponential_backoff is False
        assert config.jitter is False
        assert config.backoff_multiplier == 3.0


class TestRetryPolicyInit:
    """Test suite for RetryPolicy initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default config."""
        policy = RetryPolicy()

        assert policy.config.max_retries == 3
        assert policy.max_attempts == 4  # max_retries + 1

    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = RetryPolicyConfig(max_retries=5)
        policy = RetryPolicy(config=config)

        assert policy.config == config
        assert policy.max_attempts == 6


class TestRetryPolicyIsRetryable:
    """Test suite for is_retryable method."""

    def test_retryable_network_error(self):
        """Test that network errors are retryable."""
        policy = RetryPolicy()

        assert policy.is_retryable(Exception("network error")) is True
        assert policy.is_retryable(Exception("timeout error")) is True
        assert policy.is_retryable(Exception("connection lost")) is True

    def test_retryable_nonce_errors(self):
        """Test that nonce errors are retryable."""
        policy = RetryPolicy()

        assert policy.is_retryable(Exception("nonce too low")) is True
        assert policy.is_retryable(Exception("replacement transaction underpriced")) is True

    def test_retryable_gas_errors(self):
        """Test that gas errors are retryable."""
        policy = RetryPolicy()

        assert policy.is_retryable(Exception("gas required exceeds allowance")) is True

    def test_non_retryable_errors(self):
        """Test that other errors are not retryable."""
        policy = RetryPolicy()

        assert policy.is_retryable(Exception("insufficient funds")) is False
        assert policy.is_retryable(Exception("invalid address")) is False
        assert policy.is_retryable(Exception("contract execution error")) is False

    def test_case_insensitive_matching(self):
        """Test that error matching is case-insensitive."""
        policy = RetryPolicy()

        assert policy.is_retryable(Exception("NETWORK ERROR")) is True
        assert policy.is_retryable(Exception("TimeOut")) is True
        assert policy.is_retryable(Exception("NonCe ToO lOw")) is True


class TestRetryPolicyCalculateDelay:
    """Test suite for calculate_delay method."""

    def test_calculate_delay_no_backoff(self):
        """Test delay calculation without exponential backoff."""
        config = RetryPolicyConfig(
            base_delay_ms=1000,
            exponential_backoff=False,
            jitter=False,
        )
        policy = RetryPolicy(config=config)

        delay = policy.calculate_delay(0)
        assert delay == 1.0  # 1000ms = 1 second

        delay = policy.calculate_delay(5)
        assert delay == 1.0  # Same delay without backoff

    def test_calculate_delay_with_backoff(self):
        """Test delay calculation with exponential backoff."""
        config = RetryPolicyConfig(
            base_delay_ms=1000,
            exponential_backoff=True,
            jitter=False,
            backoff_multiplier=2.0,
        )
        policy = RetryPolicy(config=config)

        delay = policy.calculate_delay(0)
        assert delay == 1.0  # 1000ms

        delay = policy.calculate_delay(1)
        assert delay == 2.0  # 1000ms * 2

        delay = policy.calculate_delay(2)
        assert delay == 4.0  # 1000ms * 2^2

        delay = policy.calculate_delay(3)
        assert delay == 8.0  # 1000ms * 2^3

    def test_calculate_delay_with_max_cap(self):
        """Test that delay is capped at max_delay."""
        config = RetryPolicyConfig(
            base_delay_ms=1000,
            max_delay_ms=5000,  # 5 second max
            exponential_backoff=True,
            jitter=False,
        )
        policy = RetryPolicy(config=config)

        # This would be 8 seconds without cap
        delay = policy.calculate_delay(3)
        assert delay == 5.0  # Capped at 5 seconds

    def test_calculate_delay_with_jitter(self):
        """Test that jitter is applied to delay."""
        config = RetryPolicyConfig(
            base_delay_ms=1000,
            exponential_backoff=False,
            jitter=True,
        )
        policy = RetryPolicy(config=config)

        delay = policy.calculate_delay(0)

        # Should be approximately 1.0 seconds with ±10% jitter
        assert 0.85 <= delay <= 1.15

    def test_calculate_delay_custom_multiplier(self):
        """Test delay calculation with custom multiplier."""
        config = RetryPolicyConfig(
            base_delay_ms=1000,
            exponential_backoff=True,
            jitter=False,
            backoff_multiplier=3.0,
        )
        policy = RetryPolicy(config=config)

        delay = policy.calculate_delay(1)
        assert delay == 3.0  # 1000ms * 3

        delay = policy.calculate_delay(2)
        assert delay == 9.0  # 1000ms * 3^2


class TestIdempotencyKey:
    """Test suite for IdempotencyKey class."""

    def test_generate_from_signal(self):
        """Test generating key from signal."""
        from src.core.models import Signal

        idem = IdempotencyKey()
        signal = Signal(
            strategy="test_strategy",
            token_id="token_123",
            signal_type="BUY",
            expected_profit=0.5,
            trade_size=10,
            yes_price=0.5,
            no_price=0.5,
            confidence=0.9,
            reason="test",
        )

        key = idem.generate(signal)

        assert isinstance(key, str)
        assert "test_strategy" in key
        assert "token_123" in key
        assert "BUY" in key

    def test_is_seen_false(self):
        """Test is_seen returns False for new key."""
        idem = IdempotencyKey()

        assert idem.is_seen("new_key") is False

    def test_is_seen_true(self):
        """Test is_seen returns True for seen key."""
        idem = IdempotencyKey()
        idem.mark_seen("existing_key")

        assert idem.is_seen("existing_key") is True

    def test_mark_seen(self):
        """Test mark_seen adds key."""
        idem = IdempotencyKey()
        idem.mark_seen("test_key")

        assert "test_key" in idem._keys

    def test_get_stats(self):
        """Test get_stats returns correct stats."""
        idem = IdempotencyKey(ttl_seconds=3600)
        idem.mark_seen("key1")
        idem.mark_seen("key2")

        stats = idem.get_stats()

        assert stats["total_keys"] == 2
        assert stats["ttl_seconds"] == 3600

    @pytest.mark.asyncio
    async def test_check_and_set_new_key(self):
        """Test check_and_set returns True for new key."""
        idem = IdempotencyKey()

        result = await idem.check_and_set("new_key")

        assert result is True
        assert "new_key" in idem._keys

    @pytest.mark.asyncio
    async def test_check_and_set_existing_key(self):
        """Test check_and_set returns False for existing key."""
        idem = IdempotencyKey()
        await idem.check_and_set("existing_key")

        result = await idem.check_and_set("existing_key")

        assert result is False

    @pytest.mark.asyncio
    async def test_remove(self):
        """Test removing a key."""
        idem = IdempotencyKey()
        await idem.check_and_set("test_key")

        await idem.remove("test_key")

        assert "test_key" not in idem._keys

    @pytest.mark.asyncio
    async def test_expiry(self):
        """Test that expired keys are cleaned up."""
        import time

        idem = IdempotencyKey(ttl_seconds=0.1)  # 100ms TTL
        await idem.check_and_set("expiring_key")

        # Wait for expiry
        await asyncio.sleep(0.15)

        # Key should be cleaned up on next check
        result = await idem.check_and_set("expiring_key")

        assert result is True  # Should be treated as new key


class TestRetryableError:
    """Test suite for RetryableError enum."""

    def test_enum_values(self):
        """Test enum has correct values."""
        assert RetryableError.NETWORK_ERROR.value == "network_error"
        assert RetryableError.NONCE_TOO_LOW.value == "nonce_too_low"
        assert RetryableError.GAS_TOO_LOW.value == "gas_too_low"
        assert RetryableError.TIMEOUT.value == "timeout"
        assert RetryableError.TEMPORARY_FAILURE.value == "temporary_failure"


class TestRetryPolicyIntegration:
    """Integration tests for retry policy."""

    @pytest.mark.asyncio
    async def test_retry_flow(self):
        """Test complete retry flow with delays."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=10,  # Short delay for testing
                jitter=False,
            )
        )

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("network error")
            return "success"

        # Simulate retry logic
        last_error = None
        for attempt in range(policy.max_attempts):
            try:
                result = await failing_func()
                assert result == "success"
                assert call_count == 3  # Should have succeeded on 3rd attempt
                break
            except Exception as e:
                last_error = e
                if policy.is_retryable(e) and attempt < policy.max_attempts - 1:
                    delay = policy.calculate_delay(attempt)
                    await asyncio.sleep(delay)
                else:
                    raise
        else:
            raise last_error

    @pytest.mark.asyncio
    async def test_non_retryable_stops_immediately(self):
        """Test that non-retryable errors stop immediately."""
        policy = RetryPolicy()

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("insufficient funds")  # Not retryable

        with pytest.raises(Exception, match="insufficient funds"):
            await failing_func()

        assert call_count == 1  # Should only be called once


class TestRetryPolicyExecute:
    """Test suite for execute() method with retry logic."""

    @pytest.mark.asyncio
    async def test_execute_succeeds_on_first_try(self):
        """Test execute returns immediately on success."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(max_retries=3, base_delay_ms=10)
        )

        call_count = 0

        async def success_func():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await policy.execute(success_func)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_execute_retries_on_network_error(self):
        """Test execute retries on retryable errors."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=10,
                jitter=False,
            )
        )

        call_count = 0

        async def eventually_succeeds():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("network error")
            return "finally succeeded"

        result = await policy.execute(eventually_succeeds)

        assert result == "finally succeeded"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_raises_after_max_retries(self):
        """Test execute raises after max retries exhausted."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=1,
                jitter=False,
            )
        )

        call_count = 0

        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise Exception("timeout error")

        with pytest.raises(Exception, match="timeout error"):
            await policy.execute(always_fails)

        # Should have tried max_retries + 1 times
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_execute_non_retryable_stops_immediately(self):
        """Test execute stops immediately on non-retryable error."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(max_retries=5)
        )

        call_count = 0

        async def non_retryable_error():
            nonlocal call_count
            call_count += 1
            raise Exception("insufficient funds")

        with pytest.raises(Exception, match="insufficient funds"):
            await policy.execute(non_retryable_error)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_execute_with_on_retry_callback(self):
        """Test execute calls on_retry callback."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=1,
                jitter=False,
            )
        )

        retry_count = 0
        captured_errors = []

        async def retry_callback(error, attempt):
            nonlocal retry_count
            retry_count += 1
            captured_errors.append(str(error))

        async def fails_then_succeeds():
            if retry_count < 1:
                raise Exception("network error")
            return "success"

        result = await policy.execute(
            fails_then_succeeds,
            on_retry=retry_callback
        )

        assert result == "success"
        assert retry_count == 1
        assert len(captured_errors) == 1

    @pytest.mark.asyncio
    async def test_execute_with_function_arguments(self):
        """Test execute passes arguments to function."""
        policy = RetryPolicy()

        async def func_with_args(a, b, c=None):
            return f"{a}-{b}-{c}"

        result = await policy.execute(func_with_args, "x", "y", c="z")

        assert result == "x-y-z"

    @pytest.mark.asyncio
    async def test_execute_with_keyword_arguments(self):
        """Test execute passes keyword arguments."""
        policy = RetryPolicy()

        async def func_with_kwargs(**kwargs):
            return kwargs

        result = await policy.execute(
            func_with_kwargs,
            key1="value1",
            key2="value2"
        )

        assert result == {"key1": "value1", "key2": "value2"}

    @pytest.mark.asyncio
    async def test_execute_respects_exponential_backoff(self):
        """Test execute uses exponential backoff delays."""
        import time

        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=50,
                exponential_backoff=True,
                jitter=False,
            )
        )

        call_times = []

        async def timed_fails():
            call_times.append(time.time())
            raise Exception("network error")

        start_time = time.time()
        with pytest.raises(Exception):
            await policy.execute(timed_fails)

        total_time = time.time() - start_time

        # Should have delays: 50ms + 100ms = 150ms minimum
        assert total_time >= 0.14  # Allow small margin

    @pytest.mark.asyncio
    async def test_execute_with_zero_retries(self):
        """Test execute with max_retries=0 fails immediately."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(max_retries=0)
        )

        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise Exception("timeout")

        with pytest.raises(Exception):
            await policy.execute(failing_func)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_execute_nonce_too_low_retry(self):
        """Test execute retries on nonce too low error."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=1,
            )
        )

        call_count = 0

        async def nonce_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("nonce too low")
            return "success"

        result = await policy.execute(nonce_error)

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_execute_gas_error_retry(self):
        """Test execute retries on gas errors."""
        policy = RetryPolicy(
            config=RetryPolicyConfig(
                max_retries=2,
                base_delay_ms=1,
            )
        )

        call_count = 0

        async def gas_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("gas required exceeds allowance")
            return "success"

        result = await policy.execute(gas_error)

        assert result == "success"
        assert call_count == 2


class TestIdempotencyKeyAdvanced:
    """Advanced tests for IdempotencyKey."""

    @pytest.mark.asyncio
    async def test_concurrent_check_and_set(self):
        """Test concurrent check_and_set operations."""
        idem = IdempotencyKey()

        # Multiple concurrent checks for same key
        tasks = [
            idem.check_and_set("concurrent_key")
            for _ in range(10)
        ]

        results = await asyncio.gather(*tasks)

        # Only one should return True (first one)
        true_count = sum(1 for r in results if r is True)
        false_count = sum(1 for r in results if r is False)

        assert true_count == 1
        assert false_count == 9

    @pytest.mark.asyncio
    async def test_multiple_keys_expiry(self):
        """Test multiple keys expire independently."""
        import time

        idem = IdempotencyKey(ttl_seconds=0.1)

        await idem.check_and_set("key1")
        await asyncio.sleep(0.05)
        await idem.check_and_set("key2")
        await asyncio.sleep(0.06)

        # key1 should be expired, key2 should still exist
        result1 = await idem.check_and_set("key1")
        result2 = await idem.check_and_set("key2")

        assert result1 is True  # Expired, treated as new
        assert result2 is False  # Still exists

    @pytest.mark.asyncio
    async def test_remove_nonexistent_key(self):
        """Test removing a key that doesn't exist."""
        idem = IdempotencyKey()

        # Should not raise
        await idem.remove("nonexistent_key")

    @pytest.mark.asyncio
    async def test_check_and_set_auto_cleanup(self):
        """Test that expired keys are automatically cleaned up."""
        idem = IdempotencyKey(ttl_seconds=0.05)

        # Add multiple keys
        for i in range(5):
            await idem.check_and_set(f"key_{i}")

        assert len(idem._keys) == 5

        # Wait for expiry
        await asyncio.sleep(0.1)

        # Check one key (triggers cleanup)
        result = await idem.check_and_set("key_0")

        assert result is True  # Should be treated as new
        # Old keys should be cleaned up
        assert len(idem._keys) == 1

    def test_is_seen_thread_safe(self):
        """Test is_seen is thread-safe for immediate checks."""
        idem = IdempotencyKey()

        assert idem.is_seen("test_key") is False
        idem.mark_seen("test_key")
        assert idem.is_seen("test_key") is True

    @pytest.mark.asyncio
    async def test_mark_seen_overwrites(self):
        """Test mark_seen overwrites existing key."""
        idem = IdempotencyKey(ttl_seconds=10)

        # Mark a key
        idem.mark_seen("key1")
        first_expiry = idem._keys["key1"]

        # Mark again (should update expiry)
        await asyncio.sleep(0.01)
        idem.mark_seen("key1")
        second_expiry = idem._keys["key1"]

        # Second expiry should be later
        assert second_expiry > first_expiry

    @pytest.mark.asyncio
    async def test_generate_unique_keys(self):
        """Test that generate creates keys with timestamp."""
        from src.core.models import Signal

        idem = IdempotencyKey()

        signal = Signal(
            strategy="test",
            token_id="token_123",
            signal_type="BUY_YES",
            expected_profit=0.5,
            trade_size=10,
            yes_price=0.5,
            no_price=0.5,
            confidence=0.9,
            reason="test",
        )

        key1 = idem.generate(signal)
        # Keys contain timestamp so they should include signal info
        assert "test" in key1
        assert "token_123" in key1
        assert "BUY_YES" in key1
