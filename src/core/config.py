"""
Configuration management for PolyArb-X.
"""
import os
from decimal import Decimal
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class Config:
    """Configuration settings for PolyArb-X."""

    # Polymarket WebSocket
    POLYMARKET_WS_URL: str = os.getenv(
        "POLYMARKET_WS_URL", "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    )

    # Polygon RPC
    POLYGON_RPC_URL: str = os.getenv("POLYGON_RPC_URL", "https://polygon-rpc.com")
    POLYGON_CHAIN_ID: int = int(os.getenv("POLYGON_CHAIN_ID", "137"))

    # Wallet (for dry-run, can be fake)
    PRIVATE_KEY: Optional[str] = os.getenv("PRIVATE_KEY")
    WALLET_ADDRESS: Optional[str] = os.getenv("WALLET_ADDRESS")

    # Gas Configuration
    GAS_PRICE_MODE: str = os.getenv("GAS_PRICE_MODE", "eip1559")
    MAX_GAS_PRICE: int = int(os.getenv("MAX_GAS_PRICE", "500000000000"))  # 500 gwei
    GAS_LIMIT_MULTIPLIER: float = float(os.getenv("GAS_LIMIT_MULTIPLIER", "1.2"))

    # Strategy Configuration
    MIN_PROFIT_THRESHOLD: Decimal = Decimal(os.getenv("MIN_PROFIT_THRESHOLD", "0.01"))  # 1%
    TRADE_SIZE: Decimal = Decimal(os.getenv("TRADE_SIZE", "10"))  # $10 USDC
    MAX_SLIPPAGE: Decimal = Decimal(os.getenv("MAX_SLIPPAGE", "0.02"))  # 2%

    # Fee rate (Polymarket CLOB fee)
    FEE_RATE: Decimal = Decimal("0.0035")  # 0.35%

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "data/polyarb.log")

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "data/polyarb.db")

    # Trading mode
    DRY_RUN: bool = os.getenv("DRY_RUN", "true").lower() == "true"

    # Risk Management Configuration
    MAX_POSITION_SIZE: Decimal = Decimal(os.getenv("MAX_POSITION_SIZE", "1000"))  # $1000
    MAX_GAS_COST: Decimal = Decimal(os.getenv("MAX_GAS_COST", "1.0"))  # $1

    # Execution Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "1.0"))

    @classmethod
    def validate(cls) -> None:
        """Validate configuration settings."""
        if not cls.DRY_RUN and not cls.PRIVATE_KEY:
            raise ValueError("PRIVATE_KEY required when not in dry-run mode")

        if cls.TRADE_SIZE <= 0:
            raise ValueError("TRADE_SIZE must be positive")

        if cls.MIN_PROFIT_THRESHOLD < 0:
            raise ValueError("MIN_PROFIT_THRESHOLD must be non-negative")

        if cls.MAX_POSITION_SIZE <= 0:
            raise ValueError("MAX_POSITION_SIZE must be positive")
