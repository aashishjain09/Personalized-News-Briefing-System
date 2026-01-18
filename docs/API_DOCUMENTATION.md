# API Documentation & OpenAPI Specification

## Base URL
```
http://localhost:8080  (Development)
https://api.news-brief.com  (Production)
```

## Authentication
All endpoints require `X-User-ID` header:
```
X-User-ID: user_123
```

---

## Briefing Endpoints

### Generate Personalized Brief
**POST** `/briefing/generate`

Generate a personalized news briefing for a user on a specific date.

**Request:**
```json
{
  "date": "2026-01-18",
  "topics": ["technology", "business"],  // Optional filter
  "max_articles": 10,  // Default: 10
  "summary_length": "medium"  // "short" | "medium" | "long"
}
```

**Headers:**
```
X-User-ID: user_123
Content-Type: application/json
```

**Response:** 200 OK
```json
{
  "status": "success",
  "data": {
    "date": "2026-01-18",
    "user_id": "user_123",
    "total_articles": 8,
    "articles": [
      {
        "id": "article_001",
        "title": "AI Breakthroughs Accelerate",
        "source": "techcrunch.com",
        "published_date": "2026-01-18T10:30:00Z",
        "summary": "Major AI models reach new capabilities...",
        "content": "Full article content here...",
        "image_url": "https://...",
        "topics": ["technology", "AI"],
        "relevance_score": 0.95,
        "reading_time_minutes": 5,
        "quality": {
          "grounding_score": 0.92,
          "gates_passed": 6,
          "total_gates": 6,
          "evaluation_time": "2026-01-18T10:35:00Z"
        }
      }
    ],
    "summary": {
      "top_topics": ["AI", "Technology", "Business"],
      "sentiment": "positive",
      "key_insights": ["AI advancing rapidly", "Market reactions mixed"]
    },
    "quality_summary": {
      "avg_grounding_score": 0.88,
      "articles_passed_gates": 8,
      "total_articles": 8,
      "overall_quality": "HIGH"
    }
  },
  "timestamp": "2026-01-18T10:35:00Z"
}
```

**Error Response:** 400 Bad Request
```json
{
  "error": "Invalid date format",
  "detail": "Date must be YYYY-MM-DD",
  "status": 400
}
```

---

### Get Brief History
**GET** `/briefing/history`

Retrieve past briefings for a user.

**Query Parameters:**
```
?limit=10&offset=0&start_date=2026-01-01&end_date=2026-01-18
```

**Response:** 200 OK
```json
{
  "status": "success",
  "data": {
    "total": 18,
    "briefings": [
      {
        "date": "2026-01-18",
        "article_count": 8,
        "avg_quality_score": 0.88,
        "created_at": "2026-01-18T10:35:00Z"
      }
    ]
  },
  "pagination": {
    "limit": 10,
    "offset": 0,
    "has_more": true
  }
}
```

---

### Get Brief Quality Metrics
**GET** `/briefing/quality`

Get quality summary and gate status for user's briefings.

**Headers:**
```
X-User-ID: user_123
```

**Response:** 200 OK
```json
{
  "summary": {
    "avg_grounding_score": 0.87,
    "pass_rate": 0.96,
    "hallucination_rate": 0.02,
    "total_evaluated": 145,
    "time_window_hours": 24
  },
  "gates": [
    {
      "name": "grounding_score",
      "status": "PASS",
      "last_check": "2026-01-18T10:35:00Z",
      "trend": {
        "samples": 145,
        "pass_rate": 0.98,
        "avg_value": 0.89,
        "min_value": 0.76,
        "max_value": 0.98
      }
    },
    {
      "name": "hallucination_rate",
      "status": "PASS",
      "last_check": "2026-01-18T10:35:00Z",
      "trend": {
        "samples": 145,
        "pass_rate": 0.99,
        "avg_value": 0.018,
        "min_value": 0.0,
        "max_value": 0.05
      }
    }
  ],
  "timestamp": "2026-01-18T10:35:00Z"
}
```

---

## Q&A Endpoints

### Ask Question
**POST** `/qa/ask`

