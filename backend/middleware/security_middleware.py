<<<<<<< HEAD
from django.http import HttpResponseForbidden
from django.conf import settings
from django.core.cache import cache
from typing import Callable, Any, Dict
import time
import logging
from functools import wraps
import re
import html

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    def __init__(self):
        self.rate_limit_window = 60  # 1 minuta
        self.max_requests = 100  # maksimalni broj zahtjeva po minuti
        self.sql_injection_patterns = [
            r"(\b(select|insert|update|delete|drop|union|alter)\b)",
            r"(\b(or|and)\s*=\s*\d+)",
            r"(\b(or|and)\s*'[^']*'\s*=\s*'[^']*')",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:[^>]*",
            r"on\w+\s*=",
        ]

    def rate_limit(self, request):
        """Rate limiting po IP-u"""
        ip = request.META.get('REMOTE_ADDR')
        key = f"rate_limit:{ip}"
        
        # Dohvati trenutni broj zahtjeva
        current = cache.get(key, 0)
        
        # Provjeri limit
        if current >= self.max_requests:
            logger.warning(f"Rate limit prekoračen za IP: {ip}")
            return HttpResponseForbidden("Rate limit exceeded")
        
        # Povećaj brojač
        cache.set(key, current + 1, self.rate_limit_window)
        return None

    def sql_injection_check(self, data: Dict[str, Any]) -> bool:
        """Provjera SQL injection napada"""
        for value in data.values():
            if isinstance(value, str):
                for pattern in self.sql_injection_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(f"Detektiran SQL injection pokušaj: {value}")
                        return True
        return False

    def xss_check(self, data: Dict[str, Any]) -> bool:
        """Provjera XSS napada"""
        for value in data.values():
            if isinstance(value, str):
                for pattern in self.xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(f"Detektiran XSS pokušaj: {value}")
                        return True
        return False

    def sanitize_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizacija korisničkog unosa"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = html.escape(value)
            else:
                sanitized[key] = value
        return sanitized

    def csrf_check(self, request):
        """CSRF zaštita"""
        if request.method in ['POST', 'PUT', 'DELETE']:
            if not request.is_secure():
                logger.warning("Nesiguran zahtjev - CSRF check")
                return HttpResponseForbidden("CSRF check failed")
        return None

    def security_headers(self, response):
        """Dodavanje sigurnosnih headera"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = "default-src 'self'"
        return response

    def process_request(self, request):
        """Obrada zahtjeva"""
        # Rate limiting
        rate_limit_response = self.rate_limit(request)
        if rate_limit_response:
            return rate_limit_response

        # CSRF check
        csrf_response = self.csrf_check(request)
        if csrf_response:
            return csrf_response

        # SQL injection check
        if self.sql_injection_check(request.POST):
            return HttpResponseForbidden("Invalid input")

        # XSS check
        if self.xss_check(request.POST):
            return HttpResponseForbidden("Invalid input")

        # Sanitize input
        request.POST = self.sanitize_input(request.POST)

    def process_response(self, request, response):
        """Obrada odgovora"""
        return self.security_headers(response)

# Inicijalizacija middleware-a
security_middleware = SecurityMiddleware()

def require_https(view_func: Callable) -> Callable:
    """Dekorator koji osigurava HTTPS"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.is_secure():
            return HttpResponseForbidden('HTTPS je obavezan')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def rate_limit(view_func: Callable) -> Callable:
    """Dekorator za rate limiting na razini view-a"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        ip = request.META.get('REMOTE_ADDR')
        key = f'view_rate_limit:{ip}:{view_func.__name__}'
        
        current = cache.get(key, 0)
        if current >= 50:  # 50 zahtjeva po minuti
            return HttpResponseForbidden('Previše zahtjeva. Molimo pričekajte.')
            
        cache.set(key, current + 1, 60)
        return view_func(request, *args, **kwargs)
=======
from django.http import HttpResponseForbidden
from django.conf import settings
from django.core.cache import cache
from typing import Callable, Any, Dict
import time
import logging
from functools import wraps
import re
import html

logger = logging.getLogger(__name__)

class SecurityMiddleware:
    def __init__(self):
        self.rate_limit_window = 60  # 1 minuta
        self.max_requests = 100  # maksimalni broj zahtjeva po minuti
        self.sql_injection_patterns = [
            r"(\b(select|insert|update|delete|drop|union|alter)\b)",
            r"(\b(or|and)\s*=\s*\d+)",
            r"(\b(or|and)\s*'[^']*'\s*=\s*'[^']*')",
        ]
        self.xss_patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:[^>]*",
            r"on\w+\s*=",
        ]

    def rate_limit(self, request):
        """Rate limiting po IP-u"""
        ip = request.META.get('REMOTE_ADDR')
        key = f"rate_limit:{ip}"
        
        # Dohvati trenutni broj zahtjeva
        current = cache.get(key, 0)
        
        # Provjeri limit
        if current >= self.max_requests:
            logger.warning(f"Rate limit prekoračen za IP: {ip}")
            return HttpResponseForbidden("Rate limit exceeded")
        
        # Povećaj brojač
        cache.set(key, current + 1, self.rate_limit_window)
        return None

    def sql_injection_check(self, data: Dict[str, Any]) -> bool:
        """Provjera SQL injection napada"""
        for value in data.values():
            if isinstance(value, str):
                for pattern in self.sql_injection_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(f"Detektiran SQL injection pokušaj: {value}")
                        return True
        return False

    def xss_check(self, data: Dict[str, Any]) -> bool:
        """Provjera XSS napada"""
        for value in data.values():
            if isinstance(value, str):
                for pattern in self.xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        logger.warning(f"Detektiran XSS pokušaj: {value}")
                        return True
        return False

    def sanitize_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizacija korisničkog unosa"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                sanitized[key] = html.escape(value)
            else:
                sanitized[key] = value
        return sanitized

    def csrf_check(self, request):
        """CSRF zaštita"""
        if request.method in ['POST', 'PUT', 'DELETE']:
            if not request.is_secure():
                logger.warning("Nesiguran zahtjev - CSRF check")
                return HttpResponseForbidden("CSRF check failed")
        return None

    def security_headers(self, response):
        """Dodavanje sigurnosnih headera"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = "default-src 'self'"
        return response

    def process_request(self, request):
        """Obrada zahtjeva"""
        # Rate limiting
        rate_limit_response = self.rate_limit(request)
        if rate_limit_response:
            return rate_limit_response

        # CSRF check
        csrf_response = self.csrf_check(request)
        if csrf_response:
            return csrf_response

        # SQL injection check
        if self.sql_injection_check(request.POST):
            return HttpResponseForbidden("Invalid input")

        # XSS check
        if self.xss_check(request.POST):
            return HttpResponseForbidden("Invalid input")

        # Sanitize input
        request.POST = self.sanitize_input(request.POST)

    def process_response(self, request, response):
        """Obrada odgovora"""
        return self.security_headers(response)

# Inicijalizacija middleware-a
security_middleware = SecurityMiddleware()

def require_https(view_func: Callable) -> Callable:
    """Dekorator koji osigurava HTTPS"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.is_secure():
            return HttpResponseForbidden('HTTPS je obavezan')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def rate_limit(view_func: Callable) -> Callable:
    """Dekorator za rate limiting na razini view-a"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        ip = request.META.get('REMOTE_ADDR')
        key = f'view_rate_limit:{ip}:{view_func.__name__}'
        
        current = cache.get(key, 0)
        if current >= 50:  # 50 zahtjeva po minuti
            return HttpResponseForbidden('Previše zahtjeva. Molimo pričekajte.')
            
        cache.set(key, current + 1, 60)
        return view_func(request, *args, **kwargs)
>>>>>>> c45eb88e3e23e6f6a3bf252c5a572f1c5cdb8266
    return _wrapped_view 