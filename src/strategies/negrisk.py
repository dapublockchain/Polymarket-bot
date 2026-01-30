"""
NegRisk Strategy - Arbitrage for mutually exclusive markets.

This strategy detects opportunities in multi-outcome markets where only one
outcome can occur (e.g., "Who will win the election?").

Strategy: If Sum(YES prices) < 1.0 - fees - gas, buy all YES positions.
"""
from decimal import Decimal
from typing import Dict, List, Optional
from datetime import datetime

from src.core.models import (
    OrderBook,
    Ask,
    MarketMetadata,
    NegRiskSignal,
    TokenOpportunity,
    VWAPResult,
)


class NegRiskStrategy:
    """
    NegRisk (NegRisk/Mutually Exclusive) arbitrage strategy.

    For markets with 3+ mutually exclusive outcomes where only ONE can occur:
    - Buy YES tokens for ALL outcomes
    - Exactly one outcome will pay $1.00
    - Profit = $1.00 - Sum(YES prices) - fees - gas

    Example: "Who will win the 2024 election?"
    - Outcomes: Trump, Biden, Harris, Other
    - If YES prices sum to $0.98, buy all 4 YES positions
    - Guaranteed profit: $1.00 - $0.98 - fees - gas
    """

    def __init__(
        self,
        fee_rate: Decimal = Decimal("0.0035"),  # 0.35% default
        min_profit_threshold: Decimal = Decimal("0.005"),  # 0.5% default
        trade_size: Decimal = Decimal("10.0"),  # $10 USDC per token
        gas_estimate: Decimal = Decimal("0.0"),  # Gas cost in USDC
    ):
        """
        Initialize the NegRisk strategy.

        Args:
            fee_rate: Trading fee rate (e.g., 0.0035 for 0.35%)
            min_profit_threshold: Minimum profit percentage to trigger trade
            trade_size: USDC amount to trade per token (e.g., $10)
            gas_estimate: Estimated gas cost in USDC
        """
        self.fee_rate = fee_rate
        self.min_profit_threshold = min_profit_threshold
        self.trade_size = trade_size
        self.gas_estimate = gas_estimate

    def _calculate_vwap(self, asks: List[Ask], trade_size: Decimal, token_id: str) -> VWAPResult:
        """
        Calculate Volume-Weighted Average Price (VWAP) for a single token.

        Walks through the order book depth to calculate the average price
        needed to fill the specified trade size.

        Args:
            asks: List of ask orders sorted by price (lowest first)
            trade_size: Target trade size in USDC
            token_id: Token identifier

        Returns:
            VWAPResult with calculated price, cost, and shares
        """
        if not asks:
            return VWAPResult(
                token_id=token_id,
                vwap_price=Decimal("0"),
                vwap_cost=Decimal("0"),
                shares=Decimal("0"),
                trade_size=trade_size,
                filled=False,
            )

        remaining_usdc = trade_size
        total_cost = Decimal("0")
        total_tokens = Decimal("0")

        for order in asks:
            if remaining_usdc <= 0:
                break

            # Calculate USDC value available at this price level
            level_value = order.size * order.price

            if level_value >= remaining_usdc:
                # This order can fill the remaining size
                tokens_needed = remaining_usdc / order.price
                total_cost += remaining_usdc
                total_tokens += tokens_needed
                remaining_usdc = Decimal("0")
                break
            else:
                # Take entire order and move to next level
                total_cost += level_value
                total_tokens += order.size
                remaining_usdc -= level_value

        filled = remaining_usdc == 0

        if not filled:
            # Return partial fill result
            return VWAPResult(
                token_id=token_id,
                vwap_price=total_cost / total_tokens if total_tokens > 0 else Decimal("0"),
                vwap_cost=total_cost,
                shares=total_tokens,
                trade_size=trade_size,
                filled=False,
            )

        # VWAP = total cost / total tokens
        vwap_price = total_cost / total_tokens

        return VWAPResult(
            token_id=token_id,
            vwap_price=vwap_price,
            vwap_cost=total_cost,
            shares=total_tokens,
            trade_size=trade_size,
            filled=True,
        )

    def calculate_total_cost(
        self,
        order_books: Dict[str, OrderBook],
        trade_size: Decimal,
    ) -> Dict[str, VWAPResult]:
        """
        Calculate VWAP for all tokens in the market.

        Args:
            order_books: Dictionary mapping token_id to OrderBook
            trade_size: Trade size in USDC for each token

        Returns:
            Dictionary mapping token_id to VWAPResult
        """
        results: Dict[str, VWAPResult] = {}

        for token_id, order_book in order_books.items():
            vwap_result = self._calculate_vwap(order_book.asks, trade_size, token_id)
            results[token_id] = vwap_result

        return results

    def calculate_profit(
        self,
        total_cost: Decimal,
        num_tokens: int,
    ) -> Decimal:
        """
        Calculate expected profit from NegRisk arbitrage.

        Args:
            total_cost: Total USDC cost to buy all tokens
            num_tokens: Number of tokens in the market

        Returns:
            Expected profit in USDC
        """
        # Payout = num_tokens * $1.00 (one winner pays $1 for each token)
        total_payout = Decimal(str(num_tokens))

        # Calculate fees
        fees = total_cost * self.fee_rate

        # Profit = payout - cost - fees - gas
        profit = total_payout - total_cost - fees - self.gas_estimate

        return profit

    def check_threshold(self, profit: Decimal, total_investment: Decimal) -> bool:
        """
        Check if profit meets minimum threshold.

        Args:
            profit: Expected profit in USDC
            total_investment: Total investment in USDC

        Returns:
            True if profit meets threshold, False otherwise
        """
        if profit <= 0:
            return False

        profit_percentage = profit / total_investment
        return profit_percentage >= self.min_profit_threshold

    def check_opportunity(
        self,
        market_metadata: MarketMetadata,
        order_books: Dict[str, OrderBook],
    ) -> Optional[NegRiskSignal]:
        """
        Check if a NegRisk arbitrage opportunity exists.

        Args:
            market_metadata: Market metadata including outcomes
            order_books: Dictionary mapping token_id to OrderBook

        Returns:
            NegRiskSignal if profitable opportunity exists, None otherwise
        """
        # Skip binary markets (use atomic strategy instead)
        if market_metadata.is_binary:
            return None

        # Check that we have order books for all tokens
        token_ids = market_metadata.outcome_token_ids
        if not all(token_id in order_books for token_id in token_ids):
            return None

        # Calculate VWAP for each token
        # We want to buy equal shares of each token (e.g., 1 share each)
        # So we calculate cost to buy 1 share of each
        shares_per_token = Decimal("1.0")

        total_cost = Decimal("0")
        opportunities: List[TokenOpportunity] = []

        for outcome in market_metadata.outcomes:
            order_book = order_books[outcome.token_id]

            if not order_book.asks:
                return None

            best_ask = order_book.get_best_ask()
            if not best_ask:
                return None

            # Cost to buy 1 share at best ask
            cost = best_ask.price * shares_per_token
            total_cost += cost

            opportunities.append(
                TokenOpportunity(
                    token_id=outcome.token_id,
                    outcome_name=outcome.name,
                    yes_price=best_ask.price,
                    vwap_cost=cost,
                    shares=shares_per_token,
                )
            )

        # Calculate profit
        # Payout = $1.00 (since we buy 1 share of each token, and exactly one will win)
        total_payout = Decimal("1.0")

        # Fees
        fees = total_cost * self.fee_rate

        # Profit = payout - cost - fees - gas
        profit = total_payout - total_cost - fees - self.gas_estimate

        # Check if profit meets threshold
        if not self.check_threshold(profit, total_cost):
            return None

        # Calculate profit percentage
        profit_percentage = profit / total_cost

        # Create signal
        signal = NegRiskSignal(
            market_id=market_metadata.market_id,
            market_title=market_metadata.title,
            opportunities=opportunities,
            total_cost=total_cost,
            total_payout=total_payout,
            estimated_profit=profit,
            profit_percentage=profit_percentage,
            gas_cost=self.gas_estimate,
            fees=fees,
            timestamp=datetime.now(),
        )

        return signal
