"""Regression gate system for quality enforcement."""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import json
from enum import Enum
from src.layer1_settings import logger


class GateStatus(Enum):
    """Gate status values."""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    UNKNOWN = "unknown"


@dataclass
class GateThreshold:
    """Threshold for a gate."""
    
    name: str
    metric: str  # Which metric to track
    threshold_value: float  # Min/max value required
    is_lower_bound: bool = True  # True if metric must be >= threshold, False if <=
    
    def check(self, actual_value: float) -> bool:
        """Check if value passes gate."""
        if self.is_lower_bound:
            return actual_value >= self.threshold_value
        else:
            return actual_value <= self.threshold_value


@dataclass
class GateResult:
    """Result of gate check."""
    
    gate_name: str
    status: GateStatus
    actual_value: float
    threshold_value: float
    passed: bool
    timestamp: datetime
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "gate": self.gate_name,
            "status": self.status.value,
            "actual": self.actual_value,
            "threshold": self.threshold_value,
            "passed": self.passed,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
        }


class RegressionGate:
    """Single regression gate."""
    
    def __init__(self, threshold: GateThreshold):
        """Initialize gate."""
        self.threshold = threshold
        self.history: List[GateResult] = []
    
    def check(self, actual_value: float, message: str = "") -> GateResult:
        """
        Check if actual value passes gate.
        
        Args:
            actual_value: Measured metric value
            message: Optional message
            
        Returns:
            GateResult with status
        """
        passed = self.threshold.check(actual_value)
        
        status = GateStatus.PASS if passed else GateStatus.FAIL
        
        result = GateResult(
            gate_name=self.threshold.name,
            status=status,
            actual_value=actual_value,
            threshold_value=self.threshold.threshold_value,
            passed=passed,
            timestamp=datetime.utcnow(),
            message=message,
        )
        
        self.history.append(result)
        
        # Keep only last 1000 results
        if len(self.history) > 1000:
            self.history.pop(0)
        
        return result
    
    def get_trend(self, window_hours: int = 24) -> Dict[str, Any]:
        """Get trend over time window."""
        cutoff = datetime.utcnow() - timedelta(hours=window_hours)
        recent = [r for r in self.history if r.timestamp > cutoff]
        
        if not recent:
            return {
                "gate": self.threshold.name,
                "samples": 0,
                "pass_rate": 0.0,
                "avg_value": 0.0,
            }
        
        pass_count = sum(1 for r in recent if r.passed)
        values = [r.actual_value for r in recent]
        
        return {
            "gate": self.threshold.name,
            "samples": len(recent),
            "pass_rate": pass_count / len(recent),
            "avg_value": sum(values) / len(values) if values else 0.0,
            "min_value": min(values) if values else 0.0,
            "max_value": max(values) if values else 0.0,
        }


