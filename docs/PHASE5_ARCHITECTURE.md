# Phase 5: Evaluation & Observability Architecture

## Overview

Phase 5 introduces enterprise-grade evaluation, metrics collection, and quality gating to the personalized news briefing system. This layer sits above all 6 lower layers and provides:

1. **Evaluation:** RAGAS-based framework for measuring hallucinations and grounding
2. **Metrics:** Prometheus-compatible observability with performance tracking
3. **Quality Gates:** Automated quality enforcement with regression detection
4. **Monitoring:** Real-time dashboards and alerts

---

## Architecture Layers

```
Layer 7: EVALUATION & OBSERVABILITY (Phase 5)
├── Evaluation (RAGASEvaluator)
├── Metrics (MetricsRegistry + PerformanceMonitor)
├── Regression Gates (RegressionGateSet + QualityDashboard)
└── Monitoring (Prometheus + Grafana)

Layer 6: API & ORCHESTRATION
├── FastAPI Routes (briefing, qa, feedback)
├── LangGraph Orchestration (briefing_graph, qa_graph)
├── Policies (grounding, safety)
└── Tools (retriever, feedback)

Layer 5: DOMAIN SERVICES
├── BriefingService
├── IngestService
├── QAService
├── PersonalizationService
└── RetrievalService

Layer 4: PERSISTENCE & STATE
├── PostgreSQL (metadata)
├── Redis (cache)
├── Chroma (vector embeddings)
└── SQLite (fallback)

Layer 3: ADAPTERS & INTEGRATIONS
├── LLM (OpenAI)
├── Memory (Redis, SQLite)
├── News Sources (NewsAPI, RSS)
├── Schedulers (APScheduler)
└── Vector Stores (Chroma, Pinecone)

Layer 2: SAFETY & RESILIENCE (Phase 4)
├── Input Sanitization
├── Circuit Breakers
├── Rate Limiting
├── Retry Logic
└── Security Checks

Layer 1: CORE MODELS & PORTS
├── Domain Models (Article, Briefing, User)
├── Ports (LLMPort, NewsSourcePort, etc.)
└── Shared Types

Layer 0: SCAFFOLDING & CONFIG
├── FastAPI Application
├── Configuration Management
├── Logging & Utilities
└── Docker & Deployment
```

---

## Layer 7 Components

### 1. RAGAS Evaluator

**Location:** [src/layer7_observability/evaluator.py](../src/layer7_observability/evaluator.py)

**Purpose:** Evaluate Q&A quality using 4 core metrics derived from RAGAS framework.

**Architecture:**
```
RAGASEvaluator
├── evaluate(RagasInput) → EvaluationMetrics
│   ├── _evaluate_faithfulness(answer, contexts)
│   │   └── Detects contradictions between answer and context
│   ├── _evaluate_context_recall(answer, contexts, ground_truth)
│   │   └── Measures how much context info is utilized
│   ├── _evaluate_context_precision(question, contexts)
│   │   └── Measures relevance of retrieved contexts
│   ├── _evaluate_answer_relevancy(question, answer)
│   │   └── Measures how well answer addresses question
│   └── _calculate_confidence(faithfulness, precision, relevancy)
│       └── Composite confidence score
├── _calculate_grounding_score(metrics)
│   └── 40% faithfulness + 25% recall + 25% precision + 10% relevancy
├── get_summary() → Statistics
│   └── Rolling history of evaluations
└── History Tracking
    └── Maintains evaluation results for trend analysis
```

**Key Data Structures:**
```python
@dataclass
class RagasInput:
    question: str
    answer: str
    contexts: List[str]
    ground_truth: Optional[str] = None

@dataclass
class EvaluationMetrics:
    faithfulness: float  # 0-1: Answer/context alignment
    context_recall: float  # 0-1: Context info utilization
    context_precision: float  # 0-1: Retrieval quality
    answer_relevancy: float  # 0-1: Question addressing
    grounding_score: float  # 0-1: Composite score
    has_hallucination: bool  # Faithfulness < 0.6
    confidence: float  # 0-1: Overall confidence
    evaluated_at: datetime
```

**Scoring Details:**

