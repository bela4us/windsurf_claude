from django.conf import settings
from django.core.cache import cache
from typing import Dict, Any, List, Optional
import logging
import time
import json
from functools import wraps
import psutil
import os
from prometheus_client import Counter, Histogram, Gauge
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration
from elasticsearch import Elasticsearch
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class MonitoringOptimizer:
    def __init__(self):
        self.metrics_interval = 60  # sekunde
        self.log_retention_days = 30
        self.alert_thresholds = {
            'cpu': 90,
            'memory': 90,
            'disk': 90
        }
        
        # Prometheus metrike
        self.request_count = Counter('http_requests_total', 'Total HTTP requests')
        self.request_latency = Histogram('http_request_duration_seconds', 'HTTP request duration')
        self.error_count = Counter('http_errors_total', 'Total HTTP errors')
        self.active_users = Gauge('active_users', 'Number of active users')
        self.game_sessions = Gauge('game_sessions', 'Number of active game sessions')
        
        # Elasticsearch klijent
        self.es = Elasticsearch([settings.ELASTICSEARCH_URL])
        
        # Inicijalizacija Sentry-a
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            integrations=[DjangoIntegration()],
            traces_sample_rate=1.0,
        )

    def track_request(self, view_func):
        """Dekorator za praćenje HTTP zahtjeva"""
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            start_time = time.time()
            
            try:
                response = view_func(request, *args, **kwargs)
                
                # Zabilježi metrike
                duration = time.time() - start_time
                self.request_count.inc()
                self.request_latency.observe(duration)
                
                # Logiraj zahtjev
                self._log_request(request, response, duration)
                
                return response
            except Exception as e:
                self.error_count.inc()
                self._log_error(e, request)
                raise
                
        return wrapper

    def _log_request(self, request, response, duration: float):
        """Logiraj detalje HTTP zahtjeva"""
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'method': request.method,
            'path': request.path,
            'status_code': response.status_code,
            'duration': duration,
            'ip': request.META.get('REMOTE_ADDR'),
            'user_agent': request.META.get('HTTP_USER_AGENT')
        }
        
        # Spremi u Elasticsearch
        self.es.index(
            index=f'http-logs-{datetime.now().strftime("%Y.%m")}',
            document=log_data
        )
        
        logger.info(f"HTTP Request: {json.dumps(log_data)}")

    def _log_error(self, error: Exception, request):
        """Logiraj greške"""
        error_data = {
            'timestamp': datetime.now().isoformat(),
            'error_type': type(error).__name__,
            'error_message': str(error),
            'path': request.path,
            'method': request.method,
            'ip': request.META.get('REMOTE_ADDR')
        }
        
        # Spremi u Elasticsearch
        self.es.index(
            index=f'error-logs-{datetime.now().strftime("%Y.%m")}',
            document=error_data
        )
        
        # Šalji u Sentry
        sentry_sdk.capture_exception(error)
        
        logger.error(f"Error: {json.dumps(error_data)}")

    def collect_system_metrics(self):
        """Prikupljanje sistemskih metrika"""
        try:
            # CPU metrike
            cpu_percent = psutil.cpu_percent()
            
            # Memory metrike
            memory = psutil.virtual_memory()
            
            # Disk metrike
            disk = psutil.disk_usage('/')
            
            metrics = {
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'disk_percent': disk.percent,
                'timestamp': datetime.now().isoformat()
            }
            
            # Spremi u cache
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
                        'timestamp': datetime.now().isoformat()
                    }
                    
                    logger.warning(f"Alert: {json.dumps(alert_data)}")
                    sentry_sdk.capture_message(
                        f"High {metric} usage: {value}%",
                        level='warning'
                    )

    def cleanup_old_logs(self):
        """Čišćenje starih logova"""
        try:
            # Očisti Elasticsearch indekse
            cutoff_date = datetime.now() - timedelta(days=self.log_retention_days)
            old_indices = self.es.indices.get_alias().keys()
            
            for index in old_indices:
                if 'logs-' in index:
                    index_date = datetime.strptime(
                        index.split('-')[-1],
                        '%Y.%m'
                    )
                    if index_date < cutoff_date:
                        self.es.indices.delete(index=index)
                        logger.info(f"Deleted old index: {index}")
            
            # Očisti log datoteke
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

    def track_game_metrics(self, game_id: int, metrics: Dict[str, Any]):
        """Praćenje metrika igre"""
        try:
            # Ažuriraj Prometheus metrike
            self.game_sessions.inc()
            
            # Spremi detaljne metrike u Elasticsearch
            game_metrics = {
                'game_id': game_id,
                'timestamp': datetime.now().isoformat(),
                **metrics
            }
            
            self.es.index(
                index=f'game-metrics-{datetime.now().strftime("%Y.%m")}',
                document=game_metrics
            )
            
        except Exception as e:
            logger.error(f"Error tracking game metrics: {e}")
            sentry_sdk.capture_exception(e)

    def track_user_metrics(self, user_id: int, metrics: Dict[str, Any]):
        """Praćenje metrika korisnika"""
        try:
            # Ažuriraj Prometheus metrike
            self.active_users.inc()
            
            # Spremi detaljne metrike u Elasticsearch
            user_metrics = {
                'user_id': user_id,
                'timestamp': datetime.now().isoformat(),
                **metrics
            }
            
            self.es.index(
                index=f'user-metrics-{datetime.now().strftime("%Y.%m")}',
                document=user_metrics
            )
            
        except Exception as e:
            logger.error(f"Error tracking user metrics: {e}")
            sentry_sdk.capture_exception(e)

# Inicijalizacija optimizatora
monitoring_optimizer = MonitoringOptimizer() 