Ask a question and get an answer with automatic quality evaluation.

**Request:**
```json
{
  "question": "What are the latest developments in quantum computing?",
  "context": "news",  // "news" | "briefing" | "all"
  "top_k": 5,  // Number of context chunks to retrieve
  "detailed_evaluation": true  // Include evaluation details
}
```

**Headers:**
```
X-User-ID: user_123
Content-Type: application/json
```

**Response:** 200 OK
```json
{
  "status": "success",
  "data": {
    "question": "What are the latest developments in quantum computing?",
    "answer": "Recent quantum computing breakthroughs include...",
    "source_articles": [
      {
        "id": "article_001",
        "title": "Quantum Computing Advances",
        "source": "nature.com",
        "published_date": "2026-01-16T08:00:00Z"
      }
    ],
    "contexts": [
      "Context excerpt from article 1...",
      "Context excerpt from article 2..."
    ],
    "quality": {
      "grounding_score": 0.89,
      "faithfulness": 0.91,
      "context_recall": 0.85,
      "answer_relevancy": 0.88,
      "has_hallucination": false,
      "confidence": 0.87
    },
    "gates": {
      "passed": 6,
      "total": 6,
      "failures": []
    },
    "performance": {
      "llm_duration_ms": 1234,
      "total_duration_ms": 1890,
      "retrieval_count": 5
    }
  },
  "timestamp": "2026-01-18T10:35:00Z"
}
```

**Error Response:** 422 Unprocessable Entity
```json
{
  "error": "Evaluation failed",
  "detail": "Grounding score below threshold (0.72 < 0.90)",
  "quality": {
    "grounding_score": 0.72,
    "gates_failed": ["grounding_score"]
  },
  "status": 422
}
```

---

### Get Question History
**GET** `/qa/history`

Retrieve conversation history for a user.

**Query Parameters:**
```
?limit=20&offset=0&search=quantum&start_date=2026-01-01
```

**Response:** 200 OK
```json
{
  "status": "success",
  "data": {
    "total": 42,
    "conversations": [
      {
        "id": "conv_001",
        "question": "What are the latest developments in quantum computing?",
        "answer_preview": "Recent quantum computing breakthroughs...",
        "quality_score": 0.89,
        "created_at": "2026-01-18T10:35:00Z",
        "updated_at": "2026-01-18T10:35:00Z"
      }
    ]
  },
  "pagination": {
    "limit": 20,
    "offset": 0,
    "has_more": true
  }
}
```

---

## Feedback Endpoints

### Submit Feedback
**POST** `/feedback/submit`

Submit user feedback on answer quality.

**Request:**
```json
{
  "question_id": "conv_001",
  "rating": 4,  // 1-5 stars
  "is_helpful": true,
  "has_hallucination": false,
  "is_grounded": true,
  "comments": "Very helpful and accurate response"
}
```

**Headers:**
```
X-User-ID: user_123
Content-Type: application/json
```

**Response:** 201 Created
```json
{
  "status": "success",
  "data": {
    "feedback_id": "feedback_001",
    "question_id": "conv_001",
    "rating": 4,
    "created_at": "2026-01-18T10:35:00Z"
  },
  "message": "Thank you for your feedback!"
}
```

---

### Get Feedback Summary
**GET** `/feedback/summary`

Get aggregated feedback metrics.

**Query Parameters:**
```
?start_date=2026-01-01&end_date=2026-01-18&question_id=conv_001
```

**Response:** 200 OK
```json
{
  "status": "success",
  "data": {
    "total_feedback": 127,
    "avg_rating": 4.2,
    "helpful_rate": 0.92,
    "hallucination_rate": 0.08,
    "grounding_rate": 0.94,
    "rating_distribution": {
      "1": 2,
      "2": 5,
      "3": 12,
      "4": 54,
      "5": 54
    },
    "time_period": "2026-01-01 to 2026-01-18"
  }
}
```

---

## Admin Endpoints

### Get System Health
**GET** `/health`

Check system health status.

