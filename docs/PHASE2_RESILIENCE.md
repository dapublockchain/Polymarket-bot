# Phase 2: Resilience & Fault Tolerance

## Overview

Phase 2 implements resilience patterns and fault tolerance mechanisms for the PolyArb-X trading system. These features ensure the system can gracefully handle failures, network issues, and high-load scenarios.

## Components

### 1. Circuit Breaker (`src/execution/circuit_breaker.py`)

**Purpose**: Prevents cascading failures by automatically stopping requests to failing services.

**States**:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Circuit tripped, requests blocked
- **HALF_OPEN**: Testing if system has recovered

**Features**:
- Consecutive failure threshold
- Failure rate threshold (configurable percentage)
- Gas cost threshold (to prevent expensive failed transactions)
- Automatic recovery after timeout
- Context manager support for clean execution

**Configuration** (`config/sandbox.yaml`):
```yaml
circuit_breaker:
  consecutive_failures_threshold: 3  # Trip after 3 consecutive failures
  failure_rate_threshold: 0.5         # Trip at 50% failure rate
  open_timeout_seconds: 60            # Stay OPEN for 60 seconds
  half_open_max_calls: 3              # Allow 3 test calls in HALF_OPEN
  gas_cost_threshold: 2.0             # USDC gas cost limit
```

**Usage**:
```python
from src.execution.circuit_breaker import CircuitBreaker

# Create circuit breaker
breaker = CircuitBreaker(
    consecutive_failures_threshold=5,
    open_timeout_seconds=60
)

# Use with context manager
async with breaker.execute("trade"):
    result = await execute_trade()
```

### 2. Nonce Manager (`src/execution/nonce_manager.py`)

**Purpose**: Manages Ethereum transaction nonces to prevent conflicts and ensure proper transaction ordering.

**Features**:
- On-chain nonce recovery on initialization
- Pending nonce tracking
- Automatic nonce reuse for failed transactions
- Thread-safe nonce allocation with asyncio.Lock
- Comprehensive statistics

**Methods**:
- `initialize()`: Fetch on-chain nonce
- `get_nonce()` / `allocate_nonce()`: Allocate next nonce
- `mark_confirmed(nonce)`: Mark transaction as confirmed
- `mark_failed(nonce)`: Mark transaction as failed (nonce available for reuse)
- `is_pending(nonce)`: Check if nonce is pending
- `get_stats()`: Get nonce manager statistics

**Usage**:
```python
from src.execution.nonce_manager import NonceManager

# Initialize
nonce_mgr = NonceManager(web3_client=wallet.address)
await nonce_mgr.initialize()

# Allocate nonce
nonce = await nonce_mgr.allocate_nonce()

# After transaction
await tx_sender.send_transaction(tx, nonce)

# Mark confirmed
await nonce_mgr.mark_confirmed(nonce)
```

### 3. Retry Policy (`src/execution/retry_policy.py`)

**Purpose**: Implements intelligent retry logic with exponential backoff and jitter.

**Features**:
- Configurable retry limits
- Exponential backoff
- Jitter to prevent thundering herd
- Error classification (retryable vs non-retryable)
- Idempotency key management

**Retryable Errors**:
- Network errors
- Timeout errors
- Connection errors
- "Nonce too low" errors
- "Replacement transaction underpriced" errors
- "Gas required exceeds allowance" errors

**Non-Retryable Errors**:
- Insufficient funds
- Invalid address
- Contract execution errors
- Authorization errors

**Configuration** (`config/sandbox.yaml`):
```yaml
retry_policy:
  max_retries: 3                    # Maximum retry attempts
  base_delay_ms: 1000               # Starting delay (1 second)
  max_delay_ms: 30000               # Maximum delay (30 seconds)
  exponential_backoff: true         # Use exponential backoff
  jitter: true                      # Add random jitter
  backoff_multiplier: 2.0           # Backoff multiplier
```

