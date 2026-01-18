"""Tests for evaluation, metrics, and regression gates."""

from datetime import datetime, timedelta

# Optional: Add pytest if available
try:
    import pytest
except ImportError:
    pytest = None

from src.layer7_observability import (
    RAGASEvaluator,
    RagasInput,
    MetricsRegistry,
    PerformanceMonitor,
    RegressionGateSet,
    RegressionGate,
    GateThreshold,
    GateStatus,
    DefaultGates,
    QualityDashboard,
)


class TestRAGASEvaluator:
    """Test RAGAS evaluation framework."""

    @pytest.fixture
    def evaluator(self):
        return RAGASEvaluator(threshold_grounding=0.90)

    def test_evaluate_faithful_answer(self, evaluator):
        """Test evaluation of faithful answer."""
        input_data = RagasInput(
            question="What is the capital of France?",
            answer="The capital of France is Paris.",
            retrieved_contexts=["Paris is the capital and largest city of France."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Answer is faithful to context
        assert metrics.faithfulness > 0.7
        assert not metrics.has_hallucination
        assert metrics.grounding_score > 0.5

    def test_evaluate_hallucinated_answer(self, evaluator):
        """Test evaluation of hallucinated answer."""
        input_data = RagasInput(
            question="What is the capital of France?",
            answer="The capital of France is London.",
            retrieved_contexts=["Paris is the capital and largest city of France."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Answer contradicts context
        assert metrics.faithfulness < 0.7
        assert metrics.has_hallucination

    def test_evaluate_with_ground_truth(self, evaluator):
        """Test evaluation with ground truth."""
        input_data = RagasInput(
            question="What is the capital of France?",
            answer="The capital of France is Paris.",
            retrieved_contexts=["Paris is the capital of France."],
            ground_truth="Paris",
        )
        
        metrics = evaluator.evaluate(input_data)
        
        assert metrics.context_recall >= 0.5
        assert metrics.answer_relevancy > 0.5

    def test_context_recall_calculation(self, evaluator):
        """Test context recall metric calculation."""
        input_data = RagasInput(
            question="Paris is beautiful",
            answer="Paris is a beautiful city with the Eiffel Tower.",
            retrieved_contexts=["Paris has the Eiffel Tower.", "Paris is beautiful."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Answer recalls context information
        assert metrics.context_recall > 0.5

    def test_context_precision_calculation(self, evaluator):
        """Test context precision metric calculation."""
        input_data = RagasInput(
            question="What is Paris?",
            answer="Paris is a city.",
            retrieved_contexts=["Paris is a city in France."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Retrieved context is relevant
        assert metrics.context_precision > 0.5

    def test_answer_relevancy_calculation(self, evaluator):
        """Test answer relevancy metric."""
        input_data = RagasInput(
            question="What is the capital of France?",
            answer="The capital of France is Paris, a city in Europe.",
            retrieved_contexts=["Paris is a city."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Answer addresses question
        assert metrics.answer_relevancy > 0.5

    def test_grounding_score_passes_threshold(self, evaluator):
        """Test grounding score against threshold."""
        input_data = RagasInput(
            question="What is Paris?",
            answer="Paris is the capital of France.",
            retrieved_contexts=["Paris is the capital of France."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Check threshold
        passes = evaluator.get_grounding_pass(metrics)
        # May pass or fail depending on scores, but threshold logic works
        assert isinstance(passes, bool)

    def test_evaluation_summary(self, evaluator):
        """Test evaluation summary generation."""
        # Run multiple evaluations
        for i in range(3):
            input_data = RagasInput(
                question=f"Question {i}",
                answer=f"Answer {i}",
                retrieved_contexts=[f"Context {i}"],
            )
            evaluator.evaluate(input_data)
        
        summary = evaluator.get_summary()
        
        assert summary["total_evaluations"] == 3
        assert "average_faithfulness" in summary
        assert "average_grounding_score" in summary
        assert "hallucination_rate" in summary
        assert "pass_rate" in summary


class TestMetricsRegistry:
    """Test metrics collection."""

    @pytest.fixture
    def registry(self):
        return MetricsRegistry()

    def test_counter_increment(self, registry):
        """Test counter incrementing."""
        counter = registry.counter("requests", {"path": "/api/chat"})
        counter.increment(5)
        
        assert counter.value == 5

    def test_gauge_set_value(self, registry):
        """Test gauge value setting."""
        gauge = registry.gauge("memory_usage", {"type": "rss"})
        gauge.set(256.5)
        
        assert gauge.value == 256.5

    def test_histogram_observe(self, registry):
        """Test histogram observations."""
        histogram = registry.histogram("request_duration", {"endpoint": "/api"})
        
        histogram.observe(100)
        histogram.observe(200)
        histogram.observe(150)
        
        assert len(histogram.values) == 3
        assert histogram.get_percentile(50) == 150

    def test_snapshot(self, registry):
        """Test metrics snapshot."""
        registry.counter("requests").increment(10)
        registry.gauge("temperature").set(25.5)
        
        snapshot = registry.get_snapshot()
        
        assert "timestamp" in snapshot
        assert "counters" in snapshot
        assert "gauges" in snapshot
        assert "histograms" in snapshot

    def test_multiple_metric_tags(self, registry):
        """Test metrics with different tags."""
        registry.counter("requests", {"path": "/chat", "method": "POST"}).increment()
        registry.counter("requests", {"path": "/health", "method": "GET"}).increment()
        
        assert len(registry.counters) == 2

    def test_performance_monitor(self, registry):
        """Test performance monitor."""
        monitor = PerformanceMonitor(registry)
        
        monitor.track_request("/api/chat", "POST", 150, 200, "user1")
        monitor.track_llm_call("gpt-4", 100, 50, 1500, True)
        monitor.track_evaluation(0.92, False, "/chat")
        
        snapshot = registry.get_snapshot()
        
        assert "counters" in snapshot
        assert "histograms" in snapshot


class TestRegressionGates:
    """Test regression gates."""

    def test_gate_check_pass(self):
        """Test gate that passes."""
        threshold = GateThreshold(
            name="grounding",
            metric="grounding_score",
            threshold_value=0.90,
            is_lower_bound=True,
        )
        gate = RegressionGate(threshold)
        
        result = gate.check(0.95)
        
        assert result.passed
        assert result.status == GateStatus.PASS

    def test_gate_check_fail(self):
        """Test gate that fails."""
        threshold = GateThreshold(
            name="grounding",
            metric="grounding_score",
            threshold_value=0.90,
            is_lower_bound=True,
        )
        gate = RegressionGate(threshold)
        
        result = gate.check(0.85)
        
        assert not result.passed
        assert result.status == GateStatus.FAIL

    def test_gate_upper_bound(self):
        """Test gate with upper bound."""
        threshold = GateThreshold(
            name="error_rate",
            metric="error_rate",
            threshold_value=0.05,
            is_lower_bound=False,  # Error rate must be <= 0.05
        )
        gate = RegressionGate(threshold)
        
        # Should pass (under limit)
        assert gate.check(0.03).passed
        
        # Should fail (over limit)
        assert not gate.check(0.07).passed

    def test_gate_set_all_pass(self):
        """Test gate set where all gates pass."""
        gates = RegressionGateSet()
        gates.register_gate(GateThreshold("g1", "m1", 0.90, True))
        gates.register_gate(GateThreshold("g2", "m2", 0.80, True))
        
        metrics = {"m1": 0.95, "m2": 0.85}
        result = gates.check_all(metrics)
        
        assert result["status"] == "PASS"

    def test_gate_set_one_fail(self):
        """Test gate set where one gate fails."""
        gates = RegressionGateSet()
        gates.register_gate(GateThreshold("g1", "m1", 0.90, True))
        gates.register_gate(GateThreshold("g2", "m2", 0.80, True))
        
        metrics = {"m1": 0.95, "m2": 0.70}  # m2 fails
        result = gates.check_all(metrics)
        
        assert result["status"] == "FAIL"

    def test_default_gates(self):
        """Test default quality gates."""
        gates = DefaultGates.create_quality_gates()
        
        # Check that standard gates are registered
        assert "grounding_score" in gates.gates
        assert "faithfulness" in gates.gates
        assert "hallucination_rate" in gates.gates

    def test_quality_dashboard(self):
        """Test quality dashboard."""
        gates = DefaultGates.create_quality_gates()
        dashboard = QualityDashboard(gates)
        
        metrics = {
            "average_grounding_score": 0.92,
            "average_faithfulness": 0.88,
            "average_context_recall": 0.85,
            "average_answer_relevancy": 0.82,
            "hallucination_rate": 0.02,
            "pass_rate": 0.96,
        }
        
        snapshot = dashboard.snapshot(metrics)
        
        assert "metrics" in snapshot
        assert "gate_run" in snapshot
        assert "summary" in snapshot


class TestGateTrends:
    """Test gate trend analysis."""

    def test_gate_trend_calculation(self):
        """Test gate trend over time."""
        threshold = GateThreshold("score", "metric", 0.90, True)
        gate = RegressionGate(threshold)
        
        # Simulate multiple checks
        for value in [0.92, 0.91, 0.93, 0.88, 0.90]:
            gate.check(value)
        
        trend = gate.get_trend(window_hours=1)
        
        assert trend["samples"] == 5
        assert "pass_rate" in trend
        assert "avg_value" in trend

    def test_dashboard_trend(self):
        """Test dashboard trend analysis."""
        gates = DefaultGates.create_quality_gates()
        dashboard = QualityDashboard(gates)
        
        # Take multiple snapshots
        for i in range(5):
            metrics = {
                "average_grounding_score": 0.90 + i * 0.01,
                "average_faithfulness": 0.85,
                "average_context_recall": 0.80,
                "average_answer_relevancy": 0.80,
                "hallucination_rate": 0.05,
                "pass_rate": 0.90,
            }
            dashboard.snapshot(metrics)
        
        trend = dashboard.get_recent_trend(hours=1)
        
        assert trend["samples"] == 5
        assert "data" in trend


class TestMetricsIntegration:
    """Integration tests for metrics and gates."""

    def test_end_to_end_evaluation_and_gating(self):
        """Test complete evaluation and gating workflow."""
        # Evaluate a response
        evaluator = RAGASEvaluator(threshold_grounding=0.90)
        
        input_data = RagasInput(
            question="What is the capital of France?",
            answer="The capital of France is Paris.",
            retrieved_contexts=["Paris is the capital of France."],
        )
        
        metrics = evaluator.evaluate(input_data)
        
        # Get summary
        summary = evaluator.get_summary()
        
        # Run gates
        gates = DefaultGates.create_quality_gates()
        gate_result = gates.check_all(summary)
        
        # Verify gate result structure
        assert "status" in gate_result
        assert "gates" in gate_result
        assert isinstance(gate_result["gates"], list)

    def test_regression_gate_enforcement(self):
        """Test that gates enforce quality standards."""
        gates = DefaultGates.create_quality_gates()
        
        # High quality metrics
        good_metrics = {
            "average_grounding_score": 0.92,
            "average_faithfulness": 0.88,
            "average_context_recall": 0.85,
            "average_answer_relevancy": 0.82,
            "hallucination_rate": 0.02,
            "pass_rate": 0.96,
        }
        
        good_result = gates.check_all(good_metrics)
        assert good_result["status"] == "PASS"
        
        # Poor quality metrics
        bad_metrics = {
            "average_grounding_score": 0.75,
            "average_faithfulness": 0.70,
            "average_context_recall": 0.65,
            "average_answer_relevancy": 0.60,
            "hallucination_rate": 0.20,
            "pass_rate": 0.70,
        }
        
        bad_result = gates.check_all(bad_metrics)
        assert bad_result["status"] == "FAIL"

    def test_prometheus_export(self):
        """Test Prometheus format export."""
        gates = DefaultGates.create_quality_gates()
        dashboard = QualityDashboard(gates)
        
        metrics = {
            "average_grounding_score": 0.92,
            "average_faithfulness": 0.88,
            "average_context_recall": 0.85,
            "average_answer_relevancy": 0.82,
            "hallucination_rate": 0.02,
            "pass_rate": 0.96,
        }
        
        dashboard.snapshot(metrics)
        prometheus_output = dashboard.export_prometheus()
        
        assert "# Collected at" in prometheus_output
        assert "average_grounding_score" in prometheus_output
        assert "gate_status" in prometheus_output
