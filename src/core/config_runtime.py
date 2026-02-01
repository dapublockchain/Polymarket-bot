"""
Runtime configuration module with hot-reload support.

This module provides:
- YAML-based configuration loading
- File watching for hot-reload
- Configuration validation with ranges
- Change logging and callbacks

Example:
    config = RuntimeConfig.load("config.yaml")
    config.watch(on_change=lambda old, new: print(f"Config changed: {old} -> {new}"))
"""
import asyncio
import logging
from pathlib import Path
from typing import Optional, Callable, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime

import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

from loguru import logger


logger = logger.bind(context="config_runtime")


@dataclass
class TradingLimits:
    """Trading limits configuration."""

    max_position_size: float = 1000.0
    min_profit_threshold: float = 0.01
    max_gas_cost: float = 1.0
    max_slippage: float = 0.01
    max_trades_per_hour: int = 100
    max_daily_loss: float = 100.0


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""

    enabled: bool = True
    consecutive_failures_threshold: int = 5
    failure_rate_threshold: float = 0.5
    gas_cost_threshold: float = 2.0
    open_timeout_seconds: int = 60
    half_open_max_calls: int = 3


@dataclass
class RetryPolicyConfig:
    """Retry policy configuration."""

    max_retries: int = 3
    base_delay_ms: int = 1000
    max_delay_ms: int = 30000
    exponential_backoff: bool = True
    jitter: bool = True


