"""Metrics collection and monitoring framework."""

from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
from collections import defaultdict
from src.layer1_settings import logger


@dataclass
class Metric:
    """Base metric data class."""
    
    name: str
    value: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_prometheus(self) -> str:
        """Convert to Prometheus format."""
        tags_str = ",".join(f'{k}="{v}"' for k, v in self.tags.items())
        if tags_str:
            return f'{self.name}{{{tags_str}}} {self.value}'
        return f'{self.name} {self.value}'


@dataclass
class Counter:
    """Monotonically increasing counter."""
    
    name: str
    value: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    
    def increment(self, amount: float = 1.0) -> None:
        """Increment counter."""
        self.value += amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": "counter",
            "value": self.value,
            "tags": self.tags,
        }


@dataclass
class Gauge:
    """Point-in-time measurement."""
    
    name: str
    value: float = 0.0
    tags: Dict[str, str] = field(default_factory=dict)
    
    def set(self, value: float) -> None:
        """Set gauge value."""
        self.value = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": "gauge",
            "value": self.value,
            "tags": self.tags,
        }


@dataclass
class Histogram:
    """Distribution of measurements."""
    
    name: str
    values: List[float] = field(default_factory=list)
    buckets: List[float] = field(default_factory=lambda: [0.1, 0.5, 1.0, 5.0, 10.0])
    tags: Dict[str, str] = field(default_factory=dict)
    
    def observe(self, value: float) -> None:
        """Record observation."""
        self.values.append(value)
    
    def get_percentile(self, percentile: float) -> float:
        """Get percentile value."""
        if not self.values:
            return 0.0
        sorted_values = sorted(self.values)
        idx = int(len(sorted_values) * percentile / 100)
        return sorted_values[min(idx, len(sorted_values) - 1)]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": "histogram",
            "count": len(self.values),
            "sum": sum(self.values),
            "min": min(self.values) if self.values else 0.0,
            "max": max(self.values) if self.values else 0.0,
            "avg": sum(self.values) / len(self.values) if self.values else 0.0,
            "p50": self.get_percentile(50),
            "p95": self.get_percentile(95),
            "p99": self.get_percentile(99),
            "tags": self.tags,
        }


