# Issue #85 — Deployment monitoring dashboard

**Scope:** Make the existing monitoring dashboard work for *deployed* models by closing the real
gaps, not rebuilding infrastructure. The frontend already calls real endpoints; the backend
in-memory `prediction_log` + `/monitoring` routes already exist. We extend them.

## Adapted plan (lazy — reuse existing in-memory log + `/monitoring` router)

### Backend
1. Log predictions + errors from production serving path (production.py:295 TODO never logs).
   Call PredictionMonitoringService.log_prediction per record on success (best-effort); log an
   error event on the except path before re-raising the 500.
2. Real error rate + latency percentiles in prediction_monitoring.py. Add optional `error` field;
   get_model_metrics returns real error_rate + p50/p90/p95/p99. Readers exclude error entries.
3. Usage timeline: get_usage_timeline(model_id, hours, bucket_minutes) -> buckets for charts.
4. Health + error-rate alerts: get_health(model_id) -> status/error_rate/latency/alerts[].
5. Endpoints on existing /monitoring router: GET .../{id}/timeline, GET .../{id}/health; extend
   /metrics with percentiles + error fields.

### Frontend
6. Enhance app/monitor/[id]/page.tsx: health badge + alerts, percentiles, LineChart timeline,
   BarChart distribution. Add getUsageTimeline/getDeploymentHealth + fields to production.ts.

### Tests
7. Backend unit (percentiles/error_rate/timeline/health/alerts) + production_predict logging +
   endpoint tests. Frontend detail-page rendering + service methods.

## Acceptance criteria
- [ ] Real-time request monitoring per deployment (count, latency percentiles, error rate)
- [ ] Prediction distribution tracking (already exists - wire to BarChart)
- [ ] Health status + usage analytics over time
- [ ] Error-rate alerts
- [ ] Wire app/monitor/page.tsx to real data (overview already real - enhance detail page)

## Deviations from Traycer plan (over-scoped / stale)
- In-memory log reused, NO MongoDB time-series collections (header: "Beta can rely on basic
  logging"). Persistence-across-restart = documented beta limitation; upgrade path = swap
  prediction_log for a Beanie time-series collection behind the same service API.
- No cost tracking (CostRecord, /costs) - not in AC.
- No anomaly detection / drift expansion - not in AC.
- No alert-rule CRUD / notification channels - "error-rate alerts" met by threshold alerts in health.
- No parallel /deployments router - a deployed model IS an MLModel keyed by model_id (#84); extend
  /monitoring/models/{id}/...
