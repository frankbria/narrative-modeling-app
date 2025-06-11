"""
Tests for Monitoring Service
"""

import pytest
import time
from unittest.mock import patch
from app.services.monitoring import ApplicationMonitor


class TestApplicationMonitor:
    """Test cases for monitoring functionality"""
    
    def setup_method(self):
        self.monitor = ApplicationMonitor()
    
    def test_increment_counter(self):
        """Test incrementing counters"""
        metric_name = "test.counter"
        
        # Increment counter
        self.monitor.increment(metric_name, 1)
        self.monitor.increment(metric_name, 2)
        
        # Check counters directly
        assert self.monitor.counters[metric_name] == 3
    
    def test_record_api_call(self):
        """Test recording API calls"""
        endpoint = "/api/test"
        method = "GET"
        status_code = 200
        duration = 0.5
        
        self.monitor.record_api_call(endpoint, method, status_code, duration)
        
        # Check that timers and counters were updated
        assert self.monitor.counters["api.requests_total"] == 1
        assert len(self.monitor.timers["api.response_time"]) == 1
        assert self.monitor.response_times[endpoint] == [duration]
    
    def test_record_upload_metrics(self):
        """Test recording upload metrics"""
        file_size = 1024 * 1024  # 1MB
        upload_time = 2.5
        has_pii = True
        
        self.monitor.record_upload_event("user123", "test.csv", file_size, has_pii, True, upload_time)
        
        metrics = self.monitor.get_health_metrics()
        assert metrics["upload_stats"]["total_uploads"] == 1
        assert metrics["upload_stats"]["total_bytes"] == file_size
        assert metrics["upload_stats"]["pii_detections"] == 1
    
    def test_record_security_event(self):
        """Test recording security events"""
        event_type = "pii_detected"
        user_id = "user123"
        details = {"column": "email", "type": "email"}
        severity = "warning"
        
        self.monitor.record_security_event(event_type, user_id, details, severity)
        
        # Check that security event was recorded
        assert len(self.monitor.security_events) == 1
        assert self.monitor.counters[f"security.{event_type}"] == 1
    
    def test_error_rate_calculation(self):
        """Test error rate calculation"""
        # Record some successful calls
        for i in range(8):
            self.monitor.record_api_call("/api/test", "GET", 200, 0.1)
        
        # Record some errors
        for i in range(2):
            self.monitor.record_api_call("/api/test", "GET", 500, 0.1)
        
        # Check total requests
        assert self.monitor.counters["api.requests_total"] == 10
        assert self.monitor.counters["api.errors_total"] == 2
    
    def test_timing_functionality(self):
        """Test timing functionality"""
        metric_name = "test.timing"
        duration = 1.5
        
        self.monitor.timing(metric_name, duration)
        
        assert len(self.monitor.timers[metric_name]) == 1
        assert self.monitor.timers[metric_name][0] == duration
    
    def test_gauge_functionality(self):
        """Test gauge functionality"""
        metric_name = "test.gauge"
        value = 42.5
        
        self.monitor.gauge(metric_name, value)
        
        assert self.monitor.gauges[metric_name] == value
    
    def test_health_metrics_structure(self):
        """Test health metrics structure"""
        metrics = self.monitor.get_health_metrics()
        
        # Check that all expected keys are present
        expected_keys = [
            'timestamp', 'uptime_seconds', 'total_events', 
            'recent_events_1min', 'avg_response_time_ms', 
            'error_rate_1min', 'upload_stats', 'memory_usage',
            'active_counters'
        ]
        
        for key in expected_keys:
            assert key in metrics
    
    def test_security_summary_structure(self):
        """Test security summary structure"""
        summary = self.monitor.get_security_summary()
        
        expected_keys = [
            'recent_events_1hour', 'event_types', 
            'failed_auth_attempts', 'high_severity_events'
        ]
        
        for key in expected_keys:
            assert key in summary
    
    def test_pii_detection_recording(self):
        """Test PII detection recording"""
        user_id = "user123"
        filename = "test.csv"
        pii_types = ["email", "phone"]
        risk_level = "high"
        
        self.monitor.record_pii_detection(user_id, filename, pii_types, risk_level)
        
        # Should record a security event
        assert len(self.monitor.security_events) == 1
        event = self.monitor.security_events[0]
        assert event['type'] == 'pii_detected'
        assert event['severity'] == 'warning'  # high risk -> warning
        assert event['details']['filename'] == filename
        assert event['details']['pii_types'] == pii_types
    
    def test_multiple_upload_events(self):
        """Test multiple upload events"""
        # Record multiple uploads
        uploads = [
            (1024, 1.0, False, True),      # 1KB, 1s, no PII, success
            (2048, 2.0, True, True),       # 2KB, 2s, has PII, success  
            (4096, 1.5, False, False),     # 4KB, 1.5s, no PII, failed
        ]
        
        for file_size, upload_time, has_pii, success in uploads:
            self.monitor.record_upload_event(
                "user123", "test.csv", file_size, has_pii, success, upload_time
            )
        
        metrics = self.monitor.get_health_metrics()
        stats = metrics["upload_stats"]
        assert stats["total_uploads"] == 3
        assert stats["failed_uploads"] == 1
        assert stats["pii_detections"] == 1
        assert stats["total_bytes"] == 1024 + 2048 + 4096
    
    def test_timer_context_manager(self):
        """Test timer context manager"""
        metric_name = "test.timer_context"
        
        with self.monitor.timer(metric_name):
            time.sleep(0.01)  # Small delay
        
        assert len(self.monitor.timers[metric_name]) == 1
        assert self.monitor.timers[metric_name][0] > 0