@dataclass
class RuntimeConfig:
    """
    Runtime configuration with validation.

    All numeric values have min/max constraints for validation.
    """

    # Trading limits
    trading: TradingLimits = field(default_factory=TradingLimits)

    # Circuit breaker
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # Retry policy
    retry: RetryPolicyConfig = field(default_factory=RetryPolicyConfig)

    # Sandbox mode
    sandbox_mode: bool = True

    # Dry run
    dry_run: bool = True

    # WebSocket settings
    ws_max_reconnect_attempts: int = 5
    ws_reconnect_delay: float = 2.0
    ws_heartbeat_timeout: int = 30

    # Metadata
    _loaded_at: datetime = None
    _version: str = "1.0"

    @classmethod
    def load(cls, config_path: Path) -> "RuntimeConfig":
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to config.yaml

        Returns:
            RuntimeConfig instance

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            data = yaml.safe_load(f)

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RuntimeConfig":
        """
        Create RuntimeConfig from dictionary.

        Args:
            data: Configuration dictionary

        Returns:
            RuntimeConfig instance
        """
        # Parse nested configs
        trading_data = data.get("trading", {})
        circuit_breaker_data = data.get("circuit_breaker", {})
        retry_data = data.get("retry", {})

        trading = TradingLimits(**trading_data)
        circuit_breaker = CircuitBreakerConfig(**circuit_breaker_data)
        retry = RetryPolicyConfig(**retry_data)

        return cls(
            trading=trading,
            circuit_breaker=circuit_breaker,
            retry=retry,
            sandbox_mode=data.get("sandbox_mode", True),
            dry_run=data.get("dry_run", True),
            ws_max_reconnect_attempts=data.get("ws_max_reconnect_attempts", 5),
            ws_reconnect_delay=data.get("ws_reconnect_delay", 2.0),
            ws_heartbeat_timeout=data.get("ws_heartbeat_timeout", 30),
            _loaded_at=datetime.now(),
            _version=data.get("version", "1.0")
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trading": {
                "max_position_size": self.trading.max_position_size,
                "min_profit_threshold": self.trading.min_profit_threshold,
                "max_gas_cost": self.trading.max_gas_cost,
                "max_slippage": self.trading.max_slippage,
                "max_trades_per_hour": self.trading.max_trades_per_hour,
                "max_daily_loss": self.trading.max_daily_loss,
            },
            "circuit_breaker": {
                "enabled": self.circuit_breaker.enabled,
                "consecutive_failures_threshold": self.circuit_breaker.consecutive_failures_threshold,
                "failure_rate_threshold": self.circuit_breaker.failure_rate_threshold,
                "gas_cost_threshold": self.circuit_breaker.gas_cost_threshold,
                "open_timeout_seconds": self.circuit_breaker.open_timeout_seconds,
                "half_open_max_calls": self.circuit_breaker.half_open_max_calls,
            },
            "retry": {
                "max_retries": self.retry.max_retries,
                "base_delay_ms": self.retry.base_delay_ms,
                "max_delay_ms": self.retry.max_delay_ms,
                "exponential_backoff": self.retry.exponential_backoff,
                "jitter": self.retry.jitter,
            },
            "sandbox_mode": self.sandbox_mode,
            "dry_run": self.dry_run,
            "ws_max_reconnect_attempts": self.ws_max_reconnect_attempts,
            "ws_reconnect_delay": self.ws_reconnect_delay,
            "ws_heartbeat_timeout": self.ws_heartbeat_timeout,
            "version": self._version,
        }

    def validate(self) -> List[str]:
        """
        Validate configuration values.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        # Validate trading limits
        if self.trading.max_position_size <= 0:
            errors.append("trading.max_position_size must be positive")

        if not (0 <= self.trading.min_profit_threshold <= 1):
            errors.append("trading.min_profit_threshold must be between 0 and 1")

        if self.trading.max_gas_cost < 0:
            errors.append("trading.max_gas_cost must be non-negative")

        if not (0 <= self.trading.max_slippage <= 1):
            errors.append("trading.max_slippage must be between 0 and 1")

        if self.trading.max_trades_per_hour <= 0:
            errors.append("trading.max_trades_per_hour must be positive")

        if self.trading.max_daily_loss < 0:
            errors.append("trading.max_daily_loss must be non-negative")

        # Validate circuit breaker
        if self.circuit_breaker.consecutive_failures_threshold <= 0:
            errors.append("circuit_breaker.consecutive_failures_threshold must be positive")

        if not (0 <= self.circuit_breaker.failure_rate_threshold <= 1):
            errors.append("circuit_breaker.failure_rate_threshold must be between 0 and 1")

        if self.circuit_breaker.gas_cost_threshold < 0:
            errors.append("circuit_breaker.gas_cost_threshold must be non-negative")

        if self.circuit_breaker.open_timeout_seconds <= 0:
            errors.append("circuit_breaker.open_timeout_seconds must be positive")

        # Validate retry policy
        if self.retry.max_retries < 0:
            errors.append("retry.max_retries must be non-negative")

        if self.retry.base_delay_ms <= 0:
            errors.append("retry.base_delay_ms must be positive")

        if self.retry.max_delay_ms <= 0:
            errors.append("retry.max_delay_ms must be positive")

        if self.retry.base_delay_ms > self.retry.max_delay_ms:
            errors.append("retry.base_delay_ms must not exceed max_delay_ms")

        # Validate WebSocket settings
        if self.ws_max_reconnect_attempts <= 0:
            errors.append("ws_max_reconnect_attempts must be positive")

        if self.ws_reconnect_delay <= 0:
            errors.append("ws_reconnect_delay must be positive")

        if self.ws_heartbeat_timeout <= 0:
            errors.append("ws_heartbeat_timeout must be positive")

        return errors


class ConfigWatcher:
    """
    File system watcher for configuration changes.

    Monitors config.yaml for changes and reloads on modification.
    """

    def __init__(self, config_path: Path, on_change: Callable[[RuntimeConfig, RuntimeConfig], None]):
        """
        Initialize config watcher.

        Args:
            config_path: Path to config file
            on_change: Callback(old_config, new_config) when config changes
        """
        self.config_path = config_path
        self.on_change = on_change
        self.observer: Optional[Observer] = None
        self._current_config: Optional[RuntimeConfig] = None

    def _load_config(self) -> RuntimeConfig:
        """Load and validate configuration."""
        config = RuntimeConfig.load(self.config_path)
        errors = config.validate()

        if errors:
            logger.error(f"Config validation failed: {errors}")
            raise ValueError(f"Invalid configuration: {errors}")

        return config

    def start(self) -> RuntimeConfig:
        """
        Start watching for configuration changes.

        Returns:
            Initial configuration

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If configuration is invalid
        """
        # Load initial config
        self._current_config = self._load_config()
        logger.info(f"Loaded config from {self.config_path}")

        # Setup file watcher
        class ConfigHandler(FileSystemEventHandler):
            def __init__(self, parent: "ConfigWatcher"):
                self.parent = parent

            def on_modified(self, event):
                if event.src_path != str(self.parent.config_path):
                    return

                try:
                    logger.info(f"Config file modified: {event.src_path}")
                    new_config = self.parent._load_config()

                    # Call callback
                    if self.parent._current_config:
                        self.parent.on_change(self.parent._current_config, new_config)

                    self.parent._current_config = new_config

                    # Log changes
                    logger.info("Configuration reloaded successfully")

                except Exception as e:
                    logger.error(f"Failed to reload config: {e}")

        handler = ConfigHandler(self)
        self.observer = Observer()
        self.observer.schedule(handler, path=str(self.config_path.parent), recursive=False)
        self.observer.start()
        logger.info(f"Watching config file: {self.config_path}")

        return self._current_config

    def stop(self):
        """Stop watching for configuration changes."""
        if self.observer:
            self.observer.stop()
            self.observer.join()
            self.observer = None
            logger.info("Config watcher stopped")

    def get_config(self) -> RuntimeConfig:
        """Get current configuration."""
        if self._current_config is None:
            raise RuntimeError("Config watcher not started. Call start() first.")
        return self._current_config


# Global config instance
_global_config: Optional[RuntimeConfig] = None
_global_watcher: Optional[ConfigWatcher] = None


def initialize_config(
    config_path: Path,
    on_change: Optional[Callable[[RuntimeConfig, RuntimeConfig], None]] = None
) -> RuntimeConfig:
    """
    Initialize global runtime configuration.

    Args:
        config_path: Path to config.yaml
        on_change: Optional callback for config changes

    Returns:
        RuntimeConfig instance
    """
    global _global_config, _global_watcher

    if on_change is None:
        # Default: log changes
        def log_changes(old: RuntimeConfig, new: RuntimeConfig):
            logger.info("Configuration changed:")
            logger.info(f"  max_position_size: {old.trading.max_position_size} -> {new.trading.max_position_size}")
            logger.info(f"  min_profit_threshold: {old.trading.min_profit_threshold} -> {new.trading.min_profit_threshold}")

        on_change = log_changes

    _global_watcher = ConfigWatcher(config_path, on_change)
    _global_config = _global_watcher.start()

    return _global_config


def get_config() -> RuntimeConfig:
    """
    Get global runtime configuration.

    Returns:
        RuntimeConfig instance

    Raises:
        RuntimeError: If config not initialized
    """
    if _global_config is None:
        raise RuntimeError("Config not initialized. Call initialize_config() first.")
    return _global_config


def stop_config_watcher():
    """Stop global config watcher."""
    global _global_watcher
    if _global_watcher:
        _global_watcher.stop()
        _global_watcher = None
