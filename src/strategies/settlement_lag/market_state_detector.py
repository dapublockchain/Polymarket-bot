"""
Market State Detector for Settlement Lag Strategy.

This module analyzes market conditions using ONLY publicly available information
to identify suitable markets for settlement lag trading.
"""
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from loguru import logger


@dataclass
class MarketState:
    """Detected state of a settlement market.

    Attributes:
        market_id: Market identifier
        in_resolution_window: Whether market is in resolution window
        hours_to_resolution: Hours until resolution (negative if already passed)
        volatility_score: Volatility score (0-1, higher = more volatile)
        liquidity_score: Liquidity score (0-1, higher = more liquid)
        spread_bps: Bid-ask spread in basis points
        volume_24h: 24-hour volume in USDC
        is_suitable: Whether this market is suitable for settlement lag trading
        disqualification_reason: Reason why market is not suitable (if any)
    """
    market_id: str
    in_resolution_window: bool
    hours_to_resolution: float
    volatility_score: float
    liquidity_score: float
    spread_bps: int
    volume_24h: Decimal
    is_suitable: bool
    disqualification_reason: Optional[str] = None


class MarketStateDetector:
    """
    Detects market states suitable for settlement lag trading.

    Uses ONLY public information from the order book and market metadata.
    No private or insider information is used.
    """

    def __init__(
        self,
        min_resolution_window_hours: float = 1.0,
        max_resolution_window_hours: float = 72.0,
        min_volume_usd: Decimal = Decimal("1000"),
        max_spread_bps: int = 200,  # 2%
        min_liquidity_score: float = 0.3,
    ):
        """
        Initialize market state detector.

        Args:
            min_resolution_window_hours: Minimum hours until resolution
            max_resolution_window_hours: Maximum hours until resolution
            min_volume_usd: Minimum 24h volume in USDC
            max_spread_bps: Maximum allowed bid-ask spread in basis points
            min_liquidity_score: Minimum liquidity score (0-1)
        """
        self.min_resolution_window_hours = min_resolution_window_hours
        self.max_resolution_window_hours = max_resolution_window_hours
        self.min_volume_usd = min_volume_usd
        self.max_spread_bps = max_spread_bps
        self.min_liquidity_score = min_liquidity_score

    async def detect_market_state(
        self,
        market_id: str,
        end_date: Optional[datetime],
        order_book_snapshot: Dict[str, Any],
        market_metadata: Optional[Dict[str, Any]] = None,
    ) -> MarketState:
        """
        Detect market state from public information.

        Args:
            market_id: Market identifier
            end_date: Market end date (from public metadata)
            order_book_snapshot: Current order book snapshot
            market_metadata: Optional additional market metadata

        Returns:
            MarketState with analysis results
        """
        # Calculate hours to resolution
        hours_to_resolution, in_window = self._calculate_resolution_window(end_date)

        # Calculate volatility from order book depth
        volatility_score = self._calculate_volatility_score(order_book_snapshot)

        # Calculate liquidity score
        liquidity_score = self._calculate_liquidity_score(order_book_snapshot)

        # Calculate spread
        spread_bps = self._calculate_spread_bps(order_book_snapshot)

        # Get volume from metadata
        volume_24h = self._get_volume(market_metadata)

        # Determine suitability
        is_suitable, reason = self._assess_suitability(
            hours_to_resolution=hours_to_resolution,
            in_window=in_window,
            volatility_score=volatility_score,
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            volume_24h=volume_24h,
        )

        state = MarketState(
            market_id=market_id,
            in_resolution_window=in_window,
            hours_to_resolution=hours_to_resolution,
            volatility_score=volatility_score,
            liquidity_score=liquidity_score,
            spread_bps=spread_bps,
            volume_24h=volume_24h,
            is_suitable=is_suitable,
            disqualification_reason=reason if not is_suitable else None,
        )

        if is_suitable:
            logger.info(
                f"Market {market_id} suitable for settlement lag: "
                f"{hours_to_resolution:.1f}h to resolution, "
                f"volatility={volatility_score:.2f}, "
                f"liquidity={liquidity_score:.2f}"
            )

        return state

    def _calculate_resolution_window(
        self,
        end_date: Optional[datetime],
    ) -> tuple[float, bool]:
        """
        Calculate hours until resolution.

        Args:
            end_date: Market end date from public metadata

        Returns:
            Tuple of (hours_to_resolution, in_resolution_window)
        """
        if end_date is None:
            # No end date available - cannot use this market
            return float('inf'), False

        now = datetime.now()
        time_to_resolution = end_date - now

        if time_to_resolution.total_seconds() <= 0:
            # Market already ended
            return abs(time_to_resolution.total_seconds() / 3600), False

        hours_to_resolution = time_to_resolution.total_seconds() / 3600

        # Check if in resolution window
        in_window = (
            self.min_resolution_window_hours
            <= hours_to_resolution
            <= self.max_resolution_window_hours
        )

        return hours_to_resolution, in_window

    def _calculate_volatility_score(
        self,
        order_book_snapshot: Dict[str, Any],
    ) -> float:
        """
        Calculate volatility score from order book.

        Higher score = more volatile = less stable prices.

        Uses order book depth as a proxy for volatility.
        Deeper books = more stable = lower volatility.

        Args:
            order_book_snapshot: Current order book data

        Returns:
            Volatility score (0-1, higher = more volatile)
        """
        bids = order_book_snapshot.get('bids', [])
        asks = order_book_snapshot.get('asks', [])

        if not bids or not asks:
            return 1.0  # Maximum volatility - no liquidity

        # Calculate total depth
        bid_depth = sum(float(b.get('size', 0)) for b in bids)
        ask_depth = sum(float(a.get('size', 0)) for a in asks)
        total_depth = bid_depth + ask_depth

        # Calculate price dispersion (standard deviation of prices)
        bid_prices = [float(b.get('price', 0)) for b in bids]
        ask_prices = [float(a.get('price', 0)) for a in asks]

        if len(bid_prices) < 2 or len(ask_prices) < 2:
            return 0.5  # Moderate volatility - insufficient data

        # Simple volatility metric: depth inverted
        # More depth = less volatile
        if total_depth > 10000:  # Very deep book
            return 0.1
        elif total_depth > 5000:
            return 0.3
        elif total_depth > 1000:
            return 0.5
        elif total_depth > 500:
            return 0.7
        else:
            return 0.9  # Shallow book = high volatility

    def _calculate_liquidity_score(
        self,
        order_book_snapshot: Dict[str, Any],
    ) -> float:
        """
        Calculate liquidity score from order book.

        Higher score = more liquid.

        Args:
            order_book_snapshot: Current order book data

        Returns:
            Liquidity score (0-1, higher = more liquid)
        """
        bids = order_book_snapshot.get('bids', [])
        asks = order_book_snapshot.get('asks', [])

        if not bids or not asks:
            return 0.0  # No liquidity

        # Calculate depth at top of book (best 5 levels)
        top_bid_depth = sum(float(b.get('size', 0)) for b in bids[:5])
        top_ask_depth = sum(float(a.get('size', 0)) for a in asks[:5])
        top_depth = top_bid_depth + top_ask_depth

        # Calculate total depth
        total_bid_depth = sum(float(b.get('size', 0)) for b in bids)
        total_ask_depth = sum(float(a.get('size', 0)) for a in asks)
        total_depth = total_bid_depth + total_ask_depth

        # Normalize to 0-1 scale
        # Assume $10,000+ is excellent liquidity (1.0)
        # Assume <$100 is poor liquidity (0.0)
        if total_depth >= 10000:
            return 1.0
        elif total_depth >= 5000:
            return 0.8
        elif total_depth >= 1000:
            return 0.6
        elif total_depth >= 500:
            return 0.4
        elif total_depth >= 100:
            return 0.2
        else:
            return 0.1

    def _calculate_spread_bps(
        self,
        order_book_snapshot: Dict[str, Any],
    ) -> int:
        """
        Calculate bid-ask spread in basis points.

        Args:
            order_book_snapshot: Current order book data

        Returns:
            Spread in basis points (1 bp = 0.01%)
        """
        bids = order_book_snapshot.get('bids', [])
        asks = order_book_snapshot.get('asks', [])

        if not bids or not asks:
            return 10000  # Maximum spread - no liquidity

        # Get best bid and ask
        best_bid = float(bids[0].get('price', 0))
        best_ask = float(asks[0].get('price', 0))

        if best_bid == 0 or best_ask == 0:
            return 10000

        # Calculate spread as percentage of mid price
        mid_price = (best_bid + best_ask) / 2
        spread_pct = abs(best_ask - best_bid) / mid_price

        # Convert to basis points
        return int(spread_pct * 10000)

    def _get_volume(
        self,
        market_metadata: Optional[Dict[str, Any]],
    ) -> Decimal:
        """
        Get 24-hour volume from metadata.

        Args:
            market_metadata: Market metadata

        Returns:
            24-hour volume in USDC
        """
        if market_metadata is None:
            return Decimal("0")

        volume = market_metadata.get('volume_24h', '0')

        try:
            return Decimal(str(volume))
        except (ValueError, TypeError):
            return Decimal("0")

    def _assess_suitability(
        self,
        hours_to_resolution: float,
        in_window: bool,
        volatility_score: float,
        liquidity_score: float,
        spread_bps: int,
        volume_24h: Decimal,
    ) -> tuple[bool, Optional[str]]:
        """
        Assess whether market is suitable for settlement lag trading.

        Args:
            hours_to_resolution: Hours until resolution
            in_window: Whether in resolution window
            volatility_score: Volatility score (0-1)
            liquidity_score: Liquidity score (0-1)
            spread_bps: Spread in basis points
            volume_24h: 24-hour volume

        Returns:
            Tuple of (is_suitable, disqualification_reason)
        """
        # Must be in resolution window
        if not in_window:
            return False, f"Not in resolution window: {hours_to_resolution:.1f}h"

        # Must have sufficient volume
        if volume_24h < self.min_volume_usd:
            return False, f"Insufficient volume: ${volume_24h} < ${self.min_volume_usd}"

        # Spread must be reasonable
        if spread_bps > self.max_spread_bps:
            return False, f"Spread too wide: {spread_bps} bps > {self.max_spread_bps} bps"

        # Must have minimum liquidity
        if liquidity_score < self.min_liquidity_score:
            return False, f"Liquidity too low: {liquidity_score:.2f} < {self.min_liquidity_score}"

        # Volatility should not be excessive
        # Note: Some volatility is good for opportunities, but too much is risky
        if volatility_score > 0.8:
            return False, f"Volatility too high: {volatility_score:.2f}"

        return True, None
