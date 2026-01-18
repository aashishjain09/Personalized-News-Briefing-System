# Deployment & Operations Runbook

## Quick Start

### Prerequisites
- Docker & Docker Compose (version 20.10+)
- Python 3.10+
- Virtual environment

### Environment Setup

1. **Create `.env` file:**
```bash
# Database
DB_PASSWORD=your_secure_db_password

# Redis
REDIS_PASSWORD=your_secure_redis_password

# OpenAI
OPENAI_API_KEY=sk-your-openai-key

# SendGrid (email)
SENDGRID_API_KEY=SG.your-sendgrid-key

# Grafana
GRAFANA_PASSWORD=your_secure_grafana_password

# Logging
LOG_LEVEL=INFO

# Environment
ENVIRONMENT=production
```

2. **Install Python dependencies:**
```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows
python -m pip install -r requirements.txt
```

### Local Development

```bash
# Start all services
docker-compose -f docker/docker-compose-dev.yml up -d

# Check service health
docker-compose -f docker/docker-compose-dev.yml ps

# View logs
docker-compose -f docker/docker-compose-dev.yml logs -f app

# Run tests
pytest tests/ -v

# Stop services
docker-compose -f docker/docker-compose-dev.yml down
```

### Production Deployment

```bash
# Build and start all services
docker-compose -f docker/docker-compose-prod.yml up -d

# Verify health checks
docker-compose -f docker/docker-compose-prod.yml ps
docker-compose -f docker/docker-compose-prod.yml exec app curl http://localhost:8000/health

# View application logs
docker-compose -f docker/docker-compose-prod.yml logs -f app

# View metrics
open http://localhost:9090  # Prometheus
open http://localhost:3000  # Grafana

# Stop services
docker-compose -f docker/docker-compose-prod.yml down
```

## Services

### Application (Port 8080)
- **API:** http://localhost:8080
- **Health:** http://localhost:8080/health
- **Metrics:** http://localhost:8080/metrics
- **Docs:** http://localhost:8080/docs (OpenAPI)

### Database (Port 5432)
- PostgreSQL for metadata storage
- Default user: `news_user`
- Default database: `personalized_brief`

### Cache (Port 6379)
- Redis for session and embedding cache
- Requires password authentication

### Vector Store (Port 8000)
- Chroma for vector embeddings
- REST API for similarity search

### Monitoring (Port 9090)
- Prometheus metrics scraping
- Time-series data storage

### Dashboards (Port 3000)
- Grafana visualization
- Quality metrics and alerts

## Monitoring & Observability

### Key Metrics

**Evaluation Metrics:**
- `evaluation.grounding_score` - Faithfulness to source documents
- `evaluation.hallucinations` - Count of hallucination detections
- `gate_status` - Quality gate pass/fail status

**Performance Metrics:**
- `http.request.duration_ms` - API response time
- `llm.duration_ms` - LLM API call latency
- `llm.tokens.in/out` - Token usage per request

**System Metrics:**
- `rate_limit.checks` - Rate limit checks
- `circuit_breaker.state` - Circuit breaker state
- `cache.accesses` - Cache hits/misses

### Quality Gates

Default regression gates:
- ✅ Grounding Score >= 0.90
- ✅ Faithfulness >= 0.85
- ✅ Context Recall >= 0.80
- ✅ Answer Relevancy >= 0.80
- ✅ Hallucination Rate <= 0.05 (5%)
- ✅ Pass Rate >= 0.95

### Dashboard Access

1. **Prometheus:**
   - URL: http://localhost:9090
   - Query metrics: `rate(http_requests_total[5m])`
   - Explore evaluation metrics

2. **Grafana:**
   - URL: http://localhost:3000
   - Default login: admin / (password from .env)
   - Pre-built dashboards:
     - Evaluation Quality
     - API Performance
     - System Health

## Troubleshooting

### Services Won't Start