**Response:** 200 OK
```json
{
  "status": "healthy",
  "services": {
    "database": "healthy",
    "cache": "healthy",
    "vector_store": "healthy",
    "openai": "healthy"
  },
  "uptime_seconds": 3600,
  "timestamp": "2026-01-18T10:35:00Z"
}
```

**Response:** 503 Service Unavailable
```json
{
  "status": "unhealthy",
  "services": {
    "database": "healthy",
    "cache": "down",
    "vector_store": "healthy",
    "openai": "healthy"
  },
  "message": "Cache service unavailable",
  "timestamp": "2026-01-18T10:35:00Z"
}
```

---

### Get Metrics
**GET** `/metrics`

Get Prometheus-formatted metrics.

**Response:** 200 OK (text/plain)
```
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET",status="200",endpoint="/briefing/generate"} 1234

# HELP http_request_duration_ms HTTP request duration in milliseconds
# TYPE http_request_duration_ms histogram
http_request_duration_ms_bucket{endpoint="/qa/ask",le="100"} 45
http_request_duration_ms_bucket{endpoint="/qa/ask",le="500"} 234
http_request_duration_ms_bucket{endpoint="/qa/ask",le="1000"} 245

# HELP evaluation_grounding_score Evaluation grounding score
# TYPE evaluation_grounding_score gauge
evaluation_grounding_score{endpoint="/briefing/generate"} 0.89

# HELP gate_pass_total Total gate passes
# TYPE gate_pass_total counter
gate_pass_total{gate="grounding_score"} 2345
```

---

## Error Handling

### Common Errors

**400 Bad Request** - Invalid input
```json
{
  "error": "Validation Error",
  "detail": "Field 'date' is required",
  "status": 400
}
```

**401 Unauthorized** - Missing/invalid authentication
```json
{
  "error": "Unauthorized",
  "detail": "X-User-ID header required",
  "status": 401
}
```

**429 Too Many Requests** - Rate limit exceeded
```json
{
  "error": "Rate Limited",
  "detail": "User limit: 10 requests/sec, you've exceeded the limit",
  "retry_after_seconds": 60,
  "status": 429
}
```

**500 Internal Server Error** - Server error
```json
{
  "error": "Internal Server Error",
  "detail": "An unexpected error occurred",
  "request_id": "req_abc123",
  "status": 500,
  "timestamp": "2026-01-18T10:35:00Z"
}
```

---

## Rate Limiting

- **Global:** 100 requests/sec
- **Per-user:** 10 requests/sec
- **Daily quota:** 1,000 requests/day

Rate limit headers in response:
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 9
X-RateLimit-Reset: 1642510200
```

---

## Pagination

Paginated endpoints support:
```
?limit=20&offset=0
```

Response includes pagination metadata:
```json
{
  "data": [...],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 100,
    "has_more": true
  }
}
```

---

## WebSocket (Real-time Briefing)

**WebSocket** `/briefing/stream/{date}`

Stream briefing generation in real-time.

**Connection:**
```javascript
const ws = new WebSocket(
  'ws://localhost:8080/briefing/stream/2026-01-18',
  {
    headers: { 'X-User-ID': 'user_123' }
  }
);

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log(message.type); // "article_started", "article_completed", "briefing_complete"
};
```

**Message Types:**
```json
{
  "type": "article_started",
  "data": {
    "article_id": "article_001",
    "title": "...",
    "processing_status": "generating_summary"
  }
}
```

```json
{
  "type": "article_completed",
  "data": {
    "article_id": "article_001",
    "quality": {
      "grounding_score": 0.92,
      "gates_passed": 6
    }
  }
}
```

```json
{
  "type": "briefing_complete",
  "data": {
    "total_articles": 8,
    "avg_quality": 0.88,
    "duration_seconds": 45
  }
}
```

---

## OpenAPI/Swagger

Interactive API documentation available at:
```
http://localhost:8080/docs  (Swagger UI)
http://localhost:8080/redoc  (ReDoc)
```

OpenAPI schema:
```
http://localhost:8080/openapi.json
```

---

**Last Updated:** January 18, 2026
**API Version:** 1.0.0
