from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseForbidden
from typing import Dict, Any, List, Optional
import logging
import time
import json
from functools import wraps
import re
import hashlib
import hmac
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import jwt
from datetime import datetime, timedelta
import ipaddress
import dns.resolver
import socket
import ssl
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

class SecurityOptimizer:
    def __init__(self):
        self.rate_limit_window = 60  # 1 minuta
        self.max_requests = 100  # maksimalni broj zahtjeva po minuti
        self.block_duration = 3600  # 1 sat
        self.max_failed_attempts = 5
        self.password_min_length = 12
        self.session_timeout = 1800  # 30 minuta
        self.encryption_key = Fernet.generate_key()
        self.fernet = Fernet(self.encryption_key)
        
        # Sigurnosni patterni
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
        self.path_traversal_patterns = [
            r"\.\./",
            r"\.\.\\",
            r"\.\.$",
        ]

    def rate_limit(self, request):
        """Rate limiting po IP-u"""
        ip = request.META.get('REMOTE_ADDR')
        key = f"rate_limit:{ip}"
        
        # Provjeri je li IP blokiran
        if self._is_ip_blocked(ip):
            return HttpResponseForbidden("IP je blokiran zbog previše zahtjeva")
        
        # Dohvati trenutni broj zahtjeva
        current = cache.get(key, 0)
        
        # Provjeri limit
        if current >= self.max_requests:
            self._block_ip(ip)
            return HttpResponseForbidden("Rate limit prekoračen")
        
        # Povećaj brojač
        cache.set(key, current + 1, self.rate_limit_window)
        return None

    def _is_ip_blocked(self, ip: str) -> bool:
        """Provjeri je li IP blokiran"""
        return cache.get(f"blocked_ip:{ip}") is not None

    def _block_ip(self, ip: str):
        """Blokiraj IP"""
        cache.set(f"blocked_ip:{ip}", True, self.block_duration)
        logger.warning(f"IP blokiran: {ip}")

    def validate_password(self, password: str) -> bool:
        """Validacija lozinke"""
        if len(password) < self.password_min_length:
            return False
            
        # Provjeri kompleksnost
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        return all([has_upper, has_lower, has_digit, has_special])

    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple:
        """Hashiranje lozinke"""
        if salt is None:
            salt = os.urandom(16)
            
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return key, salt

    def verify_password(self, password: str, hashed: bytes, salt: bytes) -> bool:
        """Verifikacija lozinke"""
        key, _ = self.hash_password(password, salt)
        return hmac.compare_digest(key, hashed)

    def encrypt_data(self, data: str) -> str:
        """Šifriranje podataka"""
        return self.fernet.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        """Dešifriranje podataka"""
        return self.fernet.decrypt(encrypted_data.encode()).decode()

    def generate_jwt(self, user_id: int, expires_in: int = 3600) -> str:
        """Generiranje JWT tokena"""
        payload = {
            'user_id': user_id,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

    def verify_jwt(self, token: str) -> Optional[Dict[str, Any]]:
        """Verifikacija JWT tokena"""
        try:
            return jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def validate_input(self, data: Dict[str, Any]) -> bool:
        """Validacija korisničkog unosa"""
        for value in data.values():
            if isinstance(value, str):
                # SQL Injection check
                for pattern in self.sql_injection_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return False
                        
                # XSS check
                for pattern in self.xss_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        return False
                        
                # Path Traversal check
                for pattern in self.path_traversal_patterns:
                    if re.search(pattern, value):
                        return False
        return True

    def sanitize_input(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitizacija korisničkog unosa"""
        sanitized = {}
        for key, value in data.items():
            if isinstance(value, str):
                # Ukloni HTML tagove
                value = re.sub(r'<[^>]+>', '', value)
                # Escape specijalne znakove
                value = value.replace('&', '&amp;')
                value = value.replace('<', '&lt;')
                value = value.replace('>', '&gt;')
                value = value.replace('"', '&quot;')
                value = value.replace("'", '&#x27;')
            sanitized[key] = value
        return sanitized

    def validate_url(self, url: str) -> bool:
        """Validacija URL-a"""
        try:
            result = urlparse(url)
            return all([result.scheme, result.netloc])
        except:
            return False

    def check_ssl_certificate(self, domain: str) -> bool:
        """Provjera SSL certifikata"""
        try:
            context = ssl.create_default_context()
            with socket.create_connection((domain, 443)) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    # Provjeri istek certifikata
                    if datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z') < datetime.now():
                        return False
                    return True
        except:
            return False

    def validate_ip(self, ip: str) -> bool:
        """Validacija IP adrese"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def check_dns(self, domain: str) -> bool:
        """Provjera DNS zapisa"""
        try:
            dns.resolver.resolve(domain, 'A')
            return True
        except:
            return False

    def security_headers(self, response):
        """Dodavanje sigurnosnih headera"""
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        response['Content-Security-Policy'] = "default-src 'self'"
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
        return response

    def validate_session(self, session_id: str) -> bool:
        """Validacija sesije"""
        session_data = cache.get(f"session:{session_id}")
        if not session_data:
            return False
            
        # Provjeri timeout
        if time.time() - session_data['last_activity'] > self.session_timeout:
            cache.delete(f"session:{session_id}")
            return False
            
        # Ažuriraj aktivnost
        session_data['last_activity'] = time.time()
        cache.set(f"session:{session_id}", session_data, self.session_timeout)
        return True

    def handle_failed_login(self, username: str, ip: str):
        """Upravljanje neuspješnim prijavama"""
        key = f"failed_login:{ip}:{username}"
        attempts = cache.get(key, 0) + 1
        
        if attempts >= self.max_failed_attempts:
            self._block_ip(ip)
            logger.warning(f"Korisnički račun blokiran zbog previše neuspješnih prijava: {username}")
        else:
            cache.set(key, attempts, self.block_duration)

# Inicijalizacija optimizatora
security_optimizer = SecurityOptimizer() 