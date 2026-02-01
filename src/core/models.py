"""
Core data models for PolyArb-X.

All models use Pydantic for validation and serialization.
"""
from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


class RiskTag(str, Enum):
    """Risk tags for identifying signal risk types."""
    TAIL_RISK = "tail_risk"
    SETTLEMENT_RISK = "settlement_risk"
    MANIPULATION_RISK = "manipulation_risk"
    DISPUTE_RISK = "dispute_risk"
    LOW_LIQUIDITY = "low_liquidity"
    CARRY_COST_RISK = "carry_cost_risk"
    CORRELATION_CLUSTER_RISK = "correlation_cluster_risk"


class Bid(BaseModel):
    """Bid order in the order book."""

    price: Decimal = Field(..., description="Price in USDC")
    size: Decimal = Field(..., description="Size in tokens")
    token_id: str = Field(..., description="Token identifier")

    @field_validator("price", "size")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure price and size are positive."""
        if v <= 0:
            raise ValueError("Price and size must be positive")
        return v


class Ask(BaseModel):
    """Ask order in the order book."""

    price: Decimal = Field(..., description="Price in USDC")
    size: Decimal = Field(..., description="Size in tokens")
    token_id: str = Field(..., description="Token identifier")

    @field_validator("price", "size")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure price and size are positive."""
        if v <= 0:
            raise ValueError("Price and size must be positive")
        return v


class OrderBook(BaseModel):
    """Order book for a single token."""

    token_id: str = Field(..., description="Token identifier")
    bids: list[Bid] = Field(default_factory=list, description="Sorted bids (highest first)")
    asks: list[Ask] = Field(default_factory=list, description="Sorted asks (lowest first)")
    last_update: int = Field(..., description="Timestamp of last update (ms)")
    event_received_ms: Optional[int] = Field(
        None,
        description="Timestamp when this orderbook data was received (ms), for latency tracking"
    )

    def get_best_bid(self) -> Optional[Bid]:
        """Get highest bid (best price for selling)."""
        if not self.bids:
            return None
        # Sort bids by price descending (highest first)
        sorted_bids = sorted(self.bids, key=lambda x: x.price, reverse=True)
        return sorted_bids[0]

    def get_best_ask(self) -> Optional[Ask]:
        """Get lowest ask (best price for buying)."""
        if not self.asks:
            return None
        # Sort asks by price ascending (lowest first)
        sorted_asks = sorted(self.asks, key=lambda x: x.price)
        return sorted_asks[0]

    @field_validator("bids", "asks")
    @classmethod
    def validate_sorted(cls, v: list) -> list:
        """Ensure orders are properly sorted."""
        # Note: This will be enforced by the order book manager
        return v


class Signal(BaseModel):
    """Trading signal from a strategy."""

    strategy: str = Field(..., description="Strategy name that generated this signal")
    token_id: str = Field(..., description="Token identifier")
    signal_type: str = Field(..., description="Signal type:BUY_YES, BUY_NO, or ARBITRAGE")
    expected_profit: Decimal = Field(..., description="Expected profit in USDC")
    trade_size: Decimal = Field(..., description="Trade size in USDC")
    yes_price: Optional[Decimal] = Field(None, description="YES token price")
    no_price: Optional[Decimal] = Field(None, description="NO token price")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    reason: str = Field(..., description="Human-readable explanation")

    @field_validator("expected_profit", "trade_size")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure profit and size are non-negative."""
        if v < 0:
            raise ValueError("Expected profit and trade size must be non-negative")
        return v


class ArbitrageOpportunity(Signal):
    """Specific signal for arbitrage opportunities."""

    yes_token_id: str = Field(..., description="YES token identifier")
    no_token_id: str = Field(..., description="NO token identifier")
    yes_cost: Decimal = Field(..., description="Cost to buy YES tokens")
    no_cost: Decimal = Field(..., description="Cost to buy NO tokens")
    total_cost: Decimal = Field(..., description="Total cost of arbitrage")
    fees: Decimal = Field(..., description="Trading fees in USDC")
    gas_estimate: Decimal = Field(..., description="Estimated gas cost in USDC")
    net_profit: Decimal = Field(..., description="Net profit after fees and gas")

    @field_validator("yes_cost", "no_cost", "total_cost", "fees", "gas_estimate", "net_profit")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure costs are non-negative."""
        if v < 0:
            raise ValueError("Costs cannot be negative")
        return v


