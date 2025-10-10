# Monitoring Runbook - Narrative Modeling App

**Version**: 1.0
**Last Updated**: 2025-10-09
**Maintained By**: Engineering Team

---

## Table of Contents

1. [Overview](#overview)
2. [Alert Response Procedures](#alert-response-procedures)
3. [Common Issues Troubleshooting](#common-issues-troubleshooting)
4. [Metric Interpretation Guide](#metric-interpretation-guide)
5. [Escalation Procedures](#escalation-procedures)
6. [Tools and Access](#tools-and-access)
7. [Appendix](#appendix)

---

## Overview

### Purpose
This runbook provides on-call engineers with standardized procedures for responding to monitoring alerts and troubleshooting issues in the Narrative Modeling App.

### Monitoring Stack
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization and dashboards
- **FastAPI Metrics**: Application instrumentation

### Dashboards
1. **System Health** (`system-health`) - Request latency, errors, throughput
2. **ML Operations** (`ml-operations`) - Training metrics, predictions, model performance
3. **Business Metrics** (`business-metrics`) - User activity, datasets, usage trends

### Alert Channels
- **Severity Levels**:
  - 🔴 **Critical** - Immediate action required (page on-call)
  - 🟡 **Warning** - Investigate within 15 minutes
  - 🟢 **Info** - Review during business hours

---

## Alert Response Procedures

### 🔴 CRITICAL: High 5xx Error Rate

**Alert**: `High 5xx Error Rate`
**Threshold**: >5 errors/second over 5 minutes
**Dashboard**: System Health
**Severity**: Critical

#### Immediate Actions (First 5 Minutes)

1. **Acknowledge Alert**
   ```bash
   # Access Grafana alert and acknowledge
   # Note: Document time of acknowledgment
   ```

2. **Assess Scope**
   - Open System Health dashboard
   - Check which endpoints are affected
   - Look at error rate graph - is it spiking or sustained?

3. **Check System Health**
   ```bash
   # SSH to production server
   ssh production-server

   # Check service status
   docker ps
   docker logs narrative-backend --tail=100

   # Check system resources
   top
   df -h
   free -m
   ```

4. **Identify Error Patterns**
   ```bash
   # Review recent logs for error patterns
   docker logs narrative-backend --since=10m | grep "ERROR"

   # Check for common errors:
   # - Database connection errors
   # - External API timeouts (OpenAI, S3)
   # - Memory errors (OOM)
   # - Unhandled exceptions
   ```

#### Investigation (Minutes 5-15)

1. **Check Dependencies**
   ```bash
   # MongoDB connectivity
   docker exec narrative-mongodb-prod mongosh --eval "db.adminCommand('ping')"

   # Redis connectivity
   docker exec narrative-redis-prod redis-cli ping

   # S3/LocalStack (if applicable)
   curl http://localhost:4566/_localstack/health
   ```

2. **Review Recent Deployments**
   ```bash
   # Check git log for recent changes
   git log --since="1 hour ago" --oneline

   # Check deployment history
   kubectl get pods -n production --sort-by=.metadata.creationTimestamp
   ```

3. **Analyze Error Details**
   - Review stack traces in logs
   - Check Sentry/error tracking (if configured)
   - Look for common error types

#### Resolution Actions

**Common Causes & Fixes**:

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Database connection pool exhausted | `pymongo.errors.ServerSelectionTimeoutError` | Restart backend service, increase pool size |
| OpenAI API rate limits | `openai.error.RateLimitError` | Implement exponential backoff, check API quota |
| Memory leak | Gradual increase in 5xx, high memory usage | Restart service, investigate memory profiling |
| S3 access issues | `botocore.exceptions.ClientError` | Verify S3 credentials, check bucket permissions |
| Code bug in recent deployment | Errors specific to new endpoint | Rollback to previous version |

**Rollback Procedure**:
```bash
# If recent deployment caused issue
git checkout <previous-stable-commit>
docker compose -f docker-compose.prod.yml up -d --build

# Or use Kubernetes rollback
kubectl rollout undo deployment/narrative-backend -n production
```

#### Post-Incident

1. **Verify Resolution**
   - Error rate returns to <1/sec
   - System Health dashboard shows green
   - No new alerts firing

2. **Document Incident**
   - Create incident report in incident tracker
   - Note root cause, resolution, time to recovery
   - Update runbook if new issue pattern discovered

---

### 🟡 WARNING: High Prediction Latency

**Alert**: `High Prediction Latency`
**Threshold**: p99 >1 second over 5 minutes
**Dashboard**: ML Operations
**Severity**: Warning

#### Immediate Actions (First 5 Minutes)

1. **Check Current Latency**
   - Open ML Operations dashboard
   - Review prediction latency panel (p50, p95, p99)
   - Identify which models are slow

2. **Assess Impact**
   ```bash
   # Check active prediction requests
   curl http://localhost:8000/metrics | grep ml_prediction_latency

   # Look for patterns by model_type
   ```

#### Investigation (Minutes 5-15)

1. **Model Performance Analysis**
   - Check if specific model types are slow (random_forest, neural_network, etc.)
   - Review model size and complexity
   - Check if model loading is the bottleneck

2. **Resource Check**
   ```bash
   # CPU usage
   docker stats narrative-backend --no-stream

   # Memory usage
   docker exec narrative-backend ps aux | grep python
   ```

3. **Database Query Performance**
   ```bash
   # Check for slow MongoDB queries
   docker exec narrative-mongodb-prod mongosh --eval "db.currentOp()"

   # Look for long-running operations
   ```

#### Resolution Actions

**Common Causes & Fixes**:

| Cause | Symptoms | Fix |
|-------|----------|-----|
| Model not cached | First prediction slow | Implement model caching/preloading |
| Large feature sets | Consistent high latency | Feature selection, dimensionality reduction |
| Database bottleneck | Latency spikes correlate with DB queries | Add indexes, query optimization |
| CPU contention | High CPU usage | Scale up resources, optimize inference code |
| Memory swapping | System memory >90% | Increase memory, reduce model count |

**Quick Fixes**:
```bash
# Restart backend to clear any memory issues
docker compose -f docker-compose.prod.yml restart backend

# Clear Redis cache if stale data suspected
docker exec narrative-redis-prod redis-cli FLUSHDB

# Check model cache status
curl http://localhost:8000/api/v1/models/cache/status
```

---

### 🟡 WARNING: High Request Latency

**Alert**: Manual monitoring (no alert configured, but should be watched)
**Threshold**: p95 >2 seconds sustained
**Dashboard**: System Health
**Severity**: Warning

#### Immediate Actions

1. **Identify Slow Endpoints**
   - Review Request Latency panel
   - Sort by endpoint to find slowest paths
   - Check if latency is across all endpoints or specific ones

2. **Check Dependencies**
   ```bash
   # OpenAI API latency
   time curl -X POST https://api.openai.com/v1/chat/completions \
     -H "Authorization: Bearer $OPENAI_API_KEY" \
     -d '{"model":"gpt-3.5-turbo","messages":[{"role":"user","content":"test"}]}'

   # S3 access latency
   time aws s3 ls s3://your-bucket/ --endpoint-url=http://localhost:4566
   ```

3. **Review Recent Traffic Patterns**
   - Check Request Throughput panel
   - Look for unusual spikes in traffic
   - Verify auto-scaling is functioning

#### Investigation

1. **Slow Query Analysis**
   ```bash
   # MongoDB slow queries (>100ms)
   docker exec narrative-mongodb-prod mongosh --eval "db.setProfilingLevel(1, 100)"
   docker exec narrative-mongodb-prod mongosh --eval "db.system.profile.find().sort({millis:-1}).limit(5).pretty()"
   ```

2. **Application Profiling**
   ```bash
   # Enable Python profiling (if instrumented)
   curl -X POST http://localhost:8000/debug/profiling/enable

   # Generate profile report after 5 minutes
   curl http://localhost:8000/debug/profiling/report
   ```

---

## Common Issues Troubleshooting

### Issue: Application Won't Start

**Symptoms**:
- Container crashes immediately
- Backend service unavailable
- Health check failing

**Diagnostic Steps**:
```bash
# Check container logs
docker logs narrative-backend --tail=100

# Check container status
docker ps -a | grep narrative-backend

# Verify environment variables
docker exec narrative-backend env | grep -E "MONGODB|OPENAI|AWS"
```

**Common Causes**:

1. **Missing Environment Variables**
   ```bash
   # Verify .env file exists
   ls -la /path/to/backend/.env

   # Check required variables
   grep -E "MONGODB_URI|OPENAI_API_KEY|AWS_ACCESS_KEY_ID" .env
   ```
   **Fix**: Update `.env` file with required variables

2. **Database Connection Failure**
   ```bash
   # Test MongoDB connection
   docker exec narrative-mongodb-prod mongosh \
     --eval "db.adminCommand('ping')" \
     mongodb://localhost:27017/narrative_modeling
   ```
   **Fix**: Ensure MongoDB is running, check network connectivity

3. **Port Conflicts**
   ```bash
   # Check if port 8000 is already in use
   lsof -i :8000
   ```
   **Fix**: Stop conflicting process or change backend port

---

### Issue: MongoDB Connection Errors

**Symptoms**:
- `pymongo.errors.ServerSelectionTimeoutError`
- `pymongo.errors.ConnectionFailure`
- Application logs show MongoDB errors

**Diagnostic Steps**:
```bash
# Check MongoDB status
docker ps | grep mongodb
docker logs narrative-mongodb-prod --tail=50

# Test connection
docker exec narrative-mongodb-prod mongosh \
  --eval "db.adminCommand('ping')"

# Check replica set status (if applicable)
docker exec narrative-mongodb-prod mongosh \
  --eval "rs.status()"
```

**Common Causes**:

1. **MongoDB Not Running**
   ```bash
   docker compose -f docker-compose.prod.yml up -d mongodb
   ```

2. **Network Issues**
   ```bash
   # Check Docker network
   docker network inspect narrative-network

   # Verify backend can reach MongoDB
   docker exec narrative-backend ping mongodb -c 3
   ```

3. **Connection Pool Exhausted**
   - **Symptom**: Works initially, then fails under load
   - **Fix**: Increase `maxPoolSize` in MongoDB connection URI
   ```python
   # In backend config
   MONGODB_URI = "mongodb://localhost:27017/?maxPoolSize=100&minPoolSize=10"
   ```

4. **Authentication Failure**
   ```bash
   # Verify MongoDB credentials
   docker exec narrative-mongodb-prod mongosh \
     -u "$MONGO_USER" -p "$MONGO_PASSWORD" \
     --eval "db.adminCommand('ping')"
   ```

---

### Issue: Redis Cache Unavailable

**Symptoms**:
- Cache misses
- `redis.exceptions.ConnectionError`
- Degraded performance

**Diagnostic Steps**:
```bash
# Check Redis status
docker ps | grep redis
docker logs narrative-redis-prod --tail=50

# Test Redis connectivity
docker exec narrative-redis-prod redis-cli ping

# Check Redis memory usage
docker exec narrative-redis-prod redis-cli INFO memory
```

**Common Causes**:

1. **Redis Not Running**
   ```bash
   docker compose -f docker-compose.prod.yml up -d redis
   ```

2. **Redis Out of Memory**
   ```bash
   # Check maxmemory
   docker exec narrative-redis-prod redis-cli CONFIG GET maxmemory

   # Clear cache if needed
   docker exec narrative-redis-prod redis-cli FLUSHDB
   ```
   **Fix**: Increase Redis memory limit or implement eviction policy

3. **Too Many Connections**
   ```bash
   # Check connection count
   docker exec narrative-redis-prod redis-cli INFO clients
   ```
   **Fix**: Increase `maxclients` in Redis config or implement connection pooling

---

### Issue: S3/LocalStack Access Errors

**Symptoms**:
- File upload failures
- `botocore.exceptions.ClientError`
- Timeout errors on S3 operations

**Diagnostic Steps**:
```bash
# Check LocalStack status (development)
curl http://localhost:4566/_localstack/health

# Test S3 access with AWS CLI
aws s3 ls s3://narrative-uploads/ --endpoint-url=http://localhost:4566

# Check S3 logs
docker logs narrative-localstack-dev --tail=50
```

**Common Causes**:

1. **Bucket Doesn't Exist**
   ```bash
   # List buckets
   aws s3 ls --endpoint-url=http://localhost:4566

   # Create bucket
   aws s3 mb s3://narrative-uploads --endpoint-url=http://localhost:4566
   ```

2. **Invalid Credentials**
   ```bash
   # Verify AWS credentials in backend
   docker exec narrative-backend env | grep AWS

   # Test credentials
   aws sts get-caller-identity --endpoint-url=http://localhost:4566
   ```

3. **Network Issues**
   ```bash
   # Test connectivity from backend to LocalStack
   docker exec narrative-backend curl http://localstack:4566/_localstack/health
   ```

---

### Issue: OpenAI API Failures

**Symptoms**:
- `openai.error.RateLimitError`
- `openai.error.Timeout`
- AI analysis workflows failing

**Diagnostic Steps**:
```bash
# Check OpenAI API key
docker exec narrative-backend env | grep OPENAI_API_KEY

# Test API connectivity
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer $OPENAI_API_KEY"

# Check recent API usage
curl https://api.openai.com/v1/usage \
  -H "Authorization: Bearer $OPENAI_API_KEY"
```

**Common Causes**:

1. **Rate Limit Exceeded**
   - **Symptom**: `RateLimitError` in logs
   - **Fix**: Implement exponential backoff, reduce request frequency
   ```python
   # In code, implement retry logic
   @retry(wait=wait_exponential(multiplier=1, min=4, max=60))
   def call_openai_api():
       # API call here
       pass
   ```

2. **API Key Invalid or Expired**
   ```bash
   # Verify API key format (starts with sk-)
   echo $OPENAI_API_KEY | cut -c1-3
   ```
   **Fix**: Update API key in environment variables

3. **Quota Exceeded**
   - **Symptom**: 429 errors, quota exceeded messages
   - **Fix**: Upgrade OpenAI plan or reduce usage

4. **Timeout Issues**
   - **Fix**: Increase timeout in OpenAI client configuration
   ```python
   # In backend config
   openai.timeout = 60  # Increase from default
   ```

---

## Metric Interpretation Guide

### System Metrics

#### Request Latency (HTTP)

**Metric**: `http_request_duration_seconds`
**Type**: Histogram
**Labels**: `method`, `endpoint`, `status_code`

**Interpretation**:
- **p50 (median)**: Typical user experience
  - **Good**: <200ms
  - **Acceptable**: 200-500ms
  - **Poor**: >500ms

- **p95**: Experience for 95% of users
  - **Good**: <500ms
  - **Acceptable**: 500ms-1s
  - **Poor**: >1s

- **p99**: Experience for 99% of users (worst case)
  - **Good**: <1s
  - **Acceptable**: 1-2s
  - **Poor**: >2s

**What to Watch**:
- Sudden spikes indicate performance degradation
- Gradual increase may indicate memory leak or resource exhaustion
- High p99 with low p50 suggests occasional slow requests (cache misses, cold starts)

#### Request Throughput

**Metric**: `http_requests_total`
**Type**: Counter
**Labels**: `method`, `endpoint`, `status_code`

**Interpretation**:
- **Normal Range**: 10-100 req/sec for typical load
- **High Traffic**: >100 req/sec (may need scaling)
- **Low Traffic**: <5 req/sec (off-peak hours)

**What to Watch**:
- Sudden drops may indicate service outage or user issues
- Sudden spikes may indicate DDoS attack or legitimate traffic surge
- Compare with error rates - high traffic + high errors = system overload

#### Active Requests

**Metric**: `http_requests_active`
**Type**: Gauge
**Labels**: `method`, `endpoint`

**Interpretation**:
- **Normal**: 0-10 active requests
- **Busy**: 10-50 active requests
- **Overloaded**: >50 active requests (request queuing)

**What to Watch**:
- Steadily increasing value indicates requests not completing (deadlock, slow queries)
- High value with low throughput suggests all workers are blocked

#### Error Rates

**Metric**: `http_requests_total{status_code=~"5.."}`
**Type**: Counter
**Labels**: `method`, `endpoint`, `status_code`

**Interpretation**:
- **Healthy**: <0.1% error rate (1 in 1000 requests)
- **Warning**: 0.1-1% error rate
- **Critical**: >1% error rate

**Common Error Codes**:
- **500**: Internal server error (application bug)
- **502**: Bad gateway (backend unavailable)
- **503**: Service unavailable (overloaded, maintenance)
- **504**: Gateway timeout (slow backend)

---

### ML Metrics

#### Training Duration

**Metric**: `ml_training_duration_seconds`
**Type**: Histogram
**Labels**: `model_type`, `problem_type`

**Interpretation**:
- **Fast**: <10 seconds (small datasets, simple models)
- **Normal**: 10-300 seconds (typical workflows)
- **Slow**: >300 seconds (large datasets, complex models)

**What to Watch**:
- Compare by `model_type` to identify slow algorithms
- Increasing duration over time may indicate dataset growth
- Sudden spikes suggest resource contention or algorithmic issues

#### Prediction Latency

**Metric**: `ml_prediction_latency_seconds`
**Type**: Histogram
**Labels**: `model_type`, `model_id`

**Interpretation**:
- **Fast**: <10ms (real-time inference)
- **Acceptable**: 10-100ms (interactive applications)
- **Slow**: >100ms (may need optimization)

**What to Watch**:
- First prediction often slower (model loading)
- Compare by `model_type` to identify inefficient models
- High variance suggests caching issues or resource contention

#### Model Accuracy

**Metric**: `ml_model_accuracy`
**Type**: Gauge
**Labels**: `model_id`, `model_type`, `metric_name`

**Interpretation**:
- **Classification**: 0.7-0.95 typical range
- **Regression**: R² score, aim for >0.7
- **Domain-specific**: Depends on problem complexity

**What to Watch**:
- Sudden accuracy drop indicates data drift or model degradation
- Compare across model versions to track improvements
- Low accuracy suggests need for retraining or feature engineering

#### Dataset Size

**Metric**: `ml_dataset_size_rows`
**Type**: Histogram
**Labels**: `dataset_id`

**Interpretation**:
- **Small**: <1,000 rows
- **Medium**: 1,000-100,000 rows
- **Large**: >100,000 rows

**What to Watch**:
- Increasing dataset sizes require resource scaling
- Very small datasets may produce unreliable models
- Unusually large datasets may indicate data quality issues (duplicates)

---

### Business Metrics

#### Active Users

**Metric**: `business_active_users`
**Type**: Gauge
**Labels**: `time_window` (day, week, month)

**Interpretation**:
- **DAU** (Daily Active Users): Current day engagement
- **WAU** (Weekly Active Users): Weekly engagement
- **MAU** (Monthly Active Users): Monthly reach

**What to Watch**:
- Sudden drops may indicate user-facing issues
- Compare DAU/MAU ratio for engagement trends (healthy: >20%)
- Seasonal patterns (weekdays vs weekends)

#### Datasets Created

**Metric**: `business_datasets_created_total`
**Type**: Counter
**Labels**: `user_id`

**Interpretation**:
- **Growth Indicator**: Increasing trend = user adoption
- **User Segmentation**: Identify power users vs occasional users

**What to Watch**:
- Spikes may indicate successful marketing campaigns
- Drops may indicate UI issues or user churn
- Per-user trends for retention analysis

#### Models Trained

**Metric**: `business_models_trained_total`
**Type**: Counter
**Labels**: `model_type`, `user_id`

**Interpretation**:
- **Platform Usage**: Core value delivery metric
- **Model Type Distribution**: Which algorithms are popular

**What to Watch**:
- Increasing trend = successful user workflows
- Preferred model types guide feature development
- Drop in training volume may indicate workflow friction

#### Predictions Made

**Metric**: `business_predictions_made_total`
**Type**: Counter
**Labels**: `model_id`

**Interpretation**:
- **Model Utilization**: Are trained models being used?
- **Production Value**: Predictions = real business impact

**What to Watch**:
- High predictions per model = valuable models
- Low predictions may indicate poor model quality
- Prediction volume guides infrastructure scaling

---

## Escalation Procedures

### Escalation Matrix

| Severity | Response Time | Escalation Path | Notification |
|----------|--------------|-----------------|--------------|
| 🔴 Critical | Immediate | → On-Call Engineer → Senior Engineer → Engineering Manager → CTO | PagerDuty, Slack |
| 🟡 Warning | 15 minutes | → On-Call Engineer → Senior Engineer | Slack |
| 🟢 Info | 2 hours | → On-Call Engineer | Email |

### Escalation Decision Tree

```
Incident Detected
├─ Can you resolve in 30 minutes?
│  ├─ Yes → Resolve and document
│  └─ No → Escalate to Senior Engineer
├─ Is production completely down?
│  ├─ Yes → CRITICAL: Page all on-call + manager
│  └─ No → Continue troubleshooting
├─ Is data at risk?
│  ├─ Yes → CRITICAL: Page security team
│  └─ No → Continue with standard procedure
└─ Is it affecting >50% of users?
   ├─ Yes → WARNING: Notify manager
   └─ No → Continue monitoring
```

### Escalation Contacts

**Primary On-Call Engineer**:
- Slack: `@on-call-engineer`
- PagerDuty: Automatic rotation
- Phone: On-call rotation schedule

**Senior Engineer (Level 2)**:
- Slack: `@senior-backend-engineer`
- Email: senior-engineer@company.com
- Escalation after: 30 minutes of L1 troubleshooting

**Engineering Manager (Level 3)**:
- Slack: `@engineering-manager`
- Email: eng-manager@company.com
- Phone: Emergency only
- Escalation after: 1 hour of incident or production-wide outage

**Security Team**:
- Slack: `@security-team`
- Email: security@company.com
- Escalation for: Data breaches, unauthorized access, security vulnerabilities

**CTO (Level 4)**:
- Email: cto@company.com
- Phone: Emergency only
- Escalation for: Complete production outage >2 hours, major security incident

### Incident Communication

**Internal Communication**:
```
#incident-response Slack Channel

Initial Alert:
🚨 INCIDENT: [Brief description]
Severity: [Critical/Warning/Info]
Impact: [User impact description]
Started: [Time]
Acknowledged by: [Your name]
Status: Investigating

Updates (every 15 minutes):
⏱️ UPDATE: [Progress summary]
Current action: [What you're doing]
Next steps: [What's next]

Resolution:
✅ RESOLVED: [Summary]
Root cause: [Brief explanation]
Resolution: [What fixed it]
Duration: [Total time]
Post-mortem: [Link to incident report]
```

**User Communication** (if needed):
```
Status Page Update:

Title: [Service Degradation/Outage]
Status: Investigating/Identified/Monitoring/Resolved
Description: We are experiencing [issue description].
Impact: [What users are experiencing]
Update: [Current status and progress]
```

---

## Tools and Access

### Grafana Access

**URL**: `http://localhost:3000` (development)
**Production URL**: `https://grafana.narrativemodeling.com`

**Login**:
```bash
Username: admin
Password: [Check password manager or .env]
```

**Key Dashboards**:
- System Health: http://localhost:3000/d/system-health
- ML Operations: http://localhost:3000/d/ml-operations
- Business Metrics: http://localhost:3000/d/business-metrics

### Prometheus Access

**URL**: `http://localhost:9090` (development)

**Useful Queries**:
```promql
# Current error rate
rate(http_requests_total{status_code=~"5.."}[5m])

# Request latency p95
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le, endpoint))

# Active requests
sum(http_requests_active)

# Training jobs in last hour
increase(business_models_trained_total[1h])
```

### Application Logs

**Docker Logs**:
```bash
# Backend logs (last 100 lines)
docker logs narrative-backend --tail=100 --follow

# MongoDB logs
docker logs narrative-mongodb-prod --tail=50

# Redis logs
docker logs narrative-redis-prod --tail=50

# Filter logs by severity
docker logs narrative-backend 2>&1 | grep ERROR
docker logs narrative-backend 2>&1 | grep WARNING
```

**Log Locations** (if not using Docker):
```
/var/log/narrative-modeling/backend.log
/var/log/narrative-modeling/access.log
/var/log/narrative-modeling/error.log
```

### Database Access

**MongoDB**:
```bash
# Connect to production MongoDB
docker exec -it narrative-mongodb-prod mongosh

# Run queries
use narrative_modeling
db.user_data.find().limit(5)
db.trained_model.countDocuments()

# Check slow queries
db.system.profile.find().sort({millis:-1}).limit(5)
```

**Redis**:
```bash
# Connect to Redis CLI
docker exec -it narrative-redis-prod redis-cli

# Check keys
KEYS *
GET user:123:session

# Monitor commands in real-time
MONITOR
```

### Health Check Endpoints

```bash
# Backend health check
curl http://localhost:8000/health

# Detailed health with dependencies
curl http://localhost:8000/health/detailed

# Prometheus metrics
curl http://localhost:8000/metrics

# OpenAPI docs (verify API is up)
curl http://localhost:8000/docs
```

---

## Appendix

### A. Metric Quick Reference

| Metric Name | Type | Purpose | Alert Threshold |
|-------------|------|---------|----------------|
| `http_request_duration_seconds` | Histogram | Request latency | p95 > 2s |
| `http_requests_total` | Counter | Request count | N/A |
| `http_requests_active` | Gauge | Concurrent requests | >100 |
| `ml_training_duration_seconds` | Histogram | Training time | p95 > 600s |
| `ml_prediction_latency_seconds` | Histogram | Inference time | p99 > 1s |
| `ml_model_accuracy` | Gauge | Model quality | <0.6 |
| `business_active_users` | Gauge | User engagement | Drop >20% |
| `business_models_trained_total` | Counter | Platform usage | N/A |

### B. Common Prometheus Queries

```promql
# Error rate percentage
sum(rate(http_requests_total{status_code=~"5.."}[5m])) /
sum(rate(http_requests_total[5m])) * 100

# Requests per endpoint (top 10)
topk(10, sum(rate(http_requests_total[5m])) by (endpoint))

# Average training duration by model type
avg(ml_training_duration_seconds) by (model_type)

# Prediction throughput
sum(rate(business_predictions_made_total[5m]))

# Daily active users growth
increase(business_active_users{time_window="day"}[24h])
```

### C. Service Dependencies

```
Narrative Modeling Backend
├── MongoDB (database)
│   ├── Port: 27017
│   └── Health: mongosh --eval "db.adminCommand('ping')"
├── Redis (cache)
│   ├── Port: 6379
│   └── Health: redis-cli ping
├── S3/LocalStack (storage)
│   ├── Port: 4566
│   └── Health: curl /_localstack/health
└── OpenAI API (AI processing)
    ├── URL: api.openai.com
    └── Health: curl /v1/models
```

### D. Incident Post-Mortem Template

```markdown
# Incident Post-Mortem: [Incident Name]

**Date**: [Date]
**Duration**: [Start time - End time]
**Severity**: [Critical/Warning/Info]
**Responders**: [Names]

## Summary
[2-3 sentence summary of what happened]

## Impact
- Users affected: [Number/percentage]
- Services impacted: [List]
- Data loss: [Yes/No - details]

## Timeline
- [Time]: Incident detected
- [Time]: Initial response started
- [Time]: Root cause identified
- [Time]: Fix deployed
- [Time]: Incident resolved

## Root Cause
[Detailed explanation of why it happened]

## Resolution
[What was done to fix it]

## Prevention
- [ ] Short-term: [Immediate fixes to prevent recurrence]
- [ ] Long-term: [Architectural or process improvements]

## Action Items
- [ ] [Action item 1] - Owner: [Name] - Due: [Date]
- [ ] [Action item 2] - Owner: [Name] - Due: [Date]

## Lessons Learned
[Key takeaways and improvements to runbook/monitoring]
```

### E. Emergency Commands Cheat Sheet

```bash
# Quick service restart
docker compose -f docker-compose.prod.yml restart backend

# Emergency rollback
git checkout <previous-commit>
docker compose up -d --build

# Clear all Redis cache
docker exec narrative-redis-prod redis-cli FLUSHALL

# Force MongoDB repair (DANGER - only if corrupt)
docker exec narrative-mongodb-prod mongosh --eval "db.repairDatabase()"

# Check disk space (if running out)
df -h
docker system prune -f

# Kill hanging processes
docker exec narrative-backend pkill -9 python

# Export Prometheus data for analysis
curl http://localhost:9090/api/v1/query?query=http_requests_total > metrics.json
```

---

**Document Version**: 1.0
**Last Review**: 2025-10-09
**Next Review**: 2025-11-09 (monthly)
**Maintained By**: Engineering Team

For questions or updates to this runbook, contact the Engineering Manager or submit a PR to the repository.
