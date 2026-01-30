"""
Web3 client for interacting with Polygon blockchain.

This module provides functionality for:
- Connecting to Polygon RPC
- Transaction signing and broadcasting
- Balance checking (USDC)
- Gas estimation (EIP-1559)
- Nonce management

Security: Private keys are loaded from environment variables only.
"""
from decimal import Decimal
from typing import Optional, Dict, Any
from web3 import Web3
from web3.types import TxParams, TxReceipt
from eth_account import Account
from eth_account.signers.local import LocalAccount
import asyncio
from loguru import logger


class Web3Client:
    """
    Web3 client for Polygon blockchain interactions.

    This class handles all blockchain interactions including transaction
    signing, broadcasting, and balance checking.
    """

    # USDC contract address on Polygon
    USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
    USDC_ABI = [
        {
            "constant": True,
            "inputs": [{"name": "_owner", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "balance", "type": "uint256"}],
            "type": "function",
        }
    ]

    def __init__(self, rpc_url: str, private_key: str):
        """
        Initialize Web3 client.

        Args:
            rpc_url: Polygon RPC endpoint URL
            private_key: Private key for signing transactions (from environment)

        Raises:
            ValueError: If private_key is None or invalid
        """
        if not private_key:
            raise ValueError("Private key is required")

        try:
            # Validate and create account from private key
            self.account: LocalAccount = Account.from_key(private_key)
            self.address = self.account.address
        except Exception as e:
            raise ValueError(f"Invalid private key: {e}")

        self.rpc_url = rpc_url
        self.w3 = Web3(Web3.HTTPProvider(rpc_url))

        if not self.w3.is_connected():
            logger.warning(f"Failed to connect to RPC at {rpc_url}")

    async def get_balance(self, address: str) -> Decimal:
        """
        Get USDC balance for an address.

        Args:
            address: Ethereum address to check balance for

        Returns:
            USDC balance as Decimal (6 decimals)

        Raises:
            ValueError: If address is invalid
            Exception: If contract call fails
        """
        if not Web3.is_address(address):
            raise ValueError(f"Invalid address format: {address}")

        contract = self._get_usdc_contract()

        # Get balance in loop (contract calls are synchronous)
        loop = asyncio.get_event_loop()
        balance_wei = await loop.run_in_executor(
            None,
            contract.functions.balanceOf(address).call
        )

        # USDC has 6 decimals
        balance = Decimal(balance_wei) / Decimal("1000000")
        return balance

    def _get_usdc_contract(self):
        """
        Get USDC contract instance.

        Returns:
            Web3 contract instance for USDC
        """
        return self.w3.eth.contract(
            address=Web3.to_checksum_address(self.USDC_ADDRESS),
            abi=self.USDC_ABI
        )

    async def estimate_gas(
        self,
        transaction: TxParams,
        multiplier: float = 1.0
    ) -> int:
        """
        Estimate gas for a transaction.

        Args:
            transaction: Transaction parameters
            multiplier: Gas limit multiplier (default 1.0)

        Returns:
            Estimated gas limit

        Raises:
            Exception: If gas estimation fails
        """
        loop = asyncio.get_event_loop()
        gas_limit = await loop.run_in_executor(
            None,
            self.w3.eth.estimate_gas,
            transaction
        )

        # Apply multiplier for safety
        adjusted_gas_limit = int(gas_limit * multiplier)
        return adjusted_gas_limit

    async def estimate_eip1559_gas(
        self,
        priority_fee: int = 2_000_000_000,  # 2 gwei in wei
        max_gas_price: Optional[int] = None
    ) -> Dict[str, int]:
        """
        Estimate EIP-1559 gas parameters.

        Args:
            priority_fee: Priority fee in wei (default 2 gwei)
            max_gas_price: Maximum gas price cap in wei

        Returns:
            Dictionary with maxFeePerGas and maxPriorityFeePerGas

        Raises:
            Exception: If gas estimation fails
        """
        from src.core.config import Config

        if max_gas_price is None:
            max_gas_price = Config.MAX_GAS_PRICE

        # Get latest block to get base fee
        loop = asyncio.get_event_loop()
        latest_block = await loop.run_in_executor(
            None,
            self.w3.eth.get_block,
            "latest"
        )

        base_fee = latest_block.get("baseFeePerGas", 30_000_000)  # 30 gwei default

        # EIP-1559: maxFeePerGas = baseFee + maxPriorityFeePerGas
        max_priority_fee = priority_fee
        max_fee = base_fee + max_priority_fee

        # Cap at maximum
        if max_fee > max_gas_price:
            max_fee = max_gas_price
            max_priority_fee = max(0, max_gas_price - base_fee)

        return {
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": max_priority_fee,
        }

    async def sign_transaction(self, transaction: TxParams) -> bytes:
        """
        Sign a transaction with the client's private key.

        Args:
            transaction: Transaction parameters

        Returns:
            Signed transaction as bytes

        Raises:
            Exception: If signing fails
        """
        # Build transaction if needed
        if "nonce" not in transaction:
            transaction["nonce"] = await self.get_nonce()

        if "chainId" not in transaction:
            from src.core.config import Config
            transaction["chainId"] = Config.POLYGON_CHAIN_ID

        # Sign transaction
        signed_tx = self.account.sign_transaction(transaction)

        logger.debug(f"Signed transaction: {signed_tx.hash.hex()}")

        return signed_tx.rawTransaction

    async def send_transaction(self, signed_tx: bytes) -> str:
        """
        Broadcast a signed transaction to the network.

        Args:
            signed_tx: Signed transaction bytes

        Returns:
            Transaction hash

        Raises:
            Exception: If broadcast fails
        """
        loop = asyncio.get_event_loop()
        tx_hash = await loop.run_in_executor(
            None,
            self.w3.eth.send_raw_transaction,
            signed_tx
        )

        # tx_hash is already a HexStr, convert to string
        return str(tx_hash)

    async def get_transaction_receipt(self, tx_hash: str) -> Optional[TxReceipt]:
        """
        Get transaction receipt.

        Args:
            tx_hash: Transaction hash

        Returns:
            Transaction receipt or None if pending
        """
        loop = asyncio.get_event_loop()
        try:
            receipt = await loop.run_in_executor(
                None,
                self.w3.eth.get_transaction_receipt,
                tx_hash
            )
            return receipt
        except Exception:
            # Transaction might not be mined yet
            return None

    async def get_nonce(self, block: str = "pending") -> int:
        """
        Get transaction nonce for the account.

        Args:
            block: Block parameter ("pending" or "latest")

        Returns:
            Current nonce
        """
        loop = asyncio.get_event_loop()
        nonce = await loop.run_in_executor(
            None,
            self.w3.eth.get_transaction_count,
            self.address,
            block
        )
        return nonce

    async def wait_for_transaction_receipt(
        self,
        tx_hash: str,
        timeout: float = 120.0,
        poll_latency: float = 1.0
    ) -> Optional[TxReceipt]:
        """
        Wait for transaction to be mined.

        Args:
            tx_hash: Transaction hash
            timeout: Timeout in seconds
            poll_latency: Poll interval in seconds

        Returns:
            Transaction receipt or None if timeout
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            receipt = await self.get_transaction_receipt(tx_hash)

            if receipt is not None:
                return receipt

            if asyncio.get_event_loop().time() - start_time > timeout:
                logger.warning(f"Timeout waiting for transaction {tx_hash}")
                return None

            await asyncio.sleep(poll_latency)