class MarketPair(BaseModel):
    """A YES/NO market pair."""

    condition_id: str = Field(..., description="Condition ID from Polymarket")
    yes_token_id: str = Field(..., description="YES token ID")
    no_token_id: str = Field(..., description="NO token ID")
    question: str = Field(..., description="Market question")
    end_time: Optional[int] = Field(None, description="Unix timestamp when market ends")
    tick_size: Optional[Decimal] = Field(None, description="Minimum price increment")

    def is_mutually_exclusive(self, other: "MarketPair") -> bool:
        """Check if two markets are mutually exclusive."""
        # This will be implemented by LLM analysis
        return False


class Outcome(BaseModel):
    """An outcome in a multi-outcome market."""

    name: str = Field(..., description="Outcome name (e.g., 'Trump', 'Biden')")
    token_id: str = Field(..., description="Token ID for this outcome")
    is_yes: bool = Field(..., description="Whether this is a YES token")


class MarketMetadata(BaseModel):
    """Metadata for a market (binary or multi-outcome)."""

    market_id: str = Field(..., description="Market identifier")
    title: str = Field(..., description="Market title")
    question: str = Field(..., description="Market question")
    outcomes: List[Outcome] = Field(..., description="List of possible outcomes")
    outcome_token_ids: List[str] = Field(..., description="Token IDs for all outcomes")
    is_binary: bool = Field(..., description="Whether this is a binary (2-outcome) market")
    end_date: Optional[datetime] = Field(None, description="When the market ends")
    last_fetched: int = Field(
        default_factory=lambda: int(datetime.now().timestamp() * 1000),
        description="Timestamp when this metadata was fetched (ms)",
    )

    @field_validator("outcome_token_ids")
    @classmethod
    def validate_token_ids_match_outcomes(cls, v: List[str], info) -> List[str]:
        """Ensure token IDs match outcomes."""
        if "outcomes" in info.data and len(v) != len(info.data["outcomes"]):
            raise ValueError("Number of token IDs must match number of outcomes")
        return v


class VWAPResult(BaseModel):
    """Result of VWAP calculation for a single token."""

    token_id: str = Field(..., description="Token identifier")
    vwap_price: Decimal = Field(..., description="Volume-weighted average price")
    vwap_cost: Decimal = Field(..., description="Total USDC cost to fill trade size")
    shares: Decimal = Field(..., description="Number of shares obtained")
    trade_size: Decimal = Field(..., description="Target trade size in USDC")
    filled: bool = Field(..., description="Whether the full trade size was filled")

    @field_validator("vwap_price", "vwap_cost", "shares", "trade_size")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        """Ensure values are non-negative."""
        if v < 0:
            raise ValueError("Value must be non-negative")
        return v


class TokenOpportunity(BaseModel):
    """An opportunity to buy a single outcome token."""

    token_id: str = Field(..., description="Token identifier")
    outcome_name: str = Field(..., description="Outcome name")
    yes_price: Decimal = Field(..., description="Current YES price")
    vwap_cost: Decimal = Field(..., description="VWAP cost to buy target trade size")
    shares: Decimal = Field(..., description="Number of shares to buy")

    @field_validator("yes_price", "vwap_cost", "shares")
    @classmethod
    def validate_positive(cls, v: Decimal) -> Decimal:
        """Ensure values are positive."""
        if v <= 0:
            raise ValueError("Price, cost, and shares must be positive")
        return v


class NegRiskSignal(BaseModel):
    """Trading signal for NegRisk (mutually exclusive) strategy."""

    market_id: str = Field(..., description="Market identifier")
    market_title: str = Field(..., description="Market title")
    opportunities: List[TokenOpportunity] = Field(
        ...,
        description="List of token opportunities (one per outcome)",
        min_length=2,
    )
    total_cost: Decimal = Field(..., description="Total USDC to spend on all tokens")
    total_payout: Decimal = Field(..., description="Expected payout (num_tokens * 1.0)")
    estimated_profit: Decimal = Field(..., description="Estimated profit in USDC")
    profit_percentage: Decimal = Field(..., description="Profit as percentage of cost")
    gas_cost: Decimal = Field(..., description="Estimated gas cost in USDC")
    fees: Decimal = Field(..., description="Trading fees in USDC")
    timestamp: datetime = Field(
        default_factory=datetime.now,
        description="When the signal was generated",
    )

    @field_validator("opportunities")
    @classmethod
    def validate_at_least_two_opportunities(cls, v: List[TokenOpportunity]) -> List[TokenOpportunity]:
        """Ensure at least 2 opportunities (multi-outcome market)."""
        if len(v) < 2:
            raise ValueError("NegRisk requires at least 2 outcomes")
        return v

    @field_validator("total_cost", "total_payout", "gas_cost", "fees")
    @classmethod
    def validate_non_negative(cls, v: Decimal) -> Decimal:
        """Ensure values are non-negative."""
        if v < 0:
            raise ValueError("Costs cannot be negative")
        return v

    @field_validator("estimated_profit")
    @classmethod
    def validate_profit_can_be_negative(cls, v: Decimal) -> Decimal:
        """Profit can be negative (no opportunity), but we typically filter these."""
        return v


