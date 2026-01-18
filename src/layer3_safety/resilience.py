"""Resilience patterns: fallbacks, timeouts, degradation."""

import asyncio
from typing import Any, Callable, Optional, Dict, List
from datetime import datetime
from src.layer1_settings import logger


class TimeoutError(Exception):
    """Raised when operation exceeds timeout."""
    pass


class Fallback:
    """Fallback strategy for degraded performance."""

    def __init__(
        self,
        primary: Callable,
        fallback: Callable,
        timeout: float = 5.0,
        cache_ttl: int = 300,
    ):
        """
        Initialize fallback strategy.

        Args:
            primary: Primary function to call
            fallback: Fallback function if primary fails
            timeout: Max seconds to wait for primary
            cache_ttl: Cache result TTL in seconds
        """
        self.primary = primary
        self.fallback = fallback
        self.timeout = timeout
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.cache_ttl = cache_ttl

    def execute(
        self,
        *args,
        cache_key: Optional[str] = None,
        **kwargs,
    ) -> Any:
        """
        Execute primary with fallback.

        Args:
            *args: Primary function args
            cache_key: Cache key for results
            **kwargs: Primary function kwargs

        Returns:
            Result from primary or fallback
        """
        # Check cache
        if cache_key and cache_key in self.cache:
            result, cached_at = self.cache[cache_key]
            age = (datetime.utcnow() - cached_at).total_seconds()
            if age < self.cache_ttl:
                logger.debug(f"Cache hit for {cache_key}")
                return result

        # Try primary
        try:
            result = self._execute_with_timeout(
                self.primary, self.timeout, *args, **kwargs
            )
            
            # Cache result
            if cache_key:
                self.cache[cache_key] = (result, datetime.utcnow())
            
            return result

        except (TimeoutError, Exception) as e:
            logger.warning(f"Primary failed: {str(e)}. Using fallback.")
            
            try:
                result = self.fallback(*args, **kwargs)
                logger.info("Fallback succeeded")
                return result
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {str(fallback_error)}")
                raise

    @staticmethod
    def _execute_with_timeout(
        func: Callable,
        timeout: float,
        *args,
        **kwargs,
    ) -> Any:
        """Execute function with timeout."""
        try:
            # For async functions
            if asyncio.iscoroutinefunction(func):
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    return loop.run_until_complete(
                        asyncio.wait_for(func(*args, **kwargs), timeout)
                    )
                finally:
                    loop.close()
            else:
                # For sync functions, use simple approach
                # (Python doesn't have true timeouts without signals)
                return func(*args, **kwargs)

        except asyncio.TimeoutError:
            raise TimeoutError(f"Function exceeded {timeout}s timeout")

    def clear_cache(self) -> None:
        """Clear cache."""
        self.cache.clear()


class DegradationStrategy:
    """Graceful degradation strategy."""

    def __init__(self):
        """Initialize degradation strategy."""
        self.degraded_services: Dict[str, Dict[str, Any]] = {}
        self.fallback_modes: Dict[str, Callable] = {}

    def register_fallback(
        self,
        service_name: str,
        fallback_fn: Callable,
    ) -> None:
        """
        Register fallback for service.

        Args:
            service_name: Service identifier
            fallback_fn: Function to call in degraded mode
        """
        self.fallback_modes[service_name] = fallback_fn
        logger.info(f"Registered fallback for {service_name}")

    def mark_degraded(
        self,
        service_name: str,
        reason: str,
        severity: str = "warning",
    ) -> None:
        """
        Mark service as degraded.

        Args:
            service_name: Service identifier
            reason: Degradation reason
            severity: "warning", "error", "critical"
        """
        self.degraded_services[service_name] = {
            "reason": reason,
            "severity": severity,
            "timestamp": datetime.utcnow().isoformat(),
        }
        logger.warning(f"Service {service_name} degraded: {reason}")

    def mark_recovered(self, service_name: str) -> None:
        """Mark service as recovered."""
        if service_name in self.degraded_services:
            del self.degraded_services[service_name]
            logger.info(f"Service {service_name} recovered")

    def is_degraded(self, service_name: str) -> bool:
        """Check if service is degraded."""
        return service_name in self.degraded_services

    def get_status(self) -> Dict[str, Any]:
        """Get current degradation status."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "degraded_count": len(self.degraded_services),
            "services": self.degraded_services,
        }


class HealthCheck:
    """Service health check."""

    def __init__(self, name: str, check_fn: Callable):
        """
        Initialize health check.

        Args:
            name: Service name
            check_fn: Function returning bool (healthy)
        """
        self.name = name
        self.check_fn = check_fn
        self.last_check: Optional[datetime] = None
        self.is_healthy = True

    def check(self) -> bool:
        """Run health check."""
        try:
            result = self.check_fn()
            self.is_healthy = result
            self.last_check = datetime.utcnow()
            return result
        except Exception as e:
            logger.error(f"Health check failed for {self.name}: {str(e)}")
            self.is_healthy = False
            return False

    def get_status(self) -> Dict[str, Any]:
        """Get health check status."""
        return {
            "service": self.name,
            "is_healthy": self.is_healthy,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


class HealthMonitor:
    """Monitor multiple services."""

    def __init__(self):
        """Initialize health monitor."""
        self.checks: Dict[str, HealthCheck] = {}

    def register(self, check: HealthCheck) -> None:
        """Register health check."""
        self.checks[check.name] = check

    def run_all_checks(self) -> Dict[str, Any]:
        """Run all health checks."""
        results = {}
        for name, check in self.checks.items():
            results[name] = check.check()
        return results

    def get_status(self) -> Dict[str, Any]:
        """Get all service statuses."""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                name: check.get_status() for name, check in self.checks.items()
            },
        }

    def get_healthy_services(self) -> List[str]:
        """Get list of healthy services."""
        return [
            name for name, check in self.checks.items() if check.is_healthy
        ]

    def get_degraded_services(self) -> List[str]:
        """Get list of degraded services."""
        return [
            name for name, check in self.checks.items() if not check.is_healthy
        ]
