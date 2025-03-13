"""
Middleware za logiranje zahtjeva u Belot aplikaciji.

Ovaj modul implementira middleware za logiranje detalja o HTTP zahtjevima
i mjerenje vremena izvršavanja, što omogućuje praćenje performansi
aplikacije i identificiranje potencijalnih problema.
"""

import time
import logging
import uuid
import json
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from utils.decorators import track_execution_time

logger = logging.getLogger('belot.request_logger')


class RequestLoggerMiddleware(MiddlewareMixin):
    """
    Middleware koji logira detalje o HTTP zahtjevima i njihovom izvršavanju.
    
    Logira informacije poput metode, putanje, vremena izvršavanja, statusnog koda
    i osnovnih podataka o korisniku. Također generira jedinstveni ID za svaki zahtjev
    koji se može koristiti za praćenje kroz sustav.
    """
    
    # Preskakanje Content-Type-ova za koje ne želimo logirati tijelo zahtjeva
    SKIP_CONTENT_TYPES = [
        'multipart/form-data',
        'application/octet-stream'
    ]
    
    # Maksimalna veličina tijela zahtjeva koja će biti logirana
    MAX_BODY_LENGTH = 1000
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py ako postoje
        self.log_request_body = getattr(settings, 'LOG_REQUEST_BODY', False)
        self.log_response_body = getattr(settings, 'LOG_RESPONSE_BODY', False)
        self.max_body_length = getattr(settings, 'MAX_BODY_LOG_LENGTH', self.MAX_BODY_LENGTH)
        
        # Putanje koje ne želimo detaljno logirati
        self.quiet_paths = getattr(settings, 'REQUEST_LOGGER_QUIET_PATHS', [
            '/static/',
            '/media/',
            '/admin/jsi18n/',
            '/favicon.ico'
        ])
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i logira detalje.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Preskočimo detaljno logiranje za određene putanje
        if any(request.path.startswith(path) for path in self.quiet_paths):
            return self.get_response(request)
        
        # Generiraj jedinstveni ID zahtjeva
        request_id = str(uuid.uuid4())
        request.id = request_id
        
        # Početak mjerenja vremena
        start_time = time.time()
        
        # Logiranje detalja zahtjeva
        self._log_request(request)
        
        # Obradi zahtjev
        response = self.get_response(request)
        
        # Završetak mjerenja vremena
        duration = time.time() - start_time
        
        # Logiranje detalja odgovora
        self._log_response(request, response, duration)
        
        # Dodaj ID zahtjeva u zaglavlje odgovora za lakše praćenje
        response['X-Request-ID'] = request_id
        
        return response
    
    def _log_request(self, request):
        """
        Logira detalje HTTP zahtjeva.
        
        Args:
            request: HTTP zahtjev
        """
        log_data = {
            'request_id': getattr(request, 'id', 'unknown'),
            'method': request.method,
            'path': request.path,
            'query': request.META.get('QUERY_STRING', ''),
            'user_id': request.user.id if request.user.is_authenticated else None,
            'ip': self._get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown')
        }
        
        # Logiranje tijela zahtjeva ako je dozvoljeno
        if self.log_request_body:
            content_type = request.META.get('CONTENT_TYPE', '')
            
            if (request.method in ['POST', 'PUT', 'PATCH'] 
                    and not any(ct in content_type for ct in self.SKIP_CONTENT_TYPES)):
                try:
                    if request.body:
                        # Pokušaj dekodirati JSON
                        if 'application/json' in content_type:
                            body = json.loads(request.body)
                            log_data['body'] = body
                        else:
                            # Za ostale Content-Type-ove, logiraj samo ograničenu duljinu
                            body_str = str(request.body[:self.max_body_length])
                            if len(request.body) > self.max_body_length:
                                body_str += '... [truncated]'
                            log_data['body'] = body_str
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log_data['body'] = '[Cannot decode request body]'
        
        logger.info(f"Request: {json.dumps(log_data)}")
    
    def _log_response(self, request, response, duration):
        """
        Logira detalje HTTP odgovora.
        
        Args:
            request: HTTP zahtjev
            response: HTTP odgovor
            duration: Vrijeme izvršavanja u sekundama
        """
        log_data = {
            'request_id': getattr(request, 'id', 'unknown'),
            'method': request.method,
            'path': request.path,
            'status': response.status_code,
            'duration': round(duration * 1000, 2),  # u milisekundama
            'content_type': response.get('Content-Type', 'unknown'),
            'content_length': response.get('Content-Length', 'unknown')
        }
        
        # Logiranje tijela odgovora ako je dozvoljeno
        if self.log_response_body and hasattr(response, 'content'):
            content_type = response.get('Content-Type', '')
            
            # Logiraj samo za JSON odgovore
            if 'application/json' in content_type:
                try:
                    body = json.loads(response.content)
                    # Truncate body if too large
                    if len(json.dumps(body)) > self.max_body_length:
                        log_data['response_body'] = '[Response body too large to log]'
                    else:
                        log_data['response_body'] = body
                except (json.JSONDecodeError, UnicodeDecodeError):
                    log_data['response_body'] = '[Cannot decode response body]'
        
        # Logiraj razinu ovisno o statusu
        if response.status_code >= 500:
            logger.error(f"Response: {json.dumps(log_data)}")
        elif response.status_code >= 400:
            logger.warning(f"Response: {json.dumps(log_data)}")
        else:
            logger.info(f"Response: {json.dumps(log_data)}")
    
    def _get_client_ip(self, request):
        """
        Dohvaća IP adresu klijenta iz zahtjeva.
        
        Uzima u obzir proxy i load balancer scenarije.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            str: IP adresa klijenta
        """
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Uzmemo prvu IP adresu iz X-Forwarded-For zaglavlja
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '0.0.0.0')
        return ip


