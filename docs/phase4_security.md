"""
# Phase 4: Security & Resilience Implementation

## Overview
Complete security hardening and resilience patterns for production deployment.

## Implemented Components

### 1. Enhanced Input Sanitization
**File:** `src/layer3_safety/input_sanitizer.py`
**Coverage:** 50+ injection patterns

#### Attack Vectors Protected Against:
- **Prompt Injection (15 patterns)**: ignore previous, system override, admin commands, roleplay breaks
- **SQL Injection (12 patterns)**: UNION SELECT, OR '1'='1, comment attacks, xp_cmdshell
- **XSS/JavaScript (15 patterns)**: script tags, javascript: protocol, event handlers, iframe injection
- **Code Execution (10 patterns)**: __import__, eval, os.system, subprocess, pickle attacks
- **Path Traversal (6 patterns)**: ../, %2e%2e, ../../etc/passwd variations
- **XML/YAML Injection (8 patterns)**: DOCTYPE, ENTITY, prototype pollution, YAML anchors
- **Credential Leaks (8 patterns)**: API keys, tokens, secrets detection

#### Features:
- HTML entity decoding (prevents double-encoding attacks)
- Null byte removal
- Control character filtering
- Whitespace normalization
- Configurable max length enforcement
- Detailed pattern matching with diagnostics

### 2. Circuit Breaker Pattern
**File:** `src/layer3_safety/circuit_breaker.py`

#### States:
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Threshold failures reached, requests rejected immediately
- **HALF_OPEN**: Testing if service recovered, limited requests allowed

#### Configuration:
```python
cb = CircuitBreaker(
    name="openai_api",
    failure_threshold=5,      # Failures before opening
    recovery_timeout=60,       # Seconds before testing recovery
    expected_exception=APIError
)
```

#### Capabilities:
- Automatic failure counting and state transition
- Configurable recovery testing
- Prevents cascading failures in distributed systems
- Per-service monitoring

### 3. Retry Logic with Exponential Backoff
**File:** `src/layer3_safety/retry_logic.py`

#### Backoff Formula:
```
delay = min(initial_delay * (base ^ (attempt - 1)), max_delay) + jitter
```

#### Configuration:
```python
config = RetryConfig(
    max_attempts=3,
    initial_delay=1.0,        # Start at 1 second
    max_delay=60.0,           # Cap at 1 minute
    exponential_base=2.0,     # Double each attempt
    jitter=True,              # Add ±10% random variation
    retriable_exceptions=(ConnectionError, TimeoutError)
)
```

#### Features:
- Exponential backoff prevents thundering herd
- Jitter prevents synchronized retries
- Configurable exception types
- Detailed logging of retry attempts

### 4. Rate Limiting
**File:** `src/layer3_safety/rate_limiter.py`

#### Token Bucket Algorithm:
- Tokens refill at configured rate
- Consumption fails if insufficient tokens
- Enables smooth rate limiting with burst allowance

#### Limits:
```python
limiter = RateLimiter(
    global_rps=100,              # Global requests/sec
    per_user_rps=10,             # Per-user requests/sec
    per_user_daily_limit=1000,   # Daily cap per user
)
```

#### Monitoring:
- Real-time token availability tracking
- Per-user quota management
- Daily limit enforcement with reset
- Statistics endpoint for dashboard

### 5. Resilience Patterns
**File:** `src/layer3_safety/resilience.py`

#### A. Fallback Strategy
```python
fallback = Fallback(
    primary=unreliable_service,
    fallback=reliable_cache,
    timeout=5.0,
    cache_ttl=300,  # Cache results for 5 minutes
)
result = fallback.execute()
```

#### B. Degradation Strategy
- Mark services as degraded with severity levels
- Track degradation reasons and timestamps
- Gracefully degrade functionality when services unavailable
- Automatic recovery detection

#### C. Health Checks
```python
monitor = HealthMonitor()
monitor.register(HealthCheck("database", lambda: db.ping()))
monitor.register(HealthCheck("cache", lambda: redis.ping()))

status = monitor.get_status()
# {
#   "database": {"is_healthy": true, "last_check": "..."},
#   "cache": {"is_healthy": false, "last_check": "..."}
# }
```

#### Features:
- Distributed health monitoring
- Per-service status tracking
- Automatic status aggregation
- Healthy/degraded service listing

## Test Coverage

### Security Tests (50+)
**File:** `tests/security/test_adversarial.py`

#### Test Classes:
1. **TestInputSanitization**: 50+ adversarial inputs
2. **TestCircuitBreaker**: State transitions and recovery
3. **TestRateLimiter**: Per-user and global limits
4. **TestRetryLogic**: Backoff calculation and exhaustion
5. **TestSanitization**: Edge cases and output handling

#### Attack Vectors Tested:
- Prompt injection (15 test cases)
- SQL injection (12 test cases)
- XSS/JavaScript (10 test cases)
- Code execution (8 test cases)
- Path traversal (5 test cases)

### Integration Tests
**File:** `tests/security/test_security_integration.py`

#### Test Scenarios:
- Complete query safety pipeline
- Circuit breaker with retry combination
- Rate limiting with fallback
- Health check integration
- Timeout handling with fallback
- Caching behavior
- Multi-user isolation

## Integration with Existing Services

### InputSanitizer Integration
```python
# In QAAgent (chat.py)
from src.layer3_safety import InputSanitizer

sanitizer = InputSanitizer()
clean_query = sanitizer.sanitize(user_query)
is_injection, patterns = sanitizer.detect_injection(clean_query)
if is_injection:
    raise SecurityError("Injection detected")
```

### CircuitBreaker for External APIs
```python
# In LLMService (llm_service.py)
from src.layer3_safety import CircuitBreaker

openai_cb = CircuitBreaker("openai_api", failure_threshold=5)

def call_openai(prompt):
    return openai_cb.call(openai.ChatCompletion.create, ...)
```

### Rate Limiting in Middleware
```python
# In FastAPI app (main.py)
from src.layer3_safety import RateLimiter

limiter = RateLimiter(global_rps=100, per_user_rps=10)

@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    user_id = get_user_id(request)
    allowed, msg = limiter.check_rate_limit(user_id)
    if not allowed:
        raise HTTPException(status_code=429, detail=msg)
    return await call_next(request)
```

### Resilience in Services
```python
# In BriefingService
from src.layer3_safety import Fallback

briefing_fallback = Fallback(
    primary=llm_service.synthesize,
    fallback=lambda: {"briefing": "Unable to generate briefing. Please try again."},
    timeout=5.0,
)

result = briefing_fallback.execute(articles)
```

## Configuration

### Recommended Defaults (Production)
```yaml
security:
  input:
    max_length: 5000
    enable_injection_detection: true
    
  circuit_breaker:
    openai:
      failure_threshold: 5
      recovery_timeout: 60
    
  rate_limiting:
    global_rps: 100
    per_user_rps: 10
    per_user_daily_limit: 1000
    
  retry:
    max_attempts: 3
    initial_delay: 1.0
    exponential_base: 2.0
    jitter: true
    
  fallback:
    cache_ttl: 300
    timeout: 5.0
```

## Metrics & Monitoring

### Tracked Metrics:
- **Input Sanitization**: Injection detection rate, pattern matches
- **Circuit Breaker**: State transitions, failure counts, recovery time
- **Rate Limiter**: Global/per-user token consumption, limit violations
- **Retry Logic**: Retry attempts, backoff delays, success rate
- **Health Checks**: Service availability, check frequency

### Dashboard Integration Points:
```python
# Get rate limiter stats
stats = limiter.get_stats(user_id)
# {"user_tokens": 8, "daily_count": 523, ...}

# Get circuit breaker state
state = circuit_breaker.get_state()
# {"name": "openai", "state": "closed", "failure_count": 2}

# Get health monitor status
health = monitor.get_status()
# {"database": {"is_healthy": true}, "cache": {"is_healthy": false}}
```

## Security Checklist

✅ **Input Validation**: 50+ injection patterns protected
✅ **Rate Limiting**: Global and per-user quotas enforced
✅ **Circuit Breaker**: Cascading failure prevention
✅ **Retry Logic**: Exponential backoff with jitter
✅ **Fallback Strategy**: Graceful degradation paths
✅ **Health Monitoring**: Service availability tracking
✅ **Test Coverage**: 50+ adversarial test cases
✅ **Error Handling**: Comprehensive exception strategies

## Next Steps (Phase 5)

- [ ] Implement full middleware integration
- [ ] Add observability/metrics collection
- [ ] Create security dashboards
- [ ] Performance benchmarking
- [ ] Load testing for rate limiter
- [ ] Integration testing with real APIs
"""
