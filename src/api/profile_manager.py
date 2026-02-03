"""
Profile Manager for PolyArb-X

Manages configuration profiles for different trading strategies and risk levels.
"""
import os
import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal
import yaml

from src.core.config import Config


class ProfileManager:
    """Manages configuration profiles."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize ProfileManager.

        Args:
            project_root: Project root directory. Defaults to current directory.
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent

        self.project_root = Path(project_root)
        self.profiles_dir = self.project_root / "config" / "profiles"
        self.custom_profiles_dir = self.profiles_dir / "custom"
        self.audit_log_path = self.project_root / "data" / "audit" / "config_changes.jsonl"

        # Ensure directories exist
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.custom_profiles_dir.mkdir(parents=True, exist_ok=True)
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    def list_profiles(self) -> List[Dict[str, Any]]:
        """List all available profiles.

        Returns:
            List of profile metadata (name, tags, description, updated_at, is_custom)
        """
        profiles = []

        # List built-in profiles
        for yaml_file in self.profiles_dir.glob("*.yaml"):
            if yaml_file.parent == self.custom_profiles_dir:
                continue  # Skip custom profiles for now

            try:
                profile_data = self._load_yaml(yaml_file)
                profiles.append({
                    "name": yaml_file.stem,
                    "tags": profile_data.get("tags", []),
                    "description": profile_data.get("description", ""),
                    "updated_at": profile_data.get("updated_at", ""),
                    "is_custom": False,
                    "risk_warnings": profile_data.get("risk_warnings", [])
                })
            except Exception as e:
                print(f"Warning: Failed to load profile {yaml_file}: {e}")

        # List custom profiles
        for yaml_file in self.custom_profiles_dir.glob("*.yaml"):
            try:
                profile_data = self._load_yaml(yaml_file)
                profiles.append({
                    "name": f"custom/{yaml_file.stem}",
                    "tags": profile_data.get("tags", []),
                    "description": profile_data.get("description", ""),
                    "updated_at": profile_data.get("updated_at", ""),
                    "is_custom": True,
                    "risk_warnings": profile_data.get("risk_warnings", [])
                })
            except Exception as e:
                print(f"Warning: Failed to load custom profile {yaml_file}: {e}")

        return profiles

    def get_profile(self, name: str) -> Dict[str, Any]:
        """Load a profile by name.

        Args:
            name: Profile name (e.g., "conservative", "custom/my_profile")

        Returns:
            Profile configuration as dictionary

        Raises:
            ValueError: If profile not found
        """
        # Handle custom profiles
        if name.startswith("custom/"):
            yaml_path = self.custom_profiles_dir / f"{name.replace('custom/', '')}.yaml"
        else:
            yaml_path = self.profiles_dir / f"{name}.yaml"

        if not yaml_path.exists():
            raise ValueError(f"Profile not found: {name}")

        profile_data = self._load_yaml(yaml_path)
        return profile_data

    def deep_merge(self, base: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Deep merge two dictionaries.

        Args:
            base: Base dictionary
            overrides: Override dictionary (partial)

        Returns:
            Merged dictionary
        """
        result = base.copy()

        for key, value in overrides.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                # Recursively merge nested dictionaries
                result[key] = self.deep_merge(result[key], value)
            else:
                # Override with new value
                result[key] = value

        return result

    def calculate_diff(self, current: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate field-level diff between two configurations.

        Args:
            current: Current configuration
            new: New configuration

        Returns:
            Dictionary with changed fields and their old/new values
        """
        diff = {}

        all_keys = set(current.keys()) | set(new.keys())

        for key in all_keys:
            old_value = current.get(key)
            new_value = new.get(key)

            if old_value != new_value:
                if isinstance(old_value, dict) and isinstance(new_value, dict):
                    # Recursively diff nested dictionaries
                    nested_diff = self.calculate_diff(old_value, new_value)
                    if nested_diff:
                        diff[key] = nested_diff
                else:
                    diff[key] = {
                        "old": old_value,
                        "new": new_value
                    }

        return diff

    def validate_config(self, config: Dict[str, Any]) -> List[str]:
        """Validate configuration values.

        Args:
            config: Configuration to validate

        Returns:
            List of validation errors (empty if valid)
        """
        errors = []

        try:
            # Validate numeric ranges
            if "MIN_PROFIT_THRESHOLD" in config:
                threshold = Decimal(str(config["MIN_PROFIT_THRESHOLD"]))
                if threshold < 0 or threshold > Decimal("1.0"):
                    errors.append("MIN_PROFIT_THRESHOLD must be between 0 and 1.0")

            if "MAX_SLIPPAGE" in config:
                slippage = Decimal(str(config["MAX_SLIPPAGE"]))
                if slippage < 0 or slippage > Decimal("0.5"):
                    errors.append("MAX_SLIPPAGE must be between 0 and 0.5 (50%)")

            if "MAX_POSITION_SIZE" in config:
                position = Decimal(str(config["MAX_POSITION_SIZE"]))
                if position <= 0:
                    errors.append("MAX_POSITION_SIZE must be positive")

            if "TRADE_SIZE" in config:
                trade_size = Decimal(str(config["TRADE_SIZE"]))
                if trade_size <= 0:
                    errors.append("TRADE_SIZE must be positive")

            # Validate boolean
            if "DRY_RUN" in config:
                if not isinstance(config["DRY_RUN"], bool):
                    errors.append("DRY_RUN must be a boolean")

            # Validate market making settings
            if config.get("MARKET_MAKING_ENABLED") and not config.get("MM_POST_ONLY", True):
                errors.append("MM_POST_ONLY must be true when MARKET_MAKING_ENABLED is true")

        except (ValueError, TypeError) as e:
            errors.append(f"Configuration type error: {str(e)}")

        return errors

    def detect_risk_changes(self, current: Dict[str, Any], new: Dict[str, Any]) -> List[str]:
        """Detect risky configuration changes.

        Args:
            current: Current configuration
            new: New configuration

        Returns:
            List of risk warning codes
        """
        warnings = []

        # Check DRY_RUN switch
        if current.get("DRY_RUN", True) and not new.get("DRY_RUN", True):
            warnings.append("SWITCH_TO_LIVE")

        # Check position size increase
        try:
            current_pos = Decimal(str(current.get("MAX_POSITION_SIZE", "1000")))
            new_pos = Decimal(str(new.get("MAX_POSITION_SIZE", "1000")))
            if new_pos > current_pos * Decimal("1.5"):
                warnings.append("INCREASE_POSITION_SIZE")
        except (ValueError, TypeError):
            pass

        # Check slippage relaxation
        try:
            current_slippage = Decimal(str(current.get("MAX_SLIPPAGE", "0.02")))
            new_slippage = Decimal(str(new.get("MAX_SLIPPAGE", "0.02")))
            if new_slippage > current_slippage * Decimal("1.5"):
                warnings.append("RELAX_SLIPPAGE")
        except (ValueError, TypeError):
            pass

        # Check profit threshold decrease
        try:
            current_threshold = Decimal(str(current.get("MIN_PROFIT_THRESHOLD", "0.01")))
            new_threshold = Decimal(str(new.get("MIN_PROFIT_THRESHOLD", "0.01")))
            if new_threshold < current_threshold * Decimal("0.5"):
                warnings.append("LOWER_PROFIT_THRESHOLD")
        except (ValueError, TypeError):
            pass

        # Check if aggressive profile is being applied
        if new.get("tags", []) and "high-risk" in new.get("tags", []):
            warnings.append("HIGH_RISK_PROFILE")

        return warnings

    def apply_profile(self, name: str, applied_by: str = "user") -> Dict[str, Any]:
        """Apply a configuration profile.

        Args:
            name: Profile name
            applied_by: User or system applying the profile

        Returns:
            Dictionary with applied profile, diff, risk_warnings

        Raises:
            ValueError: If profile not found or validation fails
        """
        # Load current config (from Config class)
        current_config = self._get_current_config()

        # Load profile
        profile_data = self.get_profile(name)

        # Extract profile overrides (exclude metadata)
        profile_overrides = {k: v for k, v in profile_data.items()
                           if k not in ["name", "description", "tags", "version", "updated_at", "risk_warnings"]}

        # Deep merge
        new_config = self.deep_merge(current_config, profile_overrides)

        # Calculate diff
        diff = self.calculate_diff(current_config, new_config)

        # Validate
        validation_errors = self.validate_config(new_config)
        if validation_errors:
            raise ValueError(f"Configuration validation failed: {', '.join(validation_errors)}")

        # Detect risks
        risk_warnings = self.detect_risk_changes(current_config, new_config)
        risk_warnings.extend(profile_data.get("risk_warnings", []))

        # Save previous config snapshot
        previous_config_snapshot = current_config.copy()

        # Apply to .env file (Config reads from environment)
        self._apply_config_to_env(new_config)

        # Write audit log
        self._write_audit_log({
            "timestamp": datetime.now().isoformat(),
            "applied_by": applied_by,
            "profile_name": name,
            "diff": diff,
            "previous_config": previous_config_snapshot,
            "risk_warnings": risk_warnings
        })

        return {
            "profile_name": name,
            "applied_at": datetime.now().isoformat(),
            "diff": diff,
            "risk_warnings": risk_warnings,
            "new_config": new_config
        }

    def save_custom_profile(self, name: str, description: str, tags: List[str],
                           config_override: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Save current configuration as a custom profile.

        Args:
            name: Profile name
            description: Profile description
            tags: Profile tags
            config_override: Optional config overrides to apply before saving

        Returns:
            Saved profile metadata
        """
        # Get current config
        current_config = self._get_current_config()

        # Apply overrides if provided
        if config_override:
            config_to_save = self.deep_merge(current_config, config_override)
        else:
            config_to_save = current_config

        # Build profile YAML
        profile_data = {
            "name": name,
            "description": description,
            "tags": tags,
            "version": "1.0.0",
            "updated_at": datetime.now().isoformat()
        }

        # Add config fields (exclude sensitive ones)
        sensitive_fields = ["PRIVATE_KEY", "WALLET_ADDRESS"]
        for key, value in config_to_save.items():
            if key not in sensitive_fields and not key.startswith("_"):
                profile_data[key] = value

        # Write to file
        yaml_path = self.custom_profiles_dir / f"{name}.yaml"
        with open(yaml_path, 'w') as f:
            yaml.dump(profile_data, f, default_flow_style=False)

        return {
            "name": f"custom/{name}",
            "description": description,
            "tags": tags,
            "updated_at": profile_data["updated_at"],
            "is_custom": True
        }

    def rollback(self) -> Dict[str, Any]:
        """Rollback to previous configuration.

        Returns:
            Rolled back configuration metadata

        Raises:
            ValueError: If no previous configuration found
        """
        # Read audit log to find previous config
        previous_configs = []
        if self.audit_log_path.exists():
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        if "previous_config" in record:
                            previous_configs.append(record)
                    except json.JSONDecodeError:
                        continue

        if not previous_configs:
            raise ValueError("No previous configuration found in audit log")

        # Get most recent previous config
        last_record = previous_configs[-1]
        previous_config = last_record["previous_config"]

        # Apply previous config
        self._apply_config_to_env(previous_config)

        # Write rollback audit log
        self._write_audit_log({
            "timestamp": datetime.now().isoformat(),
            "applied_by": "rollback",
            "profile_name": "rollback",
            "diff": {},
            "previous_config": {},
            "rolled_back_from": last_record["profile_name"],
            "rolled_back_at": datetime.now().isoformat()
        })

        return {
            "rolled_back": True,
            "rolled_back_from": last_record["profile_name"],
            "restored_config": previous_config
        }

    def get_audit_history(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get configuration change audit history.

        Args:
            limit: Maximum number of records to return

        Returns:
            List of audit records
        """
        history = []

        if self.audit_log_path.exists():
            with open(self.audit_log_path, 'r') as f:
                for line in f:
                    try:
                        record = json.loads(line)
                        history.append(record)
                    except json.JSONDecodeError:
                        continue

        # Return most recent first
        return history[-limit:][::-1]

    def _load_yaml(self, yaml_path: Path) -> Dict[str, Any]:
        """Load YAML file.

        Args:
            yaml_path: Path to YAML file

        Returns:
            Parsed YAML as dictionary
        """
        with open(yaml_path, 'r') as f:
            return yaml.safe_load(f)

    def _get_current_config(self) -> Dict[str, Any]:
        """Get current configuration from Config class.

        Returns:
            Current configuration as dictionary
        """
        config = {}

        # Get all class attributes
        for attr_name in dir(Config):
            if not attr_name.startswith("_"):
                attr_value = getattr(Config, attr_name)
                if not callable(attr_value):
                    # Convert to JSON-serializable types
                    if isinstance(attr_value, Decimal):
                        config[attr_name] = str(attr_value)
                    elif isinstance(attr_value, (bool, int, float, str, list, dict, type(None))):
                        config[attr_name] = attr_value

        return config

    def _apply_config_to_env(self, config: Dict[str, Any]) -> None:
        """Apply configuration to .env file.

        Args:
            config: Configuration to apply
        """
        env_path = self.project_root / ".env"

        # Read existing .env
        existing_lines = []
        if env_path.exists():
            with open(env_path, 'r') as f:
                existing_lines = f.readlines()

        # Parse existing env vars
        existing_vars = {}
        for line in existing_lines:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                existing_vars[key.strip()] = value.strip()

        # Update with new config
        for key, value in config.items():
            if isinstance(value, (bool, int, float, str, Decimal)):
                if isinstance(value, bool):
                    value = "true" if value else "false"
                elif isinstance(value, Decimal):
                    value = str(value)
                else:
                    value = str(value)
                existing_vars[key] = value

        # Write back to .env
        with open(env_path, 'w') as f:
            for key, value in existing_vars.items():
                f.write(f"{key}={value}\n")

    def _write_audit_log(self, record: Dict[str, Any]) -> None:
        """Write audit log entry.

        Args:
            record: Audit record to write
        """
        with open(self.audit_log_path, 'a') as f:
            f.write(json.dumps(record) + "\n")

    # ========== Mode Detection and Status ==========

    def get_active_profile(self) -> str:
        """Get the currently active profile name.

        Reads the current configuration and matches it against known profiles.

        Returns:
            Profile name (e.g., "live_shadow_atomic_v1") or "custom" if no match
        """
        current_config = self._get_current_config()

        # Get current DRY_RUN and PROFILE_NAME from config
        current_dry_run = current_config.get("DRY_RUN", True)
        current_profile_name = current_config.get("PROFILE_NAME", "")

        # If PROFILE_NAME is set, check if it matches
        if current_profile_name:
            try:
                profile_data = self.get_profile(current_profile_name)
                profile_dry_run = profile_data.get("DRY_RUN", True)

                # Check if DRY_RUN matches
                if profile_dry_run == current_dry_run:
                    return current_profile_name
            except ValueError:
                pass  # Profile not found, continue

        # Try to match by DRY_RUN status and trade size
        for profile_info in self.list_profiles():
            if profile_info["is_custom"]:
                continue

            try:
                profile_data = self.get_profile(profile_info["name"])
                profile_dry_run = profile_data.get("DRY_RUN", True)

                if profile_dry_run == current_dry_run:
                    # Additional check: trade size match
                    current_trade_size = str(current_config.get("TRADE_SIZE", ""))
                    profile_trade_size = str(profile_data.get("TRADE_SIZE", ""))

                    if current_trade_size == profile_trade_size:
                        return profile_info["name"]
            except ValueError:
                continue

        # No exact match found
        return "custom"

    def get_mode_status(self) -> Dict[str, Any]:
        """Get current trading mode and active profile.

        Returns:
            Dictionary with mode, profile, and dry_run status
        """
        current_config = self._get_current_config()
        dry_run = current_config.get("DRY_RUN", True)

        return {
            "mode": "dry_run" if dry_run else "live",
            "dry_run": dry_run,
            "profile": self.get_active_profile(),
            "config": {
                "DRY_RUN": dry_run,
                "TRADE_SIZE": current_config.get("TRADE_SIZE", "10"),
                "MAX_POSITION_SIZE": current_config.get("MAX_POSITION_SIZE", "1000"),
                "MAX_DAILY_LOSS": current_config.get("MAX_DAILY_LOSS", "10"),
                "MAX_SLIPPAGE": current_config.get("MAX_SLIPPAGE", "0.02"),
            }
        }

    def can_switch_to_live(self) -> Tuple[bool, List[str]]:
        """Check if system can safely switch to LIVE mode.

        Performs pre-flight checks before allowing live mode activation.
        Integrates PolymarketConfigValidator for comprehensive validation.

        Returns:
            Tuple of (can_switch: bool, errors: List[str])
        """
        errors = []

        # Use PolymarketConfigValidator for detailed configuration checks
        from src.core.polymarket_config import PolymarketConfigValidator

        config_status = PolymarketConfigValidator.get_configuration_status()

        # Add missing configuration items
        if config_status["missing"]:
            for item in config_status["missing"]:
                errors.append(f"Missing: {item}")

        # Add invalid configuration items
        if config_status["invalid"]:
            for item in config_status["invalid"]:
                errors.append(f"Invalid: {item}")

        # Add warnings (non-blocking but informative)
        if config_status.get("warnings"):
            for warning in config_status["warnings"]:
                errors.append(f"Warning: {warning}")

        # Validate configuration values (trade limits)
        current_config = self._get_current_config()

        # Check trade size is reasonable
        try:
            trade_size = Decimal(str(current_config.get("TRADE_SIZE", "10")))
            if trade_size <= 0:
                errors.append("TRADE_SIZE must be positive")
            elif trade_size > Decimal("100"):
                errors.append("TRADE_SIZE is too large for first live run (recommended: $2-10)")
        except (ValueError, TypeError):
            errors.append("Invalid TRADE_SIZE value")

        # Check position size
        try:
            max_position = Decimal(str(current_config.get("MAX_POSITION_SIZE", "1000")))
            if max_position <= 0:
                errors.append("MAX_POSITION_SIZE must be positive")
            elif max_position > Decimal("100"):
                errors.append("MAX_POSITION_SIZE should be ≤ $100 for Phase 1")
        except (ValueError, TypeError):
            errors.append("Invalid MAX_POSITION_SIZE value")

        # Check daily loss limit
        try:
            max_daily_loss = Decimal(str(current_config.get("MAX_DAILY_LOSS", "10")))
            if max_daily_loss <= 0:
                errors.append("MAX_DAILY_LOSS must be positive")
            elif max_daily_loss > Decimal("10"):
                errors.append("MAX_DAILY_LOSS should be ≤ $10 for Phase 1")
        except (ValueError, TypeError):
            errors.append("Invalid MAX_DAILY_LOSS value")

        return len(errors) == 0, errors

    def switch_profile(self, profile_name: str, applied_by: str = "web_ui",
                       confirm_live: bool = False) -> Dict[str, Any]:
        """Switch to a specific configuration profile.

        Enhanced version of apply_profile() with additional safety checks.

        Args:
            profile_name: Profile name to switch to
            applied_by: Source of the switch request (default: "web_ui")
            confirm_live: User confirmed LIVE mode activation (required for live switches)

        Returns:
            Dictionary with result, warnings, and validation status

        Raises:
            ValueError: If profile not found or validation fails
        """
        # Load profile to check if it's a live mode
        try:
            profile_data = self.get_profile(profile_name)
            is_live_mode = not profile_data.get("DRY_RUN", True)
        except ValueError:
            raise ValueError(f"Profile not found: {profile_name}")

        # Safety check for LIVE mode
        if is_live_mode and not confirm_live:
            # Require explicit confirmation for live mode
            return {
                "success": False,
                "requires_confirmation": True,
                "profile_name": profile_name,
                "error": "LIVE mode requires explicit confirmation",
                "warnings": ["SWITCH_TO_LIVE"],
                "message": "Please confirm you understand the risks of live trading"
            }

        # Pre-flight checks for LIVE mode
        if is_live_mode:
            can_switch, errors = self.can_switch_to_live()
            if not can_switch:
                return {
                    "success": False,
                    "profile_name": profile_name,
                    "error": "Pre-flight checks failed",
                    "validation_errors": errors,
                    "warnings": ["SAFETY_CHECK_FAILED"]
                }

        # Apply the profile
        result = self.apply_profile(profile_name, applied_by=applied_by)

        # Add success flag
        result["success"] = True
        result["is_live_mode"] = is_live_mode

        return result
