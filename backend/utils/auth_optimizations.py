from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from typing import Dict, Any, Optional
import logging
from functools import wraps
import time
import pyotp
import qrcode
from io import BytesIO
import base64

logger = logging.getLogger(__name__)
User = get_user_model()

class AuthOptimizer:
    def __init__(self):
        self.token_refresh_threshold = 300  # 5 minuta
        self.session_timeout = 3600  # 1 sat
        self.max_failed_attempts = 5
        self.lockout_duration = 1800  # 30 minuta

    def refresh_token(self, refresh_token: str) -> Dict[str, str]:
        """Osvježi JWT token"""
        try:
            # Provjeri je li token blokiran
            if self._is_token_blacklisted(refresh_token):
                raise InvalidToken('Token je blokiran')

            # Osvježi token
            refresh = RefreshToken(refresh_token)
            access_token = str(refresh.access_token)
            new_refresh_token = str(refresh)

            # Spremi nove tokene
            self._store_tokens(refresh_token, new_refresh_token, access_token)

            return {
                'access_token': access_token,
                'refresh_token': new_refresh_token
            }
        except Exception as e:
            logger.error(f"Greška pri osvježavanju tokena: {e}")
            raise

    def _is_token_blacklisted(self, token: str) -> bool:
        """Provjeri je li token blokiran"""
        return cache.get(f"blacklist_token:{token}") is not None

    def _store_tokens(self, old_refresh: str, new_refresh: str, access: str):
        """Spremi nove tokene"""
        # Blokiraj stari refresh token
        cache.set(f"blacklist_token:{old_refresh}", True, self.session_timeout)
        
        # Spremi nove tokene
        cache.set(f"refresh_token:{new_refresh}", {
            'access_token': access,
            'created_at': time.time()
        }, self.session_timeout)

    def setup_2fa(self, user: User) -> Dict[str, Any]:
        """Postavi 2FA za korisnika"""
        try:
            # Generiraj tajni ključ
            secret = pyotp.random_base32()
            
            # Spremi tajni ključ
            user.two_factor_secret = secret
            user.save()
            
            # Generiraj QR kod
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                user.email,
                issuer_name="Belot"
            )
            
            # Generiraj QR kod
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            qr_code = base64.b64encode(buffered.getvalue()).decode()
            
            return {
                'secret': secret,
                'qr_code': qr_code
            }
        except Exception as e:
            logger.error(f"Greška pri postavljanju 2FA: {e}")
            raise

    def verify_2fa(self, user: User, code: str) -> bool:
        """Verificiraj 2FA kod"""
        try:
            totp = pyotp.TOTP(user.two_factor_secret)
            return totp.verify(code)
        except Exception as e:
            logger.error(f"Greška pri verificiranju 2FA koda: {e}")
            return False

    def handle_failed_login(self, username: str):
        """Upravljanje neuspješnim pokušajima prijave"""
        key = f"failed_login:{username}"
        attempts = cache.get(key, 0) + 1
        
        if attempts >= self.max_failed_attempts:
            # Blokiraj korisnika
            cache.set(f"locked_user:{username}", True, self.lockout_duration)
            logger.warning(f"Korisnik {username} je blokiran zbog previše neuspješnih pokušaja")
        else:
            cache.set(key, attempts, self.lockout_duration)

    def is_user_locked(self, username: str) -> bool:
        """Provjeri je li korisnik blokiran"""
        return cache.get(f"locked_user:{username}") is not None

    def require_2fa(self, view_func):
        """Dekorator koji zahtijeva 2FA"""
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return view_func(request, *args, **kwargs)
                
            if request.user.two_factor_enabled:
                if not request.session.get('2fa_verified'):
                    return Response(
                        {'error': '2FA verification required'},
                        status=status.HTTP_403_FORBIDDEN
                    )
            
            return view_func(request, *args, **kwargs)
        return wrapper

    def session_management(self, request):
        """Upravljanje sesijom"""
        if not request.user.is_authenticated:
            return
            
        # Osvježi vrijeme zadnje aktivnosti
        request.session['last_activity'] = time.time()
        
        # Provjeri timeout
        last_activity = request.session.get('last_activity', 0)
        if time.time() - last_activity > self.session_timeout:
            # Odjavi korisnika
            from django.contrib.auth import logout
            logout(request)
            raise InvalidToken('Sesija je istekla')

# Inicijalizacija optimizatora
auth_optimizer = AuthOptimizer() 