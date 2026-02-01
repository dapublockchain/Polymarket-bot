# Phase 1: Telemetry and Observability

## Overview

Phase 1 adds comprehensive observability to PolyArb-X through:
- **Distributed tracing** with trace_id propagation
- **Latency tracking** across the entire event pipeline
- **Edge breakdown** for trading decision attribution
- **Event recording** for replay and analysis

## Architecture

```
WebSocket Event → OrderBook → Strategy → Risk Manager → Execution
     ↓              ↓           ↓            ↓              ↓
   trace_id     timestamp   metrics     edge_breakdown   result
     ↓              ↓           ↓            ↓              ↓
   telemetry    telemetry   metrics     telemetry       recorder
```

## Components

### 1. Telemetry (`src/core/telemetry.py`)

**Purpose**: Distributed tracing with trace_id propagation

**Key Features**:
- `generate_trace_id()`: Generate unique trace IDs (UUID v4)
- `TraceContext`: Async context manager for trace propagation
- `log_event()`: Structured logging to `logs/telemetry.jsonl`

**Event Types**:
```python
EVENT_RECEIVED = "event_received"        # WebSocket message received
OPPORTUNITY_DETECTED = "opportunity_detected"  # Strategy found opportunity
RISK_PASSED = "risk_passed"              # Risk check completed
ORDER_SUBMITTED = "order_submitted"      # Order sent to exchange
```

**Usage**:
```python
from src.core.telemetry import generate_trace_id, TraceContext, log_event, EventType

# Generate trace_id
trace_id = generate_trace_id()

# Use context for automatic propagation
async with TraceContext(trace_id):
    await log_event(EventType.OPPORTUNITY_DETECTED, {"profit": "1.23"})

# Or pass explicitly
await log_event(EventType.EVENT_RECEIVED, {"token_id": "abc"}, trace_id=trace_id)
```

**Log Format** (JSONL):
```json
{
  "event_type": "opportunity_detected",
  "timestamp": "2025-01-31T12:34:56.789",
  "trace_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "data": {
    "strategy": "atomic",
    "expected_profit": "1.50"
  }
}
```

---

### 2. Metrics (`src/core/metrics.py`)

**Purpose**: Latency tracking and aggregation

**Key Features**:
- `record_latency()`: Record latency metrics for a trace
- `MetricsCollector`: In-memory aggregation
- `calculate_percentiles()`: P50, P95, P99 calculation

**Latency Metrics**:
```python
ws_to_book_update_ms     # WebSocket → OrderBook update
book_to_signal_ms        # OrderBook → Signal generation
signal_to_risk_ms        # Signal → Risk check
risk_to_send_ms          # Risk check → Order send
end_to_end_ms            # Total latency (sum of above)
```

**Usage**:
```python
from src.core.metrics import record_latency

await record_latency(
    trace_id="abc123",
    ws_to_book_update_ms=10.5,
    book_to_signal_ms=5.2,
    signal_to_risk_ms=3.1,
    risk_to_send_ms=15.8
)
```

**Log Format** (JSONL to `logs/metrics.jsonl`):
```json
{
  "trace_id": "abc123",
  "ws_to_book_update_ms": 10.5,
  "book_to_signal_ms": 5.2,
  "signal_to_risk_ms": 3.1,
  "risk_to_send_ms": 15.8,
  "end_to_end_ms": 34.6,
  "timestamp": "2025-01-31T12:34:56.789"
}
```

---

### 3. Metrics Summary Script (`scripts/summarize_metrics.py`)

**Purpose**: Analyze metrics and display statistics

**Usage**:
```bash
# Summarize all metrics
python3 scripts/summarize_metrics.py

# Specify custom file
python3 scripts/summarize_metrics.py --file logs/metrics.jsonl

# Only last 5 minutes
python3 scripts/summarize_metrics.py --window 300

# Output CSV format
python3 scripts/summarize_metrics.py --csv
```

**Output Example**:
```
PolyArb-X Latency Metrics Summary
================================================================================
Total events: 1500

WebSocket to OrderBook Update
  Count:    1500
  Min:      5.20 ms
  Average:  12.45 ms
  Max:      45.80 ms
  P50:      11.30 ms
  P95:      18.70 ms
  P99:      32.10 ms

OrderBook to Signal Generation
  Count:    1200
  Min:      2.10 ms
  Average:  4.85 ms
  Max:      15.30 ms
  P50:      4.50 ms
  P95:      7.20 ms
  P99:      11.80 ms

End-to-End Latency
  Count:    1200
  Min:      15.50 ms
  Average:  35.20 ms
  Max:      95.40 ms
  P50:      32.10 ms
  P95:      48.90 ms
  P99:      72.30 ms
```

