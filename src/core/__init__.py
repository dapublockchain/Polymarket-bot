"""Core modules for PolyArb-X."""

from src.core.config import Config
from src.core.models import *
from src.core.edge import EdgeBreakdown, Decision, calculate_net_edge, validate_edge_breakdown
from src.core.metrics import MetricsCollector, record_latency
from src.core.recorder import EventRecorder, EventType, get_events_path, record_event
from src.core.telemetry import TraceContext, EventType as TeleEventType, generate_trace_id, log_event

__all__ = [
    # Config
    "Config",

    # Models
    "Token",
    "Order",
    "OrderBook",
    "Side",
    "StrategySignal",

    # Edge
    "EdgeBreakdown",
    "Decision",
    "calculate_net_edge",
    "validate_edge_breakdown",

    # Metrics
    "MetricsCollector",
    "record_latency",

    # Recorder
    "EventRecorder",
    "EventType",
    "get_events_path",
    "record_event",

    # Telemetry
    "TraceContext",
    "TeleEventType",
    "generate_trace_id",
    "log_event",
]
