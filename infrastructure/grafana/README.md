# Grafana Dashboards - Narrative Modeling App

Comprehensive monitoring dashboards for the Narrative Modeling App using Grafana and Prometheus.

## 📊 Overview

This monitoring stack provides real-time visibility into:
- **System Health**: Request latency, errors, throughput, and active requests
- **ML Operations**: Training metrics, prediction performance, and model accuracy
- **Business Metrics**: User activity, dataset creation, model training, and prediction volume

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose installed
- Backend application running with `/metrics` endpoint exposed
- Ports 3001 (Grafana) and 9090 (Prometheus) available

### Setup

1. **Start the monitoring stack:**

```bash
cd infrastructure/grafana
docker-compose up -d
```

2. **Access Grafana:**

Open your browser to http://localhost:3001

- **Username**: `admin`
- **Password**: `admin` (you'll be prompted to change on first login)

3. **Access Prometheus:**

Open your browser to http://localhost:9090

### Verify Setup

1. Check Prometheus is scraping metrics:
   - Go to http://localhost:9090/targets
   - Verify `narrative-backend` target is UP

2. Check Grafana dashboards:
   - Log into Grafana at http://localhost:3001
   - Navigate to Dashboards → Browse
   - You should see 3 dashboards:
     - System Health - Narrative Modeling App
     - ML Operations - Narrative Modeling App
     - Business Metrics - Narrative Modeling App

## 📈 Dashboards

### 1. System Health Dashboard

**UID**: `system-health`
**Refresh**: Every 30 seconds
**Time Range**: Last 1 hour (default)

**Panels:**
- **Request Latency (p50, p95, p99)**: Track API response times
- **Request Throughput**: Requests per second by endpoint
- **Error Rate (5xx)**: Server errors by endpoint (with alert)
- **Client Errors (4xx)**: Client errors by status code
- **Active Requests**: Current concurrent requests
- **HTTP Status Codes**: Distribution of all status codes

**Alerts:**
- High 5xx Error Rate: Triggers when > 5 errors/sec for 5 minutes

### 2. ML Operations Dashboard

**UID**: `ml-operations`
**Refresh**: Every 30 seconds
**Time Range**: Last 6 hours (default)

**Panels:**
- **Training Duration by Model Type**: p50 and p95 training times
- **Training Jobs Over Time**: Training job volume by model type
- **Prediction Latency (p50, p95, p99)**: Inference response times
- **Prediction Throughput by Model**: Predictions/sec by model type
- **Model Accuracy Trends**: Model performance over time
- **Dataset Size Distribution**: Dataset size histogram
- **Summary Statistics**: 24h totals and averages

**Alerts:**
- High Prediction Latency: Triggers when p99 > 1 second for 5 minutes

### 3. Business Metrics Dashboard

**UID**: `business-metrics`
**Refresh**: Every 30 seconds
**Time Range**: Last 7 days (default)

**Panels:**
- **Active Users**: DAU, WAU, MAU metrics
- **Datasets Created Over Time**: Dataset creation trends
- **Top Dataset Creators**: Most active users (last 24h)
- **Models Trained Over Time**: Model training volume by type
- **Model Type Distribution**: Pie chart of model types (7d)
- **Predictions Made Over Time**: Prediction volume trends
- **Top Models by Predictions**: Most used models (last 24h)
- **Summary KPIs**: 7-day totals and growth rate

## 🔧 Configuration

### Prometheus Configuration

**File**: `prometheus.yml`

Scrapes metrics from the backend at `host.docker.internal:8000/metrics` every 10 seconds.

To change scrape interval or add more targets, edit `prometheus.yml` and restart:

```bash
docker-compose restart prometheus
```

### Grafana Datasources

**File**: `datasources.yml`

Configured to use Prometheus at `http://prometheus:9090`.

### Dashboard Provisioning

**File**: `dashboards.yml`

Auto-provisions dashboards from the `dashboards/` directory on startup.

## 📝 Customization

### Modifying Dashboards

1. **Through Grafana UI** (recommended for prototyping):
   - Edit dashboards in Grafana UI
   - Export as JSON (Share → Export → Save to file)
   - Replace files in `dashboards/` directory
   - Restart Grafana to reload

2. **Direct JSON editing**:
   - Edit JSON files in `dashboards/` directory
   - Restart Grafana: `docker-compose restart grafana`

### Adding New Panels

1. Open dashboard in Grafana
2. Click "Add" → "Visualization"
3. Select Prometheus datasource
4. Enter PromQL query (see examples below)
5. Configure visualization type and options
6. Save and export

### PromQL Query Examples

```promql
# Average request latency (p95)
histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))

# Error rate by endpoint
sum(rate(http_requests_total{status_code=~"5.."}[5m])) by (endpoint)

# Active training jobs
sum(rate(ml_training_duration_seconds_count[5m]))

# Model accuracy
ml_model_accuracy{metric_name="accuracy"}

# Active users (daily)
business_active_users{time_window="day"}

# Dataset creation rate
sum(rate(business_datasets_created_total[1h]))
```

## 🚨 Alerts

### Configured Alerts

1. **High 5xx Error Rate**
   - Condition: > 5 errors/sec for 5 minutes
   - Dashboard: System Health
   - Action: Review error logs and check circuit breaker status

2. **High Prediction Latency**
   - Condition: p99 > 1 second for 5 minutes
   - Dashboard: ML Operations
   - Action: Check model size, optimize inference, review resource usage

### Adding More Alerts

1. Edit dashboard panel
2. Go to "Alert" tab
3. Configure alert conditions
4. Set notification channels (requires Grafana notification setup)

## 🔍 Troubleshooting

### Prometheus Not Scraping Backend

**Check backend is running:**
```bash
curl http://localhost:8000/metrics
```

**Check Prometheus targets:**
- Go to http://localhost:9090/targets
- Verify `narrative-backend` target status

**Common issues:**
- Backend not exposing `/metrics` endpoint
- Firewall blocking port 8000
- Wrong hostname in `prometheus.yml` (use `host.docker.internal` on Docker Desktop)

### Dashboards Not Loading

**Check Grafana logs:**
```bash
docker-compose logs grafana
```

**Verify dashboard files:**
```bash
ls -la dashboards/
```

**Restart Grafana:**
```bash
docker-compose restart grafana
```

### No Data in Panels

**Check Prometheus has data:**
- Go to http://localhost:9090/graph
- Run query: `up{job="narrative-backend"}`
- Should return `1` if scraping successfully

**Check time range:**
- Ensure dashboard time range covers period where data exists
- Try "Last 24 hours" if unsure

**Verify metrics exist:**
- Check `/metrics` endpoint returns expected metrics
- Confirm metric names match PromQL queries

## 📦 Docker Commands

```bash
# Start monitoring stack
docker-compose up -d

# Stop monitoring stack
docker-compose down

# View logs
docker-compose logs -f

# Restart specific service
docker-compose restart grafana
docker-compose restart prometheus

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

## 🔐 Security

### Production Recommendations

1. **Change default passwords:**
   - Update `GF_SECURITY_ADMIN_PASSWORD` in `docker-compose.yml`
   - Use strong passwords

2. **Enable authentication:**
   - Configure OAuth or LDAP in Grafana
   - Disable anonymous access

3. **Secure Prometheus:**
   - Enable authentication
   - Use TLS for scraping
   - Configure network policies

4. **Network isolation:**
   - Use internal Docker networks
   - Don't expose ports publicly
   - Use reverse proxy with authentication

## 📚 Resources

- [Grafana Documentation](https://grafana.com/docs/grafana/latest/)
- [Prometheus Query Language](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/)
- [Grafana Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/best-practices-for-creating-dashboards/)

## 🆘 Support

For issues or questions:
1. Check Troubleshooting section above
2. Review Prometheus and Grafana logs
3. Consult project documentation
4. Contact the development team

---

**Last Updated**: 2025-10-09
**Maintained By**: Development team
**Version**: 1.0
