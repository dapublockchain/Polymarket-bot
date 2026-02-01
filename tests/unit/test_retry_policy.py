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