```bash
# Check Docker daemon
docker ps

# View detailed logs
docker-compose -f docker/docker-compose-prod.yml logs

# Rebuild images
docker-compose -f docker/docker-compose-prod.yml build --no-cache

# Force recreate
docker-compose -f docker/docker-compose-prod.yml down -v
docker-compose -f docker/docker-compose-prod.yml up -d
```

### Database Connection Issues

```bash
# Check PostgreSQL health
docker-compose -f docker/docker-compose-prod.yml exec postgres pg_isready

# View PostgreSQL logs
docker-compose -f docker/docker-compose-prod.yml logs postgres

# Reset database (WARNING: deletes data)
docker-compose -f docker/docker-compose-prod.yml exec postgres psql -U news_user -d personalized_brief -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
```

### Redis Connection Issues

```bash
# Check Redis health
docker-compose -f docker/docker-compose-prod.yml exec redis redis-cli ping

# Clear cache
docker-compose -f docker/docker-compose-prod.yml exec redis redis-cli FLUSHALL
```

### API Not Responding

```bash
# Check app health
curl http://localhost:8080/health

# View app logs
docker-compose -f docker/docker-compose-prod.yml logs app

# Check resource usage
docker stats
```

## Maintenance

### Daily

- Monitor dashboard for gate violations
- Check error rates in logs
- Verify backups running

### Weekly

- Review evaluation metrics trends
- Check vector store size (Chroma)
- Analyze performance metrics

### Monthly

- Prune old evaluation data
- Update dependencies
- Review security logs

## Backup & Recovery

### Backup PostgreSQL

```bash
docker-compose exec postgres pg_dump -U news_user personalized_brief > backup.sql
```

### Restore PostgreSQL

```bash
docker-compose exec -T postgres psql -U news_user personalized_brief < backup.sql
```

### Backup Redis

```bash
docker-compose exec redis redis-cli BGSAVE
docker cp personalized_brief_cache:/data/dump.rdb ./redis_backup.rdb
```

### Backup Chroma

```bash
docker cp personalized_brief_vectors:/chroma_data ./chroma_backup
```

## Performance Tuning

### Database Optimization

```sql
-- Create indexes for common queries
CREATE INDEX idx_articles_date ON articles(published_date DESC);
CREATE INDEX idx_chunks_article ON chunks(article_id);
CREATE INDEX idx_feedback_user ON feedback_events(user_id);
```

### Cache Strategy

- Embeddings cached by content hash
- Query results cached with 5-minute TTL
- Briefings cached by date

### Rate Limiting

Current limits:
- Global: 100 requests/sec
- Per-user: 10 requests/sec
- Daily quota: 1,000 requests/day

Adjust in `configs/app.yaml`

## Security Checklist

- [ ] API keys stored in environment (not in code)
- [ ] Database password changed from default
- [ ] Redis password configured
- [ ] HTTPS enabled in production
- [ ] Rate limiting configured
- [ ] Input validation enabled
- [ ] Security headers configured
- [ ] Logs monitored for anomalies

## Alerts & Notifications

### Critical Alerts (Immediate)
- Grounding score < 0.80
- Error rate > 10%
- Database down
- API response time > 5s

### Warning Alerts (Check)
- Hallucination rate > 5%
- Cache hit rate < 50%
- Circuit breaker open
- Rate limit violations > 100/hour

Configure alerts in Grafana → Alerting → Notification Channels

## Support

### Logs Location
- Application: `docker-compose logs app`
- Database: `docker-compose logs postgres`
- Cache: `docker-compose logs redis`
- Metrics: `docker-compose logs prometheus`

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
docker-compose -f docker/docker-compose-prod.yml up -d
```

### Health Endpoint

```bash
curl http://localhost:8080/health
# Response:
# {
#   "status": "healthy",
#   "services": {
#     "database": "healthy",
#     "cache": "healthy",
#     "vector_store": "healthy",
#     "openai": "healthy"
#   },
#   "timestamp": "2026-01-18T10:30:00Z"
# }
```

---

**Last Updated:** January 18, 2026
**Maintained By:** DevOps Team