| Metric | Calculation | Threshold | Status |
|--------|-------------|-----------|--------|
| Faithfulness | Overlap of answer entities + contradiction check | ≥ 0.85 | CRITICAL |
| Context Recall | Key phrase extraction from ground truth | ≥ 0.80 | HIGH |
| Context Precision | Question/context keyword overlap | ≥ 0.80 | HIGH |
| Answer Relevancy | Question/answer keyword overlap | ≥ 0.80 | MEDIUM |
| Grounding Score | Weighted composite (40+25+25+10) | ≥ 0.90 | CRITICAL |

---

### 2. Metrics Collection System

**Location:** [src/layer7_observability/metrics.py](../src/layer7_observability/metrics.py)

**Purpose:** Collect and expose Prometheus-compatible metrics.

**Architecture:**
```
MetricsRegistry (Central Storage)
├── Counter: Monotonic increment only
│   └── Examples: requests_total, errors_total, evaluations_total
├── Gauge: Point-in-time value
│   └── Examples: active_connections, memory_usage, queue_size
└── Histogram: Distribution with percentiles
    └── Examples: request_latency, token_count, evaluation_time

PerformanceMonitor (Business Metrics)
├── track_request(endpoint, method, duration, status, user_id)
├── track_llm_call(model, tokens_in/out, duration, success)
├── track_evaluation(grounding, hallucination, endpoint)
├── track_cache_hit(cache_type, hit)
├── track_rate_limit(user_id, allowed)
└── track_circuit_breaker(service, state)

Global Access
├── get_metrics_registry() → Singleton MetricsRegistry
└── get_performance_monitor() → Singleton PerformanceMonitor
```

**Metric Examples:**
```
http_requests_total{method="GET",status="200",endpoint="/briefing/generate"} 1234
http_request_duration_ms{endpoint="/qa/ask",quantile="0.95"} 1245

llm_calls_total{model="gpt-4",status="success"} 4567
llm_tokens_total{model="gpt-4",type="input"} 123456

evaluation_grounding_score{endpoint="/briefing/generate"} 0.89
evaluation_hallucinations_total{endpoint="/qa/ask"} 12

cache_hits_total{cache_type="embeddings"} 5678
rate_limit_violations_total{user_id="user_123"} 2

circuit_breaker_state{service="openai",state="closed"} 1
```

---

### 3. Regression Gates

**Location:** [src/layer7_observability/regression_gates.py](../src/layer7_observability/regression_gates.py)

**Purpose:** Enforce quality thresholds and detect regressions.

**Architecture:**
```
RegressionGateSet (Orchestration)
├── GateThreshold (Definition)
│   ├── name: str (e.g., "grounding_score")
│   ├── metric: str (e.g., "evaluation_grounding_score")
│   ├── threshold_value: float (e.g., 0.90)
│   └── is_lower_bound: bool
├── RegressionGate (Single Gate)
│   ├── check(actual_value) → GateResult
│   ├── get_trend(window_hours) → TrendStats
│   └── History Tracking
├── GateStatus: PASS | FAIL | WARNING | UNKNOWN
└── DefaultGates Factory
    ├── grounding_score >= 0.90
    ├── faithfulness >= 0.85
    ├── context_recall >= 0.80
    ├── answer_relevancy >= 0.80
    ├── hallucination_rate <= 0.05
    └── pass_rate >= 0.95

QualityDashboard (Monitoring)
├── Snapshot tracking (last 100 runs)
├── Trend analysis (24h, 7d, 30d windows)
├── Prometheus export
└── Summary statistics
```

**Gate Thresholds:**
```python
DEFAULT_GATES = [
    GateThreshold("grounding_score", metric="eval_grounding", threshold=0.90, is_lower=True),
    GateThreshold("faithfulness", metric="eval_faithfulness", threshold=0.85, is_lower=True),
    GateThreshold("context_recall", metric="eval_context_recall", threshold=0.80, is_lower=True),
    GateThreshold("answer_relevancy", metric="eval_answer_relevancy", threshold=0.80, is_lower=True),
    GateThreshold("hallucination_rate", metric="eval_hallucination_rate", threshold=0.05, is_lower=False),
    GateThreshold("pass_rate", metric="gate_pass_rate", threshold=0.95, is_lower=True),
]
```