class RegressionGateSet:
    """Set of regression gates."""
    
    def __init__(self):
        """Initialize gate set."""
        self.gates: Dict[str, RegressionGate] = {}
        self.runs: List[Dict[str, Any]] = []
    
    def register_gate(self, threshold: GateThreshold) -> None:
        """Register a new gate."""
        gate = RegressionGate(threshold)
        self.gates[threshold.name] = gate
        logger.info(f"Registered gate: {threshold.name}")
    
    def check_all(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """
        Check all gates against metrics.
        
        Args:
            metrics: Dict of metric_name -> value
            
        Returns:
            Overall result with pass/fail status
        """
        results = []
        all_passed = True
        
        for gate_name, gate in self.gates.items():
            metric_name = gate.threshold.metric
            
            if metric_name not in metrics:
                logger.warning(f"Metric {metric_name} not found for gate {gate_name}")
                result = GateResult(
                    gate_name=gate_name,
                    status=GateStatus.UNKNOWN,
                    actual_value=0.0,
                    threshold_value=gate.threshold.threshold_value,
                    passed=False,
                    timestamp=datetime.utcnow(),
                    message=f"Metric {metric_name} not available",
                )
            else:
                actual_value = metrics[metric_name]
                result = gate.check(actual_value)
            
            results.append(result.to_dict())
            
            if not result.passed and result.status == GateStatus.FAIL:
                all_passed = False
        
        run_result = {
            "timestamp": datetime.utcnow().isoformat(),
            "status": "PASS" if all_passed else "FAIL",
            "gates": results,
        }
        
        self.runs.append(run_result)
        
        # Keep only last 100 runs
        if len(self.runs) > 100:
            self.runs.pop(0)
        
        return run_result
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all gates."""
        summary = {
            "total_gates": len(self.gates),
            "gates": {},
        }
        
        for gate_name, gate in self.gates.items():
            summary["gates"][gate_name] = gate.get_trend()
        
        # Recent run status
        if self.runs:
            last_run = self.runs[-1]
            summary["last_run"] = {
                "timestamp": last_run["timestamp"],
                "status": last_run["status"],
                "gate_count": len(last_run["gates"]),
                "passed": sum(1 for g in last_run["gates"] if g["passed"]),
            }
        
        return summary


class DefaultGates:
    """Factory for creating default gates."""
    
    @staticmethod
    def create_quality_gates() -> RegressionGateSet:
        """Create standard quality gates."""
        gates = RegressionGateSet()
        
        # Grounding score must be >= 0.90
        gates.register_gate(GateThreshold(
            name="grounding_score",
            metric="average_grounding_score",
            threshold_value=0.90,
            is_lower_bound=True,
        ))
        
        # Faithfulness must be >= 0.85
        gates.register_gate(GateThreshold(
            name="faithfulness",
            metric="average_faithfulness",
            threshold_value=0.85,
            is_lower_bound=True,
        ))
        
        # Context recall must be >= 0.80
        gates.register_gate(GateThreshold(
            name="context_recall",
            metric="average_context_recall",
            threshold_value=0.80,
            is_lower_bound=True,
        ))
        
        # Answer relevancy must be >= 0.80
        gates.register_gate(GateThreshold(
            name="answer_relevancy",
            metric="average_answer_relevancy",
            threshold_value=0.80,
            is_lower_bound=True,
        ))
        
        # Hallucination rate must be <= 0.05 (5%)
        gates.register_gate(GateThreshold(
            name="hallucination_rate",
            metric="hallucination_rate",
            threshold_value=0.05,
            is_lower_bound=False,
        ))
        
        # Pass rate must be >= 0.95
        gates.register_gate(GateThreshold(
            name="pass_rate",
            metric="pass_rate",
            threshold_value=0.95,
            is_lower_bound=True,
        ))
        
        return gates


class QualityDashboard:
    """Dashboard for quality metrics."""
    
    def __init__(self, gate_set: RegressionGateSet):
        """Initialize dashboard."""
        self.gate_set = gate_set
        self.snapshots: List[Dict[str, Any]] = []
    
    def snapshot(self, metrics: Dict[str, float]) -> Dict[str, Any]:
        """Take quality snapshot."""
        # Run gates
        run_result = self.gate_set.check_all(metrics)
        
        # Create dashboard snapshot
        snapshot = {
            "timestamp": datetime.utcnow().isoformat(),
            "metrics": metrics,
            "gate_run": run_result,
            "summary": self.gate_set.get_summary(),
        }
        
        self.snapshots.append(snapshot)
        
        # Keep only last 500 snapshots
        if len(self.snapshots) > 500:
            self.snapshots.pop(0)
        
        return snapshot
    
    def get_recent_trend(self, hours: int = 24) -> Dict[str, Any]:
        """Get recent trend."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        
        recent = []
        for snapshot in self.snapshots:
            ts = datetime.fromisoformat(snapshot["timestamp"])
            if ts > cutoff:
                recent.append(snapshot)
        
        if not recent:
            return {"hours": hours, "samples": 0, "data": []}
        
        return {
            "hours": hours,
            "samples": len(recent),
            "start": recent[0]["timestamp"],
            "end": recent[-1]["timestamp"],
            "data": recent,
        }
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        if not self.snapshots:
            return "# No metrics collected yet\n"
        
        snapshot = self.snapshots[-1]
        lines = [f"# Collected at {snapshot['timestamp']}\n"]
        
        # Export metric values
        for metric_name, value in snapshot["metrics"].items():
            lines.append(f"{metric_name} {value}\n")
        
        # Export gate results
        for gate in snapshot["gate_run"]["gates"]:
            gate_name = gate["gate"]
            value = 1.0 if gate["passed"] else 0.0
            status = gate["status"]
            lines.append(f'gate_status{{gate="{gate_name}",status="{status}"}} {value}\n')
        
        return "".join(lines)