**Usage**:
```python
from src.execution.retry_policy import RetryPolicy

policy = RetryPolicy()

# Check if error is retryable
if policy.is_retryable(error):
    # Calculate delay
    delay = policy.calculate_delay(attempt)
    await asyncio.sleep(delay)
```

### 4. Runtime Configuration (`src/core/config_runtime.py`)

**Purpose**: Enables hot-reloading of configuration without restarting the system.

**Features**:
- YAML-based configuration
- File watching with watchdog
- Thread-safe config access
- Validation on reload
- Callbacks on config change

**Configuration File** (`config/sandbox.yaml`):
```yaml
# Trading limits
trading:
  max_position_size: 100.0
  min_profit_threshold: 0.02
  max_gas_cost: 1.0

# Circuit breaker
circuit_breaker:
  consecutive_failures_threshold: 3
  failure_rate_threshold: 0.5
  open_timeout_seconds: 60

# Retry policy
retry_policy:
  max_retries: 3
  base_delay_ms: 1000
  max_delay_ms: 30000
```

**Usage**:
```python
from src.core.config_runtime import get_runtime_config, ConfigWatcher

# Get current config
config = get_runtime_config()

# Watch for changes
watcher = ConfigWatcher("config/sandbox.yaml")
await watcher.start()

# Access config values
max_position = config.trading.max_position_size
```

### 5. Enhanced WebSocket Client (`src/connectors/polymarket_ws.py`)

**New Resilience Features**:

**Message Deduplication**:
- LRU cache with configurable size (default: 10,000 messages)
- Prevents processing duplicate WebSocket messages
- Cache statistics (hits, misses, hit rate)

**Sequence Number Validation**:
- Tracks sequence numbers per token
- Detects out-of-order messages
- Identifies message gaps
- Tracks sequence gap count

**Connection Statistics**:
- `connect_count`: Number of successful connections
- `disconnect_count`: Number of disconnections
- `message_count`: Total messages received
- `duplicate_count`: Duplicate messages skipped
- `sequence_gap_count`: Sequence gaps detected

**Usage**:
```python
from src.connectors.polymarket_ws import PolymarketWSClient

client = PolymarketWSClient()

# Get connection stats
stats = client.get_stats()
print(f"Messages: {stats['message_count']}")
print(f"Duplicates: {stats['duplicate_count']}")
print(f"Cache hit rate: {stats['cache_stats']['hit_rate']}")
```

### 6. Enhanced Transaction Sender (`src/execution/tx_sender.py`)

**Integrated Resilience Features**:

**Circuit Breaker Integration**:
- Automatic trading halt on repeated failures
- Rejection of signals when circuit is OPEN
- Automatic recovery testing

**Nonce Management**:
- Proper nonce allocation via NonceManager
- Automatic nonce tracking for pending transactions
- Nonce reuse for failed transactions

**Retry Policy**:
- Exponential backoff with jitter
- Smart error classification
- Configurable retry limits

**Idempotency Keys**:
- Prevents duplicate transaction execution
- Signal-based key generation
- TTL-based key expiration

**Enhanced Return Type**:
```python
@dataclass
class TxResult:
    signal: Signal
    tx_hash: Optional[str]
    success: bool
    error: Optional[str] = None
    status: TxStatus = TxStatus.PENDING
    attempt: int = 0           # Retry attempt number
    idempotency_key: Optional[str] = None
    nonce: Optional[int] = None
```

**Statistics**:
```python
stats = tx_sender.get_stats()
# Returns:
# {
#     "total_executions": 100,
#     "successful_executions": 95,
#     "failed_executions": 5,
#     "success_rate": 0.95,
#     "retry_count": 15,
#     "circuit_breaker_trips": 1,
#     "queue_size": 0,
#     "circuit_breaker_state": "closed",
#     ...
# }
```

## Configuration Files

### Sandbox Config (`config/sandbox.yaml`)

Conservative configuration for testing:

```yaml
# Trading limits
trading:
  max_position_size: 100.0        # Max $100 per position
  min_profit_threshold: 0.02       # Minimum 2% profit
  max_gas_cost: 1.0                # Max $1 gas cost

# Circuit breaker settings
circuit_breaker:
  consecutive_failures_threshold: 3   # Trip after 3 failures
  failure_rate_threshold: 0.5          # 50% failure rate
  open_timeout_seconds: 60             # 1 minute cooldown
  half_open_max_calls: 3               # Test with 3 calls
  gas_cost_threshold: 2.0              # $2 gas cost limit

# Retry policy settings
retry_policy:
  max_retries: 3                    # Max 3 retry attempts
  base_delay_ms: 1000               # Start with 1 second delay
  max_delay_ms: 30000               # Max 30 second delay
  exponential_backoff: true         # Use exponential backoff
  jitter: true                      # Add random jitter
  backoff_multiplier: 2.0           # Double delay each retry
```

## Testing

Phase 2 includes comprehensive tests for new modules:

```bash
# Run all Phase 2 tests
pytest tests/unit/test_nonce_manager.py -v
pytest tests/unit/test_retry_policy.py -v

# Run integration tests
pytest tests/integration/test_execution_layer.py -v
```

**Test Coverage**:
- `nonce_manager.py`: 100% coverage
- `retry_policy.py`: 79% coverage
- `tx_sender.py`: 89% coverage
- `circuit_breaker.py`: 83% coverage (existing tests)

**Total**: 315 tests passing, 69.51% coverage

## Monitoring

All resilience components expose statistics for monitoring:

### Circuit Breaker Stats
```python
{
    "state": "closed",
    "call_count": 100,
    "failure_count": 5,
    "consecutive_failures": 0,
    "failure_rate": 0.05,
    "last_failure_time": "2026-02-01T10:00:00Z",
}
```

### Nonce Manager Stats
```python
{
    "next_nonce": 42,
    "pending_count": 3,
    "confirmed_count": 38,
    "pending_nonces": [40, 41, 42],
}
```

### Retry Policy Stats
```python
{
    "max_attempts": 4,
    "config": {...},
}
```

### WebSocket Stats
```python
{
    "connected": true,
    "connect_count": 5,
    "message_count": 10000,
    "duplicate_count": 15,
    "sequence_gap_count": 2,
    "cache_stats": {
        "size": 500,
        "max_size": 10000,
        "hits": 9500,
        "misses": 500,
        "hit_rate": 0.95,
    },
    "heartbeat_ok": true,
}
```

### Transaction Sender Stats
```python
{
    "total_executions": 100,
    "successful_executions": 95,
    "failed_executions": 5,
    "success_rate": 0.95,
    "retry_count": 15,
    "circuit_breaker_trips": 1,
    "queue_size": 0,
    "circuit_breaker_state": "closed",
    "circuit_breaker_stats": {...},
    "nonce_manager_stats": {...},
}
```

## Best Practices

1. **Always initialize NonceManager** before use:
   ```python
   await nonce_manager.initialize()
   ```

2. **Check circuit breaker state** before critical operations:
   ```python
   if breaker.state != CircuitState.OPEN:
       # Proceed with operation
   ```

3. **Use idempotency keys** for all write operations:
   ```python
   key = idempotency.generate(signal)
   if not idempotency.is_seen(key):
       await execute_operation()
   ```

4. **Monitor statistics** regularly:
   ```python
   stats = tx_sender.get_stats()
   if stats["success_rate"] < 0.9:
       # Alert or investigate
   ```

5. **Handle non-retryable errors** immediately:
   ```python
   if not retry_policy.is_retryable(error):
       # Don't retry, handle immediately
   ```

## Integration with Phase 1

Phase 2 resilience features integrate seamlessly with Phase 1 observability:

- Circuit breaker trips are logged via telemetry
- Retry attempts emit latency metrics
- Nonce allocations are traced with trace_id
- Transaction results include full execution context

## Next Steps

**Phase 3**: Replay & Backtesting
- Event replay engine
- Historical backtesting
- Strategy optimization
- Performance analytics

---

**Status**: ✅ Complete
**Tests**: 315 passing
**Coverage**: 69.51%
**Date**: 2026-02-01
