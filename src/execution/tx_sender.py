"""
Transaction Sender for executing validated trades.

This module provides functionality for:
- Executing trading signals
- Transaction queue management
- Retry logic for failed transactions
- Transaction status tracking
- Slippage protection
- Circuit breaker integration
- Nonce management

All transactions must pass risk management before execution.

Resilience features:
- Exponential backoff with jitter for retries
- Idempotency keys to prevent duplicate transactions
- Circuit breaker for failure isolation
- NonceManager for proper Ethereum nonce handling
"""
import asyncio
from decimal import Decimal
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from src.core.models import Signal
from src.execution.risk_manager import RiskManager
from src.execution.retry_policy import RetryPolicy, IdempotencyKey
from src.execution.nonce_manager import NonceManager
from src.execution.circuit_breaker import CircuitBreaker, CircuitState
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
    attempt: int = 0  # Retry attempt number
    idempotency_key: Optional[str] = None
    nonce: Optional[int] = None


class TxSender:
    """
    Transaction sender for executing validated signals.

    Manages transaction queue, retry logic, status tracking, and resilience.

    Resilience features:
    - NonceManager for proper nonce management with pending tracking
    - RetryPolicy for exponential backoff with jitter
    - CircuitBreaker for automatic failure isolation
    - IdempotencyKey to prevent duplicate transactions
    """

    def __init__(
        self,
        web3_client: Web3Client,
        risk_manager: RiskManager,
        nonce_manager: NonceManager,
        circuit_breaker: Optional[CircuitBreaker] = None,
        retry_policy: Optional[RetryPolicy] = None,
        slippage_tolerance: Decimal = Decimal("0.02"),  # 2%
    ):
        """
        Initialize transaction sender.

        Args:
            web3_client: Web3 client for blockchain interaction
            risk_manager: Risk manager for validation
            nonce_manager: Nonce manager for Ethereum nonce handling
            circuit_breaker: Optional circuit breaker for failure isolation
            retry_policy: Optional retry policy with exponential backoff
            slippage_tolerance: Maximum acceptable slippage (0.02 = 2%)
        """
        self.web3_client = web3_client
        self.risk_manager = risk_manager
        self.nonce_manager = nonce_manager
        self.circuit_breaker = circuit_breaker
        self.retry_policy = retry_policy or RetryPolicy()
        self.slippage_tolerance = slippage_tolerance
        self.transaction_queue: List[Signal] = []

        # Execution statistics
        self._total_executions = 0
        self._successful_executions = 0
        self._failed_executions = 0
        self._retry_count = 0
        self._circuit_breaker_trips = 0

        # Idempotency key manager
        self._idempotency = IdempotencyKey()

    async def execute_signal(self, signal: Signal) -> Optional[TxResult]:
        """
        Execute a trading signal with resilience features.

        Process:
        1. Check circuit breaker state
        2. Check idempotency (prevent duplicate execution)
        3. Validate signal with risk manager
        4. Check balance
        5. Allocate nonce via NonceManager
        6. Estimate gas
        7. Build transaction
        8. Sign transaction
        9. Broadcast transaction (with retries via RetryPolicy)

        Args:
            signal: Trading signal to execute

        Returns:
            TxResult with execution details
        """
        self._total_executions += 1

        # Check circuit breaker
        if self.circuit_breaker and self.circuit_breaker.state != CircuitState.CLOSED:
            logger.warning(
                f"Circuit breaker is {self.circuit_breaker.state.value}, "
                f"rejecting signal: {signal.signal_type}"
            )
            return TxResult(
                signal=signal,
                tx_hash=None,
                success=False,
                error="Circuit breaker open",
            )

        # Generate idempotency key
        idem_key = self._idempotency.generate(signal)

        # Check for duplicate execution
        if self._idempotency.is_seen(idem_key):
            logger.warning(f"Duplicate signal detected: {idem_key}")
            # Return existing result if available
            return TxResult(
                signal=signal,
                tx_hash=None,
                success=False,
                error="Duplicate signal",
                idempotency_key=idem_key,
            )

        self._idempotency.mark_seen(idem_key)

        try:
            # Validate signal
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
                return TxResult(
                    signal=signal,
                    tx_hash=None,
                    success=False,
                    error="Risk manager rejection",
                    idempotency_key=idem_key,
                )

            # Allocate nonce
            nonce = await self.nonce_manager.allocate_nonce()

            # Build transaction with allocated nonce
            transaction = await self._build_transaction(signal, gas_params, nonce)

            # Sign transaction
            signed_tx = await self.web3_client.sign_transaction(transaction)

            # Send transaction with retry policy
            result = await self._send_transaction_with_retry(
                signal, signed_tx, idem_key, nonce
            )

            # Record circuit breaker result
            if self.circuit_breaker:
                if result.success:
                    self.circuit_breaker.record_success()
                else:
                    self.circuit_breaker.record_failure()

            # Update nonce tracking
            if result.success:
                self.nonce_manager.mark_confirmed(nonce)
            else:
                # Mark as failed so nonce can be reused
                self.nonce_manager.mark_failed(nonce)

            # Update statistics
            if result.success:
                self._successful_executions += 1
            else:
                self._failed_executions += 1

            return result

        except Exception as e:
            logger.error(f"Error executing signal: {e}")

            # Record failure with circuit breaker
            if self.circuit_breaker:
                self.circuit_breaker.record_failure()

            self._failed_executions += 1

            return TxResult(
                signal=signal,
                tx_hash=None,
                success=False,
                error=str(e),
                idempotency_key=idem_key,
            )

    async def queue_transaction(self, signal: Signal) -> None:
        """
        Add a signal to the transaction queue.

        Args:
            signal: Trading signal to queue
        """
        self.transaction_queue.append(signal)
        logger.info(f"Signal queued: {signal.signal_type} (queue size: {len(self.transaction_queue)})")

    async def process_queue(self) -> List[TxResult]:
        """
        Process all queued transactions.

        Returns:
            List of TxResult execution results
        """
        results = []

        while self.transaction_queue:
            signal = self.transaction_queue.pop(0)

            try:
                result = await self.execute_signal(signal)
                if result:
                    results.append(result)

            except Exception as e:
                logger.error(f"Error processing queued signal: {e}")
                results.append(TxResult(
                    signal=signal,
                    tx_hash=None,
                    success=False,
                    error=str(e),
                ))

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
        gas_params: Dict[str, int],
        nonce: int,
    ) -> TxParams:
        """
        Build transaction parameters.

        Args:
            signal: Trading signal
            gas_params: EIP-1559 gas parameters
            nonce: Allocated nonce from NonceManager

        Returns:
            Transaction parameters
        """
        from src.core.config import Config

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
        signal: Signal,
        signed_tx: bytes,
        idempotency_key: str,
        nonce: int,
    ) -> TxResult:
        """
        Send transaction with retry policy (exponential backoff + jitter).

        Args:
            signal: Trading signal
            signed_tx: Signed transaction bytes
            idempotency_key: Idempotency key for this transaction
            nonce: Allocated nonce for this transaction

        Returns:
            TxResult with execution details
        """
        last_error = None

        for attempt in range(self.retry_policy.max_attempts):
            try:
                tx_hash = await self.web3_client.send_transaction(signed_tx)

                return TxResult(
                    signal=signal,
                    tx_hash=tx_hash,
                    success=True,
                    status=TxStatus.PENDING,
                    attempt=attempt + 1,
                    idempotency_key=idempotency_key,
                    nonce=nonce,
                )

            except Exception as e:
                last_error = e
                self._retry_count += 1

                logger.warning(
                    f"Transaction attempt {attempt + 1}/{self.retry_policy.max_attempts} "
                    f"failed: {e}"
                )

                # Check if error is retryable
                if not self.retry_policy.is_retryable(e):
                    logger.error(f"Non-retryable error: {e}")
                    break

                # Check if we should retry
                if attempt < self.retry_policy.max_attempts - 1:
                    delay = self.retry_policy.calculate_delay(attempt)
                    logger.info(f"Retrying in {delay:.2f} seconds...")
                    await asyncio.sleep(delay)

        # All retries exhausted
        error_msg = str(last_error) if last_error else "Max retries exceeded"
        logger.error(
            f"Transaction failed after {self.retry_policy.max_attempts} attempts: {error_msg}"
        )

        return TxResult(
            signal=signal,
            tx_hash=None,
            success=False,
            error=error_msg,
            status=TxStatus.FAILED,
            attempt=self.retry_policy.max_attempts,
            idempotency_key=idempotency_key,
            nonce=nonce,
        )

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

    def get_stats(self) -> Dict[str, Any]:
        """
        Get transaction execution statistics.

        Returns:
            Dictionary with execution stats
        """
        success_rate = (
            self._successful_executions / self._total_executions
            if self._total_executions > 0
            else 0.0
        )

        return {
            "total_executions": self._total_executions,
            "successful_executions": self._successful_executions,
            "failed_executions": self._failed_executions,
            "success_rate": success_rate,
            "retry_count": self._retry_count,
            "circuit_breaker_trips": self._circuit_breaker_trips,
            "queue_size": len(self.transaction_queue),
            "circuit_breaker_state": (
                self.circuit_breaker.state.value
                if self.circuit_breaker
                else "not_configured"
            ),
            "circuit_breaker_stats": (
                self.circuit_breaker.get_stats()
                if self.circuit_breaker
                else None
            ),
            "nonce_manager_stats": self.nonce_manager.get_stats(),
            "retry_policy_max_attempts": self.retry_policy.max_attempts,
        }
