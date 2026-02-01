"""
Retry policy for resilient transaction execution.

Implements exponential backoff with jitter for retrying failed operations.
"""
import asyncio
import random
from enum import Enum
from typing import Optional, List, Callable
from dataclasses import dataclass

from loguru import logger


logger = logger.bind(context="retry_policy")


class RetryableError(str, Enum):
    """Types of retryable errors."""

    NETWORK_ERROR = "network_error"
    NONCE_TOO_LOW = "nonce_too_low"
    GAS_TOO_LOW = "gas_too_low"
    TIMEOUT = "timeout"
    TEMPORARY_FAILURE = "temporary_failure"


@dataclass
class RetryPolicyConfig:
    """Retry policy configuration."""

    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 30000
    exponential_backoff: bool = True
    jitter: bool = True
    backoff_multiplier: float = 2.0


class RetryPolicy:
    """
    Retry policy with exponential backoff and jitter.

    Features:
    - Configurable max retries
    - Exponential backoff
    - Jitter to prevent thundering herd
    - Error classification
    """

    def __init__(self, config: Optional[RetryPolicyConfig] = None):
        """
        Initialize retry policy.

        Args:
            config: Retry policy configuration
        """
        self.config = config or RetryPolicyConfig()

    def is_retryable(self, error: Exception) -> bool:
        """
        Check if error is retryable.

        Args:
            error: Exception to check

        Returns:
            True if error should be retried
        """
        # Error message patterns for retryable errors
        retryable_patterns = [
            "timeout",
            "network",
            "connection",
            "nonce too low",
            "replacement transaction underpriced",
            "gas required exceeds allowance",
        ]

        error_msg = str(error).lower()

        return any(pattern in error_msg for pattern in retryable_patterns)

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay before next retry.

        Args:
            attempt: Attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        base_delay = self.config.base_delay_ms / 1000.0

        if self.config.exponential_backoff:
            delay = base_delay * (self.config.backoff_multiplier ** attempt)
        else:
            delay = base_delay

        # Cap at max delay
        max_delay = self.config.max_delay_ms / 1000.0
        delay = min(delay, max_delay)

        # Add jitter
        if self.config.jitter:
            jitter_range = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    async def execute(
        self,
        func: Callable,
        *args,
        on_retry: Optional[Callable[[Exception, int], None]] = None,
        **kwargs
    ):
        """
        Execute function with retry logic.

        Args:
            func: Function to execute
            *args: Function arguments
            on_retry: Callback(error, attempt) on each retry
            **kwargs: Function keyword arguments

        Returns:
            Function return value

        Raises:
            Exception: If all retries exhausted
        """
        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                return await func(*args, **kwargs)

            except Exception as e:
                last_error = e

                # Check if should retry
                if attempt < self.config.max_retries and self.is_retryable(e):
                    delay = self.calculate_delay(attempt)

                    logger.warning(
                        f"Retry {attempt + 1}/{self.config.max_retries} "
                        f"after {delay:.2f}s: {str(e)[:100]}"
                    )

                    # Call retry callback
                    if on_retry:
                        await on_retry(e, attempt)

                    await asyncio.sleep(delay)
                else:
                    # Non-retryable or max retries exceeded
                    if not self.is_retryable(e):
                        logger.error(f"Non-retryable error: {str(e)[:100]}")
                    else:
                        logger.error(f"Max retries exceeded: {str(e)[:100]}")
                    raise

        # Should not reach here
        raise last_error


class IdempotencyKey:
    """
    Idempotency key manager to prevent duplicate operations.

    Tracks executed operations by trace_id to prevent duplicates.
    """

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize idempotency key manager.

        Args:
            ttl_seconds: Time-to-live for keys (default 1 hour)
        """
        self._keys: dict[str, float] = {}  # key -> expiry timestamp
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()

    async def check_and_set(self, key: str) -> bool:
        """
        Check if key exists and set if not.

        Args:
            key: Idempotency key (typically trace_id)

        Returns:
            True if key was newly created (operation should proceed)
            False if key already exists (operation is duplicate)
        """
        async with self._lock:
            # Clean up expired keys
            now = asyncio.get_event_loop().time()
            expired_keys = [k for k, exp in self._keys.items() if exp < now]
            for k in expired_keys:
                del self._keys[k]

            # Check if key exists
            if key in self._keys:
                logger.warning(f"Duplicate operation detected: {key}")
                return False

            # Set key with expiry
            self._keys[key] = now + self._ttl_seconds
            return True

    async def remove(self, key: str):
        """
        Remove idempotency key.

        Args:
            key: Key to remove
        """
        async with self._lock:
            if key in self._keys:
                del self._keys[key]

    def get_stats(self) -> dict:
        """Get idempotency key stats."""
        return {
            "total_keys": len(self._keys),
            "ttl_seconds": self._ttl_seconds,
        }