class SettlementLagSignal(Signal):
    """Signal for settlement lag window strategy.

    This strategy trades during the resolution window when market inefficiencies
    may occur due to uncertainty about the outcome.
    """

    market_id: str = Field(..., description="Market identifier")
    resolution_window_hours: float = Field(
        ...,
        ge=0,
        description="Hours until market resolution",
    )
    dispute_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Dispute risk score (0=none, 1=certain dispute)",
    )
    carry_cost: Decimal = Field(
        ...,
        ge=0,
        description="Capital carry cost in USDC",
    )
    resolution_uncertainty: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Resolution uncertainty score",
    )
    end_date: Optional[datetime] = Field(None, description="Market end date")

    @field_validator("carry_cost")
    @classmethod
    def validate_carry_cost(cls, v: Decimal) -> Decimal:
        """Ensure carry cost is non-negative."""
        if v < 0:
            raise ValueError("Carry cost must be non-negative")
        return v


class MarketMakingSignal(Signal):
    """Signal for market making strategy.

    This strategy provides bid-ask spreads to earn the spread.
    IMPORTANT: Must use post-only orders to avoid taking liquidity.
    """

    bid_price: Decimal = Field(..., description="Bid price to post")
    ask_price: Decimal = Field(..., description="Ask price to post")
    spread_bps: int = Field(..., ge=0, description="Spread in basis points")
    inventory_skew: Decimal = Field(
        ...,
        description="Inventory skew (positive=long biased, negative=short biased)",
    )
    quote_age_seconds: float = Field(
        ...,
        ge=0,
        description="How long this quote has been active",
    )
    max_position_size: Decimal = Field(
        ...,
        gt=0,
        description="Maximum position size for this quote",
    )
    post_only: bool = Field(
        default=True,
        description="Force post-only (never take liquidity)",
    )

    @field_validator("bid_price", "ask_price")
    @classmethod
    def validate_prices(cls, v: Decimal) -> Decimal:
        """Ensure prices are valid."""
        if v < 0 or v > 1:
            raise ValueError("Prices must be between 0 and 1")
        return v

    @field_validator("spread_bps")
    @classmethod
    def validate_spread(cls, v: int, info) -> int:
        """Ensure spread is reasonable."""
        if v > 1000:  # More than 10% spread is suspicious
            raise ValueError("Spread too large")
        return v


class TailRiskSignal(Signal):
    """Signal for tail risk underwriting strategy.

    This strategy insures against extreme events.
    WARNING: This is NOT risk-free. Explicit worst-case loss cap required.
    """

    worst_case_loss: Decimal = Field(
        ...,
        description="Maximum possible loss if tail event occurs",
    )
    correlation_cluster: str = Field(
        ...,
        description="Cluster ID for correlated positions",
    )
    hedge_ratio: Optional[Decimal] = Field(
        None,
        ge=0,
        le=1,
        description="Hedge ratio (0=no hedge, 1=fully hedged)",
    )
    tail_probability: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Estimated probability of tail event",
    )
    max_exposure: Decimal = Field(
        ...,
        gt=0,
        description="Maximum exposure in USDC",
    )

    @field_validator("worst_case_loss")
    @classmethod
    def validate_worst_case_loss(cls, v: Decimal) -> Decimal:
        """Ensure worst case loss is explicitly set (cannot be zero)."""
        if v <= 0:
            raise ValueError("Worst case loss must be positive (risk underwriting)")
        return v

    @field_validator("hedge_ratio")
    @classmethod
    def validate_hedge_ratio(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure hedge ratio is valid if set."""
        if v is not None and (v < 0 or v > 1):
            raise ValueError("Hedge ratio must be between 0 and 1")
        return v

