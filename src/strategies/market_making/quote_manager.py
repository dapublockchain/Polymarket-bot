"""
Quote Manager for Market Making Strategy.

This module manages quote lifecycle with post-only enforcement and aging.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import time

from loguru import logger


class QuoteStatus(str, Enum):
    """Quote status."""
    PENDING = "pending"
    POSTED = "posted"
    FILLED = "filled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


@dataclass
class Quote:
    """A market making quote.

    Attributes:
        quote_id: Unique quote identifier
        token_id: Token identifier
        bid_price: Bid price
        ask_price: Ask price
        size: Quote size in USDC
        status: Quote status
        created_at: Quote creation timestamp
        expires_at: Quote expiration timestamp
        post_only: Whether quote is post-only (MUST be true)
        age_seconds: Current age in seconds
    """
    quote_id: str
    token_id: str
    bid_price: Decimal
    ask_price: Decimal
    size: Decimal
    status: QuoteStatus
    created_at: datetime
    expires_at: datetime
    post_only: bool = True  # MUST be True for market making
    filled_size: Decimal = Decimal("0")
    cancel_reason: Optional[str] = None

    @property
    def age_seconds(self) -> float:
        """Get current age of quote in seconds."""
        return (datetime.now() - self.created_at).total_seconds()

    @property
    def is_expired(self) -> bool:
        """Check if quote is expired."""
        return datetime.now() > self.expires_at

    @property
    def is_stale(self, max_age_seconds: float) -> bool:
        """Check if quote is stale (too old)."""
        return self.age_seconds > max_age_seconds


@dataclass
class QuoteMetrics:
    """Metrics for quote management.

    Attributes:
        total_quotes_created: Total quotes created
        total_quotes_posted: Total quotes posted
        total_quotes_filled: Total quotes filled
        total_quotes_cancelled: Total quotes cancelled
        total_fill_volume: Total volume filled
        average_fill_rate: Average fill rate (filled / posted)
        cancellations_last_minute: Cancellations in last minute
    """
    total_quotes_created: int = 0
    total_quotes_posted: int = 0
    total_quotes_filled: int = 0
    total_quotes_cancelled: int = 0
    total_fill_volume: Decimal = Decimal("0")
    average_fill_rate: float = 0.0
    cancellations_last_minute: int = 0


class QuoteManager:
    """
    Manages quote lifecycle for market making.

    Key features:
    - Post-only enforcement (NEVER takes liquidity)
    - Quote aging and expiration
    - Cancellation rate limiting
    - Quote metrics tracking
    """

    def __init__(
        self,
        quote_age_limit_seconds: float = 30.0,
        max_cancel_rate_per_minute: int = 10,
    ):
        """
        Initialize quote manager.

        Args:
            quote_age_limit_seconds: Maximum age of a quote before refresh
            max_cancel_rate_per_minute: Max cancellations allowed per minute
        """
        self.quote_age_limit_seconds = quote_age_limit_seconds
        self.max_cancel_rate_per_minute = max_cancel_rate_per_minute

        self.quotes: Dict[str, Quote] = {}
        self.metrics = QuoteMetrics()

        # Track cancellation timestamps for rate limiting
        self.cancellation_times: List[float] = []

        # For quote ID generation
        self._quote_counter = 0

    async def create_quote(
        self,
        token_id: str,
        bid_price: Decimal,
        ask_price: Decimal,
        size: Decimal,
        ttl_seconds: float = 30.0,
    ) -> Quote:
        """
        Create a new quote.

        Args:
            token_id: Token identifier
            bid_price: Bid price
            ask_price: Ask price
            size: Quote size in USDC
            ttl_seconds: Time-to-live in seconds

        Returns:
            Quote object
        """
        self._quote_counter += 1
        quote_id = f"quote_{int(time.time())}_{self._quote_counter}"

        now = datetime.now()
        quote = Quote(
            quote_id=quote_id,
            token_id=token_id,
            bid_price=bid_price,
            ask_price=ask_price,
            size=size,
            status=QuoteStatus.PENDING,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            post_only=True,  # ALWAYS post-only
        )

        self.quotes[quote_id] = quote
        self.metrics.total_quotes_created += 1

        logger.info(
            f"Quote created: {quote_id} - bid={bid_price:.4f}, ask={ask_price:.4f}, size={size}"
        )

        return quote

    async def post_quote(self, quote_id: str) -> bool:
        """
        Mark quote as posted (simulated - actual posting done by trading layer).

        Args:
            quote_id: Quote identifier

        Returns:
            True if successful, False otherwise
        """
        quote = self.quotes.get(quote_id)
        if not quote:
            logger.warning(f"Quote not found: {quote_id}")
            return False

        # Must be post-only
        if not quote.post_only:
            logger.error(f"Quote {quote_id} is not post-only - REJECTING")
            return False

        quote.status = QuoteStatus.POSTED
        self.metrics.total_quotes_posted += 1

        logger.info(f"Quote posted: {quote_id}")
        return True

    async def cancel_quote(self, quote_id: str, reason: str = "manual") -> bool:
        """
        Cancel a quote with rate limiting.

        Args:
            quote_id: Quote identifier
            reason: Cancellation reason

        Returns:
            True if cancelled, False if rate limited
        """
        # Check cancellation rate
        if not self._can_cancel():
            logger.warning(f"Cancel rate limit exceeded - cannot cancel {quote_id}")
            return False

        quote = self.quotes.get(quote_id)
        if not quote:
            logger.warning(f"Quote not found: {quote_id}")
            return False

        if quote.status != QuoteStatus.POSTED:
            logger.warning(f"Quote {quote_id} not in POSTED status - cannot cancel")
            return False

        quote.status = QuoteStatus.CANCELLED
        quote.cancel_reason = reason
        self.metrics.total_quotes_cancelled += 1

        # Track cancellation for rate limiting
        now = time.time()
        self.cancellation_times.append(now)

        logger.info(f"Quote cancelled: {quote_id} - reason={reason}")
        return True

    async def fill_quote(
        self,
        quote_id: str,
        filled_size: Decimal,
    ) -> bool:
        """
        Mark quote as filled (partially or fully).

        Args:
            quote_id: Quote identifier
            filled_size: Size filled in USDC

        Returns:
            True if successful
        """
        quote = self.quotes.get(quote_id)
        if not quote:
            logger.warning(f"Quote not found: {quote_id}")
            return False

        quote.filled_size += filled_size
        self.metrics.total_fill_volume += filled_size

        # Check if fully filled
        if quote.filled_size >= quote.size:
            quote.status = QuoteStatus.FILLED
            self.metrics.total_quotes_filled += 1
            logger.info(f"Quote filled: {quote_id} - ${filled_size}")
        else:
            logger.info(f"Quote partially filled: {quote_id} - ${filled_size} / ${quote.size}")

        # Update fill rate
        if self.metrics.total_quotes_posted > 0:
            self.metrics.average_fill_rate = (
                self.metrics.total_quotes_filled / self.metrics.total_quotes_posted
            )

        return True

    def get_stale_quotes(self) -> List[Quote]:
        """
        Get all stale quotes that need refreshing.

        Returns:
            List of stale quotes
        """
        stale = [
            quote for quote in self.quotes.values()
            if quote.status == QuoteStatus.POSTED and quote.is_stale(self.quote_age_limit_seconds)
        ]

        if stale:
            logger.debug(f"Found {len(stale)} stale quotes")

        return stale

    async def refresh_stale_quotes(self) -> int:
        """
        Cancel all stale quotes.

        Returns:
            Number of quotes cancelled
        """
        stale_quotes = self.get_stale_quotes()
        cancelled = 0

        for quote in stale_quotes:
            if await self.cancel_quote(quote.quote_id, reason="stale"):
                cancelled += 1

        if cancelled > 0:
            logger.info(f"Refreshed {cancelled} stale quotes")

        return cancelled

    def get_active_quotes(self) -> List[Quote]:
        """
        Get all active (posted) quotes.

        Returns:
            List of active quotes
        """
        return [
            quote for quote in self.quotes.values()
            if quote.status == QuoteStatus.POSTED and not quote.is_expired
        ]

    def _can_cancel(self) -> bool:
        """
        Check if cancellation is allowed based on rate limit.

        Returns:
            True if allowed, False if rate limited
        """
        now = time.time()

        # Remove old cancellations (older than 1 minute)
        self.cancellation_times = [
            t for t in self.cancellation_times
            if now - t < 60
        ]

        # Check rate limit
        return len(self.cancellation_times) < self.max_cancel_rate_per_minute

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get quote management metrics.

        Returns:
            Metrics dictionary
        """
        return {
            "total_quotes_created": self.metrics.total_quotes_created,
            "total_quotes_posted": self.metrics.total_quotes_posted,
            "total_quotes_filled": self.metrics.total_quotes_filled,
            "total_quotes_cancelled": self.metrics.total_quotes_cancelled,
            "total_fill_volume": str(self.metrics.total_fill_volume),
            "average_fill_rate": self.metrics.average_fill_rate,
            "active_quotes": len(self.get_active_quotes()),
            "stale_quotes": len(self.get_stale_quotes()),
            "cancellations_last_minute": self.metrics.cancellations_last_minute,
        }
