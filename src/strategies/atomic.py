"""
Atomic Arbitrage Strategy.

Detects opportunities where buying YES and NO tokens costs less than 1.0 USDC,
guaranteeing a profit when the market resolves.
"""
from decimal import Decimal
from typing import Optional

from src.core.models import OrderBook, Ask, ArbitrageOpportunity


class AtomicArbitrageStrategy:
    """
    Atomic arbitrage strategy for YES/NO token pairs.

    Strategy: Buy YES + NO tokens when total cost < 1.0 - fees - gas
    This guarantees a profit of (1.0 - total_cost) when the market resolves.
    """

    def __init__(
        self,
        trade_size: Decimal,
        fee_rate: Decimal,
        min_profit_threshold: Decimal,
        gas_estimate: Decimal = Decimal("0.0"),
    ):
        """
        Initialize the atomic arbitrage strategy.

        Args:
            trade_size: USDC amount to trade (e.g., $10)
            fee_rate: Trading fee rate (e.g., 0.0035 for 0.35%)
            min_profit_threshold: Minimum profit to trigger a trade (e.g., 0.01 for 1%)
            gas_estimate: Estimated gas cost in USDC (default 0 for dry-run)
        """
        self.trade_size = trade_size
        self.fee_rate = fee_rate
        self.min_profit_threshold = min_profit_threshold
        self.gas_estimate = gas_estimate

    def _calculate_vwap(self, orders: list[Ask], trade_size: Decimal) -> Decimal:
        """
        Calculate Volume-Weighted Average Price (VWAP) for a given trade size.

        Walks through the order book depth to calculate the average price
        needed to fill the specified trade size.

        Args:
            orders: List of ask orders sorted by price (lowest first)
            trade_size: Target trade size in USDC

        Returns:
            VWAP as a Decimal price

        Raises:
            ValueError: If insufficient liquidity to fill the trade
        """
        if not orders:
            raise ValueError("Insufficient liquidity: empty order book")

        remaining_usdc = trade_size
        total_cost = Decimal("0")
        total_tokens = Decimal("0")

        for order in orders:
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

        if remaining_usdc > 0:
            raise ValueError(f"Insufficient liquidity: need ${trade_size}, only have ${trade_size - remaining_usdc}")

        # VWAP = total cost / total tokens
        return total_cost / total_tokens

    def check_opportunity(
        self,
        yes_orderbook: OrderBook,
        no_orderbook: OrderBook,
    ) -> Optional[ArbitrageOpportunity]:
        """
        Check if an arbitrage opportunity exists for a YES/NO pair.

        Args:
            yes_orderbook: Order book for YES token
            no_orderbook: Order book for NO token

        Returns:
            ArbitrageOpportunity if profitable, None otherwise
        """
        # Check if both order books have asks
        if not yes_orderbook.asks or not no_orderbook.asks:
            return None

        try:
            # Calculate VWAP for buying both tokens
            yes_vwap = self._calculate_vwap(yes_orderbook.asks, self.trade_size)
            no_vwap = self._calculate_vwap(no_orderbook.asks, self.trade_size)
        except ValueError:
            # Insufficient liquidity
            return None

        # Calculate cost per unit (for 1 token pair)
        # yes_vwap and no_vwap are already prices per token
        cost_per_unit = yes_vwap + no_vwap

        # Calculate total cost for the full trade size
        yes_cost = yes_vwap * self.trade_size
        no_cost = no_vwap * self.trade_size
        total_cost = yes_cost + no_cost

        # Calculate fees (applied to total cost)
        fees = total_cost * self.fee_rate

        # Check if arbitrage is profitable
        # We make $1.0 for every token pair (YES + NO = 1.0)
        # Profit per unit = 1.0 - cost_per_unit
        profit_per_unit = Decimal("1.0") - cost_per_unit
        net_profit_per_unit = profit_per_unit - (fees / self.trade_size) - (self.gas_estimate / self.trade_size)

        # Check if profit exceeds minimum threshold
        if net_profit_per_unit <= 0:
            return None

        # Calculate profit percentage
        profit_percentage = net_profit_per_unit / cost_per_unit

        if profit_percentage < self.min_profit_threshold:
            return None

        # Calculate total profit for the trade
        total_net_profit = net_profit_per_unit * self.trade_size

        # Create arbitrage opportunity
        return ArbitrageOpportunity(
            strategy="atomic",
            token_id=f"{yes_orderbook.token_id}_{no_orderbook.token_id}",
            signal_type="ARBITRAGE",
            expected_profit=total_net_profit,
            trade_size=self.trade_size,
            yes_price=yes_vwap,
            no_price=no_vwap,
            confidence=1.0,  # Atomic arbitrage is risk-free
            reason=f"YES + NO cost {cost_per_unit:.4f} < 1.0, profit: ${total_net_profit:.4f}",
            yes_token_id=yes_orderbook.token_id,
            no_token_id=no_orderbook.token_id,
            yes_cost=yes_cost,
            no_cost=no_cost,
            total_cost=total_cost,
            fees=fees,
            gas_estimate=self.gas_estimate,
            net_profit=total_net_profit,
        )