class QueryCountMiddleware(MiddlewareMixin):
    """
    Middleware koji prati broj SQL upita tijekom izvršavanja zahtjeva.
    
    Koristan za identificiranje N+1 problema i drugih performansnih
    problema s bazom podataka.
    
    Napomena: Ovaj middleware bi trebao biti korišten samo u razvojnom
    okruženju, ne u produkciji.
    """
    
    def __init__(self, get_response):
        """Inicijalizira middleware s funkcijom get_response."""
        self.get_response = get_response
        
        # Učitaj postavke iz settings.py ako postoje
        self.log_threshold = getattr(settings, 'QUERY_COUNT_THRESHOLD', 50)
        
        # Putanje koje ne želimo pratiti
        self.ignore_paths = getattr(settings, 'QUERY_COUNT_IGNORE_PATHS', [
            '/admin/',
            '/static/',
            '/media/'
        ])
    
    def __call__(self, request):
        """
        Obrađuje zahtjev i prati broj SQL upita.
        
        Args:
            request: HTTP zahtjev
            
        Returns:
            HttpResponse: Odgovor na zahtjev
        """
        # Preskočimo praćenje za određene putanje
        if any(request.path.startswith(path) for path in self.ignore_paths):
            return self.get_response(request)
        
        # Prati upite samo ako je DEBUG uključen
        if not settings.DEBUG:
            return self.get_response(request)
        
        import time
        from django.db import connection
        
        # Spremi početni broj upita
        start_queries = len(connection.queries)
        start_time = time.time()
        
        # Obradi zahtjev
        response = self.get_response(request)
        
        # Izračunaj broj upita i vrijeme izvršavanja
        end_time = time.time()
        end_queries = len(connection.queries)
        
        # Broj upita i vrijeme izvršavanja
        num_queries = end_queries - start_queries
        duration = end_time - start_time
        
        # Dodaj X-Query-Count zaglavlje u odgovor
        response['X-Query-Count'] = str(num_queries)
        response['X-Query-Duration'] = f"{duration:.2f}s"
        
        # Logiraj ako je broj upita prešao threshold
        if num_queries > self.log_threshold:
            logger.warning(
                'Excessive number of queries: %d queries in %.2fs for %s %s',
                num_queries, duration, request.method, request.path
            )
            
            # Detaljno logiranje upita za dijagnostičke svrhe
            if settings.DEBUG:
                queries = connection.queries[start_queries:end_queries]
                duplicates = {}
                
                for query in queries:
                    sql = query['sql']
                    if sql in duplicates:
                        duplicates[sql] += 1
                    else:
                        duplicates[sql] = 1
                
                # Logiraj duplicirane upite
                for sql, count in duplicates.items():
                    if count > 1:
                        logger.warning('Duplicated query (%d times): %s', count, sql[:100])
        
        return response