**Gate Result Data:**
```python
@dataclass
class GateResult:
    gate_name: str
    status: GateStatus  # PASS/FAIL/WARNING/UNKNOWN
    actual: float  # Measured value
    threshold: float  # Expected threshold
    passed: bool  # actual meets threshold
    timestamp: datetime
```

---

## Integration Points

### Integration with Layer 6 (API & Orchestration)

**FastAPI Middleware:**
```python
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    # Track request metrics
    monitor.track_request(endpoint, method, duration, status, user_id)
    return response
```

**LangGraph Integration:**
```python
async def evaluate_node(state: State):
    """Graph node for Q&A evaluation"""
    evaluation = evaluator.evaluate(
        RagasInput(
            question=state["question"],
            answer=state["answer"],
            contexts=state["contexts"],
        )
    )
    state["evaluation"] = evaluation
    state["gates_result"] = gates.check_all(evaluation.to_dict())
    return state
```

---

### Integration with Layer 5 (Services)

**BriefingService:**
```python
class BriefingService:
    async def generate_briefing(self, user_id: str, date: str):
        briefing = await self._generate_content()
        
        # Evaluate each summary
        for article in briefing["articles"]:
            evaluation = self.evaluator.evaluate(RagasInput(...))
            article["quality"] = evaluation.to_dict()
        
        return briefing
```

**QAService:**
```python
class QAService:
    async def answer_question(self, question: str, user_id: str):
        answer = await self.llm.generate(...)
        
        # Track LLM call
        self.monitor.track_llm_call(model="gpt-4", tokens_in=..., tokens_out=..., ...)
        
        # Evaluate answer
        evaluation = self.evaluator.evaluate(RagasInput(...))
        
        # Check gates
        gates_result = self.gates.check_all(evaluation.to_dict())
        
        return {
            "answer": answer,
            "quality": evaluation.to_dict(),
            "gates": gates_result,
        }
```

---

### Integration with Layer 4 (Persistence)

**Metrics Storage:**
```python
# MetricsRegistry stores in memory (last 1000 snapshots)
# For long-term storage, export to:
# - Prometheus (time-series DB)
# - PostgreSQL (structured queries)
# - ClickHouse (analytical queries)
```

**Evaluation History:**
```python
# RAGASEvaluator maintains in-memory history
# For persistence:
postgres_store.save_evaluation(evaluation)
```

---

## Data Flow

### Briefing Generation with Evaluation

```
User Request
    ↓
BriefingService.generate_briefing()
    ├─ Ingest news articles
    ├─ Personalize rankings
    ├─ For each article:
    │   ├─ Generate summary (LLM)
    │   ├─ Track LLM call in metrics
    │   ├─ Evaluate summary (RAGASEvaluator)
    │   │   ├─ Check faithfulness
    │   │   ├─ Check context recall
    │   │   ├─ Check context precision
    │   │   └─ Check answer relevancy
    │   ├─ Track evaluation in metrics
    │   ├─ Check quality gates (RegressionGateSet)
    │   │   └─ Ensure grounding >= 0.90
    │   └─ Add quality scores to article
    └─ Return briefing with quality metadata
        ↓
    Metrics exported to Prometheus
    Evaluations tracked in history
    Gates checked for regression
    Dashboard updated
```

### Q&A with Evaluation

```
User Question
    ↓
QAService.answer_question()
    ├─ Retrieve relevant contexts (metrics tracked)
    ├─ Generate answer (LLM call tracked)
    ├─ Evaluate answer
    │   ├─ Faithfulness: answer vs contexts
    │   ├─ Context recall: how much context used
    │   ├─ Context precision: context relevance
    │   └─ Answer relevancy: question addressing
    ├─ Check quality gates
    │   └─ gates.check_all(evaluation_dict)
    ├─ If gates fail → Log warning/error
    └─ Return answer with quality metrics
        ↓
    Metrics stored in registry
    Prometheus scrapes metrics
    Grafana visualizes dashboards
    Alerts triggered if gates fail
```

---

## Quality Thresholds & Enforcement

