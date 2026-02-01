"""
Nonce manager for Ethereum transaction ordering.

Prevents nonce conflicts and ensures monotonic nonce usage.
"""
import asyncio
from typing import Optional, Dict, Set
from dataclasses import dataclass
from datetime import datetime

from loguru import logger

from src.connectors.web3_client import Web3Client


logger = logger.bind(context="nonce_manager")


@dataclass
class NonceStatus:
    """Status of a nonce."""

    nonce: int
    in_use: bool = False
    confirmed: bool = False
    created_at: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()


class NonceManager:
    """
    Manages Ethereum transaction nonces.

    Features:
    - Tracks pending nonces
    - Recovers on-chain nonce on startup
    - Prevents nonce reuse
    - Thread-safe nonce allocation
    """

    def __init__(self, web3_client: Web3Client, address: str):
        """
        Initialize nonce manager.

        Args:
            web3_client: Web3 client instance
            address: Wallet address
        """
        self.web3_client = web3_client
        self.address = address

        # Nonce tracking
        self._next_nonce: Optional[int] = None
        self._pending_nonces: Dict[int, NonceStatus] = {}
        self._confirmed_nonces: Set[int] = set()

        # Lock for thread safety
        self._lock = asyncio.Lock()

    async def initialize(self) -> int:
        """
        Initialize nonce manager by fetching on-chain nonce.

        Returns:
            Current on-chain nonce

        Raises:
            Exception: If failed to fetch nonce
        """
        try:
            # Get on-chain nonce
            on_chain_nonce = await self.web3_client.get_nonce(self.address)

            async with self._lock:
                self._next_nonce = on_chain_nonce
                logger.info(f"Nonce manager initialized: next_nonce={on_chain_nonce}")

            return on_chain_nonce

        except Exception as e:
            logger.error(f"Failed to initialize nonce manager: {e}")
            raise

    async def get_nonce(self) -> int:
        """
        Get next available nonce.

        Returns:
            Nonce value

        Raises:
            RuntimeError: If nonce manager not initialized
        """
        async with self._lock:
            if self._next_nonce is None:
                raise RuntimeError("Nonce manager not initialized. Call initialize() first.")

            nonce = self._next_nonce
            self._next_nonce += 1

            # Track as pending
            self._pending_nonces[nonce] = NonceStatus(nonce=nonce, in_use=True)

            logger.debug(f"Allocated nonce: {nonce}")
            return nonce

    async def allocate_nonce(self) -> int:
        """
        Allocate next available nonce (alias for get_nonce).

        Returns:
            Nonce value

        Raises:
            RuntimeError: If nonce manager not initialized
        """
        return await self.get_nonce()

    async def mark_confirmed(self, nonce: int):
        """
        Mark nonce as confirmed.

        Args:
            nonce: Confirmed nonce value
        """
        async with self._lock:
            if nonce in self._pending_nonces:
                del self._pending_nonces[nonce]

            self._confirmed_nonces.add(nonce)
            logger.debug(f"Nonce confirmed: {nonce}")

    async def mark_failed(self, nonce: int):
        """
        Mark nonce as failed (can be reused).

        Args:
            nonce: Failed nonce value
        """
        async with self._lock:
            if nonce in self._pending_nonces:
                del self._pending_nonces[nonce]

            # Add back to pool (use this nonce first)
            if self._next_nonce is None or nonce < self._next_nonce:
                self._next_nonce = nonce

            logger.debug(f"Nonce failed and available for reuse: {nonce}")

    def is_pending(self, nonce: int) -> bool:
        """
        Check if nonce is pending.

        Args:
            nonce: Nonce value to check

        Returns:
            True if nonce is pending
        """
        return nonce in self._pending_nonces

    def get_pending_count(self) -> int:
        """Get number of pending nonces."""
        return len(self._pending_nonces)

    def get_stats(self) -> dict:
        """
        Get nonce manager statistics.

        Returns:
            Dictionary with stats
        """
        return {
            "next_nonce": self._next_nonce,
            "pending_count": len(self._pending_nonces),
            "confirmed_count": len(self._confirmed_nonces),
            "pending_nonces": list(self._pending_nonces.keys()),
        }
