<<<<<<< HEAD
import logging
import time
from functools import wraps
from typing import Callable, Any, Dict, Optional
import json
from django.conf import settings
from django.db import connection
from django.db.backends.utils import CursorDebugWrapper
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from prometheus_client import Counter, Histogram, Gauge
import psutil
import os
from django.core.cache import cache

# Konfiguracija logiranja
logger = logging.getLogger(__name__)

# Inicijalizacija Sentry-a
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
)

# Prometheus metrike
API_REQUEST_COUNT = Counter('api_requests_total', 'Total number of API requests')
API_REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'API request latency')
CPU_USAGE = Gauge('cpu_usage_percent', 'CPU usage percentage')
MEMORY_USAGE = Gauge('memory_usage_percent', 'Memory usage percentage')
DISK_USAGE = Gauge('disk_usage_percent', 'Disk usage percentage')

class MonitoringSystem:
    def __init__(self):
        self.metrics_interval = 60  # sekunde
        self.log_retention_days = 30
        self.alert_thresholds = {
            'cpu': 90,
            'memory': 90,
            'disk': 90
        }

    def track_api_request(self, view_func):
        """Dekorator za praćenje API zahtjeva"""
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                response = view_func(request, *args, **kwargs)
                
                # Zabilježi metrike
                duration = time.time() - start_time
                API_REQUEST_COUNT.inc()
                API_REQUEST_LATENCY.observe(duration)
                
                # Logiraj zahtjev
                self._log_api_request(request, response, duration)
                
                return response
            except Exception as e:
                # Zabilježi grešku
                self._log_error(e, request)
                raise
                
        return wrapper

    def _log_api_request(self, request, response, duration: float):
        """Logiraj detalje API zahtjeva"""
        log_data = {
            'timestamp': time.time(),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration': duration,
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT')
        }
        
        logger.info(f"API Request: {json.dumps(log_data)}")

    def _log_error(self, error: Exception, request):
        """Logiraj greške"""
        error_data = {
            'timestamp': time.time(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'path': request.path,
            'method': request.method,
            'ip': request.META.get('REMOTE_ADDR')
        }
        
        logger.error(f"Error: {json.dumps(error_data)}")
        
        # Šalji grešku u Sentry
        sentry_sdk.capture_exception(error)

    def collect_system_metrics(self):
        """Prikupljanje sistemskih metrika"""
        try:
            # CPU metrike
            cpu_percent = psutil.cpu_percent()
            CPU_USAGE.set(cpu_percent)
            
            # Memory metrike
            memory = psutil.virtual_memory()
            MEMORY_USAGE.set(memory.percent)
            
            # Disk metrike
            disk = psutil.disk_usage('/')
            DISK_USAGE.set(disk.percent)
            
            # Spremi metrike u cache
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'timestamp': time.time()
            }
            
            cache.set('system_metrics', metrics, self.metrics_interval)
            
            # Provjeri alertove
            self._check_alerts(metrics)
            
            logger.info(f"System metrics collected: {json.dumps(metrics)}")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            sentry_sdk.capture_exception(e)

    def _check_alerts(self, metrics: Dict[str, float]):
        """Provjeri metrike za alertove"""
        for metric, value in metrics.items():
            if metric in self.alert_thresholds:
                if value > self.alert_thresholds[metric]:
                    alert_data = {
                        'metric': metric,
                        'value': value,
                        'threshold': self.alert_thresholds[metric],
                        'timestamp': time.time()
                    }
                    
                    logger.warning(f"Alert: {json.dumps(alert_data)}")
                    sentry_sdk.capture_message(
                        f"High {metric} usage: {value}%",
                        level='warning'
                    )

    def cleanup_old_logs(self):
        """Čišćenje starih logova"""
        try:
            log_dir = settings.LOG_DIR
            current_time = time.time()
            
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)
                if os.path.getmtime(filepath) < current_time - (self.log_retention_days * 86400):
                    os.remove(filepath)
                    logger.info(f"Deleted old log file: {filename}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
            sentry_sdk.capture_exception(e)

# Inicijalizacija monitoring sustava
=======
import logging
import time
from functools import wraps
from typing import Callable, Any, Dict, Optional
import json
from django.conf import settings
from django.db import connection
from django.db.backends.utils import CursorDebugWrapper
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from prometheus_client import Counter, Histogram, Gauge
import psutil
import os
from django.core.cache import cache

# Konfiguracija logiranja
logger = logging.getLogger(__name__)

# Inicijalizacija Sentry-a
sentry_sdk.init(
    dsn=settings.SENTRY_DSN,
    integrations=[DjangoIntegration()],
    traces_sample_rate=1.0,
)

# Prometheus metrike
API_REQUEST_COUNT = Counter('api_requests_total', 'Total number of API requests')
API_REQUEST_LATENCY = Histogram('api_request_latency_seconds', 'API request latency')
CPU_USAGE = Gauge('cpu_usage_percent', 'CPU usage percentage')
MEMORY_USAGE = Gauge('memory_usage_percent', 'Memory usage percentage')
DISK_USAGE = Gauge('disk_usage_percent', 'Disk usage percentage')

class MonitoringSystem:
    def __init__(self):
        self.metrics_interval = 60  # sekunde
        self.log_retention_days = 30
        self.alert_thresholds = {
            'cpu': 90,
            'memory': 90,
            'disk': 90
        }

    def track_api_request(self, view_func):
        """Dekorator za praćenje API zahtjeva"""
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                response = view_func(request, *args, **kwargs)
                
                # Zabilježi metrike
                duration = time.time() - start_time
                API_REQUEST_COUNT.inc()
                API_REQUEST_LATENCY.observe(duration)
                
                # Logiraj zahtjev
                self._log_api_request(request, response, duration)
                
                return response
            except Exception as e:
                # Zabilježi grešku
                self._log_error(e, request)
                raise
                
        return wrapper

    def _log_api_request(self, request, response, duration: float):
        """Logiraj detalje API zahtjeva"""
        log_data = {
            'timestamp': time.time(),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration': duration,
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT')
        }
        
        logger.info(f"API Request: {json.dumps(log_data)}")

    def _log_error(self, error: Exception, request):
        """Logiraj greške"""
        error_data = {
            'timestamp': time.time(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'path': request.path,
            'method': request.method,
            'ip': request.META.get('REMOTE_ADDR')
        }
        
        logger.error(f"Error: {json.dumps(error_data)}")
        
        # Šalji grešku u Sentry
        sentry_sdk.capture_exception(error)

    def collect_system_metrics(self):
        """Prikupljanje sistemskih metrika"""
        try:
            # CPU metrike
            cpu_percent = psutil.cpu_percent()
            CPU_USAGE.set(cpu_percent)
            
            # Memory metrike
            memory = psutil.virtual_memory()
            MEMORY_USAGE.set(memory.percent)
            
            # Disk metrike
            disk = psutil.disk_usage('/')
            DISK_USAGE.set(disk.percent)
            
            # Spremi metrike u cache
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'timestamp': time.time()
            }
            
            cache.set('system_metrics', metrics, self.metrics_interval)
            
            # Provjeri alertove
            self._check_alerts(metrics)
            
            logger.info(f"System metrics collected: {json.dumps(metrics)}")
            
        except Exception as e:
            logger.error(f"Error collecting system metrics: {e}")
            sentry_sdk.capture_exception(e)

    def _check_alerts(self, metrics: Dict[str, float]):
        """Provjeri metrike za alertove"""
        for metric, value in metrics.items():
            if metric in self.alert_thresholds:
                if value > self.alert_thresholds[metric]:
                    alert_data = {
                        'metric': metric,
                        'value': value,
                        'threshold': self.alert_thresholds[metric],
                        'timestamp': time.time()
                    }
                    
                    logger.warning(f"Alert: {json.dumps(alert_data)}")
                    sentry_sdk.capture_message(
                        f"High {metric} usage: {value}%",
                        level='warning'
                    )

    def cleanup_old_logs(self):
        """Čišćenje starih logova"""
        try:
            log_dir = settings.LOG_DIR
            current_time = time.time()
            
            for filename in os.listdir(log_dir):
                filepath = os.path.join(log_dir, filename)
                if os.path.getmtime(filepath) < current_time - (self.log_retention_days * 86400):
                    os.remove(filepath)
                    logger.info(f"Deleted old log file: {filename}")
                    
        except Exception as e:
            logger.error(f"Error cleaning up old logs: {e}")
            sentry_sdk.capture_exception(e)

# Inicijalizacija monitoring sustava
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
monitoring_system = MonitoringSystem() 