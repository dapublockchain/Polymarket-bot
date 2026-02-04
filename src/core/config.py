"""
Configuration management for PolyArb-X.
"""
import os
import yaml
from decimal import Decimal
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load config.yaml
def _load_config_yaml() -> dict:
    """Load configuration from config.yaml."""
    config_path = Path("config/config.yaml")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}

_yaml_config = _load_config_yaml()


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
    # Priority: 1) Environment variable DRY_RUN, 2) config.yaml DRY_RUN, 3) default false
    _dry_run_env = os.getenv("DRY_RUN")
    if _dry_run_env is not None:
        DRY_RUN: bool = _dry_run_env.lower() == "true"
    else:
        DRY_RUN: bool = _yaml_config.get("DRY_RUN", False)

    # Risk Management Configuration
    MAX_POSITION_SIZE: Decimal = Decimal(os.getenv("MAX_POSITION_SIZE", "1000"))  # $1000
    MAX_GAS_COST: Decimal = Decimal(os.getenv("MAX_GAS_COST", "1.0"))  # $1

    # Execution Configuration
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: float = float(os.getenv("RETRY_DELAY", "1.0"))

    # ========== New Strategy Configuration (v0.4.0) ==========
    # All new strategies are OFF by default and require explicit enablement

    # Settlement Lag Strategy
    SETTLEMENT_LAG_ENABLED: bool = os.getenv("SETTLEMENT_LAG_ENABLED", "false").lower() == "true"
    SETTLEMENT_LAG_MAX_DISPUTE_SCORE: float = float(os.getenv("SETTLEMENT_LAG_MAX_DISPUTE_SCORE", "0.3"))
    SETTLEMENT_LAG_MAX_CARRY_COST_PCT: Decimal = Decimal(os.getenv("SETTLEMENT_LAG_MAX_CARRY_COST_PCT", "0.02"))  # 2%
    SETTLEMENT_LAG_MIN_WINDOW_HOURS: float = float(os.getenv("SETTLEMENT_LAG_MIN_WINDOW_HOURS", "1.0"))

    # Market Making Strategy
    MARKET_MAKING_ENABLED: bool = os.getenv("MARKET_MAKING_ENABLED", "false").lower() == "true"
    MM_POST_ONLY: bool = os.getenv("MM_POST_ONLY", "true").lower() == "true"  # MUST be true
    MM_MAX_SPREAD_BPS: int = int(os.getenv("MM_MAX_SPREAD_BPS", "100"))  # 1% max spread
    MM_QUOTE_AGE_LIMIT_SECONDS: float = float(os.getenv("MM_QUOTE_AGE_LIMIT_SECONDS", "30.0"))
    MM_MAX_POSITION_SIZE: Decimal = Decimal(os.getenv("MM_MAX_POSITION_SIZE", "500"))
    MM_MAX_CANCEL_RATE_PER_MIN: int = int(os.getenv("MM_MAX_CANCEL_RATE_PER_MIN", "10"))

    # Tail Risk Strategy
    TAIL_RISK_ENABLED: bool = os.getenv("TAIL_RISK_ENABLED", "false").lower() == "true"
    TAIL_RISK_MAX_WORST_CASE_LOSS: Decimal = Decimal(os.getenv("TAIL_RISK_MAX_WORST_CASE_LOSS", "100"))
    TAIL_RISK_MAX_CORRELATION_CLUSTER_EXPOSURE: Decimal = Decimal(os.getenv("TAIL_RISK_MAX_CORRELATION_CLUSTER_EXPOSURE", "300"))
    TAIL_RISK_MIN_TAIL_PROBABILITY: float = float(os.getenv("TAIL_RISK_MIN_TAIL_PROBABILITY", "0.05"))

    # Public Info Signals (Optional, OFF by default)
    PUBLIC_INFO_ENABLED: bool = os.getenv("PUBLIC_INFO_ENABLED", "false").lower() == "true"
    PUBLIC_INFO_MAX_LATENCY_SECONDS: float = float(os.getenv("PUBLIC_INFO_MAX_LATENCY_SECONDS", "300.0"))

    # Anomaly Defense
    ANOMALY_DEFENSE_ENABLED: bool = os.getenv("ANOMALY_DEFENSE_ENABLED", "true").lower() == "true"  # Default ON
    ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD: float = float(os.getenv("ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD", "0.10"))  # 10%
    ANOMALY_DEFENSE_CORRELATION_BREAK_THRESHOLD: float = float(os.getenv("ANOMALY_DEFENSE_CORRELATION_BREAK_THRESHOLD", "0.5"))
    ANOMALY_DEFENSE_DEPTH_DEPLETION_THRESHOLD: float = float(os.getenv("ANOMALY_DEFENSE_DEPTH_DEPLETION_THRESHOLD", "0.5"))

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

        # Validate market making post-only requirement
        if cls.MARKET_MAKING_ENABLED and not cls.MM_POST_ONLY:
            raise ValueError("MM_POST_ONLY must be true when MARKET_MAKING_ENABLED is true")

        # Validate spread limit
        if cls.MM_MAX_SPREAD_BPS < 0 or cls.MM_MAX_SPREAD_BPS > 1000:
            raise ValueError("MM_MAX_SPREAD_BPS must be between 0 and 1000")

        # Validate tail risk worst case loss
        if cls.TAIL_RISK_ENABLED and cls.TAIL_RISK_MAX_WORST_CASE_LOSS <= 0:
            raise ValueError("TAIL_RISK_MAX_WORST_CASE_LOSS must be positive when TAIL_RISK_ENABLED is true")

        # Validate settlement lag thresholds
        if cls.SETTLEMENT_LAG_MAX_DISPUTE_SCORE < 0 or cls.SETTLEMENT_LAG_MAX_DISPUTE_SCORE > 1:
            raise ValueError("SETTLEMENT_LAG_MAX_DISPUTE_SCORE must be between 0 and 1")

        # Validate anomaly defense thresholds
        if cls.ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD < 0 or cls.ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD > 1:
            raise ValueError("ANOMALY_DEFENSE_PRICE_PULSE_THRESHOLD must be between 0 and 1")