---

### 4. Edge Analysis (`src/core/edge.py`)

**Purpose**: Trading decision attribution with cost breakdown

**Key Features**:
- `EdgeBreakdown`: Detailed profit/loss calculation
- `Decision`: ACCEPT/REJECT with reason
- `calculate_net_edge()`: Profit after all costs

**Cost Components**:
```python
gross_edge       # Gross profit before costs
fees_est         # Estimated trading fees
slippage_est     # Estimated slippage
gas_est          # Estimated gas cost
latency_buffer   # Buffer for latency risk
net_edge         # Final profit (gross - costs)
```

**Usage**:
```python
from src.core.edge import EdgeBreakdown, calculate_net_edge

net_edge = calculate_net_edge(
    gross_edge=Decimal("100.0"),
    fees=Decimal("2.0"),
    slippage=Decimal("1.0"),
    gas=Decimal("0.5"),
    latency_buffer=Decimal("0.3")
)  # Returns: 96.2

edge = EdgeBreakdown(
    gross_edge=Decimal("100.0"),
    fees_est=Decimal("2.0"),
    slippage_est=Decimal("1.0"),
    gas_est=Decimal("0.5"),
    latency_buffer=Decimal("0.3"),
    min_threshold=Decimal("95.0")
)

if edge.net_edge >= edge.min_threshold:
    decision = Decision.ACCEPT
    reason = "Acceptable profit"
else:
    decision = Decision.REJECT
    reason = f"Insufficient: ${edge.net_edge} < ${edge.min_threshold}"
```

**Decision Logging**:
All risk decisions are logged with detailed breakdown to telemetry.

---

### 5. Event Recorder (`src/core/recorder.py`)

**Purpose**: Persistent event storage for replay and backtesting

**Key Features**:
- `EventRecorder`: Buffered async event writer
- Date-based sharding: `data/events/YYYYMMDD/events.jsonl`
- Auto-flush on buffer size (default: 100 events)

**Event Types**:
```python
ORDERBOOK_SNAPSHOT = "orderbook_snapshot"  # Full order book state
SIGNAL = "signal"                         # Trading signal generated
ORDER_REQUEST = "order_request"           # Order submission request
ORDER_RESULT = "order_result"             # Order execution result
```

**Usage**:
```python
from src.core.recorder import EventRecorder

recorder = EventRecorder(buffer_size=100)

# Record orderbook snapshot
await recorder.record_orderbook_snapshot(
    token_id="abc123",
    bids=[{"price": "0.50", "size": "10"}],
    asks=[{"price": "0.51", "size": "10"}]
)

# Record signal
await recorder.record_signal(
    trace_id="xyz789",
    strategy="atomic",
    yes_token="yes_123",
    no_token="no_456",
    yes_price=Decimal("0.48"),
    no_price=Decimal("0.49"),
    expected_profit=Decimal("1.50")
)

# Flush manually (optional, auto-flush on buffer full)
await recorder.flush()
```

**Storage Format** (`data/events/20250131/events.jsonl`):
```json
{"event_type": "orderbook_snapshot", "timestamp": "2025-01-31T12:34:56.789", "data": {"token_id": "abc123", "bids": [...], "asks": [...]}}
{"event_type": "signal", "timestamp": "2025-01-31T12:35:01.234", "data": {"trace_id": "xyz789", "strategy": "atomic", ...}}
```

---

## Integration Points

### Strategy Integration

Atomic arbitrage strategy now includes telemetry:

```python
async def check_opportunity(
    self,
    yes_orderbook: OrderBook,
    no_orderbook: OrderBook,
    trace_id: Optional[str] = None,  # NEW
) -> Optional[ArbitrageOpportunity]:
    # Record latency
    await record_latency(
        trace_id=trace_id,
        ws_to_book_update_ms=...,
        book_to_signal_ms=...
    )

    # Log opportunity detected
    await log_event(
        EventType.OPPORTUNITY_DETECTED,
        {...},
        trace_id=trace_id
    )
```

### Risk Manager Integration

Risk manager now returns detailed `EdgeBreakdown`:

```python
async def validate_signal_with_edge(
    self,
    signal: Signal,
    balance: Decimal,
    gas_cost: Decimal,
    trace_id: Optional[str] = None,
) -> EdgeBreakdown:
    # Calculate net edge with all costs
    net_edge = calculate_net_edge(
        gross_edge,
        fees,
        slippage_est,
        gas_cost,
        latency_buffer
    )

    # Log decision to telemetry
    await log_event(...)

    return EdgeBreakdown(
        decision=Decision.ACCEPT or REJECT,
        reason="...",
        net_edge=net_edge
    )
```

### Main Loop Integration

Main loop now records all events:

```python
recorder = EventRecorder(buffer_size=100)
trace_id = generate_trace_id()

# Record orderbook
await recorder.record_orderbook_snapshot(...)

# Check opportunity with trace
opportunity = await strategy.check_opportunity(yes_book, no_book, trace_id)

# Record signal
await recorder.record_signal(trace_id, ...)

# Flush on shutdown
await recorder.flush()
```

---

## Running the System

### Dry-Run Mode (Default)

```bash
python3 src/main.py
```

This will:
- Connect to Polymarket WebSocket
- Record orderbook snapshots to `data/events/YYYYMMDD/events.jsonl`
- Record telemetry to `logs/telemetry.jsonl`
- Record metrics to `logs/metrics.jsonl`
- NOT execute real trades

### Analyzing Metrics

```bash
# View latency summary
python3 scripts/summarize_metrics.py

# View only last hour
python3 scripts/summarize_metrics.py --window 3600

# Export to CSV
python3 scripts/summarize_metrics.py --csv > metrics.csv
```

### Inspecting Events

```bash
# View today's events
cat data/events/$(date +%Y%m%d)/events.jsonl | jq .

# Filter for signals
cat data/events/$(date +%Y%m%d)/events.jsonl | jq 'select(.event_type == "signal")'

# View specific trace
grep "trace-id-here" data/events/$(date +%Y%m%d)/events.jsonl
```

---

## Testing

### Unit Tests

```bash
# Test telemetry module
pytest tests/unit/test_telemetry.py -v

# Test metrics module
pytest tests/unit/test_metrics.py -v

# Test edge module
pytest tests/unit/test_edge.py -v

# Test recorder module
pytest tests/unit/test_recorder.py -v
```

### Coverage

Phase 1 achieves **82.46% test coverage** (264 tests passing).

---

## Troubleshooting

### Issue: Missing trace_id in logs

**Symptom**: Events without trace_id

**Solution**: Always pass trace_id or use TraceContext:
```python
# Good
async with TraceContext(trace_id):
    await strategy.check_opportunity(...)

# Also good
opportunity = await strategy.check_opportunity(..., trace_id=trace_id)
```

### Issue: High latency in book_to_signal_ms

**Symptom**: book_to_signal_ms > 50ms

**Potential causes**:
- Slow VWAP calculation (deep order books)
- Blocking operations in strategy

**Solution**: Profile strategy code, optimize hot paths

### Issue: Disk space usage

**Symptom**: Large `logs/` or `data/events/` directories

**Solution**: Implement log rotation:
```bash
# Compress old logs
gzip logs/metrics.jsonl.2025-01-30

# Delete events older than 30 days
find data/events/ -type f -mtime +30 -delete
```

---

## Next Steps

After Phase 1, proceed to:

- **Phase 2**: Resilience (circuit breakers, retry logic)
- **Phase 3**: Replay & Backtesting

---

## Files Modified/Created

| File | Type | Description |
|------|------|-------------|
| `src/core/telemetry.py` | Module | Distributed tracing |
| `src/core/metrics.py` | Module | Latency tracking |
| `src/core/edge.py` | Module | Edge analysis |
| `src/core/recorder.py` | Module | Event recording |
| `scripts/summarize_metrics.py` | Script | Metrics analysis |
| `src/core/models.py` | Modified | Added event_received_ms |
| `src/connectors/polymarket_ws.py` | Modified | Telemetry integration |
| `src/strategies/atomic.py` | Modified | Async + telemetry |
| `src/execution/risk_manager.py` | Modified | EdgeBreakdown support |
| `src/main.py` | Modified | Recorder integration |

---

## Performance Impact

| Component | Overhead | Mitigation |
|-----------|----------|------------|
| Telemetry logging | ~1ms per event | Async I/O, buffering |
| Metrics recording | <0.1ms per trace | In-memory aggregation |
| Event recording | ~2ms per snapshot | Async I/O, buffer flush |
| Total impact | <5ms per trade | Acceptable for arbitrage |

---

**Phase 1 Status**: ✅ Complete

- All modules implemented
- 264 tests passing (82.46% coverage)
- Documentation complete
- Ready for Phase 2