### Grounding Score Calculation

```
Grounding = (40% × Faithfulness) + (25% × Context_Recall) + 
            (25% × Context_Precision) + (10% × Answer_Relevancy)

Example:
Faithfulness = 0.95 → 0.40 × 0.95 = 0.38
Context Recall = 0.85 → 0.25 × 0.85 = 0.2125
Context Precision = 0.90 → 0.25 × 0.90 = 0.225
Answer Relevancy = 0.88 → 0.10 × 0.88 = 0.088

Grounding = 0.38 + 0.2125 + 0.225 + 0.088 = 0.9055 ✅ PASS
```

### Gate Enforcement Strategy

| Gate | Threshold | Action if Fail | Alert Level |
|------|-----------|----------------|-------------|
| Grounding Score | ≥ 0.90 | Block/Warn | CRITICAL |
| Faithfulness | ≥ 0.85 | Log warning | HIGH |
| Context Recall | ≥ 0.80 | Log info | MEDIUM |
| Answer Relevancy | ≥ 0.80 | Log info | MEDIUM |
| Hallucination Rate | ≤ 0.05 | Block if too high | CRITICAL |
| Pass Rate | ≥ 0.95 | Alert if trending down | HIGH |

---

## Monitoring & Dashboards

### Prometheus Scraping

**Configuration:**
```yaml
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'personalized-brief-app'
    scrape_interval: 10s
    static_configs:
      - targets: ['localhost:8000/metrics']
```

### Grafana Dashboards

**Dashboard 1: Evaluation Quality**
- Grounding score (gauge, time-series)
- Hallucination rate (counter, trend)
- Gate pass rate (percentage)
- Metric distribution (histogram)

**Dashboard 2: API Performance**
- Request latency (p50, p95, p99)
- Request rate (req/sec)
- Error rate (%)
- Endpoint comparison

**Dashboard 3: System Health**
- Service uptime
- Resource usage (CPU, memory)
- Database connections
- Cache hit rate

---

## Testing Strategy

**Unit Tests:** [tests/unit/](../tests/unit/)
- RAGASEvaluator logic
- Metrics registry operations
- Gate threshold checking

**Integration Tests:** [tests/integration/](../tests/integration/)
- End-to-end evaluation pipeline
- Metrics collection with services
- Gate enforcement in real scenarios

**Test Coverage:** 26+ test cases covering:
- Faithful vs hallucinated answers
- Gate pass/fail scenarios
- Trend analysis
- Prometheus export format
- Concurrent metric updates

---

## Performance Characteristics

| Component | Time Complexity | Space Complexity | Notes |
|-----------|-----------------|------------------|-------|
| Evaluate | O(n) where n=context words | O(n) | 50-200ms typical |
| Check Gates | O(g) where g=gates count | O(g) | < 1ms per gate |
| Track Metrics | O(1) amortized | O(m) where m=metrics | ~0.1ms per track |
| Get Summary | O(h) where h=history size | O(h) | ~10ms for 1000 entries |

---

## Deployment Checklist

- [ ] Docker Compose configured for 6 services
- [ ] PostgreSQL initialized with schema
- [ ] Redis cache configured
- [ ] Chroma vector store populated
- [ ] Prometheus scrape config in place
- [ ] Grafana datasource connected
- [ ] Environment variables set (.env)
- [ ] Rate limits configured
- [ ] Quality gates registered
- [ ] Health checks passing
- [ ] Metrics endpoint accessible
- [ ] Dashboards created in Grafana

---

## Future Enhancements

1. **Extended Metrics:** Token efficiency, semantic similarity, diversity scores
2. **Custom Gates:** User-defined quality thresholds
3. **Predictive Alerts:** Anomaly detection in metric trends
4. **A/B Testing:** Compare evaluator versions with statistical rigor
5. **Feedback Loop:** Integrate user feedback with evaluation metrics
6. **Multi-model Evaluation:** Compare multiple LLM outputs
7. **Cost Tracking:** Monitor API costs alongside quality

---

**Architecture Version:** 1.0.0  
**Last Updated:** January 18, 2026  
**Status:** Production Ready (Phase 5 Complete)
