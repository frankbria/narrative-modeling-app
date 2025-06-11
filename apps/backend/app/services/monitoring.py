"""
Application Monitoring Service
Tracks metrics, performance, and security events
"""

import time
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
import logging
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class MetricEvent:
    """Single metric event"""
    name: str
    value: float
    timestamp: datetime
    tags: Dict[str, str]


class ApplicationMonitor:
    """Application monitoring and metrics collection"""
    
    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self.events = deque(maxlen=max_events)
        self.counters = defaultdict(int)
        self.timers = defaultdict(list)
        self.gauges = defaultdict(float)
        
        # Performance tracking
        self.response_times = defaultdict(list)
        self.error_counts = defaultdict(int)
        
        # Security tracking
        self.security_events = deque(maxlen=1000)
        self.failed_auth_attempts = defaultdict(int)
        
        # Upload tracking
        self.upload_stats = {
            'total_uploads': 0,
            'failed_uploads': 0,
            'pii_detections': 0,
            'total_bytes': 0
        }
    
    def increment(self, metric_name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Increment a counter metric"""
        self.counters[metric_name] += value
        self._record_event(metric_name, value, tags or {})
    
    def gauge(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Set a gauge metric"""
        self.gauges[metric_name] = value
        self._record_event(metric_name, value, tags or {})
    
    def timing(self, metric_name: str, duration: float, tags: Optional[Dict[str, str]] = None):
        """Record timing metric"""
        self.timers[metric_name].append(duration)
        # Keep only recent timings
        if len(self.timers[metric_name]) > 1000:
            self.timers[metric_name] = self.timers[metric_name][-1000:]
        self._record_event(f"{metric_name}.timing", duration, tags or {})
    
    def timer(self, metric_name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations"""
        return TimerContext(self, metric_name, tags or {})
    
    def time_it(self, metric_name: str, tags: Optional[Dict[str, str]] = None):
        """Decorator for timing functions"""
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                with self.timer(metric_name, tags):
                    return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def record_api_call(self, endpoint: str, method: str, status_code: int, duration: float):
        """Record API call metrics"""
        tags = {
            'endpoint': endpoint,
            'method': method,
            'status_code': str(status_code)
        }
        
        self.timing('api.response_time', duration, tags)
        self.increment('api.requests_total', 1, tags)
        
        if status_code >= 400:
            self.increment('api.errors_total', 1, tags)
            
        # Store for analytics
        self.response_times[endpoint].append(duration)
        if len(self.response_times[endpoint]) > 1000:
            self.response_times[endpoint] = self.response_times[endpoint][-1000:]
    
    def record_upload_event(self, user_id: str, filename: str, file_size: int, 
                           has_pii: bool, success: bool, duration: float):
        """Record file upload metrics"""
        tags = {
            'has_pii': str(has_pii),
            'success': str(success)
        }
        
        self.timing('upload.duration', duration, tags)
        self.gauge('upload.file_size', file_size, tags)
        self.increment('upload.total', 1, tags)
        
        self.upload_stats['total_uploads'] += 1
        if not success:
            self.upload_stats['failed_uploads'] += 1
        if has_pii:
            self.upload_stats['pii_detections'] += 1
        self.upload_stats['total_bytes'] += file_size
    
    def record_security_event(self, event_type: str, user_id: str, 
                             details: Dict[str, Any], severity: str = 'info'):
        """Record security-related events"""
        event = {
            'timestamp': datetime.utcnow(),
            'type': event_type,
            'user_id': user_id,
            'details': details,
            'severity': severity
        }
        
        self.security_events.append(event)
        self.increment(f'security.{event_type}', 1, {'severity': severity})
        
        # Track failed auth attempts
        if event_type == 'auth_failure':
            self.failed_auth_attempts[user_id] += 1
    
    def record_pii_detection(self, user_id: str, filename: str, 
                           pii_types: list, risk_level: str):
        """Record PII detection event"""
        self.record_security_event(
            'pii_detected',
            user_id,
            {
                'filename': filename,
                'pii_types': pii_types,
                'risk_level': risk_level
            },
            severity='warning' if risk_level == 'high' else 'info'
        )
    
    def get_health_metrics(self) -> Dict[str, Any]:
        """Get current health metrics"""
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        
        # Recent events
        recent_events = [e for e in self.events if e.timestamp > one_minute_ago]
        
        # Calculate averages
        recent_response_times = []
        for endpoint, times in self.response_times.items():
            if times:
                recent_response_times.extend(times[-10:])  # Last 10 calls
        
        avg_response_time = sum(recent_response_times) / len(recent_response_times) if recent_response_times else 0
        
        return {
            'timestamp': now.isoformat(),
            'uptime_seconds': (now - datetime.utcnow()).total_seconds(),
            'total_events': len(self.events),
            'recent_events_1min': len(recent_events),
            'avg_response_time_ms': round(avg_response_time * 1000, 2),
            'error_rate_1min': self._calculate_error_rate(),
            'upload_stats': self.upload_stats.copy(),
            'memory_usage': self._get_memory_usage(),
            'active_counters': len(self.counters),
        }
    
    def get_security_summary(self) -> Dict[str, Any]:
        """Get security event summary"""
        now = datetime.utcnow()
        one_hour_ago = now - timedelta(hours=1)
        
        recent_security_events = [
            e for e in self.security_events 
            if e['timestamp'] > one_hour_ago
        ]
        
        event_types = defaultdict(int)
        for event in recent_security_events:
            event_types[event['type']] += 1
        
        return {
            'recent_events_1hour': len(recent_security_events),
            'event_types': dict(event_types),
            'failed_auth_attempts': dict(self.failed_auth_attempts),
            'high_severity_events': len([
                e for e in recent_security_events 
                if e['severity'] == 'high'
            ])
        }
    
    def _record_event(self, name: str, value: float, tags: Dict[str, str]):
        """Record a metric event"""
        event = MetricEvent(
            name=name,
            value=value,
            timestamp=datetime.utcnow(),
            tags=tags
        )
        self.events.append(event)
    
    def _calculate_error_rate(self) -> float:
        """Calculate error rate for last minute"""
        now = datetime.utcnow()
        one_minute_ago = now - timedelta(minutes=1)
        
        recent_api_events = [
            e for e in self.events 
            if e.name == 'api.requests_total' and e.timestamp > one_minute_ago
        ]
        
        if not recent_api_events:
            return 0.0
        
        error_events = [
            e for e in recent_api_events
            if e.tags.get('status_code', '200')[0] in ['4', '5']
        ]
        
        return len(error_events) / len(recent_api_events) * 100
    
    def _get_memory_usage(self) -> Dict[str, Any]:
        """Get memory usage statistics"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_mb': round(memory_info.rss / 1024 / 1024, 2),
            'vms_mb': round(memory_info.vms / 1024 / 1024, 2),
            'percent': round(process.memory_percent(), 2)
        }


class TimerContext:
    """Context manager for timing operations"""
    
    def __init__(self, monitor: ApplicationMonitor, metric_name: str, tags: Dict[str, str]):
        self.monitor = monitor
        self.metric_name = metric_name
        self.tags = tags
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.monitor.timing(self.metric_name, duration, self.tags)


# Global monitor instance
monitor = ApplicationMonitor()