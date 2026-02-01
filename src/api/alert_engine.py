"""
Alert Engine for PolyArb-X

Monitors system metrics and triggers alerts based on configured rules.
"""
import os
import json
import asyncio
import aiohttp
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import yaml

from src.core.config import Config


class Alert:
    """Alert instance."""

    def __init__(self, alert_id: str, name: str, severity: str, status: str,
                 context: Dict[str, Any], fired_at: str):
        self.alert_id = alert_id
        self.name = name
        self.severity = severity  # CRITICAL, WARNING, INFO
        self.status = status  # FIRING, RESOLVED, ACKED
        self.context = context
        self.fired_at = fired_at
        self.resolved_at: Optional[str] = None
        self.acked_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "name": self.name,
            "severity": self.severity,
            "status": self.status,
            "context": self.context,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
            "acked_at": self.acked_at
        }


class AlertEngine:
    """Alert monitoring engine."""

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize AlertEngine.

        Args:
            project_root: Project root directory
        """
        if project_root is None:
            project_root = Path(__file__).parent.parent.parent

        self.project_root = Path(project_root)
        self.config_path = self.project_root / "config" / "alerts.yaml"
        self.events_path = self.project_root / "data" / "alerts" / "alerts.jsonl"
        self.state_path = self.project_root / "data" / "alerts" / "alerts_state.json"

        # Ensure directories exist
        self.events_path.parent.mkdir(parents=True, exist_ok=True)

        # Load configuration
        self.config = self._load_alerts_config()
        self.rules = self.config.get("rules", [])

        # Alert state
        self.active_alerts: Dict[str, Alert] = {}
        self.alert_history: List[Dict[str, Any]] = []

        # Load previous state
        self._load_state()

        # Metrics cache (for sliding window calculations)
        self.metrics_window: Dict[str, List[tuple]] = {}  # metric_name -> [(timestamp, value), ...]

    def _load_alerts_config(self) -> Dict[str, Any]:
        """Load alerts configuration from YAML file."""
        if not self.config_path.exists():
            print(f"Warning: Alerts config not found at {self.config_path}")
            return {"rules": []}

        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)

    def _load_state(self) -> None:
        """Load previous alert state."""
        if self.state_path.exists():
            try:
                with open(self.state_path, 'r') as f:
                    state = json.load(f)
                    # Load active alerts
                    for alert_data in state.get("active_alerts", []):
                        alert = Alert(
                            alert_id=alert_data["alert_id"],
                            name=alert_data["name"],
                            severity=alert_data["severity"],
                            status=alert_data["status"],
                            context=alert_data.get("context", {}),
                            fired_at=alert_data["fired_at"]
                        )
                        alert.resolved_at = alert_data.get("resolved_at")
                        alert.acked_at = alert_data.get("acked_at")
                        self.active_alerts[alert.alert_id] = alert
            except Exception as e:
                print(f"Warning: Failed to load alert state: {e}")

    def _save_state(self) -> None:
        """Save current alert state."""
        state = {
            "active_alerts": [alert.to_dict() for alert in self.active_alerts.values()],
            "last_updated": datetime.now().isoformat()
        }

        with open(self.state_path, 'w') as f:
            json.dump(state, f, indent=2)

    def _write_alert_event(self, alert: Alert) -> None:
        """Write alert event to log."""
        event = alert.to_dict()
        event["event_type"] = "alert"

        with open(self.events_path, 'a') as f:
            f.write(json.dumps(event) + "\n")

    async def _send_webhook(self, alert: Alert) -> bool:
        """Send webhook notification.

        Args:
            alert: Alert to send

        Returns:
            True if successful
        """
        webhook_config = self.config.get("notification_channels", {}).get("webhook", {})
        if not webhook_config.get("enabled") or not webhook_config.get("url"):
            return False

        url = webhook_config["url"]
        headers = webhook_config.get("headers", {"Content-Type": "application/json"})
        timeout = self.config.get("webhook_timeout_seconds", 5)
        max_retries = self.config.get("webhook_max_retries", 3)

        payload = {
            "alert_id": alert.alert_id,
            "name": alert.name,
            "severity": alert.severity,
            "status": alert.status,
            "fired_at": alert.fired_at,
            "context": alert.context
        }

        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload, headers=headers, timeout=timeout) as resp:
                        if resp.status == 200:
                            print(f"[AlertEngine] Webhook sent successfully for {alert.alert_id}")
                            return True
                        else:
                            print(f"[AlertEngine] Webhook failed with status {resp.status}")
            except Exception as e:
                print(f"[AlertEngine] Webhook attempt {attempt + 1} failed: {e}")

        print(f"[AlertEngine] Webhook failed after {max_retries} attempts for {alert.alert_id}")
        return False

    def evaluate_rules(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Evaluate all alert rules against current metrics.

        Args:
            metrics: Current system metrics

        Returns:
            List of newly triggered alerts
        """
        new_alerts = []

        # Update metrics window
        timestamp = datetime.now()
        for key, value in metrics.items():
            if key not in self.metrics_window:
                self.metrics_window[key] = []
            self.metrics_window[key].append((timestamp, value))

        # Clean old metrics (older than 10 minutes)
        cutoff_time = timestamp - timedelta(minutes=10)
        for key in self.metrics_window:
            self.metrics_window[key] = [
                (ts, val) for ts, val in self.metrics_window[key]
                if ts > cutoff_time
            ]

        # Evaluate each rule
        for rule in self.rules:
            if not rule.get("enabled", True):
                continue

            try:
                alert_id = rule["id"]

                # Check if already firing
                if alert_id in self.active_alerts:
                    existing_alert = self.active_alerts[alert_id]

                    # Check if resolved
                    if not self._check_rule_condition(rule, metrics):
                        # Resolve alert
                        existing_alert.status = "RESOLVED"
                        existing_alert.resolved_at = datetime.now().isoformat()
                        self._write_alert_event(existing_alert)
                        self._save_state()
                        del self.active_alerts[alert_id]
                        print(f"[AlertEngine] Alert resolved: {alert_id}")

                    continue

                # Check if should trigger
                if self._check_rule_condition(rule, metrics):
                    # Trigger new alert
                    alert = Alert(
                        alert_id=alert_id,
                        name=rule["name"],
                        severity=rule["severity"],
                        status="FIRING",
                        context=self._build_alert_context(rule, metrics),
                        fired_at=datetime.now().isoformat()
                    )

                    self.active_alerts[alert_id] = alert
                    self._write_alert_event(alert)
                    new_alerts.append(alert)

                    print(f"[AlertEngine] Alert triggered: {alert_id} - {rule['name']}")

            except Exception as e:
                print(f"[AlertEngine] Error evaluating rule {rule.get('id')}: {e}")

        # Save state
        if new_alerts:
            self._save_state()

        return new_alerts

    def _check_rule_condition(self, rule: Dict[str, Any], metrics: Dict[str, Any]) -> bool:
        """Check if alert rule condition is met.

        Args:
            rule: Rule configuration
            metrics: Current metrics

        Returns:
            True if condition is met
        """
        query = rule.get("query", {})
        metric_name = query.get("metric")
        operator = query.get("operator")
        threshold = query.get("value")
        window_seconds = query.get("window_seconds", 0)

        if metric_name not in metrics:
            return False

        current_value = metrics[metric_name]

        # Handle different operators
        if operator == "==":
            return current_value == threshold
        elif operator == "!=":
            return current_value != threshold
        elif operator == ">":
            return current_value > threshold
        elif operator == "<":
            return current_value < threshold
        elif operator == ">=":
            return current_value >= threshold
        elif operator == "<=":
            return current_value <= threshold

        return False

    def _build_alert_context(self, rule: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Build alert context with relevant metrics.

        Args:
            rule: Rule configuration
            metrics: Current metrics

        Returns:
            Context dictionary
        """
        context = {}

        # Add current metric value
        query = rule.get("query", {})
        metric_name = query.get("metric")
        if metric_name in metrics:
            context["current_value"] = metrics[metric_name]

        # Add threshold
        context["threshold"] = query.get("value")

        return context

    def get_alert_state(self) -> Dict[str, Any]:
        """Get current alert state.

        Returns:
            Alert state dictionary
        """
        return {
            "active_alerts": [alert.to_dict() for alert in self.active_alerts.values()],
            "total_active": len(self.active_alerts),
            "last_updated": datetime.now().isoformat()
        }

    def get_alert_history(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get alert event history.

        Args:
            limit: Maximum number of events

        Returns:
            List of alert events
        """
        history = []

        if self.events_path.exists():
            with open(self.events_path, 'r') as f:
                for line in f:
                    try:
                        event = json.loads(line)
                        history.append(event)
                    except json.JSONDecodeError:
                        continue

        # Return most recent first
        return history[-limit:][::-1]

    def ack_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert.

        Args:
            alert_id: Alert ID to acknowledge

        Returns:
            True if successful
        """
        if alert_id not in self.active_alerts:
            return False

        alert = self.active_alerts[alert_id]
        alert.status = "ACKED"
        alert.acked_at = datetime.now().isoformat()

        self._write_alert_event(alert)
        self._save_state()

        print(f"[AlertEngine] Alert acknowledged: {alert_id}")
        return True

    def update_rules(self, rules: List[Dict[str, Any]]) -> bool:
        """Update alert rules.

        Args:
            rules: New rules configuration

        Returns:
            True if successful
        """
        try:
            # Update in-memory rules
            self.rules = rules

            # Update config file
            self.config["rules"] = rules
            with open(self.config_path, 'w') as f:
                yaml.dump(self.config, f, default_flow_style=False)

            print(f"[AlertEngine] Updated {len(rules)} alert rules")
            return True
        except Exception as e:
            print(f"[AlertEngine] Failed to update rules: {e}")
            return False

    def get_rules(self) -> List[Dict[str, Any]]:
        """Get all alert rules.

        Returns:
            List of rules
        """
        return self.rules
