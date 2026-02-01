#!/usr/bin/env python3
"""
Metrics summary script for PolyArb-X latency analysis.

This script reads metrics from logs/metrics.jsonl and calculates
p50, p95, p99 percentiles for all latency metrics.

Usage:
    python3 scripts/summarize_metrics.py
    python3 scripts/summarize_metrics.py --file logs/metrics.jsonl
    python3 scripts/summarize_metrics.py --window 300  # last 5 minutes
"""
import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any


# Default metrics log file
DEFAULT_METRICS_FILE = Path("logs/metrics.jsonl")


def load_metrics(
    file_path: Path,
    time_window_seconds: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Load metrics from JSONL file.

    Args:
        file_path: Path to metrics.jsonl file
        time_window_seconds: Optional time window in seconds (from now)

    Returns:
        List of metric dictionaries
    """
    if not file_path.exists():
        print(f"Error: Metrics file not found: {file_path}")
        sys.exit(1)

    metrics = []
    cutoff_time = None

    if time_window_seconds:
        cutoff_time = datetime.now() - timedelta(seconds=time_window_seconds)

    try:
        with open(file_path, 'r') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue

                try:
                    metric = json.loads(line)

                    # Filter by time window if specified
                    if cutoff_time:
                        timestamp_str = metric.get('timestamp')
                        if timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str)
                            if timestamp < cutoff_time:
                                continue

                    metrics.append(metric)

                except json.JSONDecodeError:
                    print(f"Warning: Invalid JSON on line {line_num}", file=sys.stderr)
                    continue

    except IOError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    return metrics


def calculate_percentiles(values: List[float]) -> Dict[str, float]:
    """
    Calculate p50, p95, p99 percentiles.

    Args:
        values: List of numeric values

    Returns:
        Dictionary with p50, p95, p99
    """
    if not values:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    sorted_values = sorted(values)
    n = len(sorted_values)

    def get_percentile(p: float) -> float:
        """Get percentile using linear interpolation"""
        index = (n - 1) * p / 100
        lower = int(index)
        upper = min(lower + 1, n - 1)

        if lower == upper:
            return sorted_values[lower]

        # Linear interpolation
        weight = index - lower
        return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight

    return {
        "p50": get_percentile(50),
        "p95": get_percentile(95),
        "p99": get_percentile(99)
    }


def calculate_statistics(values: List[float]) -> Dict[str, float]:
    """
    Calculate basic statistics for a list of values.

    Args:
        values: List of numeric values

    Returns:
        Dictionary with min, max, avg, count
    """
    if not values:
        return {"min": 0.0, "max": 0.0, "avg": 0.0, "count": 0}

    return {
        "min": min(values),
        "max": max(values),
        "avg": sum(values) / len(values),
        "count": len(values)
    }


def print_summary(metrics: List[Dict[str, Any]]) -> None:
    """
    Print formatted summary of latency metrics.

    Args:
        metrics: List of metric dictionaries
    """
    if not metrics:
        print("No metrics found.")
        return

    # Define all latency fields
    latency_fields = [
        ("ws_to_book_update_ms", "WebSocket to OrderBook Update"),
        ("book_to_signal_ms", "OrderBook to Signal Generation"),
        ("signal_to_risk_ms", "Signal to Risk Check"),
        ("risk_to_send_ms", "Risk Check to Order Send"),
        ("end_to_end_ms", "End-to-End Latency")
    ]

    print("=" * 80)
    print("PolyArb-X Latency Metrics Summary")
    print("=" * 80)
    print(f"Total events: {len(metrics)}")
    print()

    for field, label in latency_fields:
        values = [m.get(field, 0) for m in metrics if field in m]

        if not values:
            continue

        stats = calculate_statistics(values)
        percentiles = calculate_percentiles(values)

        print(f"{label}")
        print(f"  Count:    {stats['count']}")
        print(f"  Min:      {stats['min']:.2f} ms")
        print(f"  Average:  {stats['avg']:.2f} ms")
        print(f"  Max:      {stats['max']:.2f} ms")
        print(f"  P50:      {percentiles['p50']:.2f} ms")
        print(f"  P95:      {percentiles['p95']:.2f} ms")
        print(f"  P99:      {percentiles['p99']:.2f} ms")
        print()


def print_csv(metrics: List[Dict[str, Any]]) -> None:
    """
    Print metrics in CSV format for easy import into spreadsheet tools.

    Args:
        metrics: List of metric dictionaries
    """
    if not metrics:
        return

    latency_fields = [
        "ws_to_book_update_ms",
        "book_to_signal_ms",
        "signal_to_risk_ms",
        "risk_to_send_ms",
        "end_to_end_ms"
    ]

    # Print header
    print("metric," + ",".join(latency_fields))

    # Print each field's stats
    for field in latency_fields:
        values = [m.get(field, 0) for m in metrics if field in m]

        if not values:
            continue

        stats = calculate_statistics(values)
        percentiles = calculate_percentiles(values)

        row = [
            field,
            f"{stats['min']:.2f}",
            f"{stats['avg']:.2f}",
            f"{stats['max']:.2f}",
            f"{percentiles['p50']:.2f}",
            f"{percentiles['p95']:.2f}",
            f"{percentiles['p99']:.2f}"
        ]

        print(",".join(row))


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Summarize PolyArb-X latency metrics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Summarize all metrics
  python3 scripts/summarize_metrics.py

  # Use custom file
  python3 scripts/summarize_metrics.py --file logs/metrics.jsonl

  # Only last 5 minutes
  python3 scripts/summarize_metrics.py --window 300

  # Output CSV format
  python3 scripts/summarize_metrics.py --csv
        """
    )

    parser.add_argument(
        "--file",
        type=Path,
        default=DEFAULT_METRICS_FILE,
        help="Path to metrics.jsonl file (default: logs/metrics.jsonl)"
    )

    parser.add_argument(
        "--window",
        type=int,
        default=None,
        help="Time window in seconds (e.g., 300 for last 5 minutes)"
    )

    parser.add_argument(
        "--csv",
        action="store_true",
        help="Output in CSV format"
    )

    args = parser.parse_args()

    # Load metrics
    metrics = load_metrics(args.file, args.window)

    if not metrics:
        print("No metrics found in file.")
        sys.exit(0)

    # Print output
    if args.csv:
        print_csv(metrics)
    else:
        print_summary(metrics)


if __name__ == "__main__":
    main()