class MetricsRegistry:
    """Central metrics registry."""
    
    def __init__(self):
        """Initialize metrics registry."""
        self.counters: Dict[str, Counter] = {}
        self.gauges: Dict[str, Gauge] = {}
        self.histograms: Dict[str, Histogram] = {}
        self.snapshots: List[Dict[str, Any]] = []

    def counter(self, name: str, tags: Dict[str, str] | None = None) -> Counter:
        """Get or create counter."""
        tags = tags or {}
        key = f"{name}_{json.dumps(tags, sort_keys=True)}"
        
        if key not in self.counters:
            counter = Counter(name, tags=tags)
            self.counters[key] = counter
        
        return self.counters[key]

    def gauge(self, name: str, tags: Dict[str, str] | None = None) -> Gauge:
        """Get or create gauge."""
        tags = tags or {}
        key = f"{name}_{json.dumps(tags, sort_keys=True)}"
        
        if key not in self.gauges:
            gauge = Gauge(name, tags=tags)
            self.gauges[key] = gauge
        
        return self.gauges[key]

    def histogram(self, name: str, tags: Dict[str, str] | None = None) -> Histogram:
        """Get or create histogram."""
        tags = tags or {}
        key = f"{name}_{json.dumps(tags, sort_keys=True)}"
        
        if key not in self.histograms:
            histogram = Histogram(name, tags=tags)
            self.histograms[key] = histogram
        
        return self.histograms[key]

    def increment_counter(self, name: str, amount: float = 1.0, tags: Dict[str, str] | None = None) -> None:
        """Increment a counter."""
        counter = self.counter(name, tags)
        counter.increment(amount)

    def set_gauge(self, name: str, value: float, tags: Dict[str, str] | None = None) -> None:
        """Set a gauge value."""
        gauge = self.gauge(name, tags)
        gauge.set(value)

    def observe_histogram(self, name: str, value: float, tags: Dict[str, str] | None = None) -> None:
        """Record a histogram observation."""
        histogram = self.histogram(name, tags)
        histogram.observe(value)

    def get_snapshot(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "counters": {
                k: v.to_dict() for k, v in self.counters.items()
            },
            "gauges": {
                k: v.to_dict() for k, v in self.gauges.items()
            },
            "histograms": {
                k: v.to_dict() for k, v in self.histograms.items()
            },
        }
        
        self.snapshots.append(snapshot)
        # Keep only last 1000 snapshots
        if len(self.snapshots) > 1000:
            self.snapshots.pop(0)
        
        return snapshot

    def reset(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()


class PerformanceMonitor:
    """Monitor performance metrics for services."""
    
    def __init__(self, registry: MetricsRegistry):
        """Initialize performance monitor."""
        self.registry = registry

    def track_request(
        self,
        endpoint: str,
        method: str,
        duration_ms: float,
        status_code: int,
        user_id: Optional[str] = None,
    ) -> None:
        """Track HTTP request metrics."""
        tags = {
            "endpoint": endpoint,
            "method": method,
            "status": str(status_code),
            "user_id": user_id or "anonymous",
        }
        
        # Counter for total requests
        self.registry.increment_counter("http.requests.total", tags=tags)
        
        # Histogram for request duration
        self.registry.observe_histogram("http.request.duration_ms", duration_ms, tags=tags)
        
        # Counter for errors
        if status_code >= 400:
            self.registry.increment_counter("http.errors.total", tags=tags)

    def track_llm_call(
        self,
        model: str,
        tokens_in: int,
        tokens_out: int,
        duration_ms: float,
        success: bool,
    ) -> None:
        """Track LLM API call metrics."""
        tags = {"model": model, "success": str(success)}
        
        self.registry.increment_counter("llm.calls.total", tags=tags)
        self.registry.observe_histogram("llm.tokens.in", tokens_in, tags=tags)
        self.registry.observe_histogram("llm.tokens.out", tokens_out, tags=tags)
        self.registry.observe_histogram("llm.duration_ms", duration_ms, tags=tags)
        
        if not success:
            self.registry.increment_counter("llm.errors.total", tags=tags)

    def track_evaluation(
        self,
        grounding_score: float,
        hallucination: bool,
        endpoint: str,
    ) -> None:
        """Track evaluation metrics."""
        tags = {"endpoint": endpoint, "hallucination": str(hallucination)}
        
        self.registry.observe_histogram("evaluation.grounding_score", grounding_score, tags=tags)
        self.registry.increment_counter("evaluation.total", tags=tags)
        
        if hallucination:
            self.registry.increment_counter("evaluation.hallucinations", tags=tags)

    def track_cache_hit(self, cache_type: str, hit: bool) -> None:
        """Track cache hit/miss."""
        tags = {"cache": cache_type, "hit": str(hit)}
        self.registry.increment_counter("cache.accesses", tags=tags)

    def track_rate_limit(self, user_id: str, allowed: bool) -> None:
        """Track rate limiting."""
        tags = {"user_id": user_id, "allowed": str(allowed)}
        self.registry.increment_counter("rate_limit.checks", tags=tags)
        
        if not allowed:
            self.registry.increment_counter("rate_limit.blocked", tags=tags)

    def track_circuit_breaker(self, service: str, state: str) -> None:
        """Track circuit breaker state."""
        tags = {"service": service, "state": state}
        self.registry.set_gauge("circuit_breaker.state", 1.0, tags=tags)


# Global metrics registry
_metrics_registry: Optional[MetricsRegistry] = None


def get_metrics_registry() -> MetricsRegistry:
    """Get global metrics registry."""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


def get_performance_monitor() -> PerformanceMonitor:
    """Get global performance monitor."""
    registry = get_metrics_registry()
    return PerformanceMonitor(registry)
