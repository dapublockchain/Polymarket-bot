"""
Transaction Sender for executing validated trades.

This module provides functionality for:
- Executing trading signals
- Transaction queue management
- Retry logic for failed transactions
- Transaction status tracking
- Slippage protection

All transactions must pass risk management before execution.
"""
import asyncio
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass

from src.core.models import Signal
from src.execution.risk_manager import RiskManager
from src.connectors.web3_client import Web3Client
from web3.types import TxParams
from loguru import logger


class TxStatus(Enum):
    """Transaction status."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass
class TxResult:
    """Result of a transaction execution."""
    signal: Signal
    tx_hash: Optional[str]
    success: bool
    error: Optional[str] = None
    status: TxStatus = TxStatus.PENDING


class TxSender:
    """
    Transaction sender for executing validated signals.

    Manages transaction queue, retry logic, and status tracking.
    """

    def __init__(
        self,
        web3_client: Web3Client,
        risk_manager: RiskManager,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        slippage_tolerance: Decimal = Decimal("0.02"),  # 2%
    ):
        """
        Initialize transaction sender.

        Args:
            web3_client: Web3 client for blockchain interaction
            risk_manager: Risk manager for validation
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
            slippage_tolerance: Maximum acceptable slippage (0.02 = 2%)
        """
        self.web3_client = web3_client
        self.risk_manager = risk_manager
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.slippage_tolerance = slippage_tolerance
        self.transaction_queue: List[Signal] = []

    async def execute_signal(self, signal: Signal) -> Optional[str]:
        """
        Execute a trading signal.

        Process:
        1. Validate signal with risk manager
        2. Check balance
        3. Estimate gas
        4. Build transaction
        5. Sign transaction
        6. Broadcast transaction (with retries)

        Args:
            signal: Trading signal to execute

        Returns:
            Transaction hash if successful, None otherwise
        """
        try:
            # Step 1: Validate signal
            balance = await self.web3_client.get_balance(self.web3_client.address)

            # Estimate gas cost
            gas_params = await self.web3_client.estimate_eip1559_gas()
            gas_limit = await self.web3_client.estimate_gas(
                transaction={"to": self.web3_client.address, "from": self.web3_client.address}
            )

            gas_cost = self.risk_manager.calculate_gas_cost(
                gas_params["maxFeePerGas"],
                gas_limit
            )

            # Validate with risk manager
            if not self.risk_manager.validate_signal(signal, balance, gas_cost):
                logger.warning(f"Signal rejected by risk manager: {signal.signal_type}")
                return None

            # Step 2: Build transaction
            transaction = await self._build_transaction(signal, gas_params)

            # Step 3: Sign transaction
            signed_tx = await self.web3_client.sign_transaction(transaction)

            # Step 4: Send transaction (with retries)
            tx_hash = await self._send_transaction_with_retry(signed_tx)

            if tx_hash:
                logger.info(f"Transaction executed: {tx_hash} for {signal.signal_type}")
            else:
                logger.error(f"Failed to execute transaction for {signal.signal_type}")

            return tx_hash

        except Exception as e:
            logger.error(f"Error executing signal: {e}")
            return None

    async def queue_transaction(self, signal: Signal) -> None:
        """
        Add a signal to the transaction queue.

        Args:
            signal: Trading signal to queue
        """
        self.transaction_queue.append(signal)
        logger.info(f"Signal queued: {signal.signal_type} (queue size: {len(self.transaction_queue)})")

    async def process_queue(self) -> List[Dict[str, Any]]:
        """
        Process all queued transactions.

        Returns:
            List of execution results
        """
        results = []

        while self.transaction_queue:
            signal = self.transaction_queue.pop(0)

            try:
                tx_hash = await self.execute_signal(signal)

                result = {
                    "signal": signal,
                    "tx_hash": tx_hash,
                    "success": tx_hash is not None,
                    "error": None if tx_hash else "Execution failed",
                }

                results.append(result)

            except Exception as e:
                logger.error(f"Error processing queued signal: {e}")
                results.append({
                    "signal": signal,
                    "tx_hash": None,
                    "success": False,
                    "error": str(e),
                })

        return results

    async def check_transaction_status(self, tx_hash: str) -> TxStatus:
        """
        Check the status of a transaction.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction status
        """
        try:
            receipt = await self.web3_client.get_transaction_receipt(tx_hash)

            if receipt is None:
                return TxStatus.PENDING

            if receipt.get("status") == 1:
                return TxStatus.CONFIRMED
            else:
                return TxStatus.FAILED

        except Exception as e:
            logger.warning(f"Error checking transaction status: {e}")
            # Assume pending on error
            return TxStatus.PENDING

    async def _build_transaction(
        self,
        signal: Signal,
        gas_params: Dict[str, int]
    ) -> TxParams:
        """
        Build transaction parameters.

        Args:
            signal: Trading signal
            gas_params: EIP-1559 gas parameters

        Returns:
            Transaction parameters
        """
        from src.core.config import Config

        # Get nonce
        nonce = await self.web3_client.get_nonce()

        # Build basic transaction
        # Note: This is a simplified version. In production, you would:
        # 1. Build actual CLOB trade transaction
        # 2. Include proper token addresses
        # 3. Include trade amounts with slippage protection
        transaction: TxParams = {
            "to": self.web3_client.address,  # Placeholder - would be CLOB contract
            "from": self.web3_client.address,
            "value": 0,  # No MATIC being sent
            "gas": 100_000,  # Will be estimated properly
            "maxFeePerGas": gas_params["maxFeePerGas"],
            "maxPriorityFeePerGas": gas_params["maxPriorityFeePerGas"],
            "nonce": nonce,
            "chainId": Config.POLYGON_CHAIN_ID,
            # Additional fields for CLOB trade would go here
        }

        return transaction

    async def _send_transaction_with_retry(
        self,
        signed_tx: bytes
    ) -> Optional[str]:
        """
        Send transaction with retry logic.

        Args:
            signed_tx: Signed transaction bytes

        Returns:
            Transaction hash if successful, None after max retries
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                tx_hash = await self.web3_client.send_transaction(signed_tx)
                return tx_hash

            except Exception as e:
                last_error = e
                logger.warning(
                    f"Transaction attempt {attempt + 1}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)

        logger.error(f"Transaction failed after {self.max_retries} attempts: {last_error}")
        return None

    def _calculate_slippage_limit(
        self,
        expected_price: Decimal,
        side: str
    ) -> Decimal:
        """
        Calculate price limit with slippage protection.

        Args:
            expected_price: Expected execution price
            side: "buy" or "sell"

        Returns:
            Price limit with slippage tolerance applied
        """
        if side.lower() == "buy":
            # For buys, we're willing to pay up to slippage more
            return expected_price * (Decimal("1") + self.slippage_tolerance)
        else:
            # For sells, we're willing to accept down to slippage less
            return expected_price * (Decimal("1") - self.slippage_tolerance)
