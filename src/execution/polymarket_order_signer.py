"""
Polymarket CLOB Order Signing Module

Implements EIP-712 signing for Polymarket CLOB orders.

Based on:
- EIP-712: https://eips.ethereum.org/EIPS/eip-712
- Polymarket CLOB Docs: https://docs.polymarket.com
"""
from eth_account import Account
from eth_account.messages import encode_structured_data
from web3 import Web3
from decimal import Decimal
from typing import Dict, Any, Optional
import json
from loguru import logger


class PolymarketOrderSigner:
    """
    Signs orders for Polymarket CLOB using EIP-712 standard.

    The Polymarket CLOB requires EIP-712 typed data signatures with
    specific domain and message structures.
    """

    # EIP-712 Domain for Polymarket CLOB
    DOMAIN = {
        "name": "Polymarket CTF Exchange",
        "version": "1",
        "chainId": 137,  # Polygon
        "verifyingContract": "0x4bFb41dcdDBA6F0a3232F775EeaC3FD7dFa6477d"
    }

    # EIP-712 Order schema
    ORDER_TYPES = {
        "Order": [
            {"name": "maker", "type": "address"},
            {"name": "taker", "type": "address"},
            {"name": "tokenId", "type": "uint256"},
            {"name": "makerAmount", "type": "uint256"},
            {"name": "takerAmount", "type": "uint256"},
            {"name": "expiration", "type": "uint256"},
            {"name": "salt", "type": "uint256"},
        ]
    }

    def __init__(self, private_key: str):
        """
        Initialize order signer.

        Args:
            private_key: Private key for signing (from environment)
        """
        self.account = Account.from_key(private_key)
        self.address = self.account.address

    def create_order(
        self,
        token_id: str,
        side: str,  # "BUY" or "SELL"
        amount: Decimal,
        price: Decimal,
        expiration: int,
        salt: int
    ) -> Dict[str, Any]:
        """
        Create an order structure for signing.

        Args:
            token_id: Token ID to trade (Condition ID with outcome)
            side: Order side ("BUY" or "SELL")
            amount: Amount of tokens (in USDC for buy, tokens for sell)
            price: Price per token (in USDC)
            expiration: Unix timestamp when order expires
            salt: Random number for order uniqueness

        Returns:
            Order dictionary ready for signing
        """
        # Convert amounts to uint256 (smallest unit)
        # Polymarket uses 6 decimals for USDC, 18 decimals for tokens
        if side.upper() == "BUY":
            # Buying: makerAmount = USDC, takerAmount = tokens
            maker_amount = int(amount * Decimal("1e6"))  # USDC has 6 decimals
            taker_amount = int((amount / price) * Decimal("1e18"))  # Tokens have 18 decimals
        else:  # SELL
            # Selling: makerAmount = tokens, takerAmount = USDC
            maker_amount = int(amount * Decimal("1e18"))  # Tokens
            taker_amount = int((amount * price) * Decimal("1e6"))  # USDC

        order = {
            "maker": self.address,
            "taker": "0x0000000000000000000000000000000000000000",  # Any taker
            "tokenId": token_id,
            "makerAmount": maker_amount,
            "takerAmount": taker_amount,
            "expiration": expiration,
            "salt": salt
        }

        logger.debug(f"Created order: {order}")
        return order

    def sign_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sign an order using EIP-712.

        Args:
            order: Order dictionary from create_order()

        Returns:
            Signed order with signature
        """
        # Create EIP-712 structured data
        message = {
            "maker": Web3.to_checksum_address(order["maker"]),
            "taker": Web3.to_checksum_address(order["taker"]),
            "tokenId": str(int(order["tokenId"])),
            "makerAmount": str(order["makerAmount"]),
            "takerAmount": str(order["takerAmount"]),
            "expiration": str(order["expiration"]),
            "salt": str(order["salt"])
        }

        # Encode structured data
        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
                **self.ORDER_TYPES
            },
            "domain": self.DOMAIN,
            "primaryType": "Order",
            "message": message
        }

        # Sign
        signable_message = encode_structured_data(structured_data)
        signed_message = self.account.sign_message(signable_message)

        # Combine signature components (v, r, s)
        signature = self._encode_signature(signed_message)

        signed_order = order.copy()
        signed_order["signature"] = signature

        logger.info(f"✅ Signed order for token {order['tokenId'][:20]}...")
        logger.debug(f"Signature: {signature}")

        return signed_order

    def _encode_signature(self, signed_message) -> str:
        """
        Encode signature in the format expected by Polymarket.

        Format: r + s + v (each 32 bytes)

        Args:
            signed_message: Signed message from eth_account

        Returns:
            Hex-encoded signature string
        """
        r = signed_message.r.to_bytes(32, byteorder='big')
        s = signed_message.s.to_bytes(32, byteorder='big')
        v = signed_message.v.to_bytes(1, byteorder='big')

        # Combine: r (32) + s (32) + v (1) = 65 bytes
        signature_bytes = r + s + v
        return "0x" + signature_bytes.hex()

    def get_order_hash(self, order: Dict[str, Any]) -> str:
        """
        Get the EIP-712 hash of an order (for verification).

        Args:
            order: Order dictionary

        Returns:
            Order hash as hex string
        """
        message = {
            "maker": Web3.to_checksum_address(order["maker"]),
            "taker": Web3.to_checksum_address(order["taker"]),
            "tokenId": str(int(order["tokenId"])),
            "makerAmount": str(order["makerAmount"]),
            "takerAmount": str(order["takerAmount"]),
            "expiration": str(order["expiration"]),
            "salt": str(order["salt"])
        }

        structured_data = {
            "types": {
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"}
                ],
                **self.ORDER_TYPES
            },
            "domain": self.DOMAIN,
            "primaryType": "Order",
            "message": message
        }

        signable_message = encode_structured_data(structured_data)
        return Web3.keccak(signable_message).hex()


# Helper functions

def create_order_expiration(hours: float = 1.0) -> int:
    """
    Create order expiration timestamp.

    Args:
        hours: Hours from now (default: 1 hour)

    Returns:
        Unix timestamp
    """
    import time
    return int(time.time() + (hours * 3600))


def generate_order_salt() -> int:
    """
    Generate a random salt for order uniqueness.

    Returns:
        Random 256-bit integer
    """
    import random
    return random.randint(0, 2**256 - 